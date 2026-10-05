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

## What it writes

```bash
fluid product-new --id gold.customer360_v1
```

```text
products/
└── gold_customer360_v1/
    └── contract.fluid.json
```

```json
{
  "fluidVersion": "0.7.3",
  "kind": "DataProduct",
  "id": "gold.customer360_v1",
  "name": "customer360_v1",
  "domain": "Customer",
  "metadata": {
    "layer": "Gold",
    "productType": "CDP",
    "owner": { "team": "Data", "email": "owner@example.com" }
  },
  "consumes": [],
  "builds": [
    {
      "id": "main_build",
      "pattern": "hybrid-reference",
      "engine": "dbt",
      "repository": "./models",
      "properties": { "model": "customer360_v1" },
      "execution": { "trigger": { "type": "schedule", "cron": "15 2 * * *" } }
    }
  ],
  "exposes": []
}
```

For this id, the `gold.` prefix produced `layer: Gold` and `productType: CDP`. The owner, domain and cron are placeholders: replace them.

The skeleton does not validate yet. `fluid validate` reports `exposes: [] should be non-empty`. Add an expose with [`fluid product-add`](./product-add.md#examples), then validate:

```bash
fluid product-add products/gold_customer360_v1/contract.fluid.json exposure \
  --id customer_360 --platform local --location output/customer_360.parquet
fluid validate products/gold_customer360_v1/contract.fluid.json
```

## Notes

- The file is JSON (`contract.fluid.json`), in `<out-dir>/<id-with-underscores>/`. The skeleton has one `dbt` build with a 02:15 daily cron, and empty `consumes` and `exposes`.
- `fluid product-new` writes `fluidVersion: 0.7.3`. `0.7.3` still validates; to move to the latest stable version, change the line to `0.7.5` and run `fluid validate`. See [which `fluidVersion` each scaffolder writes](./init.md#which-fluidversion-each-path-writes) for the other paths.
- For a fuller scaffold (with sample data, overlays and CI), use [`fluid init`](./init.md) or [`fluid demo`](./demo.md). For AI-guided creation, use [`fluid forge`](./forge.md).
- To extend an existing product contract with sources, exposures, or DQ checks, use [`fluid product-add`](./product-add.md).
