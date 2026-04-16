# `fluid provider-init`

Scaffold a new FLUID provider package with tests, entry points, and an SDK conformance harness.

## Syntax

```bash
fluid provider-init NAME [--author NAME] [--description TEXT] [--output-dir DIR]
```

## Key options

| Option | Description |
| --- | --- |
| `NAME` | Provider name — lowercase, alphanumeric + underscores, must start with a letter (positional, required). |
| `--author` | Author name to write into `pyproject.toml` and the README (default `FLUID Community`). |
| `--description` | Short description for the package (defaults to `FLUID provider for <Name>`). |
| `--output-dir` | Parent directory for the new package (default `.`). |

## Examples

```bash
fluid provider-init databricks
fluid provider-init azure --author "My Company" --description "Azure Synapse"
fluid provider-init kafka --output-dir ~/projects
```

## Notes

- Creates `fluid-provider-<name>/` with a `pyproject.toml` (with the `fluid_build.providers` entry point), `src/fluid_provider_<name>/{__init__,provider}.py`, a conformance test, a fixture contract, and a README.
- Refuses reserved names: `unknown`, `stub`, `base`, `test`, `none`, `default`, `local`, `aws`, `gcp`, `snowflake`, `odps`. Refuses to overwrite an existing target directory.
- Hyphens in the provided name are normalised to underscores for the Python module; the directory name and entry-point slug use hyphens.
- The fixture contract pins `fluidVersion` to the latest schema bundled with this CLI.
- Once installed with `pip install -e ".[dev]"`, the new provider shows up in [`fluid providers`](./providers.md).
