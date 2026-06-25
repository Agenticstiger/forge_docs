# `fluid product-add`

Append a source, exposure, or data-quality check to an existing FLUID contract.

::: warning Known limitation — output does not pass `fluid validate`
`product-add` writes its items into **top-level** `sources`, `exposures`, or `dataQuality` arrays. None of those keys exist in the current FLUID schema (`fluid-schema-0.7.4.json`), and the contract root is closed (`additionalProperties: false`). A contract that was valid before `product-add` will **fail** `fluid validate` afterwards, e.g.:

```text
1. root: Additional properties are not allowed ("dataQuality" was unexpected)
```

The canonical homes are different (see [Canonical contract shape](#canonical-contract-shape) below): a dataset interface is an entry in top-level `exposes[]`, its columns live at `exposes[].contract.schema[]`, and data-quality rules live at `exposes[].contract.dq.rules[]`. Until this command is updated to emit the canonical shape, edit those sections by hand (or scaffold with [`fluid product-new`](./product-new.md), which already emits a canonical `exposes: []`).
:::

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

- New items are appended into the matching **top-level** section (`sources`, `exposures`, or `dataQuality`) and then deduplicated by `id`, keeping the last occurrence. These section keys are **not** part of the current FLUID schema — see the warning above.
- The contract is rewritten atomically. YAML inputs are written back as JSON (`.yaml`/`.yml` files are converted to `.json`); convert back manually if you prefer YAML on disk.
- To create a brand-new product first, see [`fluid product-new`](./product-new.md). To validate or apply the result, see [`fluid validate`](./validate.md) and [`fluid apply`](./apply.md) — but note that the output will not validate until you move the items into their canonical homes.

## Canonical contract shape

The FLUID schema (`fluid-schema-0.7.4.json`) is closed at the top level; its required keys are `fluidVersion`, `kind`, `id`, `name`, `metadata`, and `exposes`. There are no top-level `sources`, `exposures`, or `dataQuality` keys. The pieces `product-add` tries to add belong in these places instead:

| `product-add` writes | Canonical home |
| --- | --- |
| top-level `sources[]` | an upstream reference under `consumes[]`, or a source-aligned `exposes[]` entry |
| top-level `exposures[]` | a consumer interface under `exposes[]` (each requires `exposeId`, `kind`, `binding`, `contract`) |
| top-level `dataQuality[]` | `exposes[].contract.dq.rules[]` |

A data-quality rule (`exposes[].contract.dq.rules[]`) requires `id`, `type`, and `severity`:

- `type` — one of `freshness`, `completeness`, `uniqueness`, `valid_values`, `accuracy`, `schema`, `anomaly_detection`, `drift_detection`.
- `severity` — one of `info`, `warn`, `error`, `critical`.

```yaml
exposes:
  - exposeId: orders_curated
    kind: table
    binding: { platform: snowflake }
    contract:
      schema:
        - name: order_id
          type: string
      dq:
        rules:
          - id: freshness_check
            type: freshness
            severity: error
```

An alternate inline form is `exposes[].contract.quality[].{rule, expression, severity}`.
