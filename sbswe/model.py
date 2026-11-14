import json
from typing import Any

import litellm
from litellm import completion_cost

litellm.suppress_debug_info = True

# Compressed tool schemas (minimal descriptions to save input tokens).
_TOOL_SCHEMAS = {
 "bash": {"type": "function", "function": {"name": "bash", "description": "Run bash command.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
 "read_file": {"type": "function", "function": {"name": "read_file", "description": "Read file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "offset": {"type": "integer"}, "limit": {"type": "integer"}}, "required": ["path"]}}},
 "write_file": {"type": "function", "function": {"name": "write_file", "description": "Write file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
 "list_dir": {"type": "function", "function": {"name": "list_dir", "description": "List dir.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}}}},
 "find_files": {"type": "function", "function": {"name": "find_files", "description": "Find files.", "parameters": {"type": "object", "properties": {"root": {"type": "string"}, "glob": {"type": "string"}}}}},
 "grep": {"type": "function", "function": {"name": "grep", "description": "Grep.", "parameters": {"type": "object", "properties": {"pattern": {"type": "string"}, "root": {"type": "string"}, "glob": {"type": "string"}}}}},
 "submit": {"type": "function", "function": {"name": "submit", "description": "Finish and submit.", "parameters": {"type": "object", "properties": {"submission": {"type": "string"}}, "required": ["submission"]}}},
}

DEFAULT_TOOLS = ["bash", "submit"]


def build_tools(names):
    return [_TOOL_SCHEMAS[n] for n in names if n in _TOOL_SCHEMAS]


class ModelConfig:
    def __init__(self, model_name, model_kwargs=None, observation_template="", tools=None):
        self.model_name = model_name
        self.model_kwargs = model_kwargs or {}
        self.observation_template = observation_template
        self.tools = tools if tools is not None else list(DEFAULT_TOOLS)


class Model:
    def __init__(self, **kwargs):
        self.config = ModelConfig(
            model_name=kwargs.pop("model_name", kwargs.pop("model", "openai/gpt-4o-mini")),
            model_kwargs=kwargs.pop("model_kwargs", {}) or {},
            observation_template=kwargs.pop("observation_template", ""),
            tools=kwargs.pop("tools", None),
        )
        # allow extra kwargs into model_kwargs
        self.config.model_kwargs = {**kwargs, **self.config.model_kwargs}
        self.cost = 0.0
        self.n_calls = 0

    def get_template_vars(self, **kw):
        return {"model_name": self.config.model_name, **kw}

    def format_message(self, role, content, **kw):
        msg = {"role": role, "content": content}
        if "extra" in kw:
            msg["extra"] = kw["extra"]
        # tool messages need tool_call_id; pass via kw
        if "tool_call_id" in kw:
            msg["tool_call_id"] = kw["tool_call_id"]
        if "tool_calls" in kw:
            msg["tool_calls"] = kw["tool_calls"]
        if "name" in kw:
            msg["name"] = kw["name"]
        return msg

    def query(self, messages):
        self.n_calls += 1
        # build messages for litellm (strip extra) and sanitize roles/tool pairing
        allowed = {"system", "user", "assistant", "tool"}
        pre = []
        for m in messages:
            mm = {k: v for k, v in m.items() if k != "extra"}
            if mm.get("role") not in allowed:
                mm["role"] = "assistant"
            pre.append(mm)

        sanitized, needed = [], []

        def flush():
            for tid in list(needed):
                sanitized.append({"role": "tool", "tool_call_id": tid, "content": "ok"})
            needed.clear()

        for mm in pre:
            role = mm.get("role")
            if role == "assistant":
                flush()
                sanitized.append(mm)
                needed.extend(tc.get("id") for tc in (mm.get("tool_calls") or []) if tc.get("id"))
            elif role == "tool":
                if mm.get("tool_call_id") in needed:
                    needed.remove(mm["tool_call_id"])
                sanitized.append(mm)
            else:
                flush()
                sanitized.append(mm)
        flush()
        lm_msgs = sanitized
        # prompt caching for anthropic
        if "anthropic" in self.config.model_name or "claude" in self.config.model_name:
            # add cache_control to last system message
            for m in lm_msgs:
                if m.get("role") == "system" and isinstance(m.get("content"), str):
                    m["content"] = [{"type": "text", "text": m["content"], "cache_control": {"type": "ephemeral"}}]
        mk = dict(self.config.model_kwargs)
        mk.setdefault("timeout", 120)  # seconds per model request
        resp: Any = litellm.completion(
            model=self.config.model_name,
            messages=lm_msgs,
            tools=build_tools(self.config.tools),
            **mk,
        )
        msg = resp.choices[0].message
        # parse tool calls
        actions = []
        tool_calls_out = []
        if getattr(msg, "tool_calls", None):
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except Exception:
                    args = {}
                tool_name = tc.function.name
                if tool_name == "bash":
                    actions.append({"tool": "bash", "command": args.get("command", "")})
                else:
                    a = {"tool": tool_name}
                    a.update(args)
                    actions.append(a)
                tool_calls_out.append({"id": tc.id, "type": "function", "function": {"name": tool_name, "arguments": tc.function.arguments}})
        content = msg.content or ""
        # cost
        try:
            c = completion_cost(completion_response=resp)
        except Exception:
            c = 0.0
        self.cost += c
        out_msg = {
            "role": "assistant",
            "content": content,
            "tool_calls": tool_calls_out,
            "extra": {
                "actions": actions,
                "cost": c,
            },
        }
        return out_msg

    def format_observation_messages(self, message, outputs, template_vars):
        msgs = []
        # pair outputs with tool_calls
        tool_calls = message.get("tool_calls", [])
        # if counts mismatch, fallback
        for i, out in enumerate(outputs):
            tc_id = tool_calls[i]["id"] if i < len(tool_calls) else f"call_{i}"
            tool_name = tool_calls[i]["function"]["name"] if i < len(tool_calls) else "bash"
            content = out.get("output", "")
            # apply observation template if provided
            if self.config.observation_template:
                try:
                    from jinja2 import Template
                    content = Template(self.config.observation_template).render(
                        output=out, **template_vars)
                except Exception:
                    pass
            msgs.append({"role": "tool", "tool_call_id": tc_id, "name": tool_name, "content": content, "extra": {"raw_output": out.get("output", ""), "returncode": out.get("returncode")}})
        return msgs

    def serialize(self):
        return {"info": {"config": {"model": {"model_name": self.config.model_name}}}, "model_stats": {"instance_cost": self.cost, "api_calls": self.n_calls}}
