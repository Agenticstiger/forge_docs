# Product Types — SDP, ADP, CDP

Schema **0.7.3** introduced a Data Mesh-aligned classification, `metadata.productType`, that runs alongside the medallion `metadata.layer`. Both vocabularies are accepted. You can use either one, or both together. When both are set, `fluid validate` checks that they agree.

> **Why it matters**
> Classify each product by where it sits in the value chain (source, aggregate, consumer-aligned) so teams know what to build on and what to reuse.
> `metadata.productType` (SDP / ADP / CDP) sits alongside the medallion layer, with `consumes[]` composition rules that `fluid validate` checks.

## The vocabulary

| medallion (`metadata.layer`) | Data Mesh (`metadata.productType`) | Expansion | When to use |
|---|---|---|---|
| `Bronze` | **`SDP`** | Source-Aligned Data Product | Raw or near-raw ingestion from an external system. One source, one product. |
| `Silver` | **`ADP`** | Aggregated Data Product | Cross-source joined / domain-modelled. Built on top of one or more SDPs. |
| `Gold` | **`CDP`** | Consumption-Aligned Data Product | Analytics- or product-shaped. The thing dashboards / ML / APIs read. |
| `Platinum`, `Logical` | *(no analogue)* | none | Valid `metadata.layer` values with no `productType`. Set `metadata.layer` only. |

## Why two vocabularies

The medallion vocabulary (`Bronze / Silver / Gold`) is widely understood by Lakehouse and dbt practitioners; the Data Mesh vocabulary (`SDP / ADP / CDP`) is the language of mesh governance, marketplace listings, and federated data products. Forge accepts both because:

- Teams migrating from a Lakehouse-first architecture know `Bronze` already and don't want to relearn.
- Teams operating in a Data Mesh need `SDP / ADP / CDP` for catalog facets, ownership boundaries, and composition rules.
- Tooling that consumes Forge contracts (Data Mesh Manager, marketplaces, governance dashboards) speaks one or the other. Set both in the file when your tooling needs both; see [What lands where](#what-lands-where).

## Setting it on a contract

Either field is sufficient for validation. Set whichever is natural for your team.

**Layer-only (medallion-first):**

```yaml
metadata:
  layer: Gold
  owner:
    team: data-platform
    email: platform@example.com
```

`fluid validate` treats this product as a `CDP` when it applies the composition rules. The file itself still holds only `layer`.

**productType-only (mesh-first):**

```yaml
metadata:
  productType: SDP
  owner:
    team: ingestion
    email: ingest@example.com
```

**Both set explicitly:**

```yaml
metadata:
  layer: Silver
  productType: ADP
  owner:
    team: analytics
    email: analytics@example.com
```

If both are set, they must agree: `Bronze + SDP`, `Silver + ADP`, `Gold + CDP`. A mismatch fails `fluid validate` and quotes the pair:

```text
❌ Invalid FLUID contract (1 error(s)) (schema v0.7.5)

Validation Errors:
==================
 1. metadata consistency: metadata.layer='Gold' and metadata.productType='ADP'
are inconsistent. Canonical mapping: Bronze↔SDP, Silver↔ADP, Gold↔CDP.
```

## Composition rules

The product type controls what a contract can list in `consumes[]`:

| This contract type | Can consume from |
|---|---|
| **SDP** (`Bronze`) | Nothing. Source-aligned products ingest from external systems, not from other Forge products. |
| **ADP** (`Silver`) | `SDP`s and other `ADP`s. |
| **CDP** (`Gold`) | `SDP`s, `ADP`s and other `CDP`s. |

`fluid validate` checks the rule. A contract that declares `consumes[]` on an SDP fails:

```text
❌ Invalid FLUID contract (1 error(s)) (schema v0.7.5)

Validation Errors:
==================
 1. composition rule: SDP (Source-aligned data product (raw acquisition from an
upstream system)) does not accept upstream products.
(upstream='bronze.shop.orders_v1')
```

An ADP that consumes a CDP fails the same way: `ADP accepts upstreams of type ['ADP', 'SDP'] but 'gold.shop.revenue_v1' is CDP.` An SDP ingests with an acquisition build (`pattern: acquisition`) instead of `consumes[]`; see [Source-Aligned Acquisition](/forge_docs/advanced/source-aligned-acquisition.html).

Three limits, each measured on 0.18.1:

- **The check needs to find the upstream.** `fluid validate` looks for the upstream by scanning `*.fluid.yaml` files in the contract's own directory and up to three directories above it, stopping at the first directory that holds `.git`, `.fluid`, `fluid.yaml`, `pyproject.toml`, `.hg` or `.svn`. It reads the upstream's `id` and `metadata.productType` (or `metadata.layer`). An SDP that consumes a product it cannot find validates clean; the same contract fails once the upstream's file is in the scan. The scan walks every directory under those roots, so a contract in a directory with no marker file, under a large tree, validates slowly: can be slow. Keep contracts in a project directory that has a `.git` or `pyproject.toml`.
- **`fluid plan` does not apply the rule.** The same SDP contract that fails `fluid validate` plans and saves its plan.
- **The scan matches `*.fluid.yaml`.** A build that resolves `consumes[]` looks for files named `contract.fluid.yaml` instead; see [`consumes[]`](../concepts/builds-exposes-bindings.md#consumes-depending-on-another-product).

`fluid forge --from-product` runs the same composition rule when it assembles a downstream contract from existing products (source: `fluid_build/forge_datamodel/from_data_products/pipeline.py`; the command needs an LLM provider and was not run for this page).

## What the validator does with the pair

`fluid validate` normalizes a copy of `metadata`: it checks that `layer` is one of `Bronze`, `Silver`, `Gold`, `Platinum`, `Logical`, that `productType` is one of `SDP`, `ADP`, `CDP`, and that a pair agrees. It does not write the missing field back into your file.

```text
Bronze   ↔ SDP
Silver   ↔ ADP
Gold     ↔ CDP
Platinum ↔ (no productType)
```

## Migrating existing contracts

To write the missing twin into the files, run [`fluid contract migrate-product-type`](/forge_docs/cli/contract.html#fluid-contract-migrate-product-type). It walks `**/*.fluid.yaml` under a root and fills in the field that is missing:

```bash
fluid contract migrate-product-type --root . --check     # dry-run; non-zero exit if anything is incomplete
fluid contract migrate-product-type --root . --write --yes   # rewrite in place
```

`--write` asks for confirmation, and refuses to run without `--yes` when stdin or stdout is not a terminal (CI). A dry run on a layer-only contract prints:

```text
✏️  .../a.fluid.yaml: would write layer=Gold productType=CDP (was layer=Gold productType=<unset>)
Scanned 1 contract(s) under ...: 1 would be rewritten, 0 already complete, 0 still missing both twins.
❌ 1 contract(s) need migration; re-run with --write to apply or fix metadata by hand.
```

As of 0.18.1, `--write` rewrites the whole file through a YAML round trip, so the diff is larger than the one field:

- comments are dropped (a `# medallion layer` comment on the `layer:` line was gone after the rewrite);
- `fluidVersion: "0.7.5"` becomes `fluidVersion: 0.7.5`;
- inline mappings such as `owner: { team: shop, email: shop@example.com }` are expanded, and list items lose their indentation;
- `productType` is added at the end of `metadata`.

Commit the contracts before you run `--write` and review the diff.

## What lands where

Provider emitters read `metadata.layer` and `metadata.productType` as the file writes them. A layer-only contract produces `fluid_layer` and no `fluid_product_type`. Measured with `fluid generate iac` on 0.18.1, for a `Gold` + `CDP` contract:

| Cloud | Where the values appear |
|---|---|
| AWS | Parameters on the Glue table: `fluid_layer` = `Gold` and `fluid_product_type` = `CDP`. |
| Snowflake | Lines in the table comment: `fluid_layer: Gold` and `fluid_product_type: CDP`. |
| GCP (BigQuery) | Not emitted. The dataset and table labels carry `fluid_contract` and `managed_by`. |

Set both fields in the file, or run the migrator, if a dashboard needs to filter on either vocabulary.

## Other 0.7.3 metadata additions

Two adjacent fields shipped in the same schema bump:

| Field | Type | What it's for |
|---|---|---|
| `metadata.classification` | enum: `public`, `internal`, `confidential`, `restricted` | A data classification label. The schema describes it as propagated to catalog and access-policy enforcement. |
| `metadata.experimental` | string array | Feature gates the contract opts into. |

Neither is required.

## See also

- [Source-Aligned Acquisition](/forge_docs/advanced/source-aligned-acquisition.html) - the acquisition build pattern that powers SDP contracts
- [`consumes[]`](../concepts/builds-exposes-bindings.md#consumes-depending-on-another-product) - how a build reads an upstream product
- [`fluid contract migrate-product-type`](/forge_docs/cli/contract.html#fluid-contract-migrate-product-type) - the migrator command
- [`fluid forge --from-product`](/forge_docs/cli/forge.html) - composition-aware AI scaffolding that applies the type rules
- [Forge Data Model](/forge_docs/forge-data-model.html) - how the data-modelling pipeline emits productType into the generated contract
