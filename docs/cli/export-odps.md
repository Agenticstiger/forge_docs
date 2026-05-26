# `fluid export-odps`

Export a FLUID contract to an ODPS (Open Data Product Standard) file in one shot.

::: tip Back-compat alias
`fluid export-opds` (old name, note the letter swap) is kept as a hidden back-compat alias and will be removed in a future major release. Update scripts to use `fluid export-odps`.
:::

## Syntax

```bash
fluid export-odps CONTRACT [--env ENV] [--out PATH]
```

## Key options

| Option | Description |
| --- | --- |
| `CONTRACT` | Path to the FLUID contract (typically `contract.fluid.yaml`). |
| `--env` | Overlay environment to apply before exporting. |
| `--out` | Output path for the generated file. Default `runtime/exports/product.odps.json`. |

## Examples

```bash
fluid export-odps contract.fluid.yaml
fluid export-odps contract.fluid.yaml --env prod
fluid export-odps contract.fluid.yaml --out exports/customer360.odps.json
```

## Notes

- This is a thin convenience wrapper that always writes to a file. For interactive workflows, validation, spec selection, or stdout output use [`fluid odps`](./odps.md) instead.
- Internally calls `OdpsProvider().render()` and writes the first artifact from the returned envelope.
- The output directory is created automatically.
- See also [`fluid odps-bitol`](./odps-bitol.md) for explicit Bitol ODPS v1.0.0 export and [`fluid odcs`](./odcs.md) for the Open Data Contract Standard.
