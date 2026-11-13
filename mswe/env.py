import os
import platform
import re
import signal
import subprocess
from pathlib import Path
from pydantic import BaseModel

from mswe.exceptions import Submitted
try:
    from mswe import tools as BUILTINS
except Exception:
    import tools as BUILTINS

DEFAULT_DENY = [
    r"rm\s+-rf\s+/\s*$",
    r"rm\s+-rf\s+/\*",
    r":\s*\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;",  # fork bomb
    r"mkfs\.",
    r"dd\s+if=.*of=/dev/",
]


class EnvConfig(BaseModel):
    cwd: str = ""
    env: dict = {}
    timeout: int = 60
    spool_threshold: int = 4000
    spool_dir: str = ""
    deny: list[str] = []
    stateful: bool = True


class Environment:
    def __init__(self, *, config_class=EnvConfig, **kwargs):
        self.config = config_class(**kwargs)
        self.cwd = self.config.cwd or os.getcwd()
        self._counter = 0
        self._spool = Path(self.config.spool_dir or (Path.cwd() / ".mswe_spool"))
        self._spool.mkdir(parents=True, exist_ok=True)
        self._deny = [re.compile(p) for p in (DEFAULT_DENY + self.config.deny)]

    def _deny_check(self, command):
        for rx in self._deny:
            if rx.search(command):
                return True
        return False

    def execute(self, action):
        tool = action.get("tool") or action.get("name")
        if tool and tool != "bash":
            return self._run_tool(tool, action)
        command = action.get("command", "")
        if not command:
            # allow actions that are just a tool alias
            if tool:
                return self._run_tool(tool, action)
            return {"output": "(no command)", "returncode": 0}
        if self._deny_check(command):
            return {"output": "blocked by guardrail: command matches deny pattern", "returncode": 1}
        return self._run_bash(command)

    def _run_tool(self, tool, action):
        allowed = {"read_file", "write_file", "list_dir", "find_files", "grep"}
        fn = getattr(BUILTINS, tool, None) if tool in allowed else None
        if fn is None:
            return {"output": f"unknown tool: {tool}", "returncode": 1}
        args = {k: v for k, v in action.items() if k not in ("tool", "name")}
        field = "root" if tool in {"find_files", "grep"} else "path"
        if field in args or tool in {"list_dir", "find_files", "grep"}:
            path = Path(args.get(field, ".")).expanduser()
            args[field] = str(path if path.is_absolute() else Path(self.cwd) / path)
        try:
            res = fn(**args)
        except TypeError as e:
            res = {"output": f"bad args: {e}", "returncode": 1}
        out = res.get("output", "")
        rc = res.get("returncode", 0)
        output = {"output": out, "returncode": rc, "exception_info": ""}
        return self._spool_if_needed(output)

    def _run_bash(self, command):
        # stateful cwd tracking: append marker to capture final cwd
        marker = "__MSWE_CWD__"
        wrapped = command
        if self.config.stateful:
            wrapped = f"{command}\n__mswe_status=$?; printf '\\n{marker}%s\\n' \"$(pwd)\"; exit \"$__mswe_status\""
        try:
            result = self._popen(wrapped, self.cwd, os.environ | self.config.env, self.config.timeout)
            stdout = result.stdout
        except subprocess.TimeoutExpired as e:
            stdout = e.output if isinstance(e.output, str) else (e.output or b"").decode("utf-8", "replace")
            output = {"output": stdout + f"\n(timed out after {self.config.timeout}s)", "returncode": -1, "exception_info": "TimeoutExpired"}
            return self._spool_if_needed(output)
        except Exception as e:
            raw = getattr(e, "output", None)
            raw = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else (raw or "")
            output = {"output": raw, "returncode": -1, "exception_info": f"{type(e).__name__}: {e}"}
            self._check_finished(output)
            return self._spool_if_needed(output)

        # parse cwd marker
        new_cwd = self.cwd
        lines = stdout.splitlines(keepends=True)
        cleaned = []
        for ln in lines:
            if ln.strip().startswith(marker):
                new_cwd = ln.strip()[len(marker):].strip()
            else:
                cleaned.append(ln)
        if new_cwd and os.path.isdir(new_cwd):
            self.cwd = new_cwd
        stdout = "".join(cleaned)

        output = {"output": stdout, "returncode": result.returncode, "exception_info": ""}
        self._check_finished(output)
        return self._spool_if_needed(output)

    def _popen(self, command, cwd, env, timeout):
        process = subprocess.Popen(
            command, shell=True, text=True, cwd=cwd, env=env,
            encoding="utf-8", errors="replace",
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            start_new_session=(os.name == "posix"),
        )
        try:
            stdout, _ = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            if os.name == "posix":
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            else:
                process.kill()
            stdout, _ = process.communicate()
            raise subprocess.TimeoutExpired(command, timeout, output=stdout)
        return subprocess.CompletedProcess(command, process.returncode, stdout=stdout)

    def _spool_if_needed(self, output):
        text = output.get("output", "")
        if len(text) <= self.config.spool_threshold:
            return output
        self._counter += 1
        path = self._spool / f"output_{self._counter}.txt"
        path.write_text(text)
        head = text[: (self.config.spool_threshold // 2)]
        tail = text[-(self.config.spool_threshold // 2):]
        elided = len(text) - len(head) - len(tail)
        new_text = f"{head}\n\n... [{elided} chars elided; full output: {path}] ...\n\n{tail}"
        out = dict(output)
        out["output"] = new_text
        out["extra"] = {"spool_path": str(path), "full_length": len(text)}
        return out

    def _check_finished(self, output):
        # sentinel support (compat)
        lines = output.get("output", "").lstrip().splitlines(keepends=True)
        if lines and lines[0].strip() == "COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT" and output.get("returncode") == 0:
            submission = "".join(lines[1:])
            raise Submitted({"role": "exit", "content": submission,
                            "extra": {"exit_status": "Submitted", "submission": submission}})

    def get_template_vars(self, **kwargs):
        return {"cwd": self.cwd, "platform": platform.platform(), **kwargs}

    def serialize(self):
        return {"info": {"config": {"environment": self.config.model_dump(mode="json"), "environment_type": "mswe.Environment"}}}
