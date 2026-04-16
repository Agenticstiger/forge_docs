# Snowflake Provider

Deploy data products to Snowflake Data Cloud — databases, schemas, tables, RBAC grants — using the same contract and CLI commands as every other provider.

**Status:** ✅ Production  
**Docs Baseline:** CLI `0.7.9`  
**Tested Services:** Databases, Schemas, Tables, Warehouses, RBAC Grants

::: warning Compatibility note
This page preserves some older `0.7.1` examples for backward-compatibility context. Current scaffolds emit `fluidVersion: 0.7.2`, and new orchestration examples should prefer `fluid generate schedule --scheduler airflow`.
:::

---

## Overview

The Snowflake provider turns a FLUID contract into real Snowflake infrastructure:

- ✅ **Plan & Apply** — Databases, schemas, tables, warehouses
- ✅ **RBAC Compilation** — `fluid policy-compile` generates Snowflake `GRANT` statements from `accessPolicy`
- ✅ **Sovereignty Validation** — Region constraints enforced before deployment
- ✅ **Orchestration Generation** — prefer `fluid generate schedule --scheduler airflow` for current docs
- ✅ **Governance** — Classification, column masking, row-level security, audit labels
- ✅ **Universal Pipeline** — Same Jenkinsfile as GCP and AWS — zero provider logic

## Choose Your Starting Path

Use Snowflake in one of these two modes:

- **Enterprise recommended path:** dbt-snowflake plus explicit environment-specific warehouse, database, schema, and role settings. Start with the [`billing_history` example](https://github.com/Agenticstiger/forge-cli/tree/main/examples/snowflake/billing_history) and the [Snowflake quickstart](/getting-started/snowflake).
- **Minimal starter path:** native SQL with the [`smoke` example](https://github.com/Agenticstiger/forge-cli/tree/main/examples/snowflake/smoke) when you want the smallest contract that still proves `auth`, `validate`, `plan`, `apply`, and `verify`.

For production teams, make these explicit per environment:

- `SNOWFLAKE_ACCOUNT`
- `SNOWFLAKE_USER`
- `SNOWFLAKE_WAREHOUSE`
- `SNOWFLAKE_DATABASE`
- `SNOWFLAKE_SCHEMA`
- `SNOWFLAKE_ROLE`

For production and CI, use this authentication order:

1. `SNOWFLAKE_PRIVATE_KEY_PATH` for key-pair auth
2. `SNOWFLAKE_OAUTH_TOKEN` for federated automation
3. `SNOWFLAKE_AUTHENTICATOR` for interactive SSO

Password auth is still supported, but it should be treated as a fallback rather than the default production path.

If no explicit credentials are present, browser SSO is only attempted in an interactive TTY session. Non-interactive runs should supply key-pair, OAuth, or another explicit authenticator instead of relying on browser prompts.

## Working Example: Bitcoin Price Tracker

This is a production-tested example that runs end-to-end in Jenkins CI.

### Contract

```yaml
fluidVersion: "0.7.1"
kind: DataProduct
id: crypto.bitcoin_prices_snowflake_governed
name: Bitcoin Price Index (FLUID 0.7.1 + Snowflake + Governance)
description: >
  Real-time Bitcoin price data with comprehensive governance policies
  on Snowflake Data Cloud
domain: finance

tags:
  - cryptocurrency
  - real-time
  - governed
  - gdpr-compliant
  - snowflake

labels:
  cost_center: "CC-1234"
  business_criticality: "high"
  compliance_gdpr: "true"
  compliance_soc2: "true"
  platform: "snowflake"

metadata:
  layer: Gold
  owner:
    team: data-engineering
    email: data-engineering@company.com

# ── Data Sovereignty ──────────────────────────────────────────
sovereignty:
  jurisdiction: "EU"
  dataResidency: true
  allowedRegions:
    - eu-west-1          # Snowflake AWS Europe (Ireland)
    - eu-central-1       # Snowflake AWS Europe (Frankfurt)
    - europe-west4       # Snowflake GCP Europe (Netherlands)
  deniedRegions:
    - us-east-1
    - us-west-2
    - us-central1
  crossBorderTransfer: false
  transferMechanisms:
    - SCCs
  regulatoryFramework:
    - GDPR
    - SOC2
  enforcementMode: advisory
  validationRequired: true

# ── Access Policy: Snowflake RBAC ─────────────────────────────
accessPolicy:
  grants:
    - principal: "role:DATA_ANALYST"
      permissions: [read, select, query]

    - principal: "role:FINANCE_ANALYST"
      permissions: [read, select]

    - principal: "role:TRADER"
      permissions: [read, select, query]

    - principal: "role:DATA_ENGINEER"
      permissions: [write, insert, update, delete, create]

    - principal: "user:looker_service@company.com"
      permissions: [read, select]

# ── Expose: Snowflake Table ───────────────────────────────────
exposes:
  - exposeId: bitcoin_prices_table
    title: "Bitcoin Real-time Price Feed"
    version: "1.0.0"
    kind: table

    binding:
      platform: snowflake
      format: snowflake_table
      location:
        account: "{{ env.SNOWFLAKE_ACCOUNT }}"
        database: "CRYPTO_DATA"
        schema: "MARKET_DATA"
        table: "BITCOIN_PRICES"
      properties:
        cluster_by: ["price_timestamp"]
        table_type: "STANDARD"
        data_retention_time_in_days: 7
        change_tracking: true

    # Governance policies
    policy:
      classification: Internal
      authn: snowflake_rbac
      authz:
        readers:
          - role:DATA_ANALYST
          - role:FINANCE_ANALYST
          - role:TRADER
        writers:
          - role:DATA_ENGINEER
        columnRestrictions:
          - principal: "role:JUNIOR_ANALYST"
            columns: [market_cap_usd, volume_24h_usd]
            access: deny
      privacy:
        masking:
          - column: "ingestion_timestamp"
            strategy: "hash"
            params:
              algorithm: "SHA256"
        rowLevelPolicy:
          expression: >
            price_timestamp >= DATEADD(day, -30, CURRENT_TIMESTAMP())

    # Schema contract
    contract:
      schema:
        - name: price_timestamp
          type: TIMESTAMP_NTZ
          required: true
          description: UTC timestamp when price was recorded
          sensitivity: cleartext
          semanticType: "timestamp"

        - name: price_usd
          type: NUMBER(18,2)
          required: true
          description: Bitcoin price in USD
          sensitivity: cleartext
          semanticType: "currency"

        - name: price_eur
          type: NUMBER(18,2)
          required: false
          description: Bitcoin price in EUR

        - name: price_gbp
          type: NUMBER(18,2)
          required: false
          description: Bitcoin price in GBP

        - name: market_cap_usd
          type: NUMBER(20,2)
          required: false
          description: Total market capitalization in USD
          sensitivity: internal

        - name: volume_24h_usd
          type: NUMBER(20,2)
          required: false
          description: 24-hour trading volume in USD
          sensitivity: internal

        - name: price_change_24h_pct
          type: NUMBER(10,4)
          required: false
          description: 24-hour price change percentage

        - name: last_updated
          type: TIMESTAMP_NTZ
          required: false
          description: Timestamp from CoinGecko API

        - name: ingestion_timestamp
          type: TIMESTAMP_NTZ
          required: true
          description: When data was ingested into our system

# ── Build: API Ingestion ──────────────────────────────────────
builds:
  - id: bitcoin_price_ingestion
    description: Fetch Bitcoin prices from CoinGecko API
    pattern: hybrid-reference
    engine: python
    repository: ./runtime
    properties:
      model: ingest
    execution:
      trigger:
        type: manual
        iterations: 1
        delaySeconds: 3
      runtime:
        platform: snowflake
        resources:
          warehouse: "COMPUTE_WH"
          warehouse_size: "X-SMALL"
      retries:
        count: 3
        backoff: exponential
    outputs:
      - bitcoin_prices_table
```

### Key Schema Patterns

The 0.7.1 binding schema uses three fields to identify platform resources:

| Field | Purpose | Snowflake Values |
|-------|---------|-----------------|
| `binding.platform` | Cloud provider | `snowflake` |
| `binding.format` | Storage format | `snowflake_table` |
| `binding.location` | Resource coordinates | `account`, `database`, `schema`, `table` |

This is identical to GCP (`platform: gcp`, `format: bigquery_table`) and AWS (`platform: aws`, `format: parquet`).

## CLI Commands

Every normal Snowflake provider command is autodetected from `binding.platform`, so `--provider snowflake` is not required for `plan`, `apply`, `verify`, or `test`.

```bash
# Validate Snowflake connectivity with the same config the provider uses
fluid auth status snowflake

# Validate contract shape
fluid validate contract.fluid.yaml

# Generate execution plan
fluid plan contract.fluid.yaml --env dev --out plans/plan-dev.json

# Deploy database, schema, table, and build logic
fluid apply contract.fluid.yaml --env dev --yes

# Verify the deployed Snowflake object against the contract schema
fluid verify contract.fluid.yaml --strict

# Optional: run the live contract test flow
fluid test contract.fluid.yaml

# Validate governance declarations
fluid policy-check contract.fluid.yaml

# Compile RBAC / access bindings from accessPolicy grants
fluid policy-compile contract.fluid.yaml --env dev --out runtime/policy/bindings.json

# Apply RBAC bindings (dry-run or enforce)
fluid policy-apply runtime/policy/bindings.json --mode check
fluid policy-apply runtime/policy/bindings.json --mode enforce

# Generate Airflow DAG
fluid generate-airflow contract.fluid.yaml --out airflow-dags/bitcoin_snowflake.py
```

Recommended deployment gate for enterprise teams:

1. `fluid validate`
2. `fluid plan`
3. `fluid policy-check`
4. `fluid policy-compile`
5. `fluid apply`
6. `fluid verify --strict`
7. optional `fluid test`

Every Snowflake session opened through the provider carries a `QUERY_TAG` so statements can be attributed in Snowflake `QUERY_HISTORY`. In practice this means plan/apply/verify traffic can be traced back to the contract and environment that issued it.

## RBAC Policy Compilation

`fluid policy-compile` reads `accessPolicy.grants` and generates Snowflake `GRANT` statements:

```json
{
  "provider": "snowflake",
  "bindings": [
    {
      "role": "role:DATA_ANALYST",
      "resource": "bitcoin_prices_table",
      "permissions": [
        "SELECT on CRYPTO_DATA.MARKET_DATA.BITCOIN_PRICES",
        "USAGE on DATABASE CRYPTO_DATA",
        "USAGE on SCHEMA CRYPTO_DATA.MARKET_DATA"
      ]
    },
    {
      "role": "role:DATA_ENGINEER",
      "resource": "bitcoin_prices_table",
      "permissions": [
        "INSERT on CRYPTO_DATA.MARKET_DATA.BITCOIN_PRICES",
        "UPDATE on CRYPTO_DATA.MARKET_DATA.BITCOIN_PRICES",
        "DELETE on CRYPTO_DATA.MARKET_DATA.BITCOIN_PRICES"
      ]
    }
  ]
}
```

The permission mapping:

| Contract Permission | Snowflake GRANT |
|--------------------|-----------------|
| `read`, `select`, `query` | `SELECT` on table, `USAGE` on database + schema |
| `write`, `insert` | `INSERT` on table |
| `update` | `UPDATE` on table |
| `delete` | `DELETE` on table |

## Governance Scope

Use the governance commands this way:

- `fluid policy-check` validates governance declarations in the contract.
- `fluid policy-compile` and `fluid policy-apply` manage Snowflake RBAC and access-policy bindings.
- Snowflake governance during `apply` handles object-level controls such as tags, descriptions, and masking policies.
- `fluid verify` checks deployed schema and drift. It does not perform a full RBAC or entitlement audit.

## Credentials Setup

### Accepted `SNOWFLAKE_ACCOUNT` Formats

Forge accepts the common Snowflake account identifier formats that teams usually copy from the Snowflake UI, connector docs, or browser URL and normalizes them before opening the connection.

Accepted examples:

- `org-account`
- `xy12345`
- `xy12345.eu-central-1`
- `xy12345.eu-central-1.aws`
- `xy12345.eu-central-1.privatelink`
- `https://xy12345.eu-central-1.aws.snowflakecomputing.com`
- `https://app-org-account.privatelink.snowflakecomputing.com`

Normalization rules:

- strips `https://` and `.snowflakecomputing.com`
- strips cloud suffixes such as `.aws`, `.gcp`, and `.azure`
- preserves `.privatelink` when it is part of the effective account identifier
- strips the leading `app-` prefix from Snowsight-style browser hostnames

Invalid hostnames such as `https://example.com` fail fast with a validation error instead of being silently misparsed.

### Jenkins CI (Recommended)

Create a Jenkins **Secret File** credential containing your Snowflake env vars:

```bash
# File contents (plain key=value, no 'export' prefix)
SNOWFLAKE_ACCOUNT=xy12345.eu-central-1
SNOWFLAKE_USER=FLUID_SERVICE
SNOWFLAKE_PASSWORD=xxxxxxxxxx
SNOWFLAKE_WAREHOUSE=COMPUTE_WH
SNOWFLAKE_ROLE=SYSADMIN
SNOWFLAKE_DATABASE=CRYPTO_DATA
SNOWFLAKE_SCHEMA=MARKET_DATA
```

The [Universal Pipeline](/walkthrough/universal-pipeline) auto-detects this format and sources it into every stage. No provider-specific credential logic.

### Local Development

```bash
# .env file (same format as Jenkins)
cat > .env << 'EOF'
SNOWFLAKE_ACCOUNT=xy12345.eu-central-1
SNOWFLAKE_USER=FLUID_SERVICE
SNOWFLAKE_PASSWORD=xxxxxxxxxx
SNOWFLAKE_WAREHOUSE=COMPUTE_WH
SNOWFLAKE_ROLE=SYSADMIN
SNOWFLAKE_DATABASE=CRYPTO_DATA
SNOWFLAKE_SCHEMA=MARKET_DATA
EOF

# Source and run
set -a; . .env; set +a
fluid auth status snowflake
fluid plan contract.fluid.yaml --env dev --out runtime/plan.json
fluid apply contract.fluid.yaml --env dev --yes
fluid verify contract.fluid.yaml --strict
```

### Session Context Initialization

After connecting, Forge pins the active Snowflake session explicitly using any configured role, warehouse, database, and schema:

```sql
USE ROLE <role>;
USE WAREHOUSE <warehouse>;
USE DATABASE <database>;
USE SCHEMA <schema>;
```

This keeps runtime behavior aligned with the contract and credential settings across local runs, CI, and automation. If any configured value is invalid, Forge fails fast instead of leaving the session half-initialized.

`DATABASE` and `SCHEMA` settings may be dot-qualified when Snowflake accepts that shape, for example `ANALYTICS.RAW`.

## Infrastructure Created

When you run `fluid apply` on a Snowflake contract, the provider creates:

| Resource | Details |
|----------|---------|
| **Database** | `CRYPTO_DATA` |
| **Schema** | `CRYPTO_DATA.MARKET_DATA` |
| **Table** | `CRYPTO_DATA.MARKET_DATA.BITCOIN_PRICES` — clustered by `price_timestamp` |
| **Warehouse** | `COMPUTE_WH` (X-SMALL) — used for queries and ingestion |

### What the Pipeline Produces

After a successful run, the pipeline inserts real data:

```sql
SELECT price_timestamp, price_usd, price_eur, market_cap_usd
FROM CRYPTO_DATA.MARKET_DATA.BITCOIN_PRICES
ORDER BY price_timestamp DESC
LIMIT 5;
```

```
┌──────────────────────┬───────────┬───────────┬────────────────┐
│ PRICE_TIMESTAMP      │ PRICE_USD │ PRICE_EUR │ MARKET_CAP_USD │
├──────────────────────┼───────────┼───────────┼────────────────┤
│ 2025-01-30 14:30:52  │ 104809.00 │  96543.00 │ 2075000000.00  │
└──────────────────────┴───────────┴───────────┴────────────────┘
```

## Governance Features

### Data Sovereignty

The `sovereignty` block enforces region restrictions **before** any infrastructure is deployed:

```yaml
sovereignty:
  jurisdiction: "EU"
  allowedRegions: [eu-west-1, eu-central-1, europe-west4]
  deniedRegions: [us-east-1, us-west-2, us-central1]
  crossBorderTransfer: false
  regulatoryFramework: [GDPR, SOC2]
  enforcementMode: advisory  # or strict (blocks deployment)
```

### Column-Level Security

Restrict specific columns from specific roles:

```yaml
authz:
  columnRestrictions:
    - principal: "role:JUNIOR_ANALYST"
      columns: [market_cap_usd, volume_24h_usd]
      access: deny
```

### Privacy Masking

Hash sensitive fields and enforce retention policies:

```yaml
privacy:
  masking:
    - column: "ingestion_timestamp"
      strategy: "hash"
      params:
        algorithm: "SHA256"
  rowLevelPolicy:
    expression: "price_timestamp >= DATEADD(day, -30, CURRENT_TIMESTAMP())"
```

Row-level security expressions are intentionally validated against a narrow SQL-expression allowlist before Forge generates Snowflake row access policies. Keep these expressions to predicate-style logic such as comparisons, boolean operators, function calls, and string literals.

Forge rejects or skips unsafe expressions that contain statement separators, SQL comments, or statement-level keywords such as `SELECT`, `USE`, `GRANT`, `DROP`, or `INSERT`. When that happens, planning continues and the CLI emits a warning so you can fix the contract instead of applying unsafe SQL.

### Snowflake-Native Security

The contract's governance maps naturally to Snowflake's built-in features:

| Contract Feature | Snowflake Implementation |
|-----------------|-------------------------|
| `accessPolicy.grants` | `GRANT SELECT/INSERT/UPDATE ON TABLE ... TO ROLE ...` |
| `columnRestrictions` | Dynamic Data Masking policies |
| `rowLevelPolicy` | Row Access Policies |
| `sovereignty.allowedRegions` | Account region validation |
| `classification` | Object tagging via `TAG` |

## CI/CD Pipeline

The Snowflake example uses the exact same Jenkinsfile as GCP and AWS — the [Universal Pipeline](/walkthrough/universal-pipeline). Key stages:

| Stage | Command | What Happens |
|-------|---------|-------------|
| Validate | `fluid validate` | Contract checked against 0.7.1 schema |
| Export | `fluid odps export` / `fluid odcs export` | Standards files generated |
| Compile RBAC | `fluid policy-compile` | `accessPolicy` → Snowflake GRANT bindings |
| Plan | `fluid plan` | Execution plan generated |
| Apply | `fluid apply` | Database + schema + table created |
| Apply RBAC | `fluid policy-apply` | RBAC grants enforced |
| Execute | `fluid execute` | `ingest.py` runs, inserts rows to Snowflake |
| Airflow DAG | `fluid generate-airflow` | Production DAG generated |

## Snowflake Table Properties

The `binding.properties` block supports Snowflake-specific table features:

```yaml
binding:
  platform: snowflake
  format: snowflake_table
  location:
    database: "ANALYTICS"
    schema: "MARTS"
    table: "CUSTOMER_METRICS"
  properties:
    cluster_by: ["customer_id", "order_date"]
    table_type: "STANDARD"              # STANDARD or TRANSIENT
    data_retention_time_in_days: 7      # Time Travel retention
    change_tracking: true               # Enable CDC streams
```

## See Also

- [Snowflake Team Collaboration Walkthrough](/walkthrough/snowflake) - Role-based PR review example for Snowflake teams
- [Universal Pipeline](/walkthrough/universal-pipeline) — Same Jenkinsfile for every provider
- [AWS Provider](./aws) — Amazon Web Services integration
- [GCP Provider](./gcp) — Google Cloud Platform integration
- [CLI Reference](/cli/) — Full command documentation
