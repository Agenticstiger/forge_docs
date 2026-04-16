# `fluid odps-bitol`

Export FLUID contracts to and validate Bitol.io's ODPS (Open Data Product Standard) v1.0 format, used for marketplace integrations such as Entropy Data.

## Syntax

```bash
fluid odps-bitol export CONTRACT [--output PATH] [--format FMT] [--no-custom]
fluid odps-bitol validate ODPS_FILE
fluid odps-bitol info
```

## Key options

### `odps-bitol export`

| Option | Description |
| --- | --- |
| `CONTRACT` | Path to FLUID contract file. |
| `--output`, `-o` | Output file path. Default `<contract-name>-odps.<format>`. |
| `--format`, `-f` | Output format: `yaml` or `json`. Default `yaml`. |
| `--no-custom` | Exclude custom properties from the output. |

### `odps-bitol validate`

| Option | Description |
| --- | --- |
| `ODPS_FILE` | Path to an ODPS-Bitol data product file. |

### `odps-bitol info`

No options. Prints provider information (version, spec URL, capabilities).

## Examples

```bash
fluid odps-bitol export contract.fluid.yaml
fluid odps-bitol export contract.fluid.yaml -o product.json -f json
fluid odps-bitol validate product.yaml
fluid odps-bitol info
```

## Notes

- Despite the source file being named `odps_standard.py`, the canonical command name registered in `fluid --help` is `odps-bitol`. This avoids confusion with the official ODPS variant.
- For the official ODPS v4.1 (Linux Foundation / Open Data Product Initiative), use [`fluid odps`](./odps.md) instead.
- For the Open Data Contract Standard (ODCS), use [`fluid odcs`](./odcs.md).
- Validation checks `apiVersion` (`v1.0.0` expected), requires `kind: DataProduct`, and verifies output ports have a `name` field.
