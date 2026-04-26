# Snowflake Horizon Catalog

Source-side catalog adapter for **Snowflake Horizon**. Reads
`INFORMATION_SCHEMA`, `OBJECT_TAGS` (governance), `OBJECT_DEPENDENCIES`
(lineage), `SYSTEM$CLASSIFY` (auto-PII classification), and the
business descriptions / certified-vs-sandbox markers Horizon sets
on every object.

> **Recommended for:** any Snowflake-first team. Horizon's metadata
> is among the richest available in any commercial warehouse —
> forge-cli reads all of it and turns it into Logical model + Fluid
> contract + dbt transformation.

## Install

```bash
pip install "data-product-forge[snowflake]"
```

Adds the `snowflake-connector-python` runtime dep. Default install
ships without it; the adapter raises `CatalogConfigError` with the
exact `pip install` command if you call it without the extra.

## Privileges to grant

The adapter is **read-only on metadata** — never reads data values.
Required privileges depend on what you want forge-cli to see.

### Minimum (list + introspect tables)

```sql
-- Run as a role that can grant on the database / schema.
GRANT USAGE ON DATABASE BIZ_LAB TO ROLE ANALYST;
GRANT USAGE ON SCHEMA BIZ_LAB.SEEDED TO ROLE ANALYST;
GRANT REFERENCES ON ALL TABLES IN SCHEMA BIZ_LAB.SEEDED TO ROLE ANALYST;
GRANT REFERENCES ON FUTURE TABLES IN SCHEMA BIZ_LAB.SEEDED TO ROLE ANALYST;
```

### Full (also reads tags + lineage + sensitivity)

```sql
-- Tag reads — Horizon governance signal.
GRANT APPLY TAG ON ACCOUNT TO ROLE ANALYST;
-- (or, for a tighter scope: SHARE the relevant tag references)

-- Lineage reads from ACCOUNT_USAGE (24h-lagged).
GRANT IMPORTED PRIVILEGES ON DATABASE SNOWFLAKE TO ROLE ANALYST;

-- SYSTEM$CLASSIFY usage.
GRANT EXECUTE TASK ON ACCOUNT TO ROLE ANALYST;  -- if running classification on demand
```

If you skip the "full" block, the adapter soft-fails on those reads
(empty tags / empty lineage / no sensitivity) — you still get a
working forge from `INFORMATION_SCHEMA` alone.

## Authentication methods

| Method | When to use | Setup |
|---|---|---|
| **`key_pair`** ★ | Default for production. Most secure — no password. | Generate an RSA key pair with `openssl genrsa -out key.p8 2048`; upload public to Snowflake user; point adapter at `key.p8`. |
| `password` | Quickstart / local dev | Set `SNOWFLAKE_PASSWORD` env var or store in OS keyring. |
| `externalbrowser` | SSO / Okta / Azure AD | Adapter pops a browser window for SAML; Snowflake handles the rest. |
| `oauth` | Federated identities | OAuth bearer token (short-lived, refreshed externally). |

★ `key_pair` is the recommended path. The setup wizard pre-fills it.

## Setup

```bash
fluid ai setup --source snowflake --name snowflake-prod
# ? Catalog: snowflake
# ? Account: myorg-abc12345        (the part before .snowflakecomputing.com)
# ? Username: analyst@example.com
# ? Auth method:
#   ★ key_pair (recommended)
#     password
#     externalbrowser
#     oauth
# ? Private key path: /Users/me/.ssh/snowflake_key.p8
# ? Private key passphrase: ******     (optional; stored in keyring if set)
# ? Default warehouse: COMPUTE_WH
# ? Default role: ANALYST
# ? Default database: BIZ_LAB
# ? Default schema:   SEEDED
# ✓ Saved to ~/.fluid/sources.yaml (secrets in OS keyring)
```

Or set env vars directly:

```bash
export SNOWFLAKE_ACCOUNT=myorg-abc12345
export SNOWFLAKE_USER=analyst@example.com
export SNOWFLAKE_PRIVATE_KEY_PATH=/Users/me/.ssh/snowflake_key.p8
export SNOWFLAKE_WAREHOUSE=COMPUTE_WH
export SNOWFLAKE_ROLE=ANALYST
```

## End-to-end demo

```bash
# 1. Configure once.
fluid ai setup --source snowflake --name snowflake-prod

# 2. Forge a Data Vault 2.0 model from a schema.
fluid forge data-model from-source \
  --source snowflake \
  --credential-id snowflake-prod \
  --database BIZ_LAB --schema SEEDED \
  --technique data-vault-2 \
  -o biz_lab.fluid.yaml

# Output:
#   biz_lab.fluid.yaml             — Fluid 0.7.2 contract
#   biz_lab.fluid.yaml.model.json  — Logical IR sidecar (DV2 hubs/links/sats)
#   biz_lab.semantics.osi.yaml     — OSI v0.1.1 standalone

# 3. Generate dbt transformations from the same contract.
fluid generate transformation biz_lab.fluid.yaml -o ./dbt_biz_lab --dbt-validate
```

You'll see a cost summary at the end of step 2 with token usage
per stage. If catalog reads are slow, the adapter logs each query
at `--verbose`.

## What lands where

| Snowflake source | Forge output |
|---|---|
| Table `COMMENT` | `OSIDataset.fields[].expression.description` |
| Column `COMMENT` | `OSIDataset.fields[].expression.description` |
| Primary key | `OSIDataset.primary_key[]` |
| Foreign key | `OSIRelationship[]` (deterministic, not LLM-inferred) |
| `OBJECT_TAGS.domain` | `metadata.domain` (Fluid contract) + industry hint |
| `OBJECT_TAGS.owner_team` | `metadata.owner.team` (system roles like ACCOUNTADMIN excluded) |
| `OBJECT_TAGS.sensitivity` | `agentPolicy.sensitiveData[]` + dbt `meta:` |
| `OBJECT_DEPENDENCIES` | `metadata.lineage.upstream[]` + DV2 link inference (V1.5 Sprint E) |
| `SYSTEM$CLASSIFY` results | OSI `custom_extensions[]` for downstream policy enforcement |

## System roles never become owners

Snowflake's `ACCOUNTADMIN` / `SYSADMIN` / `SECURITYADMIN` /
`USERADMIN` / `ORGADMIN` / `PUBLIC` roles are **NOT promoted** to
`metadata.owner.team`. They land in `labels.catalogCreatingRoles`
(audit signal only) so the contract's owner field reflects the
business team, not the role that ran the DDL.

## Common errors

### `CatalogConfigError: snowflake-connector-python missing`
Run `pip install "data-product-forge[snowflake]"`.

### `CatalogPermissionError: USAGE on schema BIZ_LAB.SEEDED required`
The adapter's suggestion list contains the exact GRANT command:
```sql
GRANT USAGE ON SCHEMA BIZ_LAB.SEEDED TO ROLE ANALYST;
```

### `CatalogConnectionError: 250001 (08001): Failed to connect`
Check `SNOWFLAKE_ACCOUNT` matches the part before
`.snowflakecomputing.com` in the Snowsight URL — not the full host,
and not just the org name.

### Lineage / tags come back empty
Likely missing `IMPORTED PRIVILEGES ON DATABASE SNOWFLAKE` for the
ACCOUNT_USAGE share. The adapter soft-fails on these reads (forge
still works) — granting the privilege upgrades subsequent runs.

## See also

- [Catalog index](README.md)
- [`fluid forge data-model from-source`](../forge.md)
- [Snowflake provider page](../../providers/snowflake.md) — for the
  publish-target side (write contracts back to Snowflake).
