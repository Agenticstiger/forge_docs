# Databricks Unity Catalog

Source-side catalog adapter for **Databricks Unity Catalog**. Reads
tables, columns, lineage, column tags, column masks, business
glossary terms, and certifications.

> **Recommended for:** Databricks-native teams already using Unity
> for governance. Forge-cli reads Unity's metadata-as-truth and
> emits a Fluid contract that respects every column mask, sensitive
> tag, and certification mark.

## Install

```bash
pip install "data-product-forge[databricks]"
```

Adds the `databricks-sdk` runtime dep. Default install ships
without it; the adapter raises `CatalogConfigError` with the
install command if called without the extra.

## Privileges to grant

The adapter is **read-only on metadata** — never reads data values.

```sql
-- Run as a Unity Metastore Admin or workspace admin.
GRANT USE CATALOG       ON CATALOG main         TO `analyst@example.com`;
GRANT USE SCHEMA        ON SCHEMA main.biz_lab  TO `analyst@example.com`;
GRANT BROWSE            ON CATALOG main         TO `analyst@example.com`;
GRANT SELECT            ON SCHEMA main.biz_lab  TO `analyst@example.com`;
-- (SELECT is required for the system tables that back Unity's
-- INFORMATION_SCHEMA-equivalent views; the adapter doesn't issue
-- SELECT on user data tables.)
```

For lineage:
```sql
-- The adapter reads system.access.table_lineage / column_lineage.
GRANT USE CATALOG ON CATALOG system           TO `analyst@example.com`;
GRANT USE SCHEMA  ON SCHEMA   system.access   TO `analyst@example.com`;
GRANT SELECT      ON TABLE    system.access.table_lineage  TO `analyst@example.com`;
GRANT SELECT      ON TABLE    system.access.column_lineage TO `analyst@example.com`;
```

If lineage privileges are missing, the adapter soft-fails on
lineage reads (forge still works; downstream DV2 link inference
falls back to FK constraints only).

## Authentication methods

| Method | When to use | Setup |
|---|---|---|
| **`pat`** ★ | Default for CLI use | Generate a personal access token from the workspace UI. |
| `oauth_m2m` | Service-principal in CI | Service principal client ID + secret. |
| `oauth_user` | SSO with browser | OAuth user-to-machine; pops a browser. |
| `azure_cli` | Azure-Databricks via Azure AD | Inherits the local `az login` token. |
| `aws_iam` | Databricks-on-AWS via IAM | Inherits the local IAM identity. |

★ `pat` is the recommended path for local CLI use. CI / production
should prefer `oauth_m2m` with a service principal.

## Setup

```bash
fluid ai setup --source unity --name unity-prod
# ? Catalog: databricks
# ? Workspace host: https://dbc-12345.cloud.databricks.com
# ? Auth method:
#   ★ pat (recommended for local)
#     oauth_m2m
#     oauth_user
#     azure_cli
#     aws_iam
# ? Token: ******                    (stored in OS keyring)
# ? Default catalog: main
# ? Default schema:  biz_lab
# ✓ Saved to ~/.fluid/sources.yaml
```

Or set env vars:

```bash
export DATABRICKS_HOST=https://dbc-12345.cloud.databricks.com
export DATABRICKS_TOKEN=dapi...                # for pat auth
export DATABRICKS_CLIENT_ID=...                # for oauth_m2m
export DATABRICKS_CLIENT_SECRET=...
```

## End-to-end demo

```bash
# 1. Configure once.
fluid ai setup --source unity --name unity-prod

# 2. Forge a Dimensional model from a Unity schema.
fluid forge data-model from-source \
  --source unity \
  --credential-id unity-prod \
  --database main --schema biz_lab \
  --technique dimensional \
  -o biz_lab.fluid.yaml

# 3. Generate dbt transformations.
fluid generate transformation biz_lab.fluid.yaml -o ./dbt_biz_lab --dbt-validate
```

## What lands where

| Unity source | Forge output |
|---|---|
| Table `comment` | `OSIDataset.fields[].expression.description` |
| Column `comment` | `OSIDataset.fields[].expression.description` |
| Primary key constraint | `OSIDataset.primary_key[]` |
| Foreign key constraint | `OSIRelationship[]` (deterministic) |
| Column tag `domain` | `metadata.domain` + industry hint |
| Column tag `pii` / `phi` / `pci` | `agentPolicy.sensitiveData[]` |
| **Column mask** | Recorded as `masked: true` in metadata; modeler does NOT invent the masked value's content; mask declaration carried forward to dbt `meta:` |
| `system.access.table_lineage` | `metadata.lineage.upstream[]` |
| Certification (Unity Marketplace) | `metadata.certification` |

## Column masks are honored, not bypassed

If Unity has a column mask on `email`, the adapter records the mask
declaration in metadata; the modeler does NOT try to invent the
masked column's content (it can't — the adapter never reads data
values). The Fluid contract carries the mask declaration so
downstream tools (dbt Cloud, Databricks SQL warehouses) enforce.

## Common errors

### `CatalogConfigError: databricks-sdk missing`
Run `pip install "data-product-forge[databricks]"`.

### `CatalogPermissionError: USE SCHEMA on main.biz_lab required`
Suggestion list contains:
```sql
GRANT USE SCHEMA ON SCHEMA main.biz_lab TO `analyst@example.com`;
```

### `CatalogConnectionError: 401 Unauthorized`
PAT expired or revoked. Generate a new one in the workspace UI
(User Settings → Access tokens) and rerun `fluid ai setup --source`.

### Lineage tab empty in the forged contract
Likely missing `SELECT ON system.access.table_lineage`. Adapter
soft-fails; forge still works. Granting upgrades subsequent runs.

## See also

- [Catalog index](README.md)
- [`fluid forge data-model from-source`](../forge.md)
