# 0.1.0 release candidate

Status: prepared locally, not published. This is an experimental preview, not a
sandboxed or production-hardened agent. Repository visibility remains private.

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
- [ ] Push the reviewed commit to the existing private repo and verify remote SHA.
- [ ] Observe GitHub Actions results for Python 3.10/3.13 on Linux. The workflow
  is prepared locally; no remote CI result is claimed before it runs.
- [ ] Manually accept a real configured-provider task in a disposable directory,
  including interactive approvals and follow-up chat. Unit tests and catalog
  listing are not end-to-end authenticated model validation.
- [ ] Approve release title/version/visibility; create a draft GitHub release
  against the verified commit and attach wheel, sdist and SHA256SUMS.
- [ ] Verify remote release metadata/assets and hashes before publishing.

No PyPI publishing, public-repo conversion, release tag or GitHub release is
performed by the local preparation step. Do not push all branches.

## Known limits

See SECURITY.md. Guardrails are not a sandbox; child commands inherit the parent
account/environment. Logs/trajectories/tool output are not automatically redacted.
Unknown provider costs can report zero. Keep provider-side spending limits and a
finite step limit. OAuth browser setup and OAuth catalog discovery are not
implemented. Model catalogs can list models unavailable to your account.

Dependencies are currently version-ranged/unpinned; a fresh install is tested,
not a guarantee of all future dependency resolutions. macOS local checks and a
prepared Linux CI matrix are not a Windows support claim.
