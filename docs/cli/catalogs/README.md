# Source Catalog Integration (V1.5)

Forge data products **directly from your existing catalog metadata** —
no re-typing descriptions, tags, lineage, ownership, or sensitivity
classifications you've already invested in. V1.5 turns forge-cli into
a vendor-neutral modeling layer that consumes the seven major catalog
ecosystems and emits one Fluid contract.

```bash
fluid forge data-model from-source \
  --source snowflake \
  --credential-id snowflake-prod \
  --database BIZ_LAB --schema SEEDED \
  --technique data-vault-2 \
  -o biz_lab.fluid.yaml
```

This page is the catalog-by-catalog index. Each linked page is a
self-contained walkthrough: privileges to grant, env-vars to set,
auth methods, end-to-end demo, and error reference.

## Supported catalogs

| Catalog | What it brings | Optional install extra |
|---|---|---|
| [Snowflake Horizon](snowflake.md) | INFORMATION_SCHEMA, OBJECT_TAGS, OBJECT_DEPENDENCIES (lineage), SYSTEM$CLASSIFY (auto-PII), business descriptions, certified/sandbox markers | `pip install "data-product-forge[snowflake]"` |
| [Databricks Unity](unity.md) | Tables / columns / lineage, column tags, column masks, business glossary, certifications | `pip install "data-product-forge[databricks]"` |
| [BigQuery](bigquery.md) | INFORMATION_SCHEMA, table description + labels, partition keys, primary keys | `pip install "data-product-forge[gcp]"` |
| [Dataplex](dataplex.md) | Aspect-types (data-quality scores, freshness SLAs), business glossary, lineage entries | `pip install "data-product-forge[gcp]"` |
| [AWS Glue](glue.md) | Tables / databases / partitions / classifiers + Lake Formation tags | `pip install "data-product-forge[aws]"` |
| [DataHub](datahub.md) | Datasets, schemas, lineage, business glossary, ownership, tags, domains, business attributes | `pip install "data-product-forge[datahub]"` |
| [Data Mesh Manager](datamesh-manager.md) | Registered data products, owner, domain, contracts, lineage, certifications | already in core deps (REST over `httpx`) |

Combined: `pip install "data-product-forge[catalogs]"` installs every
optional dep at once. Default `pip install data-product-forge` ships
with **zero catalog deps** — you opt into only the catalogs you use.

## Two ways to drive a catalog forge

### 1. CLI: `fluid forge data-model from-source`

```bash
fluid forge data-model from-source \
  --source <catalog>               # snowflake, unity, bigquery, dataplex, glue, datahub, datamesh_manager
  --credential-id <name>           # saved name from ~/.fluid/sources.yaml
  --database <db> --schema <sch> \
  --tables orders customers \
  --technique data-vault-2 | dimensional \
  -o contract.fluid.yaml
```

Non-interactive; reproducible; works in CI. The `--source` value
selects the catalog adapter; `--credential-id` points at a row in
`~/.fluid/sources.yaml` configured via `fluid ai setup --source CATALOG --name NAME`.

### 2. MCP: `forge_from_source`

```jsonc
// .mcp.json (Claude Code, Cursor, any MCP client)
{
  "fluid": {
    "command": "fluid",
    "args": ["mcp", "serve"],
    "env": { "SNOWFLAKE_PRIVATE_KEY_PATH": "/path/to/key.p8" }
  }
}
```

Then tell the agent:

> Forge a data-vault-2 model from my Snowflake `BIZ_LAB.SEEDED`
> schema. Use the `snowflake` adapter with credential id
> `snowflake-prod`. Save the contract to `biz_lab.fluid.yaml`.

The agent calls the MCP `forge_from_source` tool; same pipeline,
same output.

## Setup wizard: `fluid ai setup --source CATALOG --name NAME`

For first-time setup of a new source:

```bash
fluid ai setup --source snowflake --name snowflake-prod
# ? Account: myorg-abc12345
# ? Auth method:                 # ★ marks recommended path
#   ★ key_pair (recommended)     # — most secure, no password
#     password
#     externalbrowser (SSO)
# ? Private key path: /Users/me/.ssh/snowflake_key.p8
# ? Default warehouse: COMPUTE_WH
# ? Default role: ANALYST
# ✓ Saved to ~/.fluid/sources.yaml
```

This writes a single row to `~/.fluid/sources.yaml`. Secrets land in
the OS keyring (macOS Keychain / Windows Credential Manager / Linux
secret-service); only non-sensitive fields land on disk.

## Three guarantees that hold across every catalog

1. **Read-only.** Adapters request `INFORMATION_SCHEMA`-equivalent
   privileges only. **No `SELECT *` against any data table** — only
   metadata.
2. **No data values fetched.** Tag values, descriptions, classifications,
   schema — never row data. Defends against an upstream agent
   escalating "list tables" into "dump customer PII."
3. **Audited.** Every catalog tool call writes an audit event via
   `~/.fluid/store/audit/`. Credentials are scrubbed before write.
   Use `fluid memory show audit` to query.

## Auto-detection: `fluid ai status` lists what you have

```bash
fluid ai status
# Configured sources:
#   snowflake-prod  (snowflake / key_pair, ANALYST role)
#   unity-staging   (databricks / pat)
#   datahub-corp    (datahub / pat)
```

When you run `fluid forge` without `--source`, AI mode's interview
auto-suggests the configured source — same UX as `fluid ai setup`
auto-discovering provider env vars.

## Error model

Every catalog adapter raises one of three typed exceptions, each
carrying a `suggestions: list[str]` field with the next-action:

| Exception | When | Example suggestion |
|---|---|---|
| `CatalogConfigError` | Missing dep, wrong shape, missing required field | `pip install "data-product-forge[snowflake]"` |
| `CatalogConnectionError` | Network / hostname / not-found | `Verify SNOWFLAKE_ACCOUNT="myorg-abc12345" matches the URL in the Snowsight UI.` |
| `CatalogPermissionError` | Missing privilege / wrong role | `GRANT USAGE ON SCHEMA BIZ_LAB.SEEDED TO ROLE ANALYST;` |

The next-action is in the message — not buried in the docs.

## See also

- [Forge data-model overview](../../forge-data-model.md)
- [MCP server walkthrough](../../advanced/mcp.md)
- [Add your own catalog adapter](../../contributing.md#adding-a-catalog-adapter)
