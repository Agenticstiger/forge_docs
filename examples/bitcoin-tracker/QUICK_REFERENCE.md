# Bitcoin Tracker - Quick Command Reference

## Environment Setup

```bash
# Set environment variables (required for GCP operations)
export FLUID_PROVIDER=gcp
export FLUID_PROJECT=your-project-id
export GCP_PROJECT_ID=your-project-id

# Authenticate with GCP
gcloud auth application-default login
```

## Core Commands

### Validate Contract
```bash
fluid validate contract.fluid.yaml
```
Validates YAML syntax and schema compliance (FLUID 0.7.1)

### Generate Execution Plan
```bash
fluid plan contract.fluid.yaml
```
Shows what resources will be created/updated without making changes

### Deploy to GCP
```bash
fluid apply contract.fluid.yaml
```
Creates/updates BigQuery datasets, tables, and views

### Verify Deployment
```bash
fluid verify contract.fluid.yaml
```
Confirms deployed resources match contract specification

## Data Ingestion

### Run Once
```bash
python3 ingest_bitcoin_prices.py
```
Fetches current Bitcoin price and inserts into BigQuery

### Test API Only (no BigQuery)
```bash
python3 -c "
from ingest_bitcoin_prices import fetch_bitcoin_price
data = fetch_bitcoin_price()
print(f'BTC: \${data[\"price_usd\"]:,.2f}')
"
```

## Export to Open Standards

### ODPS (Open Data Product Specification)
```bash
# Export to ODPS v4.1 JSON
fluid odps export contract.fluid.yaml --out bitcoin-tracker.odps.json

# Validate ODPS file
fluid odps validate bitcoin-tracker.odps.json

# Get ODPS info
fluid odps info
```

### ODCS (Open Data Contract Standard)
```bash
# Export to ODCS v3.1 YAML
fluid odcs export contract.fluid.yaml --out bitcoin-tracker.odcs.yaml

# Validate ODCS file
fluid odcs validate bitcoin-tracker.odcs.yaml

# Get ODCS info
fluid odcs info
```

## Query Data in BigQuery

### Using bq CLI
```bash
# Latest prices
bq query --use_legacy_sql=false \
  'SELECT * FROM `crypto_data.bitcoin_prices` 
   ORDER BY price_timestamp DESC 
   LIMIT 10'

# Daily summary
bq query --use_legacy_sql=false \
  'SELECT * FROM `crypto_data.daily_price_summary` 
   ORDER BY date DESC'

# Export to CSV
bq extract \
  --destination_format CSV \
  crypto_data.bitcoin_prices \
  gs://your-bucket/bitcoin_prices_*.csv
```

### Using Python
```python
from google.cloud import bigquery

client = bigquery.Client(project='your-project-id')

query = """
    SELECT price_timestamp, price_usd, market_cap_usd
    FROM `crypto_data.bitcoin_prices`
    ORDER BY price_timestamp DESC
    LIMIT 100
"""

df = client.query(query).to_dataframe()
print(df.head())
```

## Advanced Operations

### Check Contract Diff
```bash
# Show what changed between local and deployed
fluid diff contract.fluid.yaml
```

### Render Infrastructure Code
```bash
# Generate Terraform/CloudFormation equivalent
fluid render contract.fluid.yaml --format terraform
```

### Generate dbt Models
```bash
# Create dbt models from contract
fluid generate-dbt contract.fluid.yaml --output ./dbt/models
```

## Monitoring & Troubleshooting

### Check BigQuery Costs
```bash
# View recent jobs
bq ls -j --all --max_results 10

# Calculate storage cost
bq show --format=prettyjson crypto_data.bitcoin_prices | \
  jq '.numBytes / 1024 / 1024 / 1024 | . * 0.02'
```

### View Logs
```bash
# Fluid CLI logs (if enabled)
tail -f ~/.fluid/logs/fluid.log

# GCP Cloud Logging
gcloud logging read "resource.type=bigquery_dataset" --limit 50
```

### Common Issues

**Problem**: "Permission denied" errors  
**Solution**:
```bash
gcloud projects add-iam-policy-binding your-project-id \
  --member="user:your-email@example.com" \
  --role="roles/bigquery.admin"
```

**Problem**: "Dataset already exists"  
**Solution**: Fluid is idempotent - re-running is safe
```bash
fluid apply contract.fluid.yaml  # Updates only changed resources
```

**Problem**: CoinGecko API rate limit  
**Solution**: Add retry logic or use caching
```python
import time
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

session = requests.Session()
retry = Retry(total=3, backoff_factor=1)
adapter = HTTPAdapter(max_retries=retry)
session.mount('https://', adapter)

response = session.get(url, params=params)
```

---

## 7. Airflow Orchestration

### Generate Airflow DAG (Declarative) ⭐

```bash
# Generate production DAG from contract (RECOMMENDED)
fluid generate-airflow contract.fluid.yaml \
  -o airflow/dags/bitcoin_tracker.py \
  --dag-id bitcoin_tracker \
  --schedule "0 * * * *" \
  --verbose

# What it does:
# ✓ Reads contract declaratively
# ✓ Generates tasks for each build
# ✓ Sets up retries from contract
# ✓ Creates provider-specific commands
# ✓ Configures dependencies automatically
```

### Generate Basic DAG (Legacy)

```bash
# Basic 3-task DAG (validate → plan → apply)
export FLUID_PROVIDER=gcp
export FLUID_PROJECT=your-project-id

python3 -m fluid_build.cli scaffold-composer contract.fluid.yaml \
  --out-dir airflow/dags

# Output: airflow/dags/crypto_bitcoin_prices_gcp.py
```

### Quick Setup

```bash
# Run automated setup
./airflow-quickstart.sh

# Or manual setup:
pip install apache-airflow==2.8.0 apache-airflow-providers-google==10.12.0
airflow db init
airflow users create --username admin --password admin --role Admin \
  --firstname Admin --lastname User --email admin@example.com
```

### Start Airflow

```bash
# Option 1: All services (recommended for testing)
./airflow/start-all.sh

# Option 2: Separate terminals
# Terminal 1:
airflow webserver --port 8080

# Terminal 2:
airflow scheduler
```

### Access Airflow UI

```
URL: http://localhost:8080
Username: admin
Password: admin
```

### Airflow CLI Commands

```bash
# List all DAGs
airflow dags list

# Test DAG (dry run)
airflow dags test crypto_bitcoin_prices_gcp 2024-01-21

# Trigger DAG manually
airflow dags trigger crypto_bitcoin_prices_gcp

# List DAG runs
airflow dags list-runs -d crypto_bitcoin_prices_gcp

# View task logs
airflow tasks logs crypto_bitcoin_prices_gcp validate 2024-01-21

# Pause/unpause DAG
airflow dags pause crypto_bitcoin_prices_gcp
airflow dags unpause crypto_bitcoin_prices_gcp
```

### Cloud Composer Deployment

```bash
# Create environment
gcloud composer environments create bitcoin-tracker-env \
  --location us-central1 \
  --image-version composer-2.6.0-airflow-2.6.3

# Upload DAG
BUCKET=$(gcloud composer environments describe bitcoin-tracker-env \
  --location us-central1 \
  --format="get(config.dagGcsPrefix)")

gsutil cp airflow/dags/bitcoin_tracker_enhanced.py $BUCKET/dags/
gsutil cp ingest_bitcoin_prices.py $BUCKET/dags/
```

### Schedule Options

```python
# Hourly at minute 0
schedule="0 * * * *"

# Every 15 minutes
schedule="*/15 * * * *"

# Daily at 2 AM UTC
schedule="0 2 * * *"

# Every Monday at 9 AM
schedule="0 9 * * 1"
```

📖 **Full Airflow Guide**: [AIRFLOW_INTEGRATION.md](AIRFLOW_INTEGRATION.md)

---

## 8. Clean Up

### Delete BigQuery Resources
```bash
# Delete dataset and all tables
bq rm -r -f -d your-project-id:crypto_data
```

### Delete Entire Project
```bash
gcloud projects delete your-project-id
```

## Additional Resources

- **Full Walkthrough**: [docs/walkthrough/gcp.md](../../docs/walkthrough/gcp.md)
- **Contract Schema**: [FLUID 0.7.1 Spec](https://github.com/fluid-forge/fluid-spec)
- **ODPS Spec**: [v4.1](https://github.com/Open-Data-Product-Initiative/v4.1)
- **ODCS Spec**: [v3.1](https://github.com/bitol-io/open-data-contract-standard)

## Quick Validation Script

Run all validations at once:
```bash
./validate-complete.sh
```

This script validates:
1. ✅ Contract syntax
2. ✅ API integration
3. ✅ Execution plan generation
4. ✅ ODPS export
5. ✅ ODCS export
6. ✅ File validation
7. ✅ Python dependencies
