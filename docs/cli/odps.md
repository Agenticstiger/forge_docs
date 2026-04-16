# `fluid odps`

Export FLUID contracts to, validate, and inspect the official ODPS (Open Data Product Specification) format from the Linux Foundation / Open Data Product Initiative.

## Syntax

```bash
fluid odps export CONTRACT [--version VER] [--out PATH] [--env ENV] [--no-validate] [--compact]
fluid odps validate FILE [--version VER] [--no-full-schema]
fluid odps info [--version VER] [--json]
```

## Key options

### `odps export`

| Option | Description |
| --- | --- |
| `CONTRACT` | Path to FLUID contract file (YAML/JSON). |
| `--version` | ODPS specification version. Default `4.1`. |
| `--out` | Output file path, or `-` for stdout. Default `-`. |
| `--env` | Environment name for overlay application. |
| `--validate` / `--no-validate` | Validate output against ODPS schema. Default on. |
| `--pretty` / `--compact` | Pretty-print or compact JSON output. Default pretty. |

### `odps validate`

| Option | Description |
| --- | --- |
| `FILE` | Path to ODPS JSON file. |
| `--version` | ODPS version to validate against. Default `4.1`. |
| `--full-schema` / `--no-full-schema` | Use full JSON schema validation (requires `jsonschema`) or basic checks only. Default full. |

### `odps info`

| Option | Description |
| --- | --- |
| `--version` | Show info for a specific version only. |
| `--json` | Output in JSON format. |

## Examples

```bash
fluid odps export contract.yaml --version 4.1 --out product.odps.json
fluid odps export contract.yaml --compact > product.odps.json
fluid odps validate product.odps.json
fluid odps info --version 4.1
```

## Notes

- The source file is named `opds.py` for historical reasons; the canonical command name registered in `fluid --help` is `odps`.
- Currently only ODPS v4.1 is registered. New versions can be added without code changes elsewhere.
- If the file passed to `validate` is a wrapped render envelope (contains `artifacts`), it is unwrapped automatically.
- For Bitol.io's separate ODPS variant (used by Entropy Data marketplace), use [`fluid odps-bitol`](./odps-bitol.md). For the Open Data Contract Standard, use [`fluid odcs`](./odcs.md). For a one-shot export-to-file shortcut, see [`fluid export-opds`](./export-opds.md).
