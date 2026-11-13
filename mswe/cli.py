import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    # global mini-swe-agent .env, if present (per-user, not committed)
    load_dotenv(Path.home() / "Library" / "Application Support" / "mini-swe-agent" / ".env")
except Exception:
    pass

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


def load_config(path):
    cfg = {}
    if path and Path(path).exists():
        cfg = yaml.safe_load(Path(path).read_text()) or {}
    return cfg


@app.command()
def run(
    task: str = typer.Option(None, "-t", "--task", help="Task to solve; prompted if omitted"),
    model: str = typer.Option(None, "-m", "--model"),
    base_url: str = typer.Option(None, "--base-url", help="Custom OpenAI-compatible endpoint base URL"),
    api_key: str = typer.Option(None, "--api-key", help="API key for endpoint"),
    config: str = typer.Option(None, "-c", "--config"),
    cwd: str = typer.Option("", "--cwd"),
    cost_limit: float = typer.Option(3.0, "-l", "--cost-limit"),
    step_limit: int = typer.Option(0, "-s", "--step-limit"),
    output: str = typer.Option(None, "-o", "--output"),
    tools: str = typer.Option("bash,submit", "--tools", help="comma-separated tool names"),
    yolo: bool = typer.Option(False, "--yolo", help="Run without asking before each action"),
):
    interactive = not task or not task.strip()
    if interactive and not sys.stdin.isatty():
        console.print("Error: --task is required for non-interactive runs")
        raise typer.Exit(code=2)
    cfg = load_config(config)
    # config-provided endpoint
    if isinstance(cfg.get("model"), dict):
        if cfg["model"].get("api_base"):
            os.environ.setdefault("OPENAI_API_BASE", cfg["model"]["api_base"])
        if cfg["model"].get("api_key"):
            os.environ.setdefault("OPENAI_API_KEY", cfg["model"]["api_key"])
    if base_url:
        os.environ["OPENAI_API_BASE"] = base_url
    if api_key:
        os.environ["OPENAI_API_KEY"] = api_key
    base = os.environ.get("OPENAI_API_BASE", "")
    if model:
        mname = model
    else:
        mname = cfg.get("model", {}).get("model_name") or os.environ.get("MSWE_MODEL") or "chatgpt/gpt-6.1-sol"
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
        base = os.environ.get("OPENAI_API_BASE")
        if base:
            model_cfg["model_kwargs"].setdefault("api_base", base)
        if os.environ.get("OPENAI_API_KEY"):
            model_cfg["model_kwargs"].setdefault("api_key", os.environ["OPENAI_API_KEY"])
    if mname.startswith("chatgpt/"):
        model_cfg["model_kwargs"].setdefault("reasoning_effort", cfg.get("model", {}).get("reasoning_effort") or os.environ.get("MSWE_REASONING_EFFORT", "low"))
    model_cfg["tools"] = [t.strip() for t in tools.split(",") if t.strip()]
    m = Model(**model_cfg)
    agent_cfg = cfg.get("agent", {}) or {}
    agent_cfg["cost_limit"] = cost_limit
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
