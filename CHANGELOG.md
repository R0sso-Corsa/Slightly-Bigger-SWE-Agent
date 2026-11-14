# Changelog

## 0.1.0 — release candidate (unpublished)

First experimental release candidate of Slightly-Bigger-SWE-Agent (`mswe`).

- Local coding loop, structured submission, file tools, stateful shell directory,
  character-budget history compaction and large-output spooling.
- User YAML defaults and `${VAR}` references to gitignored environment files.
- `--configure`: saved endpoint setup with local provider-name detection.
- `--reauth`: hidden API-key replacement (not browser OAuth).
- `--models`: searchable provider catalogs and manual fallback, outside chat.
- Wheel/source packaging, upstream MIT attribution, security guidance and CI.

Limitations: not a sandbox; non-interactive tasks require explicit `--yolo`; unknown
pricing is not a reliable budget gate; OAuth model discovery and browser login
are not implemented. See SECURITY.md and RELEASE.md for acceptance scope.
