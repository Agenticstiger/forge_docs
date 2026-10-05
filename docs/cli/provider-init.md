# `fluid provider-init`

Scaffold a new FLUID provider package with tests, entry points, and an SDK conformance harness.

## Syntax

```bash
fluid provider-init NAME [--author NAME] [--description TEXT] [--output-dir DIR]
```

## Key options

| Option | Description |
| --- | --- |
| `NAME` | Provider name: a letter, then lowercase letters, digits and underscores (positional, required). Hyphens are accepted and become underscores, and uppercase is lowercased: `Bad-Name` scaffolds `bad_name`. A name that starts with a digit exits 1 with `ERR_INVALID_PROVIDER_NAME`. |
| `--author` | Author name to write into `pyproject.toml` and the README (default `FLUID Community`). |
| `--description` | Short description for the package (defaults to `FLUID provider for <Name>`). |
| `--output-dir` | Parent directory for the new package (default `.`). |

## Examples

```bash
fluid provider-init databricks
fluid provider-init azure --author "My Company" --description "Azure Synapse"
fluid provider-init kafka --output-dir ~/projects
```

## Output

`fluid provider-init my-warehouse` printed this in 0.18.1:

```text
Created fluid-provider-my-warehouse/
  pyproject.toml          — package config with entry points
  src/fluid_provider_my_warehouse/__init__.py
  src/fluid_provider_my_warehouse/provider.py  — BaseProvider subclass
  tests/test_conformance.py              — SDK harness tests
  tests/fixtures/basic_contract.yaml
  README.md

Next steps:
  cd fluid-provider-my-warehouse
  pip install -e "."
  # Implement plan() in provider.py
  # Implement apply() in provider.py
  pytest -v  # Run conformance tests
```

The tree on disk also has an empty `tests/__init__.py`.

## Notes

- Creates `fluid-provider-<name>/` with a `pyproject.toml` (with the `fluid_build.providers` entry point), `src/fluid_provider_<name>/{__init__,provider}.py`, a conformance test, a fixture contract, and a README.
- Refuses reserved names with `ERR_RESERVED_PROVIDER_NAME` and exit 1: `unknown`, `stub`, `base`, `test`, `none`, `default`, `local`, `aws`, `gcp`, `snowflake`, `odps`. Refuses to overwrite an existing target directory (`ERR_DIRECTORY_EXISTS`, exit 1). See [`fluid providers`](./providers.md#err-reserved-provider-name).
- Hyphens in the provided name are normalised to underscores. The Python module (`fluid_provider_my_warehouse`) and the entry-point name (`my_warehouse`) use underscores; the directory and the distribution name use hyphens.
- The fixture contract declares `fluidVersion: "0.7.5"`, the stable schema. It does not use the 0.7.6 preview.
- Once installed with `pip install -e ".[dev]"`, the new provider shows up in [`fluid providers`](./providers.md).
