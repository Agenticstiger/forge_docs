# `fluid product-add`

Append a source, exposure, or data-quality rule to an existing FLUID contract — writing each into its **canonical home** so the contract still passes [`fluid validate`](./validate.md) afterwards.

::: tip Requires a build newer than 0.10.0
Schema-valid output landed in the fix merged **after 0.10.0** (currently on `main`; ships in a later release). On the released **0.10.0**, `product-add` still writes legacy top-level `sources` / `exposures` / `dataQuality` keys that **fail** `fluid validate` (`root: Additional properties are not allowed`). Until you upgrade, scaffold with [`fluid product-new`](./product-new.md) or move the items into their [canonical homes](#canonical-contract-shape) by hand. The `--platform`, `--expose`, and `--severity` options below are also new in that build.
:::

## Syntax

```bash
fluid product-add CONTRACT WHAT --id ID \
  [--description TEXT] [--type TYPE] [--location LOC] \
  [--platform PLATFORM] [--expose EXPOSE_ID] [--severity LEVEL]
```

Each `WHAT` maps to a different part of the contract:

| `WHAT` | Canonical home | Shape written |
| --- | --- | --- |
| `source` | `consumes[]` | `{ productId, exposeId }` — an upstream product expose this contract reads |
| `exposure` | `exposes[]` | `{ exposeId, kind, binding, contract }` — a data interface this product publishes |
| `dq` | `exposes[].contract.dq.rules[]` | `{ id, type, severity }` — attached to a target expose |

## Key options

| Option | Applies to | Description |
| --- | --- | --- |
| `CONTRACT` | all | Path to an existing `contract.fluid.json` or `contract.fluid.yaml`. |
| `WHAT` | all | What to add: `source`, `exposure`, or `dq`. |
| `--id` | all | **Required.** `exposure` → `exposeId`; `source` → upstream `productId`; `dq` → rule `id`. |
| `--description` | all | Free-text. Stored as `description` (`exposure`/`dq`) or `purpose` (`source`). |
| `--type` | `exposure`, `dq` | `exposure` → expose `kind` (`table`/`view`/`file`/`stream`/`topic`/…; default `table`). `dq` → rule `type` (`completeness`/`freshness`/`uniqueness`/`valid_values`/`accuracy`/`schema`/…; default `completeness`). Unrecognized values fall back to the default. |
| `--location` | `exposure`, `source` | `exposure` → `binding.location.path`. `source` → the upstream `exposeId` (defaults to `--id`). |
| `--platform` | `exposure` | `binding.platform` (`local`/`gcp`/`aws`/`snowflake`/…; default `local`). The `binding.format` is derived from the platform. |
| `--expose` | `dq` | Target `exposeId` the rule attaches to. Defaults to the first expose; errors if the contract has no expose yet. |
| `--severity` | `dq` | Rule severity: `info`/`warn`/`error`/`critical` (default `warn`). |

## Examples

```bash
# source -> a consumes[] upstream reference
fluid product-add contract.fluid.json source \
  --id sales.orders_v1 --location orders_curated --description "Curated orders feed"

# exposure -> an exposes[] interface (binding.platform + location)
fluid product-add contract.fluid.json exposure \
  --id customer_360 --type table --platform snowflake --location analytics.customer_360

# dq -> a rule under the target expose's contract.dq.rules[]
fluid product-add contract.fluid.json dq \
  --id orders_freshness --type freshness --severity error --expose customer_360
```

## Notes

- Each item is written to its canonical home (`consumes[]`, `exposes[]`, or the target expose's `contract.dq.rules[]`) and deduplicated — `exposes[]` by `exposeId`, `consumes[]` by `(productId, exposeId)`, and dq rules by `id` within the expose — keeping the last occurrence.
- `product-add` emits no version-specific optional keys, so the result validates against the contract's own `fluidVersion` (e.g. a `0.7.2` contract stays `0.7.2`-valid).
- The contract is rewritten atomically. YAML inputs are written back as JSON (`.yaml`/`.yml` → `.json`); convert back manually if you prefer YAML on disk.
- To create a brand-new product first, see [`fluid product-new`](./product-new.md). To validate or apply the result, see [`fluid validate`](./validate.md) and [`fluid apply`](./apply.md).

## Canonical contract shape

The FLUID schema (`fluid-schema-0.7.5.json`) is closed at the top level; its required keys are `fluidVersion`, `kind`, `id`, `name`, `metadata`, and `exposes`. There are no top-level `sources`, `exposures`, or `dataQuality` keys — which is why `product-add` writes to the homes below (and why hand-edited contracts should too):

| Concept | Canonical home |
| --- | --- |
| an upstream source | `consumes[]` (`{ productId, exposeId }`), or a source-aligned `exposes[]` entry |
| a consumer interface | `exposes[]` — each requires `exposeId`, `kind`, `binding`, `contract` |
| a data-quality rule | `exposes[].contract.dq.rules[]` |

A `binding` requires `platform`, `format`, and `location`. A data-quality rule (`exposes[].contract.dq.rules[]`) requires `id`, `type`, and `severity`:

- `type` — one of `freshness`, `completeness`, `uniqueness`, `valid_values`, `accuracy`, `schema`, `anomaly_detection`, `drift_detection`.
- `severity` — one of `info`, `warn`, `error`, `critical`.

```yaml
exposes:
  - exposeId: orders_curated
    kind: table
    binding:
      platform: local
      format: parquet
      location:
        path: output/orders_curated.parquet
    contract:
      schema:
        - name: order_id
          type: string
      dq:
        rules:
          - id: orders_freshness
            type: freshness
            severity: error
```

An alternate inline form is `exposes[].contract.quality[].{rule, expression, severity}`.
