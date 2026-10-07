# Snowflake Provider

Deploy data products to Snowflake Data Cloud (databases, schemas and tables) using the same contract format and CLI commands as the other providers.

**Status:** ✅ Production  
**Docs Baseline:** CLI `0.18.1`<br>
**Tested Services:** Databases, Schemas, Tables

> **Why it matters**
> Target Snowflake with the same contract your other teams run elsewhere — no Snowflake-specific rewrite.
> Set `binding.platform: snowflake` and `fluid apply` compiles the contract to an OpenTofu module for the `snowflakedb/snowflake` provider and runs it.

::: warning Compatibility note
Examples on this page use the current `fluidVersion: 0.7.5` shape. New orchestration examples should prefer `fluid generate schedule --scheduler airflow` over the older `fluid generate-airflow`.
:::

---

## Overview

The Snowflake provider turns a FLUID contract into real Snowflake infrastructure:

- ✅ **Plan & Apply**: databases, schemas and tables (with `cluster_by`) through OpenTofu
- ✅ **Sovereignty validation**: region constraints checked before deployment
- ✅ **Orchestration generation**: `fluid generate schedule --scheduler airflow`
- ⚠️ **Access grants**: `fluid policy-compile` turns `accessPolicy.grants` into Snowflake grant bindings, but as of 0.18.1 nothing applies them (see [Snowflake-Native Security](#snowflake-native-security))
- ❌ **Masking, row access and column restrictions**: the contract's `policy.privacy` and `policy.authz.columnRestrictions` fields are not read on Snowflake (see [Governance Features](#governance-features))
- ✅ **Universal Pipeline**: the same Jenkinsfile as GCP and AWS

## Choose Your Starting Path

Use Snowflake in one of these two modes:

- **Enterprise recommended path:** dbt-snowflake plus explicit environment-specific warehouse, database, schema, and role settings. Start with the [`billing_history` example](https://github.com/Agenticstiger/forge-cli/tree/main/examples/snowflake/billing_history) and the [Snowflake quickstart](/forge_docs/getting-started/snowflake).
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

The contract below provisions a Snowflake table and runs a Python ingestion build. It validates on 0.18.1, and `fluid generate iac` emits a database, a schema and a clustered table from it.

### Contract

```yaml
fluidVersion: "0.7.5"
kind: DataProduct
id: crypto.bitcoin_prices_snowflake_governed
name: Bitcoin Price Index (Snowflake)
description: >
  Bitcoin price data on Snowflake
domain: finance

tags:
  - cryptocurrency
  - real-time
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
    email: data-engineering@company.example.com

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

    - principal: "user:looker_service@company.example.com"
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

    policy:
      classification: Internal
      authn: custom

    # Schema contract
    contract:
      schema:
        - name: price_timestamp
          type: TIMESTAMP
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
          type: TIMESTAMP
          required: false
          description: Timestamp from CoinGecko API

        - name: ingestion_timestamp
          type: TIMESTAMP
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

The binding schema uses three fields to identify platform resources:

| Field | Purpose | Snowflake Values |
|-------|---------|-----------------|
| `binding.platform` | Cloud provider | `snowflake` |
| `binding.format` | Storage format | `snowflake_table` |
| `binding.location` | Resource coordinates | `account`, `database`, `schema`, `table` |

This is identical to GCP (`platform: gcp`, `format: bigquery_table`) and AWS (`platform: aws`, `format: parquet`).

### Column types

| Contract type | Snowflake type |
|---|---|
| `string`, `text`, `varchar`, `char` | `VARCHAR` |
| `integer`, `int`, `bigint`, `long` | `NUMBER(38,0)` |
| `number(p,s)`, `decimal(p,s)`, `numeric(p,s)` | `NUMBER(p,s)` |
| `float`, `double`, `real` | `FLOAT` |
| `boolean` | `BOOLEAN` |
| `timestamp`, `datetime` | `TIMESTAMP_NTZ` |
| `date`, `time`, `variant`, `object`, `array`, `binary` | `DATE`, `TIME`, `VARIANT`, `OBJECT`, `ARRAY`, `BINARY` |

::: warning Other type names become `VARCHAR`
As of 0.18.1 the Snowflake module writes any type name outside this table as `VARCHAR`, without a warning. A column declared `TIMESTAMP_NTZ`, `TIMESTAMP_TZ` or `TIMESTAMP_LTZ` is created as `VARCHAR`. Declare `timestamp` for `TIMESTAMP_NTZ`. Because the module pins `lifecycle.ignore_changes = ["column"]`, a later corrected type does not change an existing table; `fluid verify --strict` reports the mismatch.
:::

## CLI Commands

Every normal Snowflake provider command is autodetected from `binding.platform`, so `--provider snowflake` is not required for `plan`, `apply`, `verify`, or `test`.

::: tip 0.14.0 reliability fixes
Three dbt-engine fixes land in `0.14.0` for Snowflake contracts: embedded-SQL builds on `platform: snowflake` now actually execute on Snowflake — earlier releases could silently run them against local DuckDB and still exit 0; the generated `profiles.yml` targets the contract's schema instead of silently defaulting to `PUBLIC`; and `fluid generate transformation --model-contracts` preserves parameterized and alias types (e.g. `NUMBER(18,2)`) instead of flattening every column to `VARCHAR(16777216)`. Net effect: a freshly generated project passes its own contract on the first `dbt run`.
:::

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

# Compile access bindings from accessPolicy grants (see the caveat below)
fluid policy-compile contract.fluid.yaml --env dev --out runtime/policy/bindings.json

# Generate Airflow DAG
fluid generate-airflow contract.fluid.yaml --output airflow-dags/bitcoin_snowflake.py
```

Recommended deployment gate for enterprise teams:

1. `fluid validate`
2. `fluid plan`
3. `fluid policy-check`
4. `fluid apply`
5. `fluid verify --strict`
6. optional `fluid test`

Grant the contract's roles with your own Snowflake tooling until the grants are applied (see [Snowflake-Native Security](#snowflake-native-security)).

Every Snowflake session opened through the provider carries a `QUERY_TAG` so statements can be attributed in Snowflake `QUERY_HISTORY`. In practice this means plan/apply/verify traffic can be traced back to the contract and environment that issued it.

## RBAC Policy Compilation

`fluid policy-compile` reads `accessPolicy.grants` and writes one binding per grant and expose:

```json
{
  "bindings": [
    {
      "provider": "snowflake",
      "resource_type": "snowflake.table",
      "resource_id": "CRYPTO_DATA.MARKET_DATA.BITCOIN_PRICES",
      "database": "CRYPTO_DATA",
      "schema": "MARKET_DATA",
      "table": "BITCOIN_PRICES",
      "principal": "role:DATA_ANALYST",
      "grants": [
        "SELECT"
      ]
    },
    ...
    {
      ...
      "principal": "role:DATA_ENGINEER",
      "grants": [
        "INSERT",
        "UPDATE",
        "DELETE",
        "SELECT"
      ]
    },
    ...
```

The permission mapping:

| Contract permissions | Snowflake privileges |
|--------------------|-----------------|
| any of `write`, `insert`, `update`, `delete` | `INSERT`, `UPDATE`, `DELETE`, `SELECT` on the table |
| otherwise (`read`, `select`, `query`) | `SELECT` on the table |

No `USAGE` on the database or schema is compiled.

An Iceberg expose on `platform: snowflake` compiles to the same Snowflake grant, except with `location.catalog: glue`, which compiles to AWS Glue bindings. When the expose names another catalog outside Snowflake (`lakekeeper`, say), the output also carries a warning that the grant covers Snowflake readers only, and that every other engine needs the grant in that catalog. *(forge-cli [#707](https://github.com/Agenticstiger/forge-cli/pull/707), unreleased)* On 0.19.0 and earlier, an Iceberg expose compiled to AWS S3 and Glue bindings, whatever its platform.

::: warning As of 0.18.1, Snowflake grants are compiled but not applied
`fluid policy-apply` on these bindings exits 0 and prints that the Snowflake provider has no standalone policy applier and that grants are applied during `fluid apply`. The Snowflake module `fluid apply` runs emits no grant from `accessPolicy`: its only grant source is a top-level `security.access_control` block, which the schema rejects. So `accessPolicy.grants` reaches no Snowflake role, and `fluid validate` does not warn. Grant the roles with your own tooling (for example a Terraform module or a SQL migration that runs `GRANT SELECT ON TABLE ... TO ROLE ...`), using the compiled bindings as the list.
:::

## Governance Scope

Use the governance commands this way:

- `fluid policy-check` validates governance declarations in the contract.
- `fluid policy-compile` lists the grants `accessPolicy` asks for; as of 0.18.1 neither `fluid policy-apply` nor `fluid apply` applies them on Snowflake.
- `fluid apply` writes the table's COMMENT: the contract description, a `FLUID classification` section (`fluid_layer`, `fluid_product_type`, `fluid_domain`, `fluid_version`) and the contract YAML.
- `fluid verify` checks deployed schema and drift. It does not audit grants.

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

::: warning `SNOWFLAKE_ACCOUNT` on the `fluid apply` path — changed in `0.15.0`
The generated OpenTofu module pins `snowflakedb/snowflake ~> 2.0`, and from the v2
provider the bare `account` field is gated behind the
`PROVIDER_CONFIGURATION_ACCOUNT_FALLBACK` experiment: the provider **errors the
moment it sees `SNOWFLAKE_ACCOUNT`**, whether or not the v2
`SNOWFLAKE_ORGANIZATION_NAME` + `SNOWFLAKE_ACCOUNT_NAME` pair is also present.

    Error: the account field requires the "PROVIDER_CONFIGURATION_ACCOUNT_FALLBACK"
    experiment to be enabled; add it to experimental_features_enabled

Before `0.15.0` fluid split `SNOWFLAKE_ACCOUNT` into that pair but **added** it
alongside the legacy variable, which is not a superset but its own failure mode — so
every `tofu plan` against Snowflake failed, and any operator with `SNOWFLAKE_ACCOUNT`
set (the standard variable the connector ecosystem uses) could not `fluid apply` to
Snowflake at all. Measured on provider `2.19.0` / OpenTofu `1.12.0`: legacy variable
only → rejected; legacy variable plus both v2 vars → rejected; the v2 vars with the
legacy variable blanked → plan succeeds.

**No contract or configuration change is needed.** As of `0.15.0` fluid derives the
v2 pair from the `<org>-<account>` form and blanks `SNOWFLAKE_ACCOUNT` in the
environment it hands to `tofu` — blanked rather than removed, because the overlay is
applied with `env.update()`, which cannot delete, and an empty value reads as unset
to the provider. An operator who keeps setting `SNOWFLAKE_ACCOUNT` in that form goes
from failing to working. Anything you set explicitly wins, so the two v2 variables
always override what fluid would derive.

Only the literal `<org>-<account>` form is bridged. Every other format on the accepted
list above still cannot `tofu plan`, in one of two ways. A bare account locator with no
organisation (`xy12345`) keeps its legacy value deliberately, so the provider's
actionable "enable the experiment" error survives instead of degrading to a vaguer
"account is empty". Every remaining form is mis-derived instead: the overlay reads the
raw environment variable, without the normalisation described above, and splits it on
its *first* hyphen, so `xy12345.eu-central-1` (and its `.aws` and `.privatelink`
variants) becomes organisation `xy12345.eu` and account `central-1`, and a browser
hostname such as `https://xy12345.eu-central-1.aws.snowflakecomputing.com` becomes
organisation `https://xy12345.eu`. Those forms do get the legacy variable blanked, so
rather than the experiment error you get a plan against an account that does not exist.
Unless your `SNOWFLAKE_ACCOUNT` is literally `<org>-<account>`, set the pair yourself:

```bash
export SNOWFLAKE_ORGANIZATION_NAME=myorg
export SNOWFLAKE_ACCOUNT_NAME=myaccount
```

Every form listed above remains valid for the **connection** credentials fluid itself
opens (`fluid auth status snowflake`, discovery, dbt). This applies only to the
OpenTofu apply path.
:::

### Jenkins CI (Recommended)

Create a Jenkins **Secret File** credential containing your Snowflake env vars:

```bash
# File contents (plain key=value, no 'export' prefix)
SNOWFLAKE_ACCOUNT=myorg-myaccount
SNOWFLAKE_USER=FLUID_SERVICE
SNOWFLAKE_PASSWORD=xxxxxxxxxx
SNOWFLAKE_WAREHOUSE=COMPUTE_WH
SNOWFLAKE_ROLE=SYSADMIN
SNOWFLAKE_DATABASE=CRYPTO_DATA
SNOWFLAKE_SCHEMA=MARKET_DATA
```

The [Universal Pipeline](/forge_docs/walkthrough/universal-pipeline) auto-detects this format and sources it into every stage. No provider-specific credential logic.

### Local Development

```bash
# .env file (same format as Jenkins)
cat > .env << 'EOF'
SNOWFLAKE_ACCOUNT=myorg-myaccount
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

When you run `fluid apply` on the contract above, the OpenTofu module creates three resources (`fluid generate iac` shows the same module). The warehouse named in `execution.runtime.resources` must already exist; it is used, not created.

| Resource | Details |
|----------|---------|
| **Database** | `CRYPTO_DATA` |
| **Schema** | `CRYPTO_DATA.MARKET_DATA` |
| **Table** | `CRYPTO_DATA.MARKET_DATA.BITCOIN_PRICES` — clustered by `price_timestamp` |


## Governance Features

### Data Sovereignty

The `sovereignty` block enforces region restrictions **before** any infrastructure is deployed:

```yaml
sovereignty:
  jurisdiction: "EU"
  allowedRegions: [eu-west-1, eu-central-1, europe-west4]
  deniedRegions: [us-east-1, us-west-2, us-central1]
  crossBorderTransfer: false
  regulatoryFramework: [GDPR]
  enforcementMode: advisory  # or strict (blocks deployment)
```

::: warning `enforcementMode` changed in `0.15.0`, in both directions
`enforcementMode` now decides the *severity* a violation carries, and so the outcome:
`strict` errors, `advisory` warns, `audit` logs. It had failed both ways at once — a
`strict` contract whose binding region resolved outside its declared `jurisdiction`
could not be blocked, and an `advisory` contract with a `deniedRegions` hit failed the
build on a mode documented as "warn". The engine's defaults also moved to the schema's
own stricter ones (`enforcementMode: strict`, `dataResidency: true`,
`crossBorderTransfer: false`) from the permissive inverse of all three, so a contract
that declares `sovereignty` while omitting those keys is now judged as documented and
can newly fail `fluid validate`. The region table is derived from the vendors' own data
as of `0.15.0` too, so `eu-west-2` and `europe-west2` (both London) resolve to `UK`
rather than `EU`. Modes, carve-outs and the full region story:
[Sovereignty enforcement modes](/forge_docs/advanced/governance.html#sovereignty-enforcement-modes-since-0-15-0).
:::

### Column restrictions, masking and row filters are not read

These fields validate on a Snowflake expose and produce nothing on Snowflake as of 0.18.1:

- `policy.authz.columnRestrictions`
- `policy.privacy.masking`
- `policy.privacy.rowLevelPolicy`
- `sensitivity: pii` on a column

Neither the Snowflake OpenTofu module nor the Snowflake provider reads them, so no masking policy, row access policy or grant comes from them. Do not rely on them to protect a Snowflake column. On GCP, `columnRestrictions` becomes [policy tags](./gcp.md#column-restrictions-policy-tags); masking at landing is applied by the DuckDB acquisition runner when it writes a local file, an S3 object or a BigQuery load file.

### Snowflake-Native Security

What 0.18.1 does with each governance field on a Snowflake binding:

| Contract field | On Snowflake |
|-----------------|-------------------------|
| `accessPolicy.grants` | compiled by `fluid policy-compile`; not applied by `fluid policy-apply` or `fluid apply` |
| `policy.authz.columnRestrictions` | not read |
| `policy.privacy.masking` | not read |
| `policy.privacy.rowLevelPolicy` | not read |
| `sovereignty` | checked against the binding's region before deployment |
| `metadata.layer`, `productType`, `domain`, `fluidVersion` | written into the table COMMENT |

The Snowflake module can emit `snowflake_masking_policy`, `snowflake_row_access_policy` and `snowflake_grant_privileges_to_account_role` objects, but only from a top-level `security:` block (`security.policies`, `security.access_control.grants`). The contract schema rejects that block, so a contract carrying it fails `fluid validate`, and even then the policies are created without being attached to a column or table.

## CI/CD Pipeline

The Snowflake example uses the exact same Jenkinsfile as GCP and AWS — the [Universal Pipeline](/forge_docs/walkthrough/universal-pipeline). Key stages:

| Stage | Command | What Happens |
|-------|---------|-------------|
| Validate | `fluid validate` | Contract checked against the bundled schema |
| Export | `fluid odps export` / `fluid odcs export` | Standards files generated |
| Compile RBAC | `fluid policy-compile` | `accessPolicy` → Snowflake grant bindings |
| Plan | `fluid plan` | Execution plan generated |
| Apply | `fluid apply` | Database + schema + table created |
| Apply RBAC | `fluid policy-apply` | No-op on Snowflake as of 0.18.1 (see above) |
| Execute | `fluid apply --mode amend-and-build` | Runs the contract's build (`ingest` in `./runtime`) after provisioning |
| Airflow DAG | `fluid generate-airflow` | Production DAG generated |

## Snowflake Table Properties

The Snowflake module reads one table property from `binding.properties`:

```yaml
binding:
  platform: snowflake
  format: snowflake_table
  location:
    database: "ANALYTICS"
    schema: "MARTS"
    table: "CUSTOMER_METRICS"
  properties:
    cluster_by: ["customer_id", "order_date"]   # must be a list of columns
```

Other keys under `binding.properties` (`table_type`, `data_retention_time_in_days`, `change_tracking`) pass validation and are not emitted. Set them on the table with your own tooling.

## Iceberg Tables via dbt (since 0.13.1)

An expose with `binding.format: iceberg` on `platform: snowflake` closes the dbt Iceberg loop in two halves:

- **`fluid generate transformation`** emits dbt's `catalogs.yml` (v1 catalogs schema, Snowflake adapter) into the generated project. *(forge-cli [#707](https://github.com/Agenticstiger/forge-cli/pull/707), unreleased)* Catalogs external to Snowflake (`location.catalog: glue`, `rest` or `iceberg_rest`, `lakekeeper`, `polaris`, `unity`, `nessie`, `bigquery`) map to `catalog_type: iceberg_rest`. No `location.catalog`, or `snowflake` (`snowflake-managed`), is Snowflake-managed (Horizon) and maps to `built_in`. `hive`, `jdbc`, `hadoop` and `dynamodb`, which Snowflake has no catalog integration for, are left out of the file with a warning, and `fluid validate` refuses them. Any other value is refused by `fluid validate`. The full table, and how spellings fold, is in [Iceberg catalogs](../advanced/source-aligned-acquisition.md#iceberg-catalogs-location-catalog). On 0.19.0 and earlier, only `glue`, `polaris`, `unity`, `rest`, `iceberg_rest` and `nessie` mapped to `iceberg_rest`, and anything else, `lakekeeper` and `hive` included, became `built_in`.
- **`fluid apply`** provisions the prerequisites dbt refuses to create: the **EXTERNAL VOLUME** for Snowflake-managed catalogs (needs an `s3://` or `gs://` `location.warehouse`, plus `location.iam_role_arn` for S3), and the **AWS Glue CATALOG INTEGRATION** for `location.catalog: glue` (needs `location.iam_role_arn` — the role Snowflake assumes — and `location.account`, the AWS account id). It creates nothing for the other `iceberg_rest` catalogs listed above: their integrations authenticate with a secret, and the emitted module is credential-free. *(forge-cli [#707](https://github.com/Agenticstiger/forge-cli/pull/707), unreleased)* On 0.19.0 and earlier, a `lakekeeper` expose got an EXTERNAL VOLUME, and `fluid validate` asked it for an `s3://` or `gs://` warehouse. *(forge-cli fix/iceberg-catalog-followups, unreleased)* While state still holds such a volume, `fluid apply` stops before it plans; see [Upgrading an Iceberg expose in an external catalog](#upgrading-an-iceberg-expose-in-an-external-catalog).

```yaml
exposes:
  - exposeId: orders_iceberg
    kind: table
    binding:
      platform: snowflake
      format: iceberg
      location:
        database: "ANALYTICS"
        schema: "MARTS"
        table: "ORDERS_ICEBERG"
        warehouse: "s3://analytics-lake/warehouse/"   # storage behind the EXTERNAL VOLUME
        iam_role_arn: "arn:aws:iam::123456789012:role/snowflake-iceberg"
```

Both halves derive names through one deterministic naming helper, so the EXTERNAL VOLUME `fluid apply` creates carries **exactly** the name `catalogs.yml` references (`FLUID_<PRODUCT_ID>_VOL`, folded from the contract id). To use a volume your Snowflake admin already created, set `binding.icebergConfig.properties.external_volume` (camelCase `externalVolume` is also accepted): `catalogs.yml` then references your volume and `fluid apply` emits no `CREATE`, so apply never collides with the operator-owned object.

Since `0.14.0`, `fluid validate` errors when an Iceberg expose is missing one of the required inputs above instead of letting the emitters silently skip it — see [Iceberg prerequisite checks](/forge_docs/cli/validate.html#iceberg-prerequisite-checks-since-0-14-0). CI note: under `--strict`, Snowflake catalogs that authenticate with secrets (`polaris` / `unity` / `rest` / `nessie`) now fail validation, because the emitted OpenTofu module is credential-free. *(forge-cli [#707](https://github.com/Agenticstiger/forge-cli/pull/707), unreleased)* The same warning covers `lakekeeper` and `bigquery`, and `hive`, `jdbc`, `hadoop` or `dynamodb` on Snowflake is an error with or without `--strict`.

### Upgrading an Iceberg expose in an external catalog

*(forge-cli fix/iceberg-catalog-followups, unreleased)* 0.19.0 and earlier created an EXTERNAL VOLUME for an Iceberg expose whose `location.catalog` is `lakekeeper` or `bigquery`, or is spelled `iceberg-rest`, and dbt wrote a Snowflake-managed table onto it. `hive`, `jdbc`, `hadoop` and `dynamodb` got one too; `fluid validate` now refuses them. The module now creates no volume for these catalogs. When the contract's OpenTofu state still holds the volume, the plan would drop it, so `fluid apply` stops before it plans (abridged):

```text
❌ iceberg_catalog_move_blocked  [ERR_ICEBERG_CATALOG_MOVE_BLOCKED]
  kind: iceberg-catalog-move
  error: iceberg catalog move blocked — this contract's OpenTofu state holds 1 Snowflake EXTERNAL VOLUME(s) for Iceberg table(s) that now live in another catalog:

  exposes[orders_iceberg]: location.catalog lakekeeper

  snowflake_external_volume.sales_orders_lake_vol_FLUID_SALES_ORDERS_LAKE_VOL
...
Drop each from this contract's state, then re-run apply:

  tofu -chdir=.fluid/iac/snowflake/sales_orders_lake state rm snowflake_external_volume.sales_orders_lake_vol_FLUID_SALES_ORDERS_LAKE_VOL
...
```

1. Run the printed command, in the form `tofu -chdir=.fluid/iac/snowflake/<safe-id> state rm snowflake_external_volume.<name>`. It changes nothing in Snowflake; it releases this contract's claim on the volume.
2. Run `fluid apply` again.
3. Drop the volume by hand (`DROP EXTERNAL VOLUME`) only once no Iceberg table uses it. A Snowflake-managed table an earlier dbt run wrote onto it still does.

If the table belongs in Snowflake's own catalog, remove `location.catalog` (or set it to `snowflake`) instead. A volume you name in `binding.icebergConfig.properties.external_volume` is never flagged, because no release created it. The same guard covers Glue resources on AWS; see [Iceberg catalog-move guard](../cli/apply.md#iceberg-catalog-move-guard).

## See Also

- [Snowflake Team Collaboration Walkthrough](/forge_docs/walkthrough/snowflake) - Role-based PR review example for Snowflake teams
- [Universal Pipeline](/forge_docs/walkthrough/universal-pipeline) — Same Jenkinsfile for every provider
- [AWS Provider](./aws) — Amazon Web Services integration
- [GCP Provider](./gcp) — Google Cloud Platform integration
- [CLI Reference](/forge_docs/cli/) — Full command documentation
