# Slightly-Bigger-SWE-Agent (mswe)

A custom build of [mini-swe-agent](https://github.com/SWE-agent/mini-swe-agent) with compaction, output spooling, guardrails, and multi-tool support — still a ~200-line core loop with YAML/Jinja2 config.

## Layout
```
mswe/                # Python package: agent.py, model.py, env.py, tools.py, cli.py
config/              # default.yaml templates
pyproject.toml
```

## Install
```
python3 -m venv .venv
.venv/bin/pip install -e .
```

## Run
```
mswe --task "Fix the bug in foo.py" --cwd /path/to/repo --step-limit 20
```

or via `python -m mswe ...`.

Colored output: red = assistant, green = user, cyan = tool, magenta = exit, plus a rule between turns.

## Config
YAML config via `-c file.yaml` (`system_template`, `instance_template`, `agent.*`, `environment.*`, `model.*`). See `config/default.yaml`.

## Provider
Model is selected per run with `-m <provider/model>`, or `--base-url`/`--api-key` (or `MSWE_MODEL` / `MSWE_REASONING_EFFORT`) for any OpenAI-compatible endpoint. Keys are read from flags or environment variables — nothing is stored in the repo.

## What this build changes vs mini-swe-agent
- Compaction: char-budget rolling compaction of older turns into a summary message
- Output spooling: large outputs saved to `.mswe_spool/` with head+tail+path
- Stateful cwd tracking across tool calls
- Guardrails: deny-pattern list (rm -rf /, fork bomb, mkfs, dd to /dev)
- Multi-tool: `bash`, `read_file`, `write_file`, `list_dir`, `find_files`, `grep`, `submit`
- Structured submit tool instead of stdout sentinel
