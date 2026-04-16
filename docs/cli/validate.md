# `fluid validate`

Validate a contract against FLUID schema rules and provider-aware checks.

## Syntax

```bash
fluid validate CONTRACT
```

## Key options

| Option | Description |
| --- | --- |
| `--env` | Apply an environment overlay |
| `--schema-version` | Validate against a specific schema version |
| `--min-version` | Minimum acceptable schema version |
| `--max-version` | Maximum acceptable schema version |
| `--strict` | Treat warnings as errors |
| `--offline` | Use only cached or bundled schemas |
| `--force-refresh` | Refresh cached schemas |
| `--clear-cache` | Clear schema cache first |
| `--cache-dir CACHE_DIR` | Custom schema cache directory |
| `--verbose`, `-v` | Detailed validation output |
| `--quiet`, `-q` | Minimal output |
| `--format` | `text` or `json` |
| `--list-versions` | List available schema versions |
| `--show-schema` | Show the schema used for validation |

## Examples

```bash
fluid validate contract.fluid.yaml
fluid validate contract.fluid.yaml --env prod
fluid validate contract.fluid.yaml --strict
fluid validate contract.fluid.yaml --schema-version 0.7.2
fluid validate contract.fluid.yaml --verbose --show-schema
```

## Notes

- A contract can legitimately use `fluidVersion: 0.7.2` even when the installed CLI release is `0.7.9`.
- For most users, plain `fluid validate contract.fluid.yaml` is enough. Reach for explicit schema flags when you are debugging compatibility or working across versions.
