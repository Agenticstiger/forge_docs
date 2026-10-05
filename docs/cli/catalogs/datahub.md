# DataHub Catalog

Source-side catalog adapter for **DataHub** (Acryl Data / open-source
DataHub). Reads datasets, schemas, lineage, business glossary,
ownership, tags, domains, and business attributes via the
DataHubGraph client.

> **Recommended for:** open-source-first teams running their own
> DataHub instance, or Acryl Cloud customers. DataHub is the most
> portable governance layer (works across Snowflake, Databricks,
> BigQuery, Redshift, Postgres, Kafka, dbt) — and forge-cli reads
> all of it through one adapter.

## Install

```bash
pip install "data-product-forge[datahub]"
```

Adds `acryl-datahub`. Default install ships without it.

## Privileges to grant

The adapter is **read-only on metadata**. DataHub's permission
model is policy-based:

1. Open the DataHub UI as an admin → Permissions → Policies.
2. Create or assign a policy that grants the user/group:
   - **`View Entity Page`** on every dataset/glossary you want
     forge-cli to see.
   - **`View Dataset Profile`** (optional — needed if you want
     statistical metadata, not yet consumed by V1.5).
   - **`View Lineage`** (recommended — without it, lineage reads
     return empty and DV2 link inference falls back to FK only).

The pre-built **`Reader`** role policy is the simplest fit — assign
to the `forge-cli` user/group.

## Authentication methods

| Method | When to use | Setup |
|---|---|---|
| **`pat`** ★ | Default for production / CI | Personal Access Token from the DataHub UI (Profile → Generate token). |
| `none` | Self-hosted dev DataHub | No auth — for sandbox instances only. The adapter logs a warning at construction time so production users don't accidentally pick this. |

★ `pat` is the recommended path. The wizard pre-fills it.

## Setup

```bash
fluid ai setup --source datahub --name datahub-corp
# ? Catalog: datahub
# ? Server URL: https://datahub.corp.example.com
# ? Auth method:
#   ★ pat (recommended)
#     none (sandbox only)
# ? Token: ******                    (stored in OS keyring)
# ✓ Saved to ~/.fluid/sources.yaml
```

Or env vars:

```bash
export DATAHUB_SERVER=https://datahub.corp.example.com
export DATAHUB_TOKEN=eyJhbGc...     # PAT from the DataHub UI
```

## End-to-end demo

```bash
fluid ai setup --source datahub --name datahub-corp

# Forge from a DataHub container scope (database.schema syntax).
fluid forge data-model from-source \
  --source datahub \
  --credential-id datahub-corp \
  --database snowflake_db \
  --schema  analytics \
  --technique data-vault-2 \
  -o analytics.fluid.yaml

# Or pass DataHub URNs directly:
fluid forge data-model from-source \
  --source datahub \
  --credential-id datahub-corp \
  --tables 'urn:li:dataset:(urn:li:dataPlatform:snowflake,db.schema.orders,PROD)' \
           'urn:li:dataset:(urn:li:dataPlatform:snowflake,db.schema.customers,PROD)' \
  -o orders.fluid.yaml
```

## URN normalisation: type the short form

Operators don't have to type DataHub's verbose URNs. The adapter
accepts three forms and normalises:

| You type | Adapter expands to |
|---|---|
| `urn:li:dataset:(urn:li:dataPlatform:snowflake,db.schema.orders,PROD)` | unchanged (full URN) |
| `snowflake.db.orders` | `urn:li:dataset:(urn:li:dataPlatform:snowflake,db.orders,PROD)` |
| `db.schema.orders` (no platform prefix) | rejected — needs platform; use `--platform snowflake` to default |

The normalisation is a pure function: see
`DataHubCatalogAdapter._normalise_urn` for the exact mapping.

## What lands where

| DataHub source | Forge output |
|---|---|
| Dataset description | `OSIDataset.fields[].expression.description` |
| Schema column descriptions | `OSIDataset.fields[].expression.description` |
| Primary key constraint | `OSIDataset.primary_key[]` |
| Upstream / downstream lineage | `metadata.lineage.upstream[]` + DV2 link inference |
| Business glossary terms | `OSI.ai_context.synonyms` + `examples` |
| Ownership (technical / business) | `metadata.owner.team` (technical) + `metadata.steward` (business) |
| Tags | `metadata.labels.tags[]` |
| Domains | `metadata.domain` + industry hint |
| Business attributes | `OSIDataset.fields[].expression.description` (appended) |

## Common errors

### `CatalogConfigError: acryl-datahub missing`
Run `pip install "data-product-forge[datahub]"`.

### `CatalogPermissionError: 401 Unauthorized: token invalid`
Suggestion list:
- Generate a new PAT from the DataHub UI (Profile → Generate token).
- Verify the policy assigned to your user includes
  `View Entity Page` for the datasets you want to forge.

### `CatalogConnectionError: 404 Not Found`
Verify the DataHub server URL is reachable AND the path you pass
(database / schema / URN) actually exists in DataHub. The adapter
distinguishes 401 (permission) from 404 (not found) so you don't
go hunting for IAM grants when the issue is a typo'd URN.

### `none` auth warning at startup
You picked the `none` auth method. The adapter logs a warning so
production users don't ship to prod with no auth. Switch to `pat`
for any non-sandbox deployment.

### Lineage tab empty in the forged contract
Likely missing the `View Lineage` policy. DV2 link inference falls
back to FK constraints only — forge still works.

## Publishing to DataHub

The page above covers the **source-side** read adapter (`fluid forge data-model from-source --source datahub`). `v0.8.3` added a **publish-side** DataHub registrar — contracts can register themselves with DataHub at apply / publish time so that the catalog reflects the data product alongside the underlying datasets.

### Opt in

Add `datahub` to the contract's catalog register list:

```yaml
# contract.fluid.yaml
properties:
  catalog:
    register: [datahub]
```

### Environment variables

| Variable | Purpose |
|---|---|
| `FLUID_CATALOG_DATAHUB_URL` | DataHub GMS endpoint (e.g. `https://datahub.corp.example.com/api/gms`). Falls back to `DATAHUB_GMS_URL`, `DATAHUB_GMS_HOST`, then `DATAHUB_SERVER`. |
| `FLUID_CATALOG_DATAHUB_TOKEN` | DataHub PAT used for the publish path. Falls back to `DATAHUB_GMS_TOKEN`, then `DATAHUB_TOKEN`. |
| `FLUID_CATALOG_DATAHUB_SPEC_BASE_URL` | Optional base URL for the contract and ODPS spec files. When set, the registrar links to `<base>/<product-id>/contract.fluid.yaml` and `spec.odps.yaml` instead of inlining them. See [What gets emitted](#what-gets-emitted). |

With no endpoint set, the registrar is not configured: it does not fall back to a default host.

The publish requests go through the CLI's guarded HTTP client, which does not follow redirects. For DataHub it allows private addresses, so a DataHub instance on an internal network is reachable. See [network safety](/forge_docs/advanced/network-safety.html).

### What gets emitted

| Contract field | DataHub entity |
|---|---|
| Data product | `DataProduct` (canonical MCP) |
| Output ports (datasets) | `Dataset` per port with full schema, ownership, tags, descriptions |
| Per-port contract | `DataContract` linked to the `Dataset` |
| `metadata.domain` | `Domain` (created if absent) |
| `metadata.layer` / `metadata.productType` | Structured properties `fluid.layer` and `fluid.productType`, when the server supports structured properties. Otherwise only the `customProperties` below carry them. |
| Quality assertions | `Assertion` MCPs linked to the parent dataset |

The registrar also writes `customProperties`, which carry the FLUID classification, and the spec documents themselves:

| Key | On | Value |
|---|---|---|
| `fluid_layer`, `fluid_product_type`, `fluid_domain`, `fluid_version` | Each `Dataset` and the `DataProduct` | The contract's layer, product type, domain and version, each present only when the contract declares it. |
| `odcs_contract` | Each `Dataset` | The per-port ODCS YAML. Present only when no spec base URL is configured. |
| `fluid_contract`, `odps_spec` | The `DataProduct` | The FLUID contract YAML and the ODPS spec. Present only when no spec base URL is configured. |

The rule is to inline a document only when it would otherwise be unreadable. With `FLUID_CATALOG_DATAHUB_SPEC_BASE_URL` set, the documents are linked and left out of `customProperties`. With it unset, which is the default, they are inlined, so entity payloads are larger. `DataContract.rawContract` is not part of the open-source DataHub GraphQL schema, which is why the contract is not left to that entity alone.

::: tip Renamed in 0.15.0
The `customProperties` keys were `fluid.layer`, `fluid.productType` and `fluid.version` before 0.15.0, and `fluid_domain` is new. A saved search, dashboard or ingestion rule keyed on the dotted names needs updating. The structured properties keep their dotted `qualifiedName`: that is a different namespace.
:::

The registrar writes are idempotent: re-publishing the same contract is a no-op against DataHub.

### Publish to DataHub

```bash
export FLUID_CATALOG_DATAHUB_URL=https://datahub.local:8080/api/gms
export FLUID_CATALOG_DATAHUB_TOKEN=$(cat ~/.datahub-pat)
fluid publish contract.fluid.yaml --target datahub
```

A contract with `properties.catalog.register: [datahub]` also registers at apply time. If the registrar can't reach DataHub there, the publish step logs a warning and the apply continues.

## See also

- [Catalog overview](./overview.md) — the unified publish-side flow
- [Catalog index](README.md) — source-side catalog reading
- [DataHub upstream docs](https://datahubproject.io/docs/) — for
  installing / configuring DataHub itself.
