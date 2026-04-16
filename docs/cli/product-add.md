# `fluid product-add`

Append a source, exposure, or data-quality check to an existing FLUID contract.

## Syntax

```bash
fluid product-add CONTRACT WHAT --id ID [--description TEXT] [--type TYPE] [--location LOC]
```

## Key options

| Option | Description |
| --- | --- |
| `CONTRACT` | Path to existing `contract.fluid.json` or `contract.fluid.yaml`. |
| `WHAT` | What to add: `source`, `exposure`, or `dq`. |
| `--id` | Identifier to add. Required. |
| `--description` | Free-text description of the item. |
| `--type` | Item type. For `source`: `table`/`view`/`file` (default `table`). For `exposure`: e.g. `dashboard` (default). For `dq`: `freshness`/`schema`/`quality` (default `quality`). |
| `--location` | Location/path. Stored as `location` for sources and as `url` for exposures. |

## Examples

```bash
fluid product-add contract.fluid.json source --id orders_raw --type table --location warehouse.raw.orders
fluid product-add contract.fluid.json exposure --id sales_dashboard --type dashboard --location https://looker/dash/123
fluid product-add contract.fluid.json dq --id freshness_check --type freshness --description "Updated daily by 06:00"
```

## Notes

- New items are appended into the matching section (`sources`, `exposures`, or `dataQuality`) and then deduplicated by `id`, keeping the last occurrence.
- The contract is rewritten atomically. YAML inputs are written back as JSON (`.yaml`/`.yml` files are converted to `.json`); convert back manually if you prefer YAML on disk.
- To create a brand-new product first, see [`fluid product-new`](./product-new.md). To validate or apply the result, see [`fluid validate`](./validate.md) and [`fluid apply`](./apply.md).
