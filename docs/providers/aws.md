# AWS Provider

Deploy data products to Amazon Web Services — S3, Glue, Athena — using the same contract and CLI commands as every other provider.

**Status:** ✅ Production  
**Docs Baseline:** CLI `0.7.9`  
**Tested Services:** S3, Glue Data Catalog, Athena, IAM

::: warning Compatibility note
This page preserves some older `0.7.1` contract snippets for backward-compatibility context. Current scaffolds emit `fluidVersion: 0.7.2`, and orchestration guidance now prefers `fluid generate schedule --scheduler airflow`.
:::

---

## Overview

The AWS provider turns a FLUID contract into real cloud infrastructure:

- ✅ **Plan & Apply** — S3 buckets, Glue databases/tables, Athena workgroups
- ✅ **IAM Policy Compilation** — `fluid policy-compile` generates S3, Glue, and Athena IAM bindings from `accessPolicy` grants
- ✅ **Sovereignty Validation** — Region allow/deny lists enforced before deployment
- ✅ **Orchestration Generation** — prefer `fluid generate schedule --scheduler airflow` for current docs and automation
- ✅ **Governance** — Classification, column masking, row-level policies, audit labels
- ✅ **Universal Pipeline** — Same Jenkinsfile as GCP and Snowflake — zero provider logic

## Working Example: Bitcoin Price Tracker

This is a production-tested example that runs end-to-end in Jenkins CI.

### Contract

```yaml
fluidVersion: "0.7.1"
kind: DataProduct
id: crypto.market_data.bitcoin_prices_aws_v1
name: Bitcoin Price Tracker (AWS Athena)
description: >
  Real-time Bitcoin price data stored in AWS Athena with S3 backend,
  with comprehensive governance
domain: Market Data

tags:
  - crypto
  - market-data
  - real-time
  - governed
  - gdpr-compliant

labels:
  team: data-engineering
  cost-center: analytics
  business_criticality: "high"
  compliance_gdpr: "true"
  platform: "aws"

metadata:
  layer: Gold
  owner:
    team: data-engineering
    email: data-eng@company.com

# ── Data Sovereignty ──────────────────────────────────────────
sovereignty:
  jurisdiction: "EU"
  dataResidency: true
  allowedRegions:
    - eu-central-1       # AWS Frankfurt (GDPR compliant)
    - eu-west-1          # AWS Ireland
  deniedRegions:
    - us-east-1
    - us-west-2
  crossBorderTransfer: false
  transferMechanisms:
    - SCCs
  regulatoryFramework:
    - GDPR
    - SOC2
  enforcementMode: advisory
  validationRequired: true

# ── Access Policy: AWS IAM Principals ─────────────────────────
accessPolicy:
  grants:
    - principal: "role:data-analyst"
      permissions: [read, select, query]

    - principal: "role:finance-team"
      permissions: [read, select]

    - principal: "role:trading-desk"
      permissions: [read, select, query]

    - principal: "role:data-engineer"
      permissions: [write, insert, update, delete, create]

    - principal: "role:pipeline-service"
      permissions: [read, write, insert]

# ── Expose: Athena Table ──────────────────────────────────────
exposes:
  - exposeId: bitcoin_prices_table
    title: Bitcoin Real-time Price Feed
    version: "1.0.0"
    kind: table

    binding:
      platform: aws
      format: parquet
      location:
        database: crypto_data
        table: bitcoin_prices
        bucket: "{{ env.S3_BUCKET }}"
        path: data/bitcoin/prices/
        region: "{{ env.AWS_REGION }}"

    # Governance policies
    policy:
      classification: Internal
      authn: iam
      authz:
        readers:
          - role:data-analyst
          - role:finance-team
          - role:trading-desk
          - role:pipeline-service
        writers:
          - role:data-engineer
          - role:pipeline-service
        columnRestrictions:
          - principal: "role:intern"
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
            price_timestamp >= DATE_ADD('day', -30, CURRENT_TIMESTAMP)

    # Schema contract
    contract:
      schema:
        - name: price_timestamp
          type: timestamp
          required: true
          description: UTC timestamp when price was recorded
          sensitivity: cleartext
          semanticType: "timestamp"

        - name: price_usd
          type: decimal(18,2)
          required: true
          description: Bitcoin price in USD
          sensitivity: cleartext
          semanticType: "currency"

        - name: price_eur
          type: decimal(18,2)
          required: false
          description: Bitcoin price in EUR

        - name: price_gbp
          type: decimal(18,2)
          required: false
          description: Bitcoin price in GBP

        - name: market_cap_usd
          type: decimal(20,2)
          required: false
          description: Total market capitalization in USD
          sensitivity: internal

        - name: volume_24h_usd
          type: decimal(20,2)
          required: false
          description: 24-hour trading volume in USD
          sensitivity: internal

        - name: price_change_24h_pct
          type: decimal(10,4)
          required: false
          description: 24-hour price change percentage

        - name: last_updated
          type: timestamp
          required: false
          description: Timestamp from CoinGecko API

        - name: ingestion_timestamp
          type: timestamp
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
        image: python:3.11-slim
        dependencies: [boto3, requests, pyarrow]
        env: [AWS_REGION, S3_BUCKET, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY]
      retries:
        count: 3
        backoff: exponential
    outputs:
      - bitcoin_prices_table
```

### Key Schema Patterns

The 0.7.1 binding schema uses three fields to identify platform resources:

| Field | Purpose | AWS Values |
|-------|---------|-----------|
| `binding.platform` | Cloud provider | `aws` |
| `binding.format` | Storage format | `parquet`, `s3_file`, `csv`, `json` |
| `binding.location` | Resource coordinates | `bucket`, `path`, `region`, `database`, `table` |

This is identical to GCP (`platform: gcp`, `format: bigquery_table`) and Snowflake (`platform: snowflake`, `format: snowflake_table`).

## CLI Commands

Every command is **identical** across providers. No `--provider` flag needed — the CLI reads the provider from the contract's `binding.platform` field.

```bash
# Validate contract against 0.7.1 JSON schema
fluid validate contract.fluid.yaml --verbose

# Generate execution plan
fluid plan contract.fluid.yaml --env dev --out plans/plan-dev.json

# Deploy S3 bucket, Glue DB, Athena table
fluid apply contract.fluid.yaml --env dev --yes

# Compile IAM policies from accessPolicy grants
fluid policy-compile contract.fluid.yaml --env dev --out runtime/policy/bindings.json

# Apply IAM bindings (dry-run or enforce)
fluid policy-apply runtime/policy/bindings.json --mode check
fluid policy-apply runtime/policy/bindings.json --mode enforce

# Run the ingest script
fluid execute contract.fluid.yaml

# Generate Airflow DAG
fluid generate-airflow contract.fluid.yaml --out airflow-dags/bitcoin_aws.py

# Export standards
fluid odps export contract.fluid.yaml --out standards/product.odps.json
fluid odcs export contract.fluid.yaml --out standards/product.odcs.yaml
```

## IAM Policy Compilation

`fluid policy-compile` reads `accessPolicy.grants` from the contract and generates AWS IAM permission bindings:

```json
{
  "provider": "aws",
  "bindings": [
    {
      "role": "role:data-analyst",
      "resource": "bitcoin_prices_table",
      "permissions": [
        "s3:GetObject",
        "s3:ListBucket",
        "glue:GetTable",
        "glue:GetDatabase",
        "athena:StartQueryExecution",
        "athena:GetQueryExecution",
        "athena:GetQueryResults"
      ]
    },
    {
      "role": "role:data-engineer",
      "resource": "bitcoin_prices_table",
      "permissions": [
        "s3:PutObject",
        "s3:DeleteObject",
        "glue:CreateTable",
        "glue:UpdateTable",
        "glue:DeleteTable"
      ]
    }
  ]
}
```

The permission mapping:

| Contract Permission | AWS IAM Actions |
|--------------------|-----------------|
| `read`, `select`, `query` | `s3:GetObject`, `s3:ListBucket`, `glue:GetTable`, `glue:GetDatabase`, `athena:StartQueryExecution`, `athena:GetQueryResults` |
| `write`, `insert`, `update`, `delete` | `s3:PutObject`, `s3:DeleteObject`, `glue:CreateTable`, `glue:UpdateTable`, `glue:DeleteTable` |

## Credentials Setup

### Jenkins CI (Recommended)

Create a Jenkins **Secret File** credential containing your AWS env vars:

```bash
# File contents (plain key=value, no 'export' prefix)
AWS_ACCESS_KEY_ID=AKIAxxxxxxxxxxxx
AWS_SECRET_ACCESS_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
AWS_REGION=eu-central-1
S3_BUCKET=my-fluid-data-bucket
```

The [Universal Pipeline](/forge_docs/walkthrough/universal-pipeline) auto-detects this format and sources it into every stage. No provider-specific credential logic.

### Local Development

```bash
# Option 1: AWS CLI profile
aws configure --profile fluid-dev

# Option 2: .env file (same format as Jenkins)
cat > .env << 'EOF'
AWS_ACCESS_KEY_ID=AKIAxxxxxxxxxxxx
AWS_SECRET_ACCESS_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
AWS_REGION=eu-central-1
S3_BUCKET=my-fluid-data-bucket
EOF

# Source and run
set -a; . .env; set +a
fluid apply contract.fluid.yaml --env dev --yes
```

## Infrastructure Created

When you run `fluid apply` on an AWS contract, the provider creates:

| Resource | Details |
|----------|---------|
| **S3 Bucket** | `s3://{S3_BUCKET}/data/bitcoin/prices/` — Parquet data storage |
| **Glue Database** | `crypto_data` — Data Catalog database |
| **Glue Table** | `bitcoin_prices` — External table pointing to S3 |
| **Athena Workgroup** | Query engine configured for the region |

### What the Pipeline Produces

After a successful run, the pipeline writes real data:

```
s3://my-fluid-bucket/data/bitcoin/prices/
  └── bitcoin_prices_20250130_143052.parquet   ← BTC at $104,809
```

Queryable immediately via Athena:

```sql
SELECT price_timestamp, price_usd, price_eur, market_cap_usd
FROM crypto_data.bitcoin_prices
ORDER BY price_timestamp DESC
LIMIT 5;
```

## Governance Features

### Data Sovereignty

The `sovereignty` block enforces region restrictions **before** any infrastructure is deployed:

```yaml
sovereignty:
  jurisdiction: "EU"
  allowedRegions: [eu-central-1, eu-west-1]
  deniedRegions: [us-east-1, us-west-2]
  crossBorderTransfer: false
  regulatoryFramework: [GDPR, SOC2]
  enforcementMode: advisory  # or strict (blocks deployment)
```

### Column-Level Security

Restrict specific columns from specific roles:

```yaml
authz:
  columnRestrictions:
    - principal: "role:intern"
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
    expression: "price_timestamp >= DATE_ADD('day', -30, CURRENT_TIMESTAMP)"
```

## CI/CD Pipeline

The AWS example uses the exact same Jenkinsfile as GCP and Snowflake — the [Universal Pipeline](/forge_docs/walkthrough/universal-pipeline). Key stages:

| Stage | Command | What Happens |
|-------|---------|-------------|
| Validate | `fluid validate` | Contract checked against 0.7.1 schema |
| Export | `fluid odps export` / `fluid odcs export` | Standards files generated |
| Compile IAM | `fluid policy-compile` | `accessPolicy` → IAM bindings JSON |
| Plan | `fluid plan` | Execution plan generated |
| Apply | `fluid apply` | S3 bucket + Glue DB/table created |
| Apply IAM | `fluid policy-apply` | IAM bindings enforced |
| Execute | `fluid execute` | `ingest.py` runs, writes Parquet to S3 |
| Airflow DAG | `fluid generate-airflow` | Production DAG generated |

## See Also

- [Universal Pipeline](/forge_docs/walkthrough/universal-pipeline) — Same Jenkinsfile for every provider
- [Snowflake Provider](./snowflake) — Snowflake Data Cloud integration
- [GCP Provider](./gcp) — Google Cloud Platform integration
- [CLI Reference](/forge_docs/cli/) — Full command documentation
