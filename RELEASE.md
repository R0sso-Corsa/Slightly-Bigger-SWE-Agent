# sbswe 0.2.0 release checks

This release packages the `sbswe` rename. It is an experimental local coding
agent, not a sandboxed or production-hardened environment.

## What to verify

- Run the regression suite on Python 3.10 and 3.13, including the package name,
  CLI branding and `0.2.0` version checks.
- Run the typechecker and `git diff --check`.
- Build the wheel and source archive, check their metadata, and install the wheel
  with fresh dependencies outside the source checkout.
- Exercise endpoint setup, key replacement, model selection, user config loading
  and non-interactive approval refusal with temporary settings and dummy keys.
- Check migration of saved endpoint settings and credential-variable references.
  Compare key values privately; never include real keys in test output or Git.
- Run a bounded authenticated test on the installed wheel, including an exact
  harmless approved shell command, submission and follow-up. Use a controlling
  PTY for the installed CLI's actual approval prompt.
- Bind final CI results and downloaded release-asset hashes to the exact release
  commit. Record the evidence in the release/PR notes rather than changing this
  file after every check and invalidating the tested artifact.

## Public-release privacy check

Before changing visibility, scan a mirror of all remote refs, both old and new
release archives, and the material exposed by PRs/issues. The deliberately local
backup branch, personal tracker, `.env`, OAuth files and diagnostic transcripts
must remain outside the remote repository. Use a redacting secret scanner and a
private known-credential-value check. These scans reduce risk; they are not a
proof that every possible secret is absent.

Public visibility exposes existing history and releases too. Keep the original
release artifacts unchanged, but inspect them before exposing them. Follow
[SECURITY.md](SECURITY.md) for credential handling.

## Earlier release evidence

The original `v0.1.0` passed its Python 3.10/3.13 CI and bounded ChatGPT OAuth task,
approval and follow-up checks. Its first OpenRouter Inkling attempts failed with a
regional HTTP 403; that provider restriction was not fixed by changing software.
An early CLI harness failed without a controlling terminal. It reproduced offline
and passed when the harness used a controlling PTY, without an application fix.

Those results describe the original release. They do not replace testing the
renamed 0.2.0 package. See [MIGRATION.md](MIGRATION.md) and [CHANGELOG.md](CHANGELOG.md).

## Limits

The agent runs with your account's access and child commands inherit environment
variables. Logs, spooled output and saved trajectories are not automatically
redacted. Unknown provider pricing can report zero; use provider spending limits
and finite step limits. Browser OAuth setup, OAuth catalog discovery, MCP/ACP,
and richer cancellation remain outside this release.

macOS and Linux checks do not establish Windows support. Dependencies are not
fully pinned, so a successful fresh installation does not cover every future
resolution. No PyPI publication is part of this GitHub release.
