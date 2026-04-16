# `fluid odcs`

Convert between FLUID contracts and the Open Data Contract Standard (ODCS) v3.1.0 from Bitol.io, in either direction.

## Syntax

```bash
fluid odcs export CONTRACT [--output PATH] [--format FMT] [--no-quality] [--no-sla]
fluid odcs import ODCS_FILE [--output PATH] [--format FMT]
fluid odcs validate ODCS_FILE
fluid odcs info
```

## Key options

### `odcs export`

| Option | Description |
| --- | --- |
| `CONTRACT` | Path to FLUID contract file. |
| `--output`, `-o` | Output file path. Default `<contract-name>-odcs.<format>`. |
| `--format`, `-f` | Output format: `yaml` or `json`. Default `yaml`. |
| `--no-quality` | Exclude quality checks from the output. |
| `--no-sla` | Exclude SLA properties from the output. |

### `odcs import`

| Option | Description |
| --- | --- |
| `ODCS_FILE` | Path to ODCS contract file. |
| `--output`, `-o` | Output file path. Default `<file>-fluid.<format>`. |
| `--format`, `-f` | Output format: `yaml` or `json`. Default `yaml`. |

### `odcs validate`

| Option | Description |
| --- | --- |
| `ODCS_FILE` | Path to an ODCS file to validate against the v3.1.0 JSON schema. |

### `odcs info`

No options. Prints provider info (version, spec URL, schema status).

## Examples

```bash
fluid odcs export contract.fluid.yaml
fluid odcs export contract.fluid.yaml -o contract.json -f json --no-sla
fluid odcs import third-party-contract.yaml -o my-contract.fluid.yaml
fluid odcs validate contract.odcs.yaml
```

## Notes

- ODCS is bidirectional: `export` goes FLUID -> ODCS, `import` goes ODCS -> FLUID.
- Validation uses the bundled ODCS v3.1.0 JSON Schema from Bitol.io.
- For Bitol.io's data-product variant (ODPS-Bitol), use [`fluid odps-bitol`](./odps-bitol.md). For the Linux Foundation ODPS, use [`fluid odps`](./odps.md).
- To publish ODCS contracts to Entropy Data alongside a data product, see [`fluid datamesh-manager publish --with-contract`](./datamesh-manager.md).
