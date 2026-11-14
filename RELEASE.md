# 0.1.0 release candidate

Status: release candidate pushed for review; full release not published. Repository
visibility remains private. This is an experimental preview, not a sandboxed or
production-hardened agent.

## Remote and live acceptance evidence

- Code candidate `7682ceb` passed both Linux CI jobs (Python 3.10 and 3.13):
  https://github.com/R0sso-Corsa/Slightly-Bigger-SWE-Agent/actions/runs/43463213010
- The configured OpenRouter Inkling model was confirmed in the live catalog, but
  authenticated chat returned HTTP 403: "This model is not available in your
  region." Two bounded attempts failed before tool execution. This is a provider
  availability restriction, not a successful end-to-end chat validation.
- With explicit user approval, live acceptance then passed using the existing
  ChatGPT OAuth login (`chatgpt/gpt-6.1-sol`), without changing the saved default:
  three authenticated requests, one exact-command approval, real shell marker
  output, successful submission and successful follow-up submission.
- A separate installed-CLI check exercised the actual `input()` approval prompt
  under a controlling PTY: one harmless approved command, submission and exit 0.
  An earlier PTY harness failed because it lacked a controlling terminal; the
  failure reproduced offline and passed with a proper controlling PTY. No app
  source fix was needed. This does not claim the initial harness run passed.
- These are bounded release smoke tests, not validation of every provider/model,
  spending cap, arbitrary tool workflow or manual UI usability scenario.

## Local acceptance

- 14 configuration/model-picker/runtime regression tests pass on macOS with
  Python 3.13 and Python 3.10.21. Re-run `python -m unittest discover -v` after edits.
- `basedpyright -p . --pythonversion 3.10` and `git diff --check` must pass.
- `python -m build` produces a wheel and sdist; `python -m twine check dist/*.whl dist/*.tar.gz`
  validates metadata. Install the wheel in a fresh virtualenv outside the checkout
  and exercise `mswe --help`, endpoint setup, key rotation and model selection.
- Inspect BOTH archives for local env files, auth files, VAULT.md, personal paths,
  upstream reference copies and known credential values. A pattern scan is not a
  proof that arbitrary secrets cannot exist.
- Keep upstream MIT notice in the repository and distributions.

## Fixed during preparation

- Saved non-OpenAI keys no longer inherit a generic OpenAI base URL.
- Cross-provider model overrides cannot silently reuse a saved endpoint's key.
- Endpoint-name punctuation uses collision-free environment-variable encoding.
- Shell cwd tracking preserves command failure status.
- Relative file tools follow the environment's cwd and shell cd, not the launcher.
- Non-TTY execution requires explicit `--yolo`; interactive approval stays default.
- Installed wheels use writable user env storage, not site-packages.
- Removed implicit loading of another project's mini-swe-agent env file.

## Remaining gates before publication

- [x] Prepare a local release-candidate branch and commit intended source/docs/tests only; do not stage `.env`, OAuth files,
  local VAULT.md, generated artifacts, or `backup/pre-github-sanitize`.
- [x] Push the reviewed code candidate to the existing private repo and verify remote SHA.
- [x] Observe successful GitHub Actions results for Python 3.10/3.13 on Linux for the code candidate.
- [ ] Confirm CI for the final documentation/asset-target commit before publication.
- [x] Pass bounded authenticated task/approval/follow-up checks using approved
  ChatGPT credentials, plus an actual installed-CLI approval-prompt check.
- [x] Create a draft v0.1.0 release with wheel, sdist and SHA256SUMS; keep private.
- [ ] Refresh/verify remote assets against the final commit before publishing.
- [ ] Obtain final approval to merge the PR and publish the release.

No PyPI publishing, public-repo conversion or full GitHub release publication has
been authorized. Keep the release draft until final approval; do not push all
branches. Use the PR checks and release metadata as the current evidence for
final-commit CI and asset verification (avoids a self-referential docs rebuild).

## Known limits

See SECURITY.md. Guardrails are not a sandbox; child commands inherit the parent
account/environment. Logs/trajectories/tool output are not automatically redacted.
Unknown provider costs can report zero. Keep provider-side spending limits and a
finite step limit. OAuth browser setup and OAuth catalog discovery are not
implemented. Model catalogs can list models unavailable to your account.

Dependencies are currently version-ranged/unpinned; a fresh install is tested,
not a guarantee of all future dependency resolutions. macOS local checks and a
prepared Linux CI matrix are not a Windows support claim.
