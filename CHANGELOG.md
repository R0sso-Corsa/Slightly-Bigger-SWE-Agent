# Changelog

## 0.2.0

The package and command are now `sbswe`. This release includes the rename that
landed after the first release, along with the updated setup documentation.

- Renamed Python imports, the console command, CI artifacts and package metadata.
- User settings now live in `~/.config/sbswe`; configuration variables use the
  `SBSWE_` prefix. History and output-spool names follow the new package name.
- Added a package/CLI branding check and a release-version check.
- Refreshed the README and documented migration from the first release.

Existing installations need to migrate their settings or run `sbswe --configure`.
See [MIGRATION.md](MIGRATION.md). The original `v0.1.0` files are unchanged.

## 0.1.0

First experimental release of Slightly-Bigger-SWE-Agent, published before the
package rename.

- Local coding loop, structured submission, file tools, stateful shell directory,
  character-budget history compaction and large-output spooling.
- User YAML defaults and `${VAR}` references to gitignored environment files.
- `--configure`: saved endpoint setup with local provider-name detection.
- `--reauth`: hidden API-key replacement (not browser OAuth).
- `--models`: searchable provider catalogs and manual fallback, outside chat.
- Wheel/source packaging, upstream MIT attribution, security guidance and CI.

Both releases are experimental. There is no sandbox, unknown model pricing can
report zero, and browser OAuth setup is not implemented. See [SECURITY.md](SECURITY.md).
