# `fluid datamesh-manager`

Publish FLUID data products and contracts to Entropy Data / Data Mesh Manager, and manage the products and teams stored there.

## Syntax

```bash
fluid datamesh-manager publish CONTRACT [options]
fluid datamesh-manager list [--format FMT]
fluid datamesh-manager get PRODUCT_ID
fluid datamesh-manager delete PRODUCT_ID [--yes]
fluid datamesh-manager teams [--format FMT]
```

A short alias `fluid dmm` is registered for the same command group.

## Key options

### `publish`

| Option | Description |
| --- | --- |
| `CONTRACT` | Path to FLUID contract file. |
| `--overlay`, `-o` | Path to overlay file. |
| `--team-id` | Team ID. Default derived from contract owner. |
| `--dry-run` | Preview the request payload without publishing. |
| `--with-contract` | Also publish a companion data contract per expose. |
| `--no-create-team` | Do not auto-create the team if it is missing. |
| `--contract-format` | `odcs` (Open Data Contract Standard v3.1.0, default) or `dcs` (Data Contract Specification 0.9.3, deprecated). |
| `--data-product-spec` | Override `dataProductSpecification` value sent to Entropy Data (e.g. `odps` or `0.0.1`). |
| `--validate-generated-contracts` | Validate generated ODCS contracts locally before PUT. |
| `--validation-mode` | `warn` (default; logs and continues) or `strict` (fails on invalid contracts). |
| `--fail-on-contract-error` | Exit non-zero if any ODCS contract publish fails. |
| `--api-key` | Entropy Data API key. Falls back to `DMM_API_KEY` env var. |
| `--api-url` | API base URL. Default `https://api.entropy-data.com`. |

### `list`, `teams`

| Option | Description |
| --- | --- |
| `--format`, `-f` | Output format: `table` (default) or `json`. |
| `--api-key` | Entropy Data API key. |
| `--api-url` | API base URL. |

### `get`, `delete`

| Option | Description |
| --- | --- |
| `PRODUCT_ID` | Data product ID. |
| `--api-key` | Entropy Data API key. |
| `--api-url` | API base URL. |
| `--yes`, `-y` | (`delete` only) Skip confirmation prompt. |

## Examples

```bash
fluid datamesh-manager publish contract.fluid.yaml --dry-run
fluid datamesh-manager publish contract.fluid.yaml --with-contract --validation-mode strict
fluid dmm list --format json
fluid dmm delete gold.customer360_v1 --yes
```

## Notes

- The short alias `fluid dmm` is equivalent to `fluid datamesh-manager`.
- Before any publish, the loaded FLUID contract is validated against the schema matching its declared `fluidVersion`. `--validation-mode strict` aborts on errors; `--validation-mode warn` (the default) logs and proceeds.
- The `dcs` contract format is marked deprecated; prefer the default `odcs`.
- For local-only export to ODCS (no publish), see [`fluid odcs`](./odcs.md). For ODPS exports, see [`fluid odps`](./odps.md) and [`fluid odps-bitol`](./odps-bitol.md).
