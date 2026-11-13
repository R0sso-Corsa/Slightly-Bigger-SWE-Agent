import json
import logging
import sys
import time
from pathlib import Path

from jinja2 import StrictUndefined, Template
from pydantic import BaseModel

from mswe.exceptions import InterruptAgentFlow, LimitsExceeded, Submitted, TimeExceeded


class AgentConfig(BaseModel):
    system_template: str
    instance_template: str
    step_limit: int = 0
    cost_limit: float = 3.0
    wall_time_limit_seconds: int = 0
    max_consecutive_no_actions: int = 3
    output_path: Path | None = None
    # compaction
    char_budget: int = 40000
    compact_keep_last: int = 4
    # interactive
    yolo: bool = False


class Agent:
    def __init__(self, model, env, *, config_class=AgentConfig, **kwargs):
        self.config = config_class(**kwargs)
        self.model = model
        self.env = env
        self.messages = []
        self.extra_template_vars = {}
        self.logger = logging.getLogger("agent")
        self.cost = 0.0
        self.n_calls = 0
        self.n_consecutive_no_actions = 0
        self._start_time = time.time()
        self._cost_baseline = 0.0
        self._show = sys.stdin is not None and sys.stdin.isatty()
        if not self._show:
            self.config.yolo = True  # no terminal: don't prompt, just run

    def get_template_vars(self, **kwargs):
        return {
            "n_model_calls": self.n_calls,
            "model_cost": self.cost,
            "elapsed_seconds": int(time.time() - self._start_time),
            **self.config.model_dump(),
            **self.env.get_template_vars(),
            **self.model.get_template_vars(),
            **self.extra_template_vars,
            **kwargs,
        }

    def _render(self, template):
        return Template(template, undefined=StrictUndefined).render(**self.get_template_vars())

    _ROLE_STYLE = {"user": "green", "assistant": "red", "tool": "cyan", "exit": "magenta"}

    def add_messages(self, *msgs):
        self.messages.extend(msgs)
        if self._show:
            from rich.console import Console
            console = Console(highlight=False)
            for m in msgs:
                role = m.get("role") or "?"
                content = m.get("content", "")
                if isinstance(content, list):
                    content = " ".join(c.get("text", "") for c in content)
                if role == "assistant":
                    console.print(f"\n[red][bold]mswe[/bold] (step [bold]{self.n_calls}[/bold], [bold]${self.cost:.2f}[/bold]):[/red]")
                elif role == "exit":
                    console.print("\n[magenta][bold]done[/bold][/magenta]")
                else:
                    style = self._ROLE_STYLE.get(role, "white")
                    console.print(f"\n[bold {style}]{role.capitalize()}[/bold {style}]:")
                if content:
                    console.print(content, markup=False, highlight=False)
                else:
                    console.print()
        return list(msgs)

    def handle_uncaught(self, e):
        return self.add_messages(self.model.format_message(
            role="exit", content=str(e),
            extra={"exit_status": type(e).__name__, "submission": "", "traceback": __import__("traceback").format_exc()}))

    def _compact(self):
        # estimate size
        total = sum(len(str(m.get("content", ""))) for m in self.messages)
        if total <= self.config.char_budget:
            return
        # keep first 2 (system + instance) and last compact_keep_last*2 messages
        if len(self.messages) <= 4:
            return
        head = self.messages[:2]
        tail_n = self.config.compact_keep_last * 2
        if tail_n >= len(self.messages) - 2:
            tail_n = max(2, len(self.messages) - 2 - 2)
        tail = self.messages[-tail_n:] if tail_n > 0 else []
        middle = self.messages[2:len(self.messages) - tail_n] if tail_n > 0 else self.messages[2:]
        # build summary
        cmds = []
        for m in middle:
            c = m.get("content", "")
            if isinstance(c, str) and len(c) > 0:
                cmds.append(c[:120].replace("\n", " "))
        summary = "Earlier steps compacted. Summary of {} messages:\n".format(len(middle)) + "\n".join(f"- {x}" for x in cmds[:40])
        compact_msg = self.model.format_message(role="user", content=f"[COMPACTION]\n{summary}")
        self.messages = head + [compact_msg] + tail

    def _reset_turn(self):
        self.n_calls = 0
        self._cost_baseline = self.cost
        self._start_time = time.time()
        self.n_consecutive_no_actions = 0

    def run(self, task="", **kwargs):
        self.extra_template_vars |= {"task": task, **kwargs}
        self.messages = []
        self._cost_baseline = 0.0
        self.n_calls = 0
        self.cost = 0.0
        self.add_messages(
            self.model.format_message(role="system", content=self._render(self.config.system_template)),
            self.model.format_message(role="user", content=self._render(self.config.instance_template)),
        )
        return self._loop()

    def followup(self, task="", **kwargs):
        """Run another task in the same conversation (keeps context)."""
        self.extra_template_vars |= {"task": task, **kwargs}
        self._reset_turn()
        self.add_messages(
            self.model.format_message(role="user", content=self._render(self.config.instance_template)),
        )
        return self._loop()

    def _loop(self):
        while True:
            try:
                self._compact()
                self.step()
            except InterruptAgentFlow as e:
                msgs = getattr(e, "messages", None)
                if msgs:
                    self.add_messages(*msgs)
            except Exception as e:
                self.handle_uncaught(e)
                raise
            finally:
                self.save(self.config.output_path)
            self.logger.info(f"step={self.n_calls} cost=${self.cost:.4f}")
            if self.messages and self.messages[-1].get("role") == "exit":
                break
        return (self.messages[-1].get("extra", {}) if self.messages else {})

    def step(self):
        if self._show:
            from rich.console import Console
            from rich.rule import Rule
            Console(highlight=False).print(Rule())
        message = self.query()
        actions = message.get("extra", {}).get("actions", [])
        if not actions:
            self.n_consecutive_no_actions += 1
            if 0 < self.config.max_consecutive_no_actions <= self.n_consecutive_no_actions:
                self.add_messages({"role": "exit", "content": "RepeatedNoAction",
                                   "extra": {"exit_status": "RepeatedNoAction", "submission": ""}})
                return []
            return self.add_messages(self.model.format_message(
                role="user",
                content="No tool calls returned. Reply with exactly one bash or submit tool call.",
            ))
        self.n_consecutive_no_actions = 0
        return self.execute_actions(message)

    def query(self):
        turn_cost = self.cost - getattr(self, "_cost_baseline", 0.0)
        if 0 < self.config.step_limit <= self.n_calls or 0 < self.config.cost_limit <= turn_cost:
            raise LimitsExceeded({"role": "exit", "content": "LimitsExceeded",
                                 "extra": {"exit_status": "LimitsExceeded", "submission": ""}})
        if 0 < self.config.wall_time_limit_seconds <= int(time.time() - self._start_time):
            raise TimeExceeded({"role": "exit", "content": "TimeExceeded",
                               "extra": {"exit_status": "TimeExceeded", "submission": ""}})
        self.n_calls += 1
        message = self.model.query(self.messages)
        self.cost += message.get("extra", {}).get("cost", 0.0)
        self.add_messages(message)
        return message

    def _approve(self, action):
        tool = action.get("tool") or "bash"
        detail = action.get("command") or action.get("path") or action.get("submission", "")
        try:
            ans = input(f"Approve {tool}: {detail}? [y/N] ").strip().lower()
        except EOFError:
            return False
        return ans in ("y", "yes")

    def execute_actions(self, message):
        actions = message.get("extra", {}).get("actions", [])
        # handle submit tool specially
        outputs = []
        for a in actions:
            if a.get("tool") == "submit":
                sub = a.get("submission", "")
                raise Submitted({"role": "exit", "content": sub,
                                "extra": {"exit_status": "Submitted", "submission": sub}})
            if not self.config.yolo:
                if not self._approve(a):
                    outputs.append({"output": "denied by user", "returncode": 126, "exception_info": ""})
                    continue
            outputs.append(self.env.execute(a))
        obs = self.model.format_observation_messages(message, outputs, self.get_template_vars())
        return self.add_messages(*obs)

    def save(self, path):
        data = self.serialize()
        if path:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_text(json.dumps(data, indent=2))

    def serialize(self):
        return {
            "info": {
                "model_stats": {"instance_cost": self.cost, "api_calls": self.n_calls},
                "config": {"agent": self.config.model_dump(mode="json"), "agent_type": "mswe.Agent"},
                "exit_status": (self.messages[-1].get("extra", {}).get("exit_status", "") if self.messages else ""),
                "submission": (self.messages[-1].get("extra", {}).get("submission", "") if self.messages else ""),
            },
            "messages": self.messages,
            "trajectory_format": "mswe-0.1",
        }
