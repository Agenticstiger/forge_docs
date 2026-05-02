# Product Types — SDP, ADP, CDP

Schema **0.7.3** introduces a Data Mesh-aligned classification, `metadata.productType`, that runs alongside the existing medallion `metadata.layer`. Both vocabularies are first-class. You can use either one, or both together. When both are set, the validator enforces the canonical pairing.

::: tip Where this fits
Schema 0.7.3 ships in the `feat/source-aligned-acquisition` branch and is not yet on PyPI. Existing 0.7.2 contracts validate unchanged — the new fields are purely additive.
:::

## The vocabulary

| medallion (`metadata.layer`) | Data Mesh (`metadata.productType`) | Expansion | When to use |
|---|---|---|---|
| `Bronze` | **`SDP`** | Source-Aligned Data Product | Raw or near-raw ingestion from an external system. One source, one product. |
| `Silver` | **`ADP`** | Aggregated Data Product | Cross-source joined / domain-modelled. Built on top of one or more SDPs. |
| `Gold` | **`CDP`** | Consumption-Aligned Data Product | Analytics- or product-shaped. The thing dashboards / ML / APIs read. |
| `Platinum` | *(no analogue)* | — | Highly curated / regulated; rare. Stay on `metadata.layer` only. |

## Why two vocabularies

The medallion vocabulary (`Bronze / Silver / Gold`) is widely understood by Lakehouse and dbt practitioners; the Data Mesh vocabulary (`SDP / ADP / CDP`) is the language of mesh governance, marketplace listings, and federated data products. Forge accepts both because:

- Teams migrating from a Lakehouse-first architecture know `Bronze` already and don't want to relearn.
- Teams operating in a Data Mesh need `SDP / ADP / CDP` for catalog facets, ownership boundaries, and composition rules.
- Tooling that consumes Forge contracts (Data Mesh Manager, marketplaces, governance dashboards) speaks one or the other — Forge propagates both.

You don't need to pick one. Set whichever fits your team's vocabulary and let the validator infer the missing twin.

## Setting it on a contract

Either field is sufficient — set whichever is natural for your team.

**Layer-only (medallion-first):**

```yaml
metadata:
  layer: Gold
  owner:
    team: data-platform
    email: platform@example.com
```

The validator infers `productType: CDP` automatically; downstream catalog tooling sees both.

**productType-only (mesh-first):**

```yaml
metadata:
  productType: SDP
  owner:
    team: ingestion
    email: ingest@example.com
```

The validator infers `layer: Bronze`.

**Both set explicitly:**

```yaml
metadata:
  layer: Silver
  productType: ADP
  owner:
    team: analytics
    email: analytics@example.com
```

If both are set, they MUST agree — `Silver + ADP`, `Gold + CDP`, `Bronze + SDP`. Mismatches produce a clear validation error pointing at the conflict.

## Composition rules

The product type controls what a contract can `consumes:`. The composition rule is enforced both at validation time (via [`fluid validate`](/forge_docs/cli/validate.html)) and during AI-assisted forging (via `fluid forge --from-product`):

| This contract type | Can consume from |
|---|---|
| **SDP** (`Bronze`) | Nothing. Source-aligned products ingest from external systems, not from other Forge products. |
| **ADP** (`Silver`) | One or more `SDP`s. Domain-modelling joins or projects raw inputs. |
| **CDP** (`Gold`) | One or more `SDP` and/or `ADP`s. The consumer-facing layer can read from anywhere. |

Setting `consumes:` on an SDP contract is a hard validation error — that's the wrong shape. Use `acquisition:` instead (see [Source-Aligned Acquisition](/forge_docs/advanced/source-aligned-acquisition.html)).

## How the missing twin gets filled

The validator's normalization step runs in three places (CLI validation, schema-level validation, runtime contract checks) and applies the same canonical mapping:

```text
Bronze   ↔ SDP
Silver   ↔ ADP
Gold     ↔ CDP
Platinum ↔ (no productType — Platinum is medallion-only)
```

If only one is set, the other is filled from this map. If both are set and disagree, validation fails with the offending pair quoted.

## Migrating existing contracts

If you have a stack of 0.7.2 contracts using only `metadata.layer`, the new [`fluid contract migrate-product-type`](/forge_docs/cli/contract.html#migrate-product-type) command walks `**/*.fluid.yaml` under a root and writes the missing twin into each:

```bash
fluid contract migrate-product-type --root . --check     # dry-run; non-zero exit if anything is incomplete
fluid contract migrate-product-type --root . --write     # rewrite in place
```

The migrator preserves comments, key order, and quoting style so the diff is minimal.

## Cloud-label propagation

Provider tag emitters (AWS / GCP / Snowflake) project both vocabularies into cloud labels using **distinct keys with the same canonical value** so dashboards filtering by either vocabulary see consistent groupings:

| Cloud | Key 1 | Key 2 |
|---|---|---|
| GCP labels | `fluid_layer` | `fluid_product_type` |
| AWS tags | `fluid_layer` | `fluid_product_type` |
| Snowflake tags | `FLUID_LAYER` | `FLUID_PRODUCT_TYPE` |

A `Gold + CDP` data product appears as `fluid_layer=Gold` AND `fluid_product_type=CDP` in BigQuery's resource manager, so a query that groups by either dimension produces the same answer.

## Other 0.7.3 metadata additions

While you're updating contracts, two adjacent fields ship in the same schema bump:

| Field | Type | What it's for |
|---|---|---|
| `metadata.classification` | enum: `public`, `internal`, `confidential`, `restricted` | Propagates to catalog access-policy enforcement and DLP scanners |
| `metadata.experimental` | string array | Feature gate — flags a product as opt-in or under active iteration |

Neither is required. Both are picked up by the catalog registrars (DataHub, OpenMetadata, Unity, Glue, Snowflake Horizon) when present.

## See also

- [Source-Aligned Acquisition](/forge_docs/advanced/source-aligned-acquisition.html) — the acquisition build pattern that powers SDP contracts
- [`fluid contract migrate-product-type`](/forge_docs/cli/contract.html#migrate-product-type) — the migrator command
- [`fluid forge --from-product`](/forge_docs/cli/forge.html) — composition-aware AI scaffolding that respects the type rules
- [Forge Data Model](/forge_docs/forge-data-model.html) — how the data-modelling pipeline emits productType into the generated contract
