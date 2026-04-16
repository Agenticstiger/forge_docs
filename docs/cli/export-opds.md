# `fluid export-opds`

Export a FLUID contract to an OPDS (Open Data Product Specification) JSON file in one shot.

## Syntax

```bash
fluid export-opds CONTRACT [--env ENV] [--out PATH]
```

## Key options

| Option | Description |
| --- | --- |
| `CONTRACT` | Path to the FLUID contract (typically `contract.fluid.yaml`). |
| `--env` | Overlay environment to apply before exporting. |
| `--out` | Output path for the generated JSON. Default `runtime/exports/product.opds.json`. |

## Examples

```bash
fluid export-opds contract.fluid.yaml
fluid export-opds contract.fluid.yaml --env prod
fluid export-opds contract.fluid.yaml --out exports/customer360.opds.json
```

## Notes

- This is a thin convenience wrapper that always writes to a file. For interactive workflows, validation, or stdout output use [`fluid odps`](./odps.md) instead.
- Internally it calls `OdpsProvider.to_odps()`. If the provider import fails it falls back to a minimal envelope containing `id`, `title`, `owner`, `domain`, and `exposes`.
- The output directory is created automatically.
- See also [`fluid odps-bitol`](./odps-bitol.md) for Bitol.io's ODPS variant and [`fluid odcs`](./odcs.md) for the Open Data Contract Standard.
