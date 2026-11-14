# Moving to sbswe 0.2.0

The first release used a different package name. Version 0.2.0 installs the
`sbswe` command and Python package. The old release downloads remain unchanged.

## New installations

Install the new wheel in a virtual environment, then run:

```bash
sbswe --configure
sbswe --models
```

The wizard stores the provider settings and asks for a key with hidden input.
It does not import credentials from an older installation or start an OAuth login.

## Keep an existing configuration

Back up your settings and secret files privately before editing them. Do not put
those backups in Git. Existing key values and provider/model identifiers do not
need to change.

| Previous location/name | New location/name |
| --- | --- |
| `~/.config/mswe/config.yaml` | `~/.config/sbswe/config.yaml` |
| `~/.config/mswe/.env` | `~/.config/sbswe/.env` |
| `MSWE_MODEL` | `SBSWE_MODEL` |
| `MSWE_REASONING_EFFORT` | `SBSWE_REASONING_EFFORT` |
| `MSWE_ENDPOINT_..._API_KEY` | `SBSWE_ENDPOINT_..._API_KEY` |
| `~/.mswe_history` | `~/.sbswe_history` |
| `.mswe_spool/` | `.sbswe_spool/` |

If you use `XDG_CONFIG_HOME`, use that directory instead of `~/.config` for both
settings locations.

1. Copy the previous configuration directory to the new location only if the new
   location does not exist. If you already configured the new installation, merge
   the settings deliberately instead of overwriting it.
2. In the copied YAML, update generated environment-variable references to the new
   prefix. Update the corresponding variable names in your secret file and shell
   setup. Preserve key values and the rest of each generated variable name.
3. An editable checkout uses its own `.env`; copy that file privately if you moved
   to another checkout. A wheel installation uses the user `.env` above. Keep
   secret files readable/writable only by your user (`chmod 600 path/to/.env`).
4. Existing provider variables such as `OPENROUTER_API_KEY`, `OPENAI_API_KEY`,
   `CHATGPT_TOKEN_DIR` and `CHATGPT_AUTH_FILE` keep their names. Do not copy OAuth
   tokens into YAML or a Git-tracked file.
5. History and spooled output are optional to move. Keep both versions if a
   destination already exists. Old trajectory records can still contain old paths.
6. Recreate an editable install's virtual environment after moving the checkout;
   launchers and editable-install metadata can contain absolute paths. Update any
   shell alias or wrapper to the new `sbswe` executable.
7. Check `sbswe --help`, then use `sbswe --models` to choose a saved endpoint. Run a
   small task in a disposable directory before using the new installation normally.

The program does not perform an automatic migration from the previous names.
Keep your private backup until you have checked the new installation. Never change
arbitrary text inside an API key while renaming variables.
