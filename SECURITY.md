# Security and release scope

sbswe is an experimental local coding agent, **not a sandbox**. Shell commands and
file tools run with your account's access. Deny patterns are convenience checks,
not a security boundary. Use a disposable checkout/container and least-privileged
credentials. Do not point it at untrusted instructions or sensitive directories.

Interactive runs ask before actions by default. Non-interactive runs require
explicit `--yolo` to acknowledge execution without approval. Cost accounting
is best-effort: unknown provider pricing can report zero, so the dollar limit is
not a hard spending cap. Use a finite `--step-limit` and provider spending limits.

API keys belong in gitignored `.env` files or environment variables. Setup stores
key references in YAML, not key values. OAuth credentials stay in the provider's
own auth file. Model/tool output, terminal errors, spooled output and saved
trajectories are **not automatically redacted** and may contain sensitive data.
Child shell processes inherit environment variables. Do not publish these logs.

Model discovery only calls a configured provider's `/models` endpoint. Redirects
are refused; HTTPS certificates are verified. HTTP endpoints are supported for
local servers but send credentials unencrypted—use HTTPS for remote services.

Report vulnerabilities privately through GitHub's private vulnerability reporting
if enabled; otherwise contact the repository owner privately. Do not include real
credentials in issues. Rotate any exposed credentials immediately.
