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

## See also

- [Catalog index](README.md)
- [DataHub upstream docs](https://datahubproject.io/docs/) — for
  installing / configuring DataHub itself.
