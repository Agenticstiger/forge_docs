# Bitcoin Price Tracker - Declarative Data Product Example

**Showcase:** How declarative contracts eliminate infrastructure code and enable multi-platform deployment

This example demonstrates the **declarative data product** pattern using FLUID:

- ✅ **One contract** defines everything (schema, governance, infrastructure, runtime)
- ✅ **Zero platform code** - contract auto-deploys to Snowflake/BigQuery/AWS
- ✅ **Platform-agnostic runtime** - same Python script works everywhere
- ✅ **Built-in governance** - RBAC, masking, sovereignty in YAML

## What Makes It "Declarative"?

| Traditional Approach | Declarative Approach |
|---------------------|----------------------|
| Write Terraform/CloudFormation | Declare contract in YAML |
| Write platform-specific SQL | Define schema once |
| Hardcode credentials in scripts | Reference via `{{ env.VAR }}` |
| Manually apply IAM/RBAC | Declare in `accessPolicy` |
| Separate docs for each cloud | One contract, all platforms |

**The magic:** `fluid apply contract.fluid.yaml` reads `binding.platform` and auto-deploys infrastructure.

## Quick Start (Snowflake)

### Prerequisites

```bash
# FLUID CLI
pip install fluid-forge

# Snowflake credentials
export SNOWFLAKE_ACCOUNT=your_account
export SNOWFLAKE_USER=your_user
export SNOWFLAKE_PASSWORD=your_password
export SNOWFLAKE_WAREHOUSE=your_warehouse
export SNOWFLAKE_ROLE=your_role
```

### 1. Validate Contract

```bash
fluid validate contract.fluid.yaml
```

**What it checks:**
- ✅ YAML syntax and schema compliance
- ✅ Governance policies (RBAC, sovereignty)
- ✅ Field-level metadata (tags, sensitivity)

### 2. Deploy Infrastructure

```bash
fluid apply contract.fluid.yaml
```

**What it creates:**
- Database: `CRYPTO_DATA`
- Schema: `MARKET_DATA`  
- Table: `BITCOIN_PRICES` (9 columns with governance)
- Grants: Reader/writer roles from `accessPolicy`

**No Terraform. No SQL scripts. Just the contract.**

### 3. Ingest Data

```bash
# Install dependencies
pip install -r requirements.txt

# Run ingestion
python3 runtime/ingest.py
```

**What it does:**
- Fetches Bitcoin price from CoinGecko API
- Transforms to contract schema
- Loads to Snowflake table
- Platform detected from `binding.platform: snowflake`

### 4. Verify

```python
import snowflake.connector

conn = snowflake.connector.connect(...)
cursor = conn.cursor()
cursor.execute("""
    SELECT price_usd, market_cap_usd, ingestion_timestamp 
    FROM CRYPTO_DATA.MARKET_DATA.BITCOIN_PRICES 
    ORDER BY ingestion_timestamp DESC 
    LIMIT 10
""")
```

## File Structure

```
bitcoin-price-tracker-0.7.1-snowflake/
├── contract.fluid.yaml          # THE contract (410 lines)
├── runtime/
│   └── ingest.py                # Platform-agnostic runtime (454 lines)
├── requirements.txt             # Python dependencies
├── .env.example                 # Environment template
├── Jenkinsfile                  # CI/CD pipeline
├── QUICKSTART.md                # Quick reference
└── README.md                    # This file
```

**Total infrastructure code: 0 lines** ✨

## The Contract: Your Single Source of Truth

[contract.fluid.yaml](contract.fluid.yaml) contains:

### 1. Metadata

```yaml
apiVersion: 0.7.1
kind: DataProduct
metadata:
  name: bitcoin-price-tracker
  domain: cryptocurrency
  owner:
    team: crypto-analytics
```

### 2. Platform Binding (Snowflake)

```yaml
exposes:
  - binding:
      platform: snowflake              # ← Auto-detected by fluid apply
      location:
        account: "{{ env.SNOWFLAKE_ACCOUNT }}"
        database: CRYPTO_DATA
        schema: MARKET_DATA
        table: BITCOIN_PRICES
```

**Switch to BigQuery?** Change `platform: bigquery` and `location` fields. Done.

### 3. Schema

```yaml
schema:
  - name: price_usd
    type: numeric
    description: "Current Bitcoin price in USD"
    required: true
    sensitivity: cleartext
    
  - name: market_cap_usd
    type: numeric
    description: "Total market capitalization"
    required: true
    
  - name: ingestion_timestamp
    type: timestamp
    required: true
```

**No manual CREATE TABLE statements.**

### 4. Governance

```yaml
accessPolicy:
  authentication:
    methods:
      - type: iam
        
  authorization:
    type: rbac
    grants:
      - role: crypto_reader
        principals:
          - "user:analyst@company.com"
        permissions: ["SELECT"]
        
      - role: crypto_writer
        principals:
          - "serviceAccount:ingestion-pipeline"
        permissions: ["SELECT", "INSERT"]
```

**IAM/RBAC applied automatically during `fluid apply`.**

### 5. Sovereignty & Compliance

```yaml
sovereignty:
  jurisdiction: "EU"
  dataResidency: true
  allowedRegions:
    - eu-central-1      # For Snowflake
  regulatoryFramework:
    - GDPR
  enforcementMode: advisory
```

**Blocks deployment to non-compliant regions.**

### 6. Runtime Configuration

```yaml
builds:
  - name: bitcoin-price-ingestion
    execution:
      trigger:
        type: manual
      runtime:
        platform: python
        entrypoint: runtime/ingest.py
        dependencies:
          - requests==2.31.0
          - snowflake-connector-python==3.12.3
```

**No hardcoded cron jobs or CI/CD pipelines required.**

## Platform-Agnostic Runtime

[runtime/ingest.py](runtime/ingest.py) auto-detects platform:

```python
# Load contract
with open('contract.fluid.yaml') as f:
    contract = yaml.safe_load(f)

platform = contract['exposes'][0]['binding']['platform']

# Platform-specific logic
if platform == 'snowflake':
    account = contract['exposes'][0]['binding']['location']['account']
    # Resolve {{ env.SNOWFLAKE_ACCOUNT }}
    if '{{' in account:
        account = os.environ['SNOWFLAKE_ACCOUNT']
    
    conn = snowflake.connector.connect(
        account=account,
        database=database,
        schema=schema,
        ...
    )
    
elif platform == 'bigquery':
    project = contract['exposes'][0]['binding']['location']['project']
    client = bigquery.Client(project=project)
```

**Same script, multiple clouds. Zero duplication.**

## CI/CD Integration

[Jenkinsfile](Jenkinsfile) demonstrates multi-platform pipeline:

```groovy
stage('Validate') {
    fluid validate contract.fluid.yaml
}

stage('Deploy Infrastructure') {
    // Auto-detects Snowflake from contract
    fluid apply contract.fluid.yaml
}

stage('Execute Build') {
    // Runs runtime/ingest.py with platform auto-detection
    fluid execute contract.fluid.yaml
}

stage('Generate Airflow DAG') {
    fluid generate-airflow contract.fluid.yaml \
        --out dags/bitcoin_tracker_dag.py
}
```

**Works for Snowflake, BigQuery, AWS - same pipeline.**

## Why Declarative Data Products?

### Before: Imperative Infrastructure

```python
# snowflake_setup.py (100+ lines)
import snowflake.connector

conn = snowflake.connector.connect(...)
cursor = conn.cursor()

cursor.execute("CREATE DATABASE IF NOT EXISTS CRYPTO_DATA")
cursor.execute("USE DATABASE CRYPTO_DATA")
cursor.execute("CREATE SCHEMA IF NOT EXISTS MARKET_DATA")
cursor.execute("""
    CREATE TABLE IF NOT EXISTS MARKET_DATA.BITCOIN_PRICES (
        PRICE_USD NUMBER(38,2),
        MARKET_CAP_USD NUMBER(38,2),
        ...
    )
""")
cursor.execute("GRANT SELECT ON TABLE MARKET_DATA.BITCOIN_PRICES TO ROLE CRYPTO_READER")
# ... 50+ more lines of SQL
```

**Problems:**
- ❌ Platform-specific code (can't reuse for BigQuery)
- ❌ Credentials hardcoded or in separate .env
- ❌ Schema evolution = manual migrations
- ❌ Governance = manual SQL GRANT statements
- ❌ No validation or dry-run capability

### After: Declarative Contract

```yaml
# contract.fluid.yaml (410 lines for EVERYTHING)
exposes:
  - binding:
      platform: snowflake
      location:
        database: CRYPTO_DATA
        schema: MARKET_DATA
        table: BITCOIN_PRICES
        
schema:
  - name: price_usd
    type: numeric
    
accessPolicy:
  grants:
    - role: crypto_reader
      permissions: ["SELECT"]
```

**Benefits:**
- ✅ Platform-agnostic (change `platform:` field)
- ✅ Environment variables templated: `{{ env.VAR }}`
- ✅ Schema evolution tracked in git
- ✅ Governance declarative: `accessPolicy.grants`
- ✅ Validate before apply: `fluid validate`

## Multi-Platform Support

**Same contract works across clouds:**

| Platform | Change Required | Commands |
|----------|----------------|----------|
| **Snowflake** | `platform: snowflake`<br>`account/database/schema/table` | `fluid apply contract.fluid.yaml` |
| **BigQuery** | `platform: bigquery`<br>`project/dataset/table` | `fluid apply contract.fluid.yaml` |
| **AWS Redshift** | `platform: redshift`<br>`cluster/database/schema/table` | `fluid apply contract.fluid.yaml` |

**Runtime script auto-adapts** by reading `binding.platform`.

## Learn More

- [QUICKSTART.md](QUICKSTART.md) - All FLUID commands
- [contract.fluid.yaml](contract.fluid.yaml) - Full contract with comments
- [Jenkinsfile](Jenkinsfile) - Production CI/CD pipeline

## Common Questions

**Q: How does `fluid apply` know which platform to deploy to?**  
A: Reads `exposes[0].binding.platform` field from contract. No `--provider` flag needed.

**Q: Can one contract deploy to multiple platforms?**  
A: Theoretically yes (multi-cloud data products), but CLI currently stops at first platform.

**Q: Where do I store credentials?**  
A: Environment variables referenced via `{{ env.SNOWFLAKE_PASSWORD }}` in contract.

**Q: How do I test changes before applying?**  
A: Run `fluid validate contract.fluid.yaml` or `fluid apply --dry-run`.

**Q: Is this production-ready?**  
A: Yes. Jenkinsfile shows full CI/CD pipeline with validation, deployment, execution, and monitoring.

---

**Built with FLUID 0.7.1** | [Documentation](https://github.com/your-org/fluid-forge)
