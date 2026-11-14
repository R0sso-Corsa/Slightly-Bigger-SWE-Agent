# sbswe · Slightly Bigger SWE Agent

A small, terminal-first coding agent built on [mini-swe-agent](https://github.com/SWE-agent/mini-swe-agent). Configure a provider, pick a model, and work on a local repository—with explicit tool approval, compacted history, and retrievable command output.

[Getting started](#getting-started) · [Commands](#commands) · [Providers](#providers-and-models) · [Security](SECURITY.md) · [Releases](https://github.com/R0sso-Corsa/Slightly-Bigger-SWE-Agent/releases)

> **Experimental. Not a sandbox.** Model-generated commands run with your account's access. Use disposable workspaces and least-privileged credentials. Read [SECURITY.md](SECURITY.md) before running tasks.

## What it adds

| Feature | What it does |
| --- | --- |
| **Provider setup** | Add or switch named endpoints through a CLI wizard; key entry is hidden. |
| **Model picker** | Search a provider's live catalog and save a default without starting a chat. |
| **History compaction** | Condense older message content when a character budget is exceeded. |
| **Output spooling** | Save large tool output to `.sbswe_spool/`, with a head/tail preview and retrieval path. |
| **Working-directory tracking** | Carry the shell's current directory into subsequent commands and relative file-tool paths. |
| **File tools** | Read, write, list, find and search files alongside the primary shell tool. |
| **Structured submission** | Finish through a `submit` tool rather than relying only on text markers. |
| **Approval and guardrails** | Ask before interactive actions and block a small set of dangerous command patterns—not a security boundary. |

## Getting started

Requires **Python 3.10+** and a POSIX shell. Tested locally on macOS and in Linux CI; Windows is not release-verified.

```bash
git clone https://github.com/R0sso-Corsa/Slightly-Bigger-SWE-Agent.git sbswe
cd sbswe
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
sbswe --configure
```

Repository access requires authorization while the project is private.

The setup wizard asks for a `provider/model` identifier, an optional base URL, and an API key. It infers a saved endpoint name where possible; custom endpoints fall back to manual naming. Then choose your default model:

```bash
sbswe --models
```

Start an interactive conversation:

```bash
sbswe --cwd /path/to/your/repo
```

The task prompt is multiline: **Esc, then Enter** submits; **Ctrl+C** cancels. Tool actions ask for approval by default. Follow-up tasks keep the conversation context.

### Run a single task

```bash
sbswe --task "Find and fix the failing test" \
  --cwd /path/to/your/repo \
  --step-limit 20
```

Non-interactive execution—such as redirected input or automation—requires explicit `--yolo`, which skips approvals:

```bash
sbswe --task "Run the test suite and report failures" \
  --cwd /path/to/disposable-checkout \
  --step-limit 10 \
  --yolo
```

## Commands

| Command / option | Purpose |
| --- | --- |
| `sbswe` | Start an interactive task prompt. |
| `sbswe --configure` | Add, edit or activate a saved endpoint. |
| `sbswe --models` | Select an endpoint, search its models, and save a default. |
| `sbswe --reauth` | Replace the active endpoint's API key using hidden input. |
| `-m provider/model` | Override the model for one run. |
| `-c file.yaml` | Layer an explicit YAML config over user defaults. |
| `--cwd PATH` | Set the task's working directory. |
| `--tools bash,submit` | Choose enabled tools; these two are the default. |
| `--step-limit N` | Limit model calls per task/turn. |
| `--cost-limit AMOUNT` | Apply a best-effort model-cost limit. |
| `-o trajectory.json` | Save the task trajectory; treat it as sensitive. |
| `--help` | Show all options. |

`python -m sbswe` is equivalent to the `sbswe` command.

To enable the file tools:

```bash
sbswe --tools bash,read_file,write_file,list_dir,find_files,grep,submit
```

## Providers and models

sbswe uses **LiteLLM** to route requests. The model identifier includes the provider route; for example, an OpenRouter catalog ID becomes `openrouter/<catalog-model-id>`. A publisher name alone is not necessarily a provider route. `--configure` does not validate credentials or make a completion request.

### Pick a model without starting chat

```bash
sbswe --models
```

1. Choose a saved endpoint by number.
2. Enter a search term, or leave it blank to list all returned models.
3. Select a model by number.

The selection becomes your default for the next chat. Discovery supports OpenRouter, OpenAI, Anthropic, Groq, DeepSeek, Mistral, and custom endpoints exposing the OpenAI-compatible `/models` response format. Unsupported or unavailable catalogs offer manual entry.

Catalog availability does not guarantee account access or regional availability. Existing ChatGPT OAuth credentials can be used by the `chatgpt/` route; browser login and OAuth catalog discovery are not implemented by the setup wizard. **`--reauth` rotates API keys; it is not OAuth reauthentication.**

### Settings and credentials

| Location | Contents |
| --- | --- |
| `~/.config/sbswe/config.yaml` | User defaults, named endpoints, and the selected model. |
| Checkout `.env` | Keys for an editable source install; gitignored. |
| `~/.config/sbswe/.env` | Keys for an installed wheel. |
| `.env.example` | Commit-safe placeholders for supported credential variables. |

`XDG_CONFIG_HOME` overrides the `~/.config` base directory. Wizard-written key files use owner-only permissions (`0600`); YAML stores `${SBSWE_ENDPOINT_..._API_KEY}` references rather than entered key values.

For manual configuration, YAML values support `${VAR}` and `$VAR` references:

```yaml
model:
  model_name: openrouter/<catalog-model-id>
  api_key: ${OPENROUTER_API_KEY}
```

Put the key in `.env`, not in the YAML:

```bash
cp -n .env.example .env
# Edit .env locally; never commit it.
```

Shell variables take precedence over the editable checkout `.env`, then the user `.env`. Model-name precedence is:

```text
CLI -m > SBSWE_MODEL > explicit -c config > user config > built-in fallback
```

Explicit endpoint key/base settings override generic `OPENAI_*` defaults; CLI flags override endpoint settings. Cross-provider switches cannot silently reuse the previous provider's saved key. Restart the chat after changing settings.

### Custom endpoints

Use `--configure` to save an endpoint. For an endpoint already configured with
the `openai/` route, you can override its model and URL for a run:

```bash
sbswe -m 'openai/<model-id>' --base-url http://localhost:8080/v1
```

Use HTTPS for remote services. HTTP is supported for local servers but does not encrypt credentials.

## Safety and limits

- **Not sandboxed:** shell and file tools can access what your account can access. Child commands inherit environment variables.
- **Approvals:** interactive actions require approval unless `--yolo` is set. Non-TTY task execution requires explicit `--yolo`.
- **Cost limits are best-effort:** unknown pricing can report zero. Use provider-side spending limits and finite step limits.
- **Sensitive output:** terminal output, spooled files and saved trajectories are not automatically redacted. Do not publish them blindly.
- **Guardrails are narrow:** deny-pattern checks are not protection against arbitrary malicious instructions.
- **Still deferred:** MCP/ACP integration, richer cancellation, and dedicated prompt-cache controls.

See [SECURITY.md](SECURITY.md) for the security scope and [RELEASE.md](RELEASE.md) for release-validation evidence and limitations.

## Development

```bash
python -m pip install -e '.[dev]'
python -m unittest discover -v
basedpyright -p .
python -m build
python -m twine check dist/*.whl dist/*.tar.gz
```

CI runs tests, typechecking, package builds, metadata checks and a fresh wheel-install smoke check on **Python 3.10 and 3.13**.

```text
sbswe/
  agent.py          Agent loop, approvals and compaction
  cli.py            Interactive chat and CLI options
  configuration.py  Endpoint setup, key rotation and model picker
  env.py            Shell execution, cwd tracking and output spooling
  model.py          LiteLLM adapter and tool schemas
  tools.py          Built-in file tools
config/             Example YAML templates
```

## Releases and naming

Current source uses the **`sbswe`** package and command. The first published `v0.1.0` predates this rename; its original artifacts are preserved. Install current `main` using the instructions above for the renamed command. A newly named release artifact will require a subsequent release.

[Release downloads](https://github.com/R0sso-Corsa/Slightly-Bigger-SWE-Agent/releases) · [Changelog](CHANGELOG.md)

## License and upstream

[MIT](LICENSE). Based on [mini-swe-agent](https://github.com/SWE-agent/mini-swe-agent); the upstream copyright notice is retained. This project is an independent derivative.
