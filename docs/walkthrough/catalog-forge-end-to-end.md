# End-to-End Walkthrough: Catalog → Contract → Transformation

Five-minute walkthrough taking you from "I have a Snowflake schema"
to "I have a working dbt project + Fluid contract" — using nothing
but `fluid` commands.

> The same flow works for every supported catalog. Pick your
> catalog from the [catalogs index](../cli/catalogs/README.md) for
> the catalog-specific privilege grant, env-var setup, and auth
> options. The walkthrough below uses Snowflake.

## Prerequisites

- Python 3.10+
- A Snowflake account with `INFORMATION_SCHEMA` read access on at
  least one schema
- An LLM API key (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`,
  `GEMINI_API_KEY`, or a local `ollama` runtime)

## Install

```bash
pip install "data-product-forge[snowflake]"
# Or if you want every catalog at once:
# pip install "data-product-forge[catalogs]"
```

## Step 1 — Configure your LLM provider (one-time)

```bash
fluid ai setup
# ? Which LLM provider? anthropic
# ? API key? sk-ant-...
# ? Default model? claude-sonnet-4-6
# ✓ Saved to ~/.fluid/ai_config.json
```

You only do this once per machine. The config is reused by every
`fluid forge` and `fluid generate` invocation.

## Step 2 — Configure your source catalog (one-time per source)

```bash
fluid ai setup --source snowflake --name snowflake-prod
# ? Catalog: snowflake
# ? Account: myorg-abc12345
# ? Auth method:
#   ★ key_pair (recommended)
#     password
#     externalbrowser
#     oauth
# ? Private key path: /Users/me/.ssh/snowflake_key.p8
# ? Default warehouse: COMPUTE_WH
# ? Default role: ANALYST
# ✓ Saved to ~/.fluid/sources.yaml (secrets in OS keyring)
```

`fluid ai status` confirms what's configured:

```
$ fluid ai status

LLM provider: anthropic / claude-sonnet-4-6
  - API key:           ✓ in OS keyring

Configured sources:
  - snowflake-prod     (snowflake / key_pair, ANALYST role)
```

## Step 3 — Forge the data model

```bash
fluid forge data-model from-source \
  --source snowflake \
  --credential-id snowflake-prod \
  --database BIZ_LAB --schema SEEDED \
  --technique data-vault-2 \
  -o biz_lab.fluid.yaml
```

What happens:

```
[CatalogConnect]   snowflake-prod (key_pair / ANALYST role)        0.4s
[CatalogList]      24 tables in BIZ_LAB.SEEDED                     2.1s
[CatalogInspect]   24 tables × (columns + tags + lineage)         11.7s
[IndustryDetect]   matched 'telco' from domain tags (18/24 tables)
[Logical]          24 tables → 23 hubs / 33 links / 23 satellites 19.4s
[Builder]          → biz_lab.fluid.yaml                            8.2s
[Transformation]   23 dbt models                                  18.5s
[Validator]        ✓ schema clean, no warnings                     0.6s

Cost summary
─────────────────────────────────────────────────────────────────
  anthropic / claude-sonnet-4-6   45,221 in  12,489 out  $0.3230
  anthropic / claude-haiku-4-5     2,891 in     876 out  $0.0073
─────────────────────────────────────────────────────────────────
  total                           48,112 in  13,365 out  $0.3303

✓ Forged to:
  biz_lab.fluid.yaml             — Fluid 0.7.2 contract
  biz_lab.fluid.yaml.model.json  — Logical IR sidecar (DV2)
  biz_lab.semantics.osi.yaml     — OSI v0.1.1 standalone
```

## Step 4 — Inspect the forged contract

```bash
# Pretty-print the contract.
cat biz_lab.fluid.yaml | head -50

# Or open the canvas — visual entity-relationship view.
fluid viz-graph biz_lab.fluid.yaml
```

The contract carries every signal the catalog provided:

```yaml
# biz_lab.fluid.yaml (excerpt)
metadata:
  name: biz_lab
  domain: telco                       # auto-detected from catalog tags
  owner:
    team: data-eng                    # from OBJECT_TAGS.owner_team
                                      # (system roles like ACCOUNTADMIN excluded)
  steward: alice@example.com
  certification: certified            # from Snowflake Horizon
  lineage:
    upstream:
      - urn: snowflake://BIZ_LAB.RAW.ORDERS
        relationship: imports

agentPolicy:
  sensitiveData:
    - column: customer_email
      classification: PII             # from SYSTEM$CLASSIFY
    - column: payment_card_number
      classification: PCI

dataQuality:
  slas:
    - column: order_date
      freshness: 24h                  # from Dataplex/Unity if present
      quality_rules:
        - not_null
        - unique
```

## Step 5 — Generate dbt transformations

```bash
fluid generate transformation biz_lab.fluid.yaml -o ./dbt_biz_lab --dbt-validate
```

You now have a working dbt project that:

- Builds 23 hub/link/satellite models in topological order.
- Honors partition keys from the catalog (dbt `partition_by`).
- Wraps every PII column in dbt `meta:` tags.
- Has dbt `tests:` for `not_null` / `unique` / `accepted_values`
  derived from catalog quality rules.
- Uses `ref()` / `source()` references that match the lineage
  chain from the catalog.

Run the dbt project:

```bash
cd dbt_biz_lab
dbt run
dbt test
```

## Step 6 — Iterate

If the modeled output isn't quite right, you have three options:

### Option 1: Re-forge with different scope or technique

```bash
# Try Dimensional instead of Data Vault 2.0:
fluid forge data-model from-source \
  --source snowflake \
  --credential-id snowflake-prod \
  --database BIZ_LAB --schema SEEDED \
  --technique dimensional \
  -o biz_lab.fluid.yaml
```

### Option 2: Review the Logical sidecar, regenerate downstream artifacts

```bash
# Edit biz_lab.fluid.yaml.model.json directly.
$EDITOR biz_lab.fluid.yaml.model.json

# Regenerate the dbt project from the contract's labels.modelSidecar.
fluid generate transformation biz_lab.fluid.yaml -o ./dbt_biz_lab --overwrite --dbt-validate
```

### Option 3: Drive interactive refinements via Claude Code / Cursor

Configure your IDE's MCP client (see [MCP walkthrough](../advanced/mcp.md)),
then:

> Read `biz_lab.fluid.yaml.model.json` and add a Satellite to
> `hub_customer` for `loyalty_status` (SCD2). Regenerate the contract.

The agent calls `read_logical_model` → `update_entity` →
`regenerate_physical` over the wire, then writes back to disk.

## What's deterministic

- Same catalog state + same intent/model input + same model + same
  `capability_matrix` → byte-identical contract on re-run (cache hit).
- `--deterministic` flag forces temp=0, seed=42 (where supported),
  cache off — emits a proof-of-determinism receipt.

## What's audited

Every catalog read writes an audit event under
`~/.fluid/store/audit/`. Query with:

```bash
fluid memory show audit --filter catalog
fluid memory show audit --window 24h --filter forge_from_source
```

Credentials are NEVER in the audit. Only metadata about the call
(catalog name, scope, table count, duration).

## What's the cost ceiling

Set a per-run cost ceiling in `~/.fluid/ai_config.json`:

```jsonc
{
  "cost_limit_usd_per_run": 5.00
}
```

The forge stops mid-pipeline if the running total exceeds the
ceiling, prints the partial cost summary, and exits non-zero.

## Errors you might see (and what to do)

| Error | What to do |
|---|---|
| `CatalogConfigError: snowflake-connector-python missing` | `pip install "data-product-forge[snowflake]"` |
| `CatalogPermissionError: USAGE on schema BIZ_LAB.SEEDED required` | Run the GRANT command in the suggestion list |
| `CatalogConnectionError: Failed to connect` | Verify `SNOWFLAKE_ACCOUNT` matches the URL in Snowsight |
| `CredentialNotFoundError: No credentials configured` | `fluid ai setup --source snowflake --name snowflake-prod` |
| `1 call had no usage data; cost may be under-reported` | Provider ate the usage block; cost figure is partial |

Each catalog page documents the catalog-specific errors. See the
[catalogs index](../cli/catalogs/README.md).

## Next steps

- [Add your own catalog adapter](../contributing.md#add-a-catalog-adapter)
- [V1.5 architecture deep-dive](../advanced/v1.5-architecture.md)
- [MCP server walkthrough](../advanced/mcp.md)
- [Cost tracking details](../advanced/cost-tracking.md)
