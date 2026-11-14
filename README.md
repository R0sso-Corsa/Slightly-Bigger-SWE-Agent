# Slightly-Bigger-SWE-Agent (sbswe)

**Experimental 0.1.0 release candidate.** See [security boundaries](SECURITY.md) before running model-generated commands.

A custom build of [mini-swe-agent](https://github.com/SWE-agent/mini-swe-agent) with compaction, output spooling, guardrails, and multi-tool support — still a ~200-line core loop with YAML/Jinja2 config.

## Layout
```
sbswe/                # Python package: agent.py, model.py, env.py, tools.py, cli.py
config/              # default.yaml templates
pyproject.toml
```

## Install
```
python3 -m venv .venv
.venv/bin/pip install -e .
source .venv/bin/activate
sbswe --configure
```

Requires Python 3.10+ on macOS/Linux (POSIX shell); Windows is not release-verified.
To install a downloaded wheel, use `python -m pip install ./sbswe-0.1.0-py3-none-any.whl`.

## Run
```
sbswe --task "Fix the bug in foo.py" --cwd /path/to/repo --step-limit 20
```

or via `python -m sbswe ...`.

Colored output: red = assistant, green = user, cyan = tool, magenta = exit, plus a rule between turns.

## Config
YAML config via `-c file.yaml` (`system_template`, `instance_template`, `agent.*`, `environment.*`, `model.*`). See `config/default.yaml`.

## Provider
Model is selected per run with `-m <provider/model>`, or `--base-url`/`--api-key` (or `SBSWE_MODEL` / `SBSWE_REASONING_EFFORT`) for any OpenAI-compatible endpoint. Keys are read from flags or environment variables — nothing is stored in the repo.

You can also set a personal default in `~/.config/sbswe/config.yaml`:

```yaml
model:
  model_name: chatgpt/gpt-6.1-sol
  reasoning_effort: low
```

## Pick a default model without starting chat

```bash
python -m sbswe --models
```

Choose a saved endpoint by number, search its live model catalog (blank shows
all), then select a model by number. The picker saves the selection to your user
config and activates that endpoint without changing its key. The next chat uses
it unless overridden by `-m`, `SBSWE_MODEL`, or `-c`.

Model discovery supports OpenRouter, OpenAI, Anthropic, Groq, DeepSeek, Mistral,
and custom endpoints exposing the OpenAI-compatible `/models` format. Unsupported
or unavailable catalogs fall back to manual `provider/model` entry. It only lists
models; it makes no completion requests. Cancel with Ctrl+C before selection to
leave your configuration unchanged. Run `--configure` first if no endpoint exists.

## Endpoint setup (no manual file editing)

```bash
python -m sbswe --configure  # add, edit or switch a named endpoint
python -m sbswe --reauth     # replace a saved endpoint's API key
```

Setup asks for the LiteLLM `provider/model` and optional HTTP(S) base URL first.
It automatically names known endpoints from their exact hostname (for example,
`openrouter.ai` → `openrouter`), or from a recognized provider prefix when no URL
is supplied. An exact saved model/URL match reuses its saved name. Unknown/custom
servers prompt for a name instead. Updating an existing endpoint requires
confirmation. API key input is hidden; blank keeps the saved key or uses no key.
`--reauth` automatically uses the saved active endpoint; if none is available it
asks for the endpoint name. Detection is local and makes no network requests.

Settings are stored in `~/.config/sbswe/config.yaml` under `endpoints`, with the
selected entry copied into `model`. Editable checkouts store keys in their gitignored
`.env`; wheel installs use `~/.config/sbswe/.env` (or `$XDG_CONFIG_HOME/sbswe/.env`).
Keys use endpoint-specific variable names and owner-only permissions (0600).
YAML contains `${SBSWE_ENDPOINT_..._API_KEY}` references, never the entered key.
Explicit endpoint keys/base URLs override generic `OPENAI_*` defaults, preventing
an unrelated OpenAI key from overriding the selected provider's credentials.
CLI flags still override endpoint values. Restart chat after setup.

This is API-key setup/rotation, **not browser OAuth reauthentication**. It does not
validate credentials against a live provider or make a paid test request. Blank
keys allow existing provider auth or local servers to be used.

## Project `.env`
For provider keys specific to this project, copy `.env.example` to `.env` and fill in only the providers you use:

```bash
cp .env.example .env
$EDITOR .env
```

`.env` is gitignored and loaded automatically. Shell variables take precedence,
followed by the editable checkout `.env`, then the sbswe user `.env`. The old
mini-swe-agent `.env` is no longer read automatically; put keys in sbswe's own env
file or run `--configure`. YAML configs also expand `${VAR}` and `$VAR`, so this works in user or project configs:

```yaml
model:
  model_name: openrouter/thinkingmachines/inkling-2-small:free
  api_key: ${OPENROUTER_API_KEY}
```

Never put real keys in `.env.example`, README files, shell history, or git.

Model-name precedence: CLI flags > `SBSWE_MODEL` > `-c file.yaml` > user config > built-in fallback. Endpoint-specific key/base references override generic `OPENAI_*` defaults; CLI flags override endpoint values. Keep API keys out of YAML unless they are `${VAR}` references; use `.env` or environment variables.

## What this build changes vs mini-swe-agent
- Compaction: char-budget rolling compaction of older turns into a summary message
- Output spooling: large outputs saved to `.sbswe_spool/` with head+tail+path
- Stateful cwd tracking across tool calls
- Guardrails: deny-pattern list (rm -rf /, fork bomb, mkfs, dd to /dev)
- Multi-tool: `bash`, `read_file`, `write_file`, `list_dir`, `find_files`, `grep`, `submit`
- Structured submit tool instead of stdout sentinel
