# Bitcoin Price Tracker - Quick Reference

## 🚀 5-Minute Quickstart (Snowflake)

```bash
# 1. Set environment variables
export SNOWFLAKE_ACCOUNT=your_account
export SNOWFLAKE_USER=your_user
export SNOWFLAKE_PASSWORD=your_password
export SNOWFLAKE_WAREHOUSE=your_warehouse
export SNOWFLAKE_ROLE=your_role

# 2. Validate contract
fluid validate contract.fluid.yaml

# 3. Deploy infrastructure (creates database/schema/table)
fluid apply contract.fluid.yaml

# 4. Install dependencies
pip install -r requirements-snowflake.txt

# 5. Ingest data
python3 runtime/ingest.py

# 6. Verify (using Python)
python3 -c "
import snowflake.connector, os
conn = snowflake.connector.connect(
    account=os.environ['SNOWFLAKE_ACCOUNT'],
    user=os.environ['SNOWFLAKE_USER'],
    password=os.environ['SNOWFLAKE_PASSWORD'],
    warehouse=os.environ['SNOWFLAKE_WAREHOUSE'],
    database='CRYPTO_DATA',
    schema='MARKET_DATA',
    role=os.environ['SNOWFLAKE_ROLE']
)
cursor = conn.cursor()
cursor.execute('SELECT price_usd, market_cap_usd, ingestion_timestamp FROM BITCOIN_PRICES ORDER BY ingestion_timestamp DESC LIMIT 5')
for row in cursor:
    print(f'BTC: \${row[0]:,.2f}, Market Cap: \${row[1]:,.0f}, Time: {row[2]}')
"
```

## 📋 Essential Commands

### Validation

```bash
# Basic validation
fluid validate contract.fluid.yaml

# Verbose output (shows sovereignty checks, governance policies)
fluid validate contract.fluid.yaml --verbose
```

### Infrastructure Deployment

```bash
# Deploy to Snowflake (auto-detected from contract)
fluid apply contract.fluid.yaml

# Dry-run (preview without executing)
fluid apply contract.fluid.yaml --dry-run
```

**What it creates:**
- Database: `CRYPTO_DATA`
- Schema: `MARKET_DATA`
- Table: `BITCOIN_PRICES` (9 columns)
- Grants: Roles from `accessPolicy.grants`

### Data Ingestion

```bash
# Run ingestion script (platform-agnostic)
python3 runtime/ingest.py
```

**What it does:**
1. Reads `contract.fluid.yaml` to detect platform (`snowflake`)
2. Fetches Bitcoin price from CoinGecko API
3. Transforms to contract schema
4. Loads to Snowflake table

### Multi-Modal Deployment

```bash
# Generate Airflow DAG from contract
fluid generate-airflow contract.fluid.yaml \
  --out dags/bitcoin_tracker_dag.py \
  --dag-id bitcoin_price_tracker \
  --schedule '@hourly'

# Export to Open Data Product Specification (ODPS)
fluid odps export contract.fluid.yaml --out contract.odps.json

# Export to Open Data Contract Standard (ODCS)
fluid odcs export contract.fluid.yaml --out contract.odcs.yaml
```

## 🔍 Verification

### Query Data (Python)

```python
import snowflake.connector
import os

conn = snowflake.connector.connect(
    account=os.environ['SNOWFLAKE_ACCOUNT'],
    user=os.environ['SNOWFLAKE_USER'],
    password=os.environ['SNOWFLAKE_PASSWORD'],
    warehouse=os.environ['SNOWFLAKE_WAREHOUSE'],
    database='CRYPTO_DATA',
    schema='MARKET_DATA',
    role=os.environ['SNOWFLAKE_ROLE']
)

cursor = conn.cursor()

# Latest price
cursor.execute("""
    SELECT price_usd, price_change_24h, ingestion_timestamp 
    FROM BITCOIN_PRICES 
    ORDER BY ingestion_timestamp DESC 
    LIMIT 1
""")
row = cursor.fetchone()
print(f"Latest BTC Price: ${row[0]:,.2f} ({row[1]:+.2f}%) at {row[2]}")

# Count rows
cursor.execute("SELECT COUNT(*) FROM BITCOIN_PRICES")
total = cursor.fetchone()[0]
print(f"Total records: {total}")

conn.close()
```

### Check Table Structure

```python
cursor.execute("""
    SELECT column_name, data_type 
    FROM CRYPTO_DATA.INFORMATION_SCHEMA.COLUMNS 
    WHERE table_name = 'BITCOIN_PRICES' 
    ORDER BY ordinal_position
""")

for col in cursor:
    print(f"{col[0]:30} {col[1]}")
```

## 🎯 CI/CD with Jenkins

### Trigger Pipeline

```bash
# Via Jenkins UI
http://localhost:8082/job/bitcoin-price-tracker-snowflake/build

# Via curl
curl -X POST http://localhost:8082/job/bitcoin-price-tracker-snowflake/build \
  --user admin:$(cat /path/to/secret-file)
```

### Pipeline Stages

The [Jenkinsfile](Jenkinsfile) demonstrates:

1. **Validate** - Check contract syntax and governance
2. **Deploy** - Apply infrastructure (database/schema/table)
3. **Execute** - Run ingestion script
4. **Generate DAG** - Create Airflow DAG
5. **Export** - Convert to ODPS/ODCS formats

**Key insight:** Same pipeline works for Snowflake, BigQuery, AWS by changing `binding.platform` in contract.

## 💡 Common Tasks

### Monitor Data Freshness

```sql
-- Last ingestion time
SELECT MAX(ingestion_timestamp) as latest_ingestion
FROM CRYPTO_DATA.MARKET_DATA.BITCOIN_PRICES;

-- Recent price changes
SELECT 
    price_timestamp,
    price_usd,
    price_change_24h,
    ingestion_timestamp
FROM CRYPTO_DATA.MARKET_DATA.BITCOIN_PRICES
ORDER BY ingestion_timestamp DESC
LIMIT 10;
```

### Troubleshooting

```bash
# Check FLUID version
fluid --version

# Test Snowflake connectivity
python3 -c "
import snowflake.connector, os
conn = snowflake.connector.connect(
    account=os.environ['SNOWFLAKE_ACCOUNT'],
    user=os.environ['SNOWFLAKE_USER'],
    password=os.environ['SNOWFLAKE_PASSWORD'],
    warehouse=os.environ['SNOWFLAKE_WAREHOUSE'],
    role=os.environ['SNOWFLAKE_ROLE']
)
print(f'Connected to Snowflake: {conn.account}')
conn.close()
"

# Validate contract syntax
fluid validate contract.fluid.yaml --verbose

# Check Python script syntax
python3 -m py_compile runtime/ingest.py
```

### Environment Setup

Create `.env` file (from `.env.example`):

```bash
SNOWFLAKE_ACCOUNT=your_account
SNOWFLAKE_USER=your_user
SNOWFLAKE_PASSWORD=your_password
SNOWFLAKE_WAREHOUSE=your_warehouse
SNOWFLAKE_ROLE=your_role
```

Load environment:

```bash
export $(cat .env | xargs)
```

## 🔒 Governance Features

### Data Sovereignty

From `contract.fluid.yaml`:

```yaml
sovereignty:
  jurisdiction: "EU"              # Must be in EU
  dataResidency: true             # No cross-border transfer
  allowedRegions:
    - eu-central-1                # Snowflake EU regions only
  regulatoryFramework:
    - GDPR                        # GDPR compliance enforced
  enforcementMode: advisory       # Warn on violations (or "strict" to block)
```

### Access Control

```yaml
accessPolicy:
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

**Applied automatically during `fluid apply`** - no manual GRANT statements!

### Privacy Controls

```yaml
privacy:
  rowLevelSecurity:
    enabled: true
    policy: "FILTER TO LAST 30 DAYS"  # Auto-applied
    
  columnRestrictions:
    - role: intern
      deniedColumns: [market_cap_usd, volume_24h_usd]  # Hidden columns
```

## 📚 File Structure

```
bitcoin-price-tracker-0.7.1-snowflake/
├── contract.fluid.yaml          # THE contract (410 lines)
├── runtime/
│   └── ingest.py                # Platform-agnostic runtime (454 lines)
├── requirements-snowflake.txt   # Dependencies
├── .env.example                 # Environment template
├── Jenkinsfile                  # CI/CD pipeline (23KB)
├── README.md                    # Full documentation
└── QUICKSTART.md                # This file
```

**Total infrastructure code: 0 lines** - everything declarative in the contract!

## 🎓 Key Concepts

### Declarative vs Imperative

| Imperative (Traditional) | Declarative (FLUID) |
|-------------------------|---------------------|
| Write SQL scripts | Declare schema in YAML |
| Write Terraform/CloudFormation | Contract auto-deploys |
| Hardcode credentials | Reference `{{ env.VAR }}` |
| Manual GRANT statements | Declare `accessPolicy.grants` |
| Platform-specific code | Change `platform:` field |

### Platform Auto-Detection

```yaml
# contract.fluid.yaml
exposes:
  - binding:
      platform: snowflake    # ← fluid apply reads this
      location:
        account: "{{ env.SNOWFLAKE_ACCOUNT }}"
        database: CRYPTO_DATA
        schema: MARKET_DATA
        table: BITCOIN_PRICES
```

**No `--provider` flag needed** - `fluid apply` detects from contract.

### Multi-Platform Support

**Same contract, different platforms:**

```yaml
# Snowflake version
platform: snowflake
location:
  account: "{{ env.SNOWFLAKE_ACCOUNT }}"
  database: CRYPTO_DATA
  schema: MARKET_DATA
  table: BITCOIN_PRICES

# BigQuery version (just change these fields)
platform: bigquery
location:
  project: "{{ env.GCP_PROJECT }}"
  dataset: crypto_data
  table: bitcoin_prices
```

**Runtime script auto-adapts** by reading `binding.platform`.

## 🆘 Need Help?

- **Full Documentation:** See [README.md](README.md)
- **Contract Reference:** View [contract.fluid.yaml](contract.fluid.yaml) with inline comments
- **CI/CD Example:** Check [Jenkinsfile](Jenkinsfile)
- **Python Dependencies:** See [requirements-snowflake.txt](requirements-snowflake.txt)

## 📖 Next Steps

1. **Customize contract** - Edit schema, governance, sovereignty rules
2. **Add transformations** - Modify `runtime/ingest.py` for your data sources
3. **Set up CI/CD** - Use Jenkinsfile as template
4. **Generate Airflow DAG** - Run `fluid generate-airflow` for production scheduling
5. **Export to standards** - Convert to ODPS/ODCS for tool interoperability

---

**Built with FLUID 0.7.1** | **Declarative Data Products** | **Multi-Platform Ready**
