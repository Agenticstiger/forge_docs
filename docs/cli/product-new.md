# `fluid product-new`

Bootstrap a new FLUID data-product skeleton with a minimal sample contract.

## Syntax

```bash
fluid product-new --id PRODUCT_ID [--out-dir DIR]
```

## Key options

| Option | Description |
| --- | --- |
| `--id` | Product ID, e.g. `gold.customer360_v1`. Required. |
| `--out-dir` | Where to create the product files. Default `products`. |

## Examples

```bash
fluid product-new --id gold.customer360_v1
fluid product-new --id silver.orders_v1 --out-dir services
```

## Notes

- Creates `<out-dir>/<id-with-underscores>/contract.fluid.json` containing a minimal `DataProduct` skeleton (one `dbt` build with a 02:15 daily cron, empty `consumes`/`exposes`).
- The scaffolded contract uses `fluidVersion: 0.5.7`; upgrade as needed before validating against newer schemas.
- For a fuller, opinionated scaffold (with sample data, overlays, and CI), use [`fluid init`](./init.md) or [`fluid demo`](./demo.md). For AI-guided creation, use [`fluid forge`](./forge.md).
- To extend an existing product contract with sources, exposures, or DQ checks, use [`fluid product-add`](./product-add.md).
