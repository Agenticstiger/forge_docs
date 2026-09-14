# `fluid export-opds` (deprecated alias)

::: warning Deprecated
`fluid export-opds` is the historical letter-swap name for the LF/ODPI ODPS v4.1 export. It still runs
in 0.15.0 and prints a deprecation warning. Prefer
[`fluid generate standard --format odps-v4.1`](./generate.md) in new scripts.

Note the earlier spelling `fluid export-odps` (ODPS, letters not swapped) is **not** a registered
command in 0.15.0 and exits 2. And the center-stage `fluid generate standard --format odps` emits
**Bitol** ODPS v1.0.0, a different standard that shares the acronym.
:::

Export a FLUID contract to an LF/ODPI ODPS v4.1 (Open Data Product Specification) JSON file in one shot.

## Syntax

```bash
fluid export-opds CONTRACT [--env ENV] [--out PATH]
```

The successor form:

```bash
fluid generate standard CONTRACT --format odps-v4.1 [--env ENV] [--out PATH]
```

`--out` / `-o` takes a **file** path, not a directory. There is no `--output` spelling.

## Key options

| Option | Description |
| --- | --- |
| `CONTRACT` | Path to the FLUID contract (typically `contract.fluid.yaml`). |
| `--env` | Overlay environment to apply before exporting. |
| `--out` | Output file path for the generated JSON. Default `runtime/exports/product.odps-v4.1.json`. |

## Examples

```bash
fluid export-opds contract.fluid.yaml
fluid export-opds contract.fluid.yaml --out my-product.odps-v4.1.json
fluid export-opds contract.fluid.yaml --env prod --out prod-product.json
```

The same output from the successor command:

```bash
fluid generate standard contract.fluid.yaml --format odps-v4.1 --out my-product.odps-v4.1.json
```

## Notes

- This is a thin convenience wrapper that always writes to a file. For interactive workflows, validation, spec selection, or stdout output use [`fluid odps`](./odps.md) instead.
- Internally invokes the ODPS exporter's `render()` and writes the first artifact from the returned envelope.
- The output directory is created automatically.
- See also [`fluid odps-bitol`](./odps-bitol.md) for explicit Bitol ODPS v1.0.0 export and [`fluid odcs`](./odcs.md) for the Open Data Contract Standard.
