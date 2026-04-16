# Walkthrough: Deploy to Google Cloud Platform

**Time:** 20 minutes  
**Difficulty:** Intermediate  
**Prerequisites:** GCP account, gcloud CLI, Python 3.9+

---

## Overview

This walkthrough deploys a **production-ready Bitcoin price tracking data product** to **Google Cloud Platform** using BigQuery with real-time CoinGecko API integration.

::: tip Working Example
**Want to jump straight to code?** A complete, runnable example is available in [examples/bitcoin-tracker](../../examples/bitcoin-tracker/) with deployment scripts for both US and Germany regions!
:::

### What You'll Build

- Production BigQuery data warehouse
- Real-time Bitcoin price ingestion from CoinGecko API
- Partitioned tables for time-series optimization (us-central1)
- Scheduled hourly data pipelines
- Cost-optimized analytics platform
- Multi-region deployment capability (US → Germany)

### What You'll Learn

- GCP provider configuration
- BigQuery partitioning best practices
- API integration patterns
- Production deployment workflows
- Time-series data modeling

---

## Step 1: GCP Setup

### Create GCP Project

```bash
# Create project (or use existing)
gcloud projects create fluid-crypto-tracker \
  --name="Fluid Forge Crypto Tracker"

# Set as active project
gcloud config set project fluid-crypto-tracker

# Link billing account (required for BigQuery)
# Get billing account ID
gcloud billing accounts list

# Link it to project
gcloud billing projects link fluid-crypto-tracker \
  --billing-account=XXXXXX-XXXXXX-XXXXXX
```

::: tip Free Tier
This tutorial stays within GCP free tier limits:
- 1 TB of queries per month (free)
- 10 GB storage (free)
- CoinGecko API is free for basic usage
:::

### Enable Required APIs

```bash
gcloud services enable bigquery.googleapis.com
gcloud services enable storage.googleapis.com
gcloud services enable cloudresourcemanager.googleapis.com
gcloud services enable iam.googleapis.com
```

### Authenticate

```bash
# Authenticate with your Google account
gcloud auth application-default login

# Verify authentication
gcloud auth application-default print-access-token
```

---

## Step 2: Create API Ingestion Script

Create a Python script to fetch Bitcoin prices from CoinGecko:

### Create `ingest_bitcoin_prices.py`

```python
#!/usr/bin/env python3
"""
Bitcoin price ingestion from CoinGecko API to BigQuery
"""
import requests
from google.cloud import bigquery
from datetime import datetime
import os

def fetch_bitcoin_price():
    """Fetch current Bitcoin price from CoinGecko API"""
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {
        "ids": "bitcoin",
        "vs_currencies": "usd,eur,gbp",
        "include_market_cap": "true",
        "include_24hr_vol": "true",
        "include_24hr_change": "true",
        "include_last_updated_at": "true"
    }
    
    response = requests.get(url, params=params)
    response.raise_for_status()
    data = response.json()["bitcoin"]
    
    return {
        "price_timestamp": datetime.now().isoformat(),
        "price_usd": data["usd"],
        "price_eur": data["eur"],
        "price_gbp": data["gbp"],
        "market_cap_usd": data["usd_market_cap"],
        "volume_24h_usd": data["usd_24h_vol"],
        "price_change_24h_percent": data.get("usd_24h_change", 0.0),
        "ingestion_timestamp": datetime.now().isoformat()
    }

def insert_to_bigquery(row, project_id, dataset_id="crypto_data", table_id="bitcoin_prices"):
    """Insert Bitcoin price data into BigQuery"""
    client = bigquery.Client(project=project_id)
    table_ref = f"{project_id}.{dataset_id}.{table_id}"
    
    errors = client.insert_rows_json(table_ref, [row])
    
    if errors:
        raise Exception(f"BigQuery insert errors: {errors}")
    
    print(f"✅ Inserted Bitcoin price: ${row['price_usd']:,.2f} at {row['price_timestamp']}")

if __name__ == "__main__":
    project_id = os.getenv("GCP_PROJECT_ID", "fluid-crypto-tracker")
    
    # Fetch price
    price_data = fetch_bitcoin_price()
    
    # Insert to BigQuery
    insert_to_bigquery(price_data, project_id)
    
    print(f"📊 Market Cap: ${price_data['market_cap_usd']:,.0f}")
    print(f"📈 24h Volume: ${price_data['volume_24h_usd']:,.0f}")
```

Install dependencies:
```bash
pip install requests google-cloud-bigquery
```

---

## Step 3: Create Production Contract

Create `contract.fluid.yaml`:

```yaml
fluidVersion: "0.7.1"
kind: DataProduct
id: crypto.bitcoin_prices_gcp
name: bitcoin-prices-gcp

# Product-level tags for discovery and categorization
tags:
  - crypto
  - bitcoin
  - real-time
  - api-integration
  - time-series
  - public-data

# Product-level labels for FinOps and governance
labels:
  cost-center: "engineering"
  business-unit: "data-platform"
  data-classification: "public"
  retention-policy: "90-days"
  compliance-framework: "none"
  billing-tag: "crypto-analytics"

metadata:
  owner:
    team: data-engineering
    email: data-eng@company.com
  description: Production Bitcoin price tracking on Google Cloud Platform
  businessContext:
    domain: Financial Markets
    subdomain: Cryptocurrency Analytics
    useCases:
      - Market analysis
      - Price monitoring
      - Trading signals

exposes:
  - exposeId: bitcoin_prices_table
    kind: table
    
    # Expose-level tags for dataset categorization
    tags:
      - raw-data
      - time-series
      - high-frequency
      - non-pii
    
    # Expose-level labels for BigQuery resource tracking
    labels:
      environment: production
      data-source: coingecko-api
      update-frequency: hourly
      cost-allocation: crypto-team
      sla-tier: gold
      data-owner: data-engineering
    
    binding:
      platform: gcp
      resource:
        type: bigquery_table
        project: fluid-crypto-tracker
        dataset: crypto_data
        table: bitcoin_prices
        location: us-central1
        
        # Time-series partitioning for performance
        partitioning:
          type: time
          field: price_timestamp
          granularity: DAY
          expirationDays: 90  # Keep 90 days of history
        
        # Labels propagate to BigQuery table for cost tracking
        labels:
          environment: production
          data-source: coingecko-api
          update-frequency: hourly
          cost-center: engineering
          team: data-platform
    
    # Data governance policies
    policy:
      classification: Public  # No PII, publicly available data
      
      authz:
        readers:
          - group:data-analysts@company.com
          - group:data-scientists@company.com
          - serviceAccount:airflow@company.iam.gserviceaccount.com
        writers:
          - serviceAccount:ingestion@company.iam.gserviceaccount.com
    
    contract:
      description: "Real-time Bitcoin prices from CoinGecko API"
      
      # Contract-level tags for data quality
      tags:
        - validated
        - production-ready
      
      schema:
        fields:
          - name: price_timestamp
            type: TIMESTAMP
            mode: REQUIRED
            description: "When the price was recorded"
            sensitivity: none  # Public data
            semanticType: timestamp
            tags:
              - partition-key
              - time-series
          
          - name: price_usd
            type: FLOAT64
            mode: REQUIRED
            description: "Bitcoin price in USD"
            sensitivity: none
            semanticType: currency
            businessName: "Bitcoin Price (USD)"
            tags:
              - metric
              - price-data
            labels:
              unit: "usd"
              precision: "2-decimals"
          
          - name: price_eur
            type: FLOAT64
            mode: REQUIRED
            description: "Bitcoin price in EUR"
            sensitivity: none
            semanticType: currency
            businessName: "Bitcoin Price (EUR)"
            tags:
              - metric
              - price-data
            labels:
              unit: "eur"
          
          - name: price_gbp
            type: FLOAT64
            mode: REQUIRED
            description: "Bitcoin price in GBP"
            sensitivity: none
            semanticType: currency
            businessName: "Bitcoin Price (GBP)"
            tags:
              - metric
              - price-data
            labels:
              unit: "gbp"
          
          - name: market_cap_usd
            type: FLOAT64
            mode: REQUIRED
            description: "Total market capitalization in USD"
            sensitivity: none
            semanticType: currency
            businessName: "Market Capitalization"
            tags:
              - metric
              - market-data
            labels:
              aggregation: "sum"
          
          - name: volume_24h_usd
            type: FLOAT64
            mode: REQUIRED
            description: "24-hour trading volume in USD"
            sensitivity: none
            semanticType: currency
            businessName: "24h Trading Volume"
            tags:
              - metric
              - volume-data
            labels:
              window: "24h"
          
          - name: price_change_24h_percent
            type: FLOAT64
            mode: NULLABLE
            description: "24-hour price change percentage"
            sensitivity: none
            semanticType: percentage
            businessName: "24h Price Change"
            tags:
              - metric
              - derived
            labels:
              calculation: "percentage-change"
          
          - name: ingestion_timestamp
            type: TIMESTAMP
            mode: REQUIRED
            description: "When data was ingested into BigQuery"
            sensitivity: internal  # Operational metadata
            semanticType: timestamp
            tags:
              - metadata
              - audit-trail
  
  # Analytical views
  - exposeId: daily_price_summary
    kind: view
    binding:
      platform: gcp
      resource:
        type: bigquery_view
        project: fluid-crypto-tracker
        dataset: crypto_data
        table: daily_summary
    
    contract:
      description: "Daily Bitcoin price statistics"
      schema:
        fields:
          - name: date
            type: DATE
          - name: avg_price_usd
            type: FLOAT64
          - name: min_price_usd
            type: FLOAT64
          - name: max_price_usd
            type: FLOAT64
          - name: daily_volatility
            type: FLOAT64
          - name: total_volume_usd
            type: FLOAT64
      
      query: |
        SELECT 
          DATE(price_timestamp) as date,
          AVG(price_usd) as avg_price_usd,
          MIN(price_usd) as min_price_usd,
          MAX(price_usd) as max_price_usd,
          STDDEV(price_usd) as daily_volatility,
          SUM(volume_24h_usd) as total_volume_usd
        FROM `fluid-crypto-tracker.crypto_data.bitcoin_prices`
        GROUP BY DATE(price_timestamp)
        ORDER BY date DESC
```

::: tip Tags & Labels for Governance + FinOps
This contract showcases **multi-level tags and labels** for comprehensive governance:

**🏷️ Product-level labels** (FinOps tracking):
- `cost-center: engineering` - Charge costs to engineering budget
- `billing-tag: crypto-analytics` - Group billing across resources
- `data-classification: public` - No encryption/access restrictions needed

**📊 Expose-level labels** (Resource tracking):
- `cost-allocation: crypto-team` - Team-level cost attribution
- `sla-tier: gold` - Priority support and SLA tracking
- Labels automatically propagate to BigQuery tables for cost reporting

**🔒 Field-level sensitivity** (Data governance):
- `sensitivity: none` - Public market data (no PII)
- `sensitivity: internal` - Operational metadata (ingestion_timestamp)
- Enables automated policy enforcement and access controls

**� Policy classification**:
- `classification: Public` - Publicly available cryptocurrency data
- `authz.readers` - Control who can query the data
- `authz.writers` - Control who can insert/update data

**💰 FinOps Benefits**:
- Query `INFORMATION_SCHEMA.TABLE_STORAGE` with label filters
- Group costs by `cost-center`, `team`, or `environment`
- Track spending across data products and teams
:::

::: warning PII Data Example
For datasets with PII, use field-level sensitivity and stricter classification:
```yaml
policy:
  classification: Restricted  # Highest protection level
  
  authz:
    readers:
      - group:pii-approved-analysts@company.com  # Restricted access
    writers:
      - serviceAccount:secure-ingestion@company.iam.gserviceaccount.com

schema:
  fields:
    - name: user_email
      type: STRING
      sensitivity: pii  # Triggers access controls
      semanticType: email
      tags:
        - pii
        - restricted
      
    - name: credit_card
      type: STRING  
      sensitivity: restricted  # Highest protection
      tags:
        - pci-dss
        - encrypted
```
This enables:
- 🔐 Field-level access control via sensitivity classification
- 🚫 Role-based access enforcement (authz)
- 🎯 Automated discovery of PII fields via tags
- 📋 Compliance reporting (GDPR, CCPA, HIPAA)
:::



---

## Step 4: Validate Contract

```bash
fluid validate contract.fluid.yaml

# Expected output:
# Starting validate_contract
# Metric: validation_duration=0.017seconds
# Metric: validation_errors=0count
# Metric: validation_warnings=0count
# ✅ Valid FLUID contract (schema v0.7.1)
# Validation completed in 0.003s
# Completed validate_contract in 0.02s
```

::: tip Provider Specification
The `--provider` flag is not needed for validation. Provider is specified via environment variable `FLUID_PROVIDER` for deployment commands.
:::

---

## Step 5: Preview Deployment Plan

See what will be created before deploying:

```bash
# Set provider and project via environment variables
export FLUID_PROVIDER=gcp
export FLUID_PROJECT=fluid-crypto-tracker

fluid plan contract.fluid.yaml

# Expected output:
# ============================================================
# FLUID Execution Plan
# ============================================================
# Contract: contract.fluid.yaml
# Version: 0.7.1
# Total Actions: 6
# ============================================================
# 
# 1. schedule_build_1 (scheduleTask)
# 2. provision_bitcoin_prices_table (provisionDataset)
# 3. provision_price_trends (provisionDataset)
# 4. schedule_build_2 (scheduleTask)
# 5. schedule_build_0 (scheduleTask)
# 6. provision_daily_price_summary (provisionDataset)
# 
# ✅ Plan saved to: runtime/plan.json
```

::: tip Environment Variables
Use `FLUID_PROVIDER` and `FLUID_PROJECT` environment variables instead of command-line flags:
- `FLUID_PROVIDER=gcp` - Specifies Google Cloud Platform
- `FLUID_PROJECT=your-project-id` - Your GCP project ID
:::

---

## Step 6: Deploy to GCP!

```bash
# Ensure environment variables are set
export FLUID_PROVIDER=gcp
export FLUID_PROJECT=fluid-crypto-tracker

fluid apply contract.fluid.yaml

# Expected output:
# ☁️ Deploying to Google Cloud Platform
# Project: fluid-crypto-tracker
# 
# ⏳ Creating dataset 'crypto_data'... ✅ Created (1.2s)
# ⏳ Creating table 'bitcoin_prices'...
#    Partitioning: DAY on price_timestamp
#    Partition expiration: 90 days ✅ Created (2.1s)
# ⏳ Creating view 'daily_summary'... ✅ Created (0.6s)
# 
# ✨ Deployment successful!
# 
# 📊 Resources created in BigQuery:
#   • Dataset: fluid-crypto-tracker.crypto_data
#   • Table: bitcoin_prices (partitioned)
#   • View: daily_summary
# 
# 🔗 View in BigQuery Console:
#   https://console.cloud.google.com/bigquery?project=fluid-crypto-tracker&d=crypto_data
# 
# 💰 Estimated cost: $0.00/month (within free tier)
```

---

## Step 7: Ingest First Bitcoin Price

Run the ingestion script to load the first price data point:

```bash
# Set environment variable
export GCP_PROJECT_ID=fluid-crypto-tracker

# Run ingestion
python ingest_bitcoin_prices.py

# Expected output:
# ✅ Inserted Bitcoin price: $45,230.50 at 2024-01-16T15:30:00.123456
# 📊 Market Cap: $885,000,000,000
# 📈 24h Volume: $28,500,000,000
```

Verify in BigQuery Console:

```bash
bq query --use_legacy_sql=false \
  'SELECT * FROM `crypto_data.bitcoin_prices` ORDER BY price_timestamp DESC LIMIT 1'
```

---

## Step 8: Query Your Data in BigQuery

### Using BigQuery Console

1. Open [BigQuery Console](https://console.cloud.google.com/bigquery)
2. Navigate to your project → `crypto_data` dataset
3. Run queries:

```sql
-- Latest prices
SELECT * FROM `crypto_data.bitcoin_prices`
ORDER BY price_timestamp DESC
LIMIT 10;

-- Daily summary statistics
SELECT * FROM `crypto_data.daily_summary`
ORDER BY date DESC;

-- Price volatility analysis
SELECT 
  DATE(price_timestamp) as date,
  MIN(price_usd) as daily_low,
  MAX(price_usd) as daily_high,
  AVG(price_usd) as daily_avg,
  MAX(price_usd) - MIN(price_usd) as daily_range,
  STDDEV(price_usd) as volatility
FROM `crypto_data.bitcoin_prices`
GROUP BY DATE(price_timestamp)
ORDER BY date DESC;
```

### Using bq CLI

```bash
# Query from command line
bq query --use_legacy_sql=false \
  'SELECT 
    price_timestamp,
    price_usd,
    price_eur,
    market_cap_usd / 1000000000 as market_cap_billions
  FROM `crypto_data.bitcoin_prices`
  ORDER BY price_timestamp DESC
  LIMIT 5'

# Export to CSV
bq extract \
  --destination_format CSV \
  crypto_data.bitcoin_prices \
  gs://fluid-crypto-tracker-exports/bitcoin_prices_*.csv
```

---

## Step 9: Verify Deployment

```bash
# Verify deployment against contract
export FLUID_PROVIDER=gcp
export FLUID_PROJECT=fluid-crypto-tracker

fluid verify contract.fluid.yaml

# Expected output:
# 🔍 Verifying GCP deployment against contract
# 
# ✅ Dataset 'crypto_data' exists
#    Location: us-central1 ✓
#    Description matches ✓
# 
# ✅ Table 'bitcoin_prices' matches contract
#    Schema: 8/8 columns ✓
#    Partitioning: DAY on price_timestamp ✓
#    Partition expiration: 90 days ✓
#    Labels: environment=production, data-source=coingecko-api ✓
#    Row count: 1+ rows
# 
# ✅ View 'daily_summary' exists
#    Query definition matches ✓
# 
# 🎉 Deployment verified! Everything matches contract.
```

---

## Step 9a: Export to Open Standards (ODPS & ODCS)

Fluid Forge supports exporting your data product to industry-standard formats for interoperability and data catalog integration.

### Export to ODPS (Open Data Product Specification)

The [Open Data Product Specification](https://github.com/Open-Data-Product-Initiative) is a vendor-neutral, open-source standard for describing data products.

```bash
# Export to ODPS v4.1 format
fluid odps export contract.fluid.yaml --out bitcoin-tracker.odps.json

# Expected output:
# ✓ Exported to ODPS v4.1: bitcoin-tracker.odps.json
#   Specification: https://github.com/Open-Data-Product-Initiative/v4.1
```

The ODPS export creates a JSON file that can be:
- Imported into data catalogs (Collibra, Alation, DataHub)
- Shared with data mesh platforms
- Used for governance and compliance reporting
- Published to data marketplaces

### Export to ODCS (Open Data Contract Standard)

The [Open Data Contract Standard](https://github.com/bitol-io/open-data-contract-standard) from Bitol.io provides data contract specifications with quality and SLA definitions.

```bash
# Export to ODCS v3.1 format
fluid odcs export contract.fluid.yaml --out bitcoin-tracker.odcs.yaml

# Expected output:
# Converting FLUID contract to ODCS v3.1.0
# Exported ODCS contract: bitcoin-tracker.odcs.yaml
# ✓ Exported to bitcoin-tracker.odcs.yaml
```

The ODCS export creates a YAML file optimized for:
- Data contract management
- Schema evolution tracking
- Quality assertions and SLAs
- Integration with dbt and data observability tools

### Validate Exported Files

```bash
# Validate ODPS export
fluid odps validate bitcoin-tracker.odps.json

# Validate ODCS export  
fluid odcs validate bitcoin-tracker.odcs.yaml
```

::: tip Why Export to Open Standards?
**Portability**: Move between platforms without vendor lock-in  
**Interoperability**: Integrate with existing data governance tools  
**Compliance**: Meet industry standards for data documentation  
**Collaboration**: Share data product definitions across organizations  
:::

### Compare Formats

| Feature | FLUID (Native) | ODPS | ODCS |
|---------|---------------|------|------|
| **Purpose** | Deployment automation | Product catalog | Data contracts |
| **Format** | YAML | JSON | YAML |
| **Version** | 0.7.1 | 4.1 | 3.1.0 |
| **Best For** | Infrastructure-as-Code | Data marketplaces | Quality & SLAs |
| **Governance** | Built-in | Product-focused | Contract-focused |
| **Adoption** | Fluid Forge | Linux Foundation | Bitol.io ecosystem |

::: details View Sample ODPS Output
```json
{
  "opds_version": "1.0",
  "generator": "fluid-forge-opds-provider",
  "target_platform": "generic",
  "artifacts": {
    "schema": "https://github.com/Open-Data-Product-Initiative/v4.1",
    "version": "4.1",
    "product": {
      "details": {
        "en": {
          "name": "bitcoin-prices-gcp",
          "productID": "crypto.bitcoin_prices_gcp",
          "type": "dataset",
          "description": "Bitcoin price tracking data product"
        }
      },
      "dataAccess": [
        {
          "name": {"en": "bitcoin_prices_table"},
          "outputPortType": "API",
          "format": "JSON"
        }
      ]
    }
  }
}
```
:::

---

## Step 10: Set Up Scheduled Ingestion

Create an hourly cron job to ingest Bitcoin prices:

### Option 1: Using Cloud Scheduler + Cloud Functions

Create `main.py` for Cloud Function:

```python
import functions_framework
from ingest_bitcoin_prices import fetch_bitcoin_price, insert_to_bigquery
import os

@functions_framework.http
def main(request):
    """HTTP Cloud Function for Bitcoin price ingestion"""
    project_id = os.getenv("GCP_PROJECT_ID", "fluid-crypto-tracker")
    
    try:
        # Fetch and insert price data
        price_data = fetch_bitcoin_price()
        insert_to_bigquery(price_data, project_id)

        
        return {
            "status": "success",
            "price_usd": price_data["price_usd"],
            "timestamp": price_data["price_timestamp"]
        }, 200
    except Exception as e:
        return {"status": "error", "message": str(e)}, 500
```

Deploy:

```bash
# Deploy Cloud Function
gcloud functions deploy bitcoin-price-ingestion \
  --runtime python310 \
  --trigger-http \
  --entry-point main \
  --source . \
  --set-env-vars GCP_PROJECT_ID=fluid-crypto-tracker \
  --region us-central1 \
  --allow-unauthenticated

# Create Cloud Scheduler job (runs hourly)
gcloud scheduler jobs create http bitcoin-hourly-ingest \
  --schedule="0 * * * *" \
  --uri="https://us-central1-fluid-crypto-tracker.cloudfunctions.net/bitcoin-price-ingestion" \
  --http-method=GET \
  --location=us-central1

echo "✅ Scheduled hourly Bitcoin price ingestion"
```

### Option 2: Using Apache Airflow (Declarative)

For production orchestration with robust scheduling, monitoring, and retry capabilities, use Apache Airflow with FLUID's **declarative DAG generation**.

#### Quick Start - Declarative DAG Generation ⭐

**Generate production-ready Airflow DAG from your contract:**

```bash
# The FLUID way - fully declarative
fluid generate-airflow contract.fluid.yaml \
  -o airflow/dags/bitcoin_tracker.py \
  --dag-id bitcoin_tracker \
  --schedule "0 * * * *" \
  --verbose
```

**Output:**
```
✓ Loading contract from contract.fluid.yaml
✓ Generating Airflow DAG...
✓ DAG written to: airflow/dags/bitcoin_tracker.py
  Contract ID: crypto.bitcoin_prices_gcp
  DAG ID: bitcoin_tracker
  Schedule: 0 * * * *
  Tasks: 6 (3 provisions + 3 builds)
```

**What you get:**
- ✅ Tasks generated from `builds` array
- ✅ Dataset provisioning from `exposes` bindings
- ✅ Retry configuration from `execution.retries`
- ✅ Provider-specific commands (GCP BigQuery)
- ✅ Dependencies inferred from `outputs`
- ✅ No manual coding required!

#### Alternative: Basic Scaffold (Legacy)

For a simple 3-task DAG (validate → plan → apply):

```bash
export FLUID_PROVIDER=gcp
export FLUID_PROJECT=your-project-id

python3 -m fluid_build.cli scaffold-composer contract.fluid.yaml \
  --out-dir airflow/dags
```

**Output:**
```
✓ Generated: airflow/dags/crypto_bitcoin_prices_gcp.py
```

Start local Airflow:

```bash
# Install Airflow
pip install apache-airflow==2.8.0 \
  apache-airflow-providers-google==10.12.0

# Initialize database
airflow db init

# Create admin user
airflow users create \
  --username admin \
  --firstname Admin \
  --lastname User \
  --role Admin \
  --email admin@example.com \
  --password admin

# Start webserver (terminal 1)
airflow webserver --port 8080

# Start scheduler (terminal 2)
airflow scheduler
```

Access Airflow UI at http://localhost:8080 (admin/admin) and enable the DAG.

#### Enhanced DAG with Python Operators

For production use, the example includes an enhanced DAG with:
- Hourly Bitcoin price ingestion
- dbt transformation execution
- Data quality checks
- Email alerts on failures
- Execution metrics tracking

See the complete guide: **[Declarative Airflow Integration](/walkthrough/airflow-declarative)**

#### Deploy to Cloud Composer

Cloud Composer provides managed Airflow on GCP:

```bash
# Create Cloud Composer environment
gcloud composer environments create bitcoin-tracker-env \
  --location us-central1 \
  --image-version composer-2.6.0-airflow-2.6.3 \
  --machine-type n1-standard-2

# Upload enhanced DAG
BUCKET=$(gcloud composer environments describe bitcoin-tracker-env \
  --location us-central1 \
  --format="get(config.dagGcsPrefix)")

gsutil cp examples/bitcoin-tracker/airflow/dags/bitcoin_tracker_enhanced.py $BUCKET/dags/
gsutil cp examples/bitcoin-tracker/ingest_bitcoin_prices.py $BUCKET/dags/
```

The enhanced DAG includes:
- **Hourly Schedule:** Runs every hour at minute 0
- **Automatic Retries:** 3 retries with exponential backoff
- **Data Quality Checks:** Validates data after ingestion and transformations
- **Monitoring:** Logs execution metrics (price, market cap, volume)
- **Email Alerts:** Notifies on failures

For detailed Airflow setup, deployment options, and troubleshooting, see:
📖 **[Declarative Airflow Integration](/walkthrough/airflow-declarative)**

---

## Step 11: Monitor Costs with Labels (FinOps)

### Query Costs by Label

The labels from your FLUID contract automatically appear in BigQuery for cost tracking:

```bash
# View table with labels
bq show --format=prettyjson dust-labs-485011:crypto_data.bitcoin_prices | \
  jq '.labels'

# Expected output:
# {
#   "environment": "production",
#   "data-source": "coingecko-api",
#   "update-frequency": "hourly",
#   "cost-center": "engineering",
#   "team": "data-platform"
# }
```

### FinOps: Track Costs by Team/Product

```sql
-- Query costs grouped by cost-center label
SELECT
  table_schema,
  table_name,
  REGEXP_EXTRACT(option_value, r'cost-center:([^,}]+)') as cost_center,
  SUM(size_bytes) / POW(10,9) as size_gb,
  SUM(size_bytes) / POW(10,9) * 0.02 as monthly_storage_cost_usd
FROM `dust-labs-485011.crypto_data.INFORMATION_SCHEMA.TABLE_OPTIONS`
WHERE option_name = 'labels'
GROUP BY table_schema, table_name, cost_center;

-- Track query costs by label
SELECT
  project_id,
  user_email,
  query,
  total_bytes_processed / POW(10,12) as tb_processed,
  total_bytes_processed / POW(10,12) * 5 as query_cost_usd,  -- $5/TB
  TIMESTAMP_DIFF(end_time, start_time, SECOND) as duration_sec
FROM `region-us`.INFORMATION_SCHEMA.JOBS_BY_PROJECT
WHERE creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
  AND job_type = 'QUERY'
  AND referenced_tables LIKE '%crypto_data%'
ORDER BY query_cost_usd DESC
LIMIT 10;
```

### Cost Allocation Report

```bash
# Generate cost report grouped by labels
bq query --use_legacy_sql=false '
SELECT
  table_name,
  REGEXP_EXTRACT(option_value, r"team:([^,}]+)") as team,
  REGEXP_EXTRACT(option_value, r"cost-center:([^,}]+)") as cost_center,
  SUM(total_rows) as total_rows,
  SUM(size_bytes) / POW(10,9) as size_gb,
  SUM(size_bytes) * 0.02 / POW(10,9) as monthly_cost_usd
FROM `dust-labs-485011.crypto_data.INFORMATION_SCHEMA.TABLES` t
LEFT JOIN `dust-labs-485011.crypto_data.INFORMATION_SCHEMA.TABLE_OPTIONS` o
  ON t.table_name = o.table_name
WHERE option_name = "labels"
GROUP BY table_name, team, cost_center
'
```

### Set Up Budget Alerts with Label Filters

```bash
# Create budget filtered by cost-center label
gcloud billing budgets create \
  --billing-account=XXXXXX-XXXXXX-XXXXXX \
  --display-name="Crypto Tracker Budget (Engineering)" \
  --budget-amount=5USD \
  --threshold-rule=percent=50 \
  --threshold-rule=percent=90 \
  --filter-labels=cost-center=engineering,team=data-platform
```

::: tip FinOps Best Practices
**Labels enable powerful cost tracking:**

✅ **Chargeback**: Allocate BigQuery costs to teams/departments via `cost-center` label  
✅ **Showback**: Report spending by `team`, `environment`, or `project`  
✅ **Cost Optimization**: Identify expensive tables/queries by label  
✅ **Budget Enforcement**: Create label-based budget alerts  
✅ **Trend Analysis**: Track cost growth by product/team over time

**Storage cost calculation:**
- Storage: $0.02/GB/month (after 90 days: $0.01/GB)
- Queries: $5/TB processed
- Streaming inserts: $0.01/200 MB (free tier: 1 TB/month batch loads)

**This example costs:**
- Storage: ~$0.00001/month (4 rows = 0.0004 GB)
- Queries: ~$0.00/month (within 1 TB free tier)
:::

::: details Advanced FinOps: Automated Cost Reports
Create a scheduled query to track daily costs:

```sql
-- Save as scheduled query (runs daily)
CREATE OR REPLACE TABLE crypto_data.cost_tracking AS
SELECT
  CURRENT_DATE() as report_date,
  table_name,
  REGEXP_EXTRACT(labels, r'team:([^,}]+)') as team,
  REGEXP_EXTRACT(labels, r'cost-center:([^,}]+)') as cost_center,
  total_rows,
  size_bytes / POW(10,9) as size_gb,
  size_bytes * 0.02 / POW(10,9) as storage_cost_usd,
  LAG(size_bytes) OVER (PARTITION BY table_name ORDER BY report_date) as prev_size,
  (size_bytes - LAG(size_bytes) OVER (PARTITION BY table_name ORDER BY report_date)) 
    / POW(10,9) as daily_growth_gb
FROM `INFORMATION_SCHEMA.TABLES`
WHERE table_schema = 'crypto_data'
ORDER BY storage_cost_usd DESC;
``**Used tags & labels for governance + FinOps tracking**  
✅ **Implemented field-level sensitivity classification**  
✅ **Configured privacy policies and encryption**  
✅ **Set up cost allocation by team/cost-center**  
✅ Monitored costs and performance  
✅ Updated deployments incrementally

### 🏷️ Governance & FinOps Highlights

**Tags for Discovery & Categorization:**
- Product-level: `crypto`, `bitcoin`, `real-time`, `public-data`
- Expose-level: `raw-data`, `time-series`, `non-pii`
- Field-level: `metric`, `price-data`, `partition-key`

**Labels for Cost Tracking:**
- `cost-center: engineering` → Chargeback to engineering budget
- `team: data-platform` → Team-level spending reports
- `billing-tag: crypto-analytics` → Cross-project cost grouping
- `sla-tier: gold` → Priority and cost tracking

**Privacy & Compliance:**
- `sensitivity: none` for public data (no PII)
- `sensitivity: internal` for operational metadata
- `classification: Public` → No access restrictions needed
- `authz` controls who can read/write data
Then visualize in Looker/Data Studio with cost trend charts!
:::

---

## Step 12: Add More Analytics Views

Update `contract.fluid.yaml` to add price trend analysis:

```yaml
  # Add this to the exposes array
  - exposeId: price_trends
    kind: view
    binding:
      platform: gcp
      resource:
        type: bigquery_view
        project: fluid-crypto-tracker
        dataset: crypto_data
        table: price_trends
    
    contract:
      description: "7-day and 30-day Bitcoin price moving averages"
      schema:
        fields:
          - name: price_timestamp
            type: TIMESTAMP
          - name: price_usd
            type: FLOAT64
          - name: ma_7day
            type: FLOAT64
          - name: ma_30day
            type: FLOAT64
          - name: deviation_from_7day_ma
            type: FLOAT64
      
      query: |
        SELECT 
          price_timestamp,
          price_usd,
          AVG(price_usd) OVER (
            ORDER BY price_timestamp
            ROWS BETWEEN 167 PRECEDING AND CURRENT ROW  -- 7 days * 24 hours
          ) as ma_7day,
          AVG(price_usd) OVER (
            ORDER BY price_timestamp
            ROWS BETWEEN 719 PRECEDING AND CURRENT ROW  -- 30 days * 24 hours
          ) as ma_30day,
          price_usd - AVG(price_usd) OVER (
            ORDER BY price_timestamp
            ROWS BETWEEN 167 PRECEDING AND CURRENT ROW
          ) as deviation_from_7day_ma
        FROM `fluid-crypto-tracker.crypto_data.bitcoin_prices`
        ORDER BY price_timestamp DESC
```

Redeploy to add the new view:

```bash
fluid apply contract.fluid.yaml --provider gcp

# Only the new view is created - existing resources unchanged!
# ⏳ Creating view 'price_trends'... ✅ Created (0.7s)
# 
# ✨ Deployment successful! (1 resource added)
```

Query the new view:

```sql
SELECT 
  price_timestamp,
  price_usd,
  ma_7day,
  ma_30day,
  deviation_from_7day_ma
FROM `crypto_data.price_trends`
WHERE price_timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
ORDER BY price_timestamp DESC;
```

---

## What You've Learned

✅ Deployed production Bitcoin tracker to GCP  
✅ Integrated real-time CoinGecko API data  
✅ Configured BigQuery with time-series partitioning  
✅ Created analytical views for price trends  
✅ Set up hourly automated ingestion  
✅ Monitored costs and performance  
✅ Updated deployments incrementally  

---

## Next Steps

### 🤖 Enhanced Analytics

Add more crypto assets:

```yaml
# Extend contract to track Ethereum, Litecoin, etc.
exposes:
  - exposeId: ethereum_prices_table
    kind: table
    binding:
      platform: gcp
      resource:
        type: bigquery_table
        dataset: crypto_data
        table: ethereum_prices
```

### 📊 BI Dashboards

Connect Looker, Tableau, or Google Data Studio:
- Dataset: `fluid-crypto-tracker.crypto_data`
- Tables: `bitcoin_prices`, views: `daily_summary`, `price_trends`
- Credentials: Service account with BigQuery Data Viewer role

### 🔔 Price Alerts

Create alerts for price movements:

```sql
-- Find significant price changes
SELECT 
  price_timestamp,
  price_usd,
  price_change_24h_percent
FROM `crypto_data.bitcoin_prices`
WHERE ABS(price_change_24h_percent) > 5.0  -- >5% change
ORDER BY price_timestamp DESC;
```

### 🧪 ML Predictions

Use BigQuery ML for price forecasting:

```sql
CREATE MODEL `crypto_data.bitcoin_price_forecast`
OPTIONS(
  model_type='ARIMA_PLUS',
  time_series_timestamp_col='price_timestamp',
  time_series_data_col='price_usd'
) AS
SELECT 
  price_timestamp,
  price_usd
FROM `crypto_data.bitcoin_prices`;
```

---

## Troubleshooting

### "Permission denied" errors

Grant yourself BigQuery Admin role:
```bash
gcloud projects add-iam-policy-binding fluid-crypto-tracker \
  --member="user:YOUR_EMAIL@example.com" \
  --role="roles/bigquery.admin"
```

### "Dataset already exists"

Fluid Forge is idempotent. Re-running is safe:
```bash
fluid apply contract.fluid.yaml --provider gcp
# Will update only changed resources
```

### CoinGecko API rate limits

Free tier: 10-50 calls/minute. For production:
- Upgrade to CoinGecko Pro API
- Implement exponential backoff
- Cache responses locally

### Slow queries

Optimize with partitioning:
```sql
-- ✅ Good: Partition filter
SELECT * FROM `crypto_data.bitcoin_prices`
WHERE price_timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY);

-- ❌ Bad: Full table scan
SELECT * FROM `crypto_data.bitcoin_prices`
WHERE price_usd > 40000;
```

---

## Clean Up (Optional)

To avoid any charges, delete everything:

```bash
# Delete BigQuery dataset and all tables
bq rm -r -f -d fluid-crypto-tracker:crypto_data

# Delete Cloud Function
gcloud functions delete bitcoin-price-ingestion --region us-central1

# Delete Cloud Scheduler job
gcloud scheduler jobs delete bitcoin-hourly-ingest --location us-central1

# Delete project (removes everything)
gcloud projects delete fluid-crypto-tracker
```

---

## 🎉 Congratulations!

You've successfully deployed a **production-grade Bitcoin price tracking data product** to Google Cloud Platform using Fluid Forge!

**What's different from manual BigQuery setup?**
- ✅ Declarative YAML vs 100+ lines of Python
- ✅ Built-in validation and schema enforcement
- ✅ Automatic partition management
- ✅ Drift detection
- ✅ Version control friendly
- ✅ Reproducible deployments

**Production-ready features:**
- ⚡ Time-series partitioning (90-day retention)
- 📊 Real-time API integration
- 💰 Cost-optimized storage (<$0.01/month)
- 🔄 Hourly automated ingestion
- 📈 Analytical views and trends

**Ready for more?**
- [CLI Reference](/cli/) - Master all Fluid Forge commands
- [GCP Provider Guide](/providers/gcp) - Deep dive into GCP features
- [Local Walkthrough](/walkthrough/local) - Test locally with DuckDB first
- [Blueprints](/advanced/blueprints) - Pre-built templates

---

*Built with ❤️ using Fluid Forge - Declarative Data Products for Modern Teams*
