import os
import re
import sys
from pathlib import Path
from typing import Any, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
USER_CONFIG_PATH = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "mswe" / "config.yaml"


def env_file_path():
    # Editable checkouts keep local .env; installed wheels use a writable user path.
    return PROJECT_ROOT / ".env" if (PROJECT_ROOT / "pyproject.toml").is_file() else USER_CONFIG_PATH.parent / ".env"


def load_env_files():
    from dotenv import load_dotenv
    for path in (env_file_path(), USER_CONFIG_PATH.parent / ".env"):
        if path.is_file():
            load_dotenv(path, override=False)


load_env_files()

import logging
os.environ.setdefault("LITELLM_LOG", "ERROR")
_agent_logger = logging.getLogger("agent")
if not _agent_logger.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(message)s"))
    _agent_logger.addHandler(_h)
_agent_logger.setLevel(logging.INFO)

import typer
import yaml
from rich.console import Console

from mswe.agent import Agent
from mswe.env import Environment
from mswe.model import Model

app = typer.Typer(help="mswe - custom mini-swe-agent build")
console = Console()

DEFAULT_MODEL = "chatgpt/gpt-6.1-sol"


def prompt_task():
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import FileHistory

    console.print("What do you want to do?")
    session = PromptSession(history=FileHistory(str(Path.home() / ".mswe_history")), multiline=True)
    try:
        console.print("[dim](Esc then Enter submits; Ctrl+C cancels)[/dim]")
        return session.prompt("", multiline=True).strip()
    except (KeyboardInterrupt, EOFError):
        return ""


def _deep_merge(base: Any, override: Any) -> dict[str, Any]:
    merged = dict(base or {})
    for key, value in (override or {}).items():
        if isinstance(merged.get(key), dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _expand_env(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _expand_env(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_expand_env(item) for item in value]
    if not isinstance(value, str):
        return value

    pattern = re.compile(r"\$(?:\{([A-Za-z_][A-Za-z0-9_]*)\}|([A-Za-z_][A-Za-z0-9_]*))")

    def replace(match: re.Match[str]) -> str:
        name = match.group(1) or match.group(2)
        replacement = os.environ.get(name)
        if replacement is None:
            console.print(f"[yellow]Warning: environment variable {name} referenced by config is not set[/yellow]")
            return ""
        return replacement

    return pattern.sub(replace, value)


def _read_yaml(path: Any) -> dict[str, Any]:
    try:
        data = _expand_env(yaml.safe_load(Path(path).read_text()) or {})
    except Exception as exc:
        console.print(f"[yellow]Warning: could not read {path}: {exc}[/yellow]")
        return {}
    return data if isinstance(data, dict) else {}


def load_config(path: Optional[str] = None) -> dict[str, Any]:
    cfg = _read_yaml(USER_CONFIG_PATH) if USER_CONFIG_PATH.exists() else {}
    if path:
        if not Path(path).exists():
            console.print(f"[yellow]Warning: config file {path} does not exist; using user config only[/yellow]")
        else:
            cfg = _deep_merge(cfg, _read_yaml(path))
    return cfg


@app.command()
def run(
    task: str = typer.Option(None, "-t", "--task", help="Task to solve; prompted if omitted"),
    model: str = typer.Option(None, "-m", "--model"),
    base_url: str = typer.Option(None, "--base-url", help="Custom OpenAI-compatible endpoint base URL"),
    api_key: str = typer.Option(None, "--api-key", help="API key for endpoint"),
    config: str = typer.Option(None, "-c", "--config"),
    cwd: str = typer.Option("", "--cwd"),
    cost_limit: Optional[float] = typer.Option(None, "-l", "--cost-limit"),
    step_limit: Optional[int] = typer.Option(None, "-s", "--step-limit"),
    output: str = typer.Option(None, "-o", "--output"),
    tools: str = typer.Option("bash,submit", "--tools", help="comma-separated tool names"),
    yolo: bool = typer.Option(False, "--yolo", is_flag=True, help="Run without asking before each action"),
    models: bool = typer.Option(False, "--models", is_flag=True, help="Pick and save a default model without starting chat"),
    configure: bool = typer.Option(False, "--configure", is_flag=True, help="Add, edit or switch saved endpoints"),
    reauth: bool = typer.Option(False, "--reauth", is_flag=True, help="Replace a saved endpoint API key (not OAuth)"),
):
    if models:
        from mswe.configuration import pick_model
        pick_model(USER_CONFIG_PATH)
        return
    if configure or reauth:
        from mswe.configuration import configure as configure_endpoint
        configure_endpoint(USER_CONFIG_PATH, env_file_path(), reauth=reauth)
        return
    interactive = not task or not task.strip()
    if interactive and not sys.stdin.isatty():
        console.print("Error: --task is required for non-interactive runs")
        raise typer.Exit(code=2)
    cfg = load_config(config)
    # Endpoint-specific credentials must not be replaced by another provider's key.
    selected = cfg.get("model", {}) or {}
    base = base_url or selected.get("api_base") or ""
    selected_key = api_key or selected.get("api_key")
    if model:
        mname = model
    else:
        mname = os.environ.get("MSWE_MODEL") or cfg.get("model", {}).get("model_name") or DEFAULT_MODEL
    saved_provider = selected.get("model_name", "").split("/", 1)[0]
    changed_provider = saved_provider and mname.split("/", 1)[0] != saved_provider
    if changed_provider and selected_key and not api_key:
        raise typer.BadParameter("Changing providers cannot reuse the saved key. Select an endpoint with --models/--configure or supply --api-key explicitly.")
    if changed_provider:
        base = base_url or ""
    if not base and not selected_key and (mname.startswith("openai/") or "/" not in mname):
        base = os.environ.get("OPENAI_API_BASE", "")
    # prefix for OpenAI-compatible custom endpoints if no provider given
    if "/" not in mname and base:
        mname = "openai/" + mname
    env_cfg = cfg.get("environment", {}) or {}
    if cwd:
        env_cfg["cwd"] = cwd
    env = Environment(**env_cfg)
    model_cfg = cfg.get("model", {}) or {}
    model_cfg["model_name"] = mname
    model_cfg.setdefault("model_kwargs", {})
    if not mname.startswith("chatgpt/"):
        if base:
            model_cfg["model_kwargs"]["api_base"] = base
        if selected_key:
            model_cfg["model_kwargs"]["api_key"] = selected_key
        elif mname.startswith("openai/") and os.environ.get("OPENAI_API_KEY"):
            model_cfg["model_kwargs"].setdefault("api_key", os.environ["OPENAI_API_KEY"])
    if mname.startswith("chatgpt/"):
        model_cfg["model_kwargs"].setdefault("reasoning_effort", os.environ.get("MSWE_REASONING_EFFORT") or cfg.get("model", {}).get("reasoning_effort") or "low")
    model_cfg["tools"] = [t.strip() for t in tools.split(",") if t.strip()]
    m = Model(**model_cfg)
    agent_cfg = cfg.get("agent", {}) or {}
    if cost_limit is not None:
        agent_cfg["cost_limit"] = cost_limit
    if step_limit is not None:
        agent_cfg["step_limit"] = step_limit
    if output:
        agent_cfg["output_path"] = Path(output)
    # templates
    sys_tpl = cfg.get("system_template")
    inst_tpl = cfg.get("instance_template")
    if sys_tpl:
        agent_cfg["system_template"] = sys_tpl
    if inst_tpl:
        agent_cfg["instance_template"] = inst_tpl
    if "system_template" not in agent_cfg:
        agent_cfg["system_template"] = "Coding agent. Use bash/submit."
    if "instance_template" not in agent_cfg:
        agent_cfg["instance_template"] = "Task: {{task}}\nCWD: {{cwd}}\nUse tools; finish with submit."
    agent_cfg["yolo"] = yolo
    agent = Agent(m, env, **agent_cfg)
    if interactive:
        first = True
        while True:
            console.print()
            t = prompt_task()
            if not t.strip():
                console.print("bye")
                return
            try:
                result = agent.run(t) if first else agent.followup(t)
            except KeyboardInterrupt:
                console.print("Aborted.")
                return
            except Exception as e:
                console.print(f"Error: {type(e).__name__}: {e}")
                return
            first = False
    try:
        result = agent.run(task)
    except KeyboardInterrupt:
        console.print("Aborted.")
        raise typer.Exit(code=130)
    except Exception as e:
        console.print(f"Error: {type(e).__name__}: {e}")
        raise typer.Exit(code=1)
    console.print(result)


if __name__ == "__main__":
    app()
