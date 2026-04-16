# Bitcoin Price Tracker - Working Example

A complete, runnable example of deploying a production Bitcoin price tracking data product to Google Cloud Platform using Fluid Forge.

## 📋 Overview

This example demonstrates:
- ✅ Real-time Bitcoin price ingestion from CoinGecko API
- ✅ BigQuery deployment with time-series partitioning
- ✅ Fluid 0.7.1 schema compliance with comprehensive governance
- ✅ Using Fluid CLI for deployment (validate → plan → apply → verify)
- ✅ dbt transformations for analytics (OHLC, moving averages)
- ✅ FinOps tracking with labels and cost allocation
- ✅ Jenkins CI/CD pipeline for automated deployments
- ✅ One-command automation script

## 🚀 Quick Start (One Command)

```bash
# Set your GCP project
export GCP_PROJECT_ID="dust-labs-485011"

# Run complete example (validates, plans, deploys, tests)
./run-complete-example.sh
```

**That's it!** The script automatically:
1. ✅ Validates FLUID contract (0 errors)
2. ✅ Generates deployment plan
3. ✅ Loads fresh Bitcoin price data
4. ✅ Verifies data quality
5. ✅ Runs analytics queries
6. ✅ Shows cost tracking info

## 📚 Documentation

- **[Jenkins CI/CD Walkthrough](../../docs/walkthrough/jenkins-cicd.md)** - Complete CI/CD pipeline guide
- **[Jenkins Quick Reference](JENKINS_QUICKREF.md)** - Commands and troubleshooting
- **[Declarative Design](DECLARATIVE_DESIGN.md)** - Best practices for declarative data products
- **[Improvement Opportunities](OPPORTUNITIES.md)** - Known issues and enhancement ideas
- **[Quick Reference](QUICK_REFERENCE.md)** - Common commands and queries

## 🎯 What's Inside

### Data Resources

**Tables:**
- `bitcoin_prices` - Raw price data with 8 fields (price_usd, market_cap, volume, etc.)

**Views:**
- `daily_price_summary` - Daily OHLC (Open, High, Low, Close) + volatility (15 fields)
- `price_trends` - Moving averages (7-day, 30-day) + trend indicators (12 fields)

### Transformations

**Build 1: Data Ingestion** (`ingest_bitcoin_prices`)
- Fetch Bitcoin prices from CoinGecko API
- Load to BigQuery using batch insert (free tier compatible)
- Includes USD, EUR, GBP prices + market metrics

**Build 2: Daily Summary** (`calculate_daily_summary`)
- dbt model: `dbt/models/daily_price_summary.sql`
- Calculates OHLC, volatility, price range
- Aggregates market cap and volume

**Build 3: Price Trends** (`calculate_price_trends`)
- dbt model: `dbt/models/price_trends.sql`
- 7-day and 30-day moving averages
- Trend indicators (ABOVE_MA, BELOW_MA)

### Governance Features

**Product-Level Labels:**
```yaml
labels:
  cost-center: "engineering"
  data-classification: "public"
  billing-tag: "crypto-analytics"
```

**Expose-Level Labels:**
```yaml
labels:
  environment: production
  cost-allocation: crypto-team
  sla-tier: silver
```

**Field-Level Metadata:**
```yaml
schema:
  - name: price_usd
    sensitivity: none
    semanticType: currency
    businessName: "Bitcoin Price (USD)"
    tags: [metric, price-data]
```

## 🏗️ Prerequisites

1. **GCP Project**: Create or use existing GCP project
2. **Fluid CLI**: Already installed (v2.0.0)
3. **Python 3.8+**: For ingestion script
4. **BigQuery API**: Enabled in your GCP project

### Step 1: Setup

```bash
# Navigate to example directory
cd examples/bitcoin-tracker

# Install Python dependencies
pip install -r requirements.txt

# Authenticate with GCP
gcloud auth application-default login

# Set your project ID
export GCP_PROJECT_ID="your-project-id"
export FLUID_PROVIDER="gcp"
export FLUID_PROJECT="your-project-id"
```

### Step 2: Validate Contract

```bash
# Check contract syntax and schema compliance
fluid validate contract.fluid.yaml

# Expected output:
# ✅ Contract schema valid (Fluid 0.7.1)
# ✅ All required fields present
# ✅ Schema definitions valid
```

### Step 3: Preview Deployment (US Region)

The contract is configured for `us-central1` by default.

```bash
# Preview what will be created
fluid plan contract.fluid.yaml --provider gcp --project your-project-id

# Expected output:
# 📋 Execution Plan for GCP
# 
# Resources to CREATE:
#   + bigquery_dataset.crypto_data (location: us-central1)
#   + bigquery_table.bitcoin_prices (partitioned DAY)
#   + bigquery_view.daily_summary
#   + bigquery_view.price_trends
```

### Step 4: Deploy to GCP

```bash
# Deploy to US region (us-central1)
fluid apply contract.fluid.yaml --provider gcp --project your-project-id

# Expected output:
# ☁️ Deploying to Google Cloud Platform
# ⏳ Creating dataset 'crypto_data'... ✅ Created
# ⏳ Creating table 'bitcoin_prices'... ✅ Created
# ⏳ Creating view 'daily_summary'... ✅ Created
# ⏳ Creating view 'price_trends'... ✅ Created
# ✨ Deployment successful!
```

### Step 5: Ingest First Bitcoin Price

```bash
# Run ingestion script
python ingest_bitcoin_prices.py

# Expected output:
# 🚀 Fetching Bitcoin price for project: your-project-id
# ✅ Inserted Bitcoin price: $89,350.00 at 2024-01-20T15:30:00
#
# 📊 Summary:
#    Price USD: $89,350.00
#    Price EUR: €76,222.00
#    Price GBP: £66,490.00
```

### Step 6: Verify Deployment

```bash
# Verify deployed resources match contract
fluid verify contract.fluid.yaml --provider gcp --project your-project-id

# Expected output:
# 🔍 Verifying GCP deployment against contract
# ✅ Dataset 'crypto_data' exists (location: us-central1)
# ✅ Table 'bitcoin_prices' matches contract
# ✅ View 'daily_summary' exists
# ✅ View 'price_trends' exists
# 🎉 Deployment verified!
```

### Step 7: Query Data

```bash
# Query latest prices
bq query --use_legacy_sql=false \
  "SELECT 
    price_timestamp,
    price_usd,
    price_eur,
    market_cap_usd / 1000000000 as market_cap_billions
  FROM \`crypto_data.bitcoin_prices\`
  ORDER BY price_timestamp DESC
  LIMIT 10"
```

## 🌍 Deploy to Germany Region

### Step 1: Update Contract

Edit `contract.fluid.yaml` and change line 24:

```yaml
# Change from:
location: us-central1  # US Central (Iowa)

# To:
location: europe-west3  # Germany (Frankfurt)
```

### Step 2: Deploy

```bash
# Preview changes
fluid plan contract.fluid.yaml --provider gcp --project your-project-id

# Deploy to Germany
fluid apply contract.fluid.yaml --provider gcp --project your-project-id --region europe-west3
```

### Step 3: Migrate Data (Optional)

If you want to copy existing data from US to Germany:

```bash
# Export from US
bq extract \
  --destination_format=NEWLINE_DELIMITED_JSON \
  "your-project-id:crypto_data.bitcoin_prices" \
  "gs://your-bucket/bitcoin_prices_*.json"

# Update contract to use Germany region first, then apply

# Import to Germany
bq load \
  --source_format=NEWLINE_DELIMITED_JSON \
  --autodetect \
  "your-project-id:crypto_data.bitcoin_prices" \
  "gs://your-bucket/bitcoin_prices_*.json"
```

## 📁 Files

```
bitcoin-tracker/
├── README.md                      # This file
├── contract.fluid.yaml            # Fluid 0.7.1 contract
├── ingest_bitcoin_prices.py       # Python ingestion script
└── requirements.txt               # Python dependencies
```

## 🔧 Available Regions

Edit the `location` field in `contract.fluid.yaml`:

**US Regions:**
- `us-central1` (Iowa)
- `us-east1` (South Carolina)
- `us-west1` (Oregon)

**Europe Regions:**
- `europe-west3` (Frankfurt, Germany)
- `europe-west1` (Belgium)
- `europe-north1` (Finland)

**Asia Regions:**
- `asia-northeast1` (Tokyo)
- `asia-southeast1` (Singapore)

## 📊 Schema

The Bitcoin price table includes:

| Field | Type | Description |
|-------|------|-------------|
| `price_timestamp` | TIMESTAMP | When the price was recorded |
| `price_usd` | FLOAT64 | Bitcoin price in USD |
| `price_eur` | FLOAT64 | Bitcoin price in EUR |
| `price_gbp` | FLOAT64 | Bitcoin price in GBP |
| `market_cap_usd` | FLOAT64 | Total market capitalization |
| `volume_24h_usd` | FLOAT64 | 24-hour trading volume |
| `price_change_24h_percent` | FLOAT64 | 24-hour price change % |
| `ingestion_timestamp` | TIMESTAMP | When data was ingested |

**Partitioning**: DAY partitioning on `price_timestamp` with 90-day expiration

## 🔄 Scheduled Ingestion

### Option 1: Declarative Airflow DAG (Recommended) ⭐

**The FLUID way - generate production-ready DAGs from your contract:**

```bash
# One command to generate complete Airflow DAG
fluid generate-airflow contract.fluid.yaml \
  -o airflow/dags/bitcoin_tracker.py \
  --dag-id bitcoin_tracker \
  --schedule "0 * * * *" \
  --verbose
```

**What you get:**
- ✅ **Fully declarative** - DAG generated from contract
- ✅ **Auto-configured** - Retries, schedule, dependencies from contract
- ✅ **Provider-aware** - GCP BigQuery commands auto-generated
- ✅ **Maintainable** - Update contract, regenerate DAG
- ✅ **No boilerplate** - No 300+ lines of Python to write
- ✅ **Single source of truth** - Contract drives everything

**Deploy:**
```bash
# Local Airflow
export AIRFLOW_HOME=$PWD/airflow
airflow db init
airflow users create --username admin --password admin --role Admin
airflow webserver --port 8080 &
airflow scheduler &
```

Access Airflow UI at http://localhost:8080 (admin/admin)

📖 **Full Declarative Guide**: [docs/walkthrough/airflow-declarative.md](../../docs/walkthrough/airflow-declarative.md)

### Option 2: Manual Airflow DAG (Advanced)

For custom orchestration logic beyond what's in the contract:

📖 **Manual Airflow Integration**: [AIRFLOW_INTEGRATION.md](AIRFLOW_INTEGRATION.md)

### Option 2: Cron (Simple)

```bash
# Add to crontab (run hourly)
crontab -e

# Add this line:
0 * * * * cd /path/to/bitcoin-tracker && /usr/bin/python3 ingest_bitcoin_prices.py
```

### Option 3: Cloud Scheduler + Cloud Functions

```bash
# Deploy as Cloud Function
gcloud functions deploy bitcoin-price-ingestion \
  --runtime python310 \
  --trigger-http \
  --entry-point main \
  --source . \
  --set-env-vars GCP_PROJECT_ID=your-project-id \
  --region us-central1

# Create scheduler job (runs hourly)
gcloud scheduler jobs create http bitcoin-hourly-ingest \
  --schedule="0 * * * *" \
  --uri="https://us-central1-your-project-id.cloudfunctions.net/bitcoin-price-ingestion" \
  --http-method=GET \
  --location=us-central1
```

### Option 3: Fluid Airflow Generator

```bash
# Generate Airflow DAG
fluid scaffold-composer contract.fluid.yaml \
  --schedule "0 * * * *" \
  --output bitcoin_tracker_dag.py
```

## 💰 Cost Estimation

With hourly ingestion and 90-day retention:
- **Storage**: ~0.0004 GB = **$0.00001/month**
- **Ingestion**: Free (streaming insert)
- **Queries**: First 1 TB/month free
- **Total**: **< $0.01/month**

## 🧪 Fluid CLI Commands Reference

```bash
# Validate contract
fluid validate contract.fluid.yaml

# Preview deployment plan
fluid plan contract.fluid.yaml --provider gcp

# Deploy to GCP
fluid apply contract.fluid.yaml --provider gcp --project PROJECT_ID

# Verify deployment
fluid verify contract.fluid.yaml --provider gcp

# Visualize data lineage
fluid viz-graph contract.fluid.yaml --out lineage.png

# Run contract tests
fluid contract-tests contract.fluid.yaml

# Check system health
fluid doctor
```

## 🐛 Troubleshooting

### "Permission denied" errors

```bash
# Grant BigQuery Admin role
gcloud projects add-iam-policy-binding your-project-id \
  --member="user:your-email@example.com" \
  --role="roles/bigquery.admin"
```

### Validate your setup

```bash
# Run Fluid diagnostics
fluid doctor

# Check authentication
gcloud auth application-default print-access-token
```

### CoinGecko API rate limits

Free tier: 10-50 calls/minute. For production:
- Space out ingestion (hourly is recommended)
- Add retry logic with exponential backoff
- Consider CoinGecko Pro for higher limits

## 🧹 Cleanup

Remove all resources:

```bash
# Delete BigQuery dataset and all tables
bq rm -r -f -d your-project-id:crypto_data

# Or delete entire project
gcloud projects delete your-project-id
```

## 📚 Next Steps

1. **Add more analytics**: Extend with moving averages, volatility indicators
2. **Multi-asset tracking**: Add Ethereum, Litecoin, etc.
3. **Alerting**: Set up price movement alerts
4. **Dashboard**: Connect to Looker, Tableau, or Data Studio
5. **ML predictions**: Use BigQuery ML for price forecasting
6. **CI/CD**: Generate CI/CD pipeline with `fluid scaffold-ci`

## 🔗 Links

- [Full Documentation](../../docs/walkthrough/gcp.md)
- [Fluid CLI Reference](../../docs/cli/)
- [CoinGecko API Docs](https://www.coingecko.com/en/api/documentation)
- [BigQuery Docs](https://cloud.google.com/bigquery/docs)

---

**Built with ❤️ using Fluid Forge - Declarative Data Products for Modern Teams**

## 📊 Schema

The Bitcoin price table includes:

| Field | Type | Description |
|-------|------|-------------|
| `price_timestamp` | TIMESTAMP | When the price was recorded |
| `price_usd` | FLOAT64 | Bitcoin price in USD |
| `price_eur` | FLOAT64 | Bitcoin price in EUR |
| `price_gbp` | FLOAT64 | Bitcoin price in GBP |
| `market_cap_usd` | FLOAT64 | Total market capitalization |
| `volume_24h_usd` | FLOAT64 | 24-hour trading volume |
| `price_change_24h_percent` | FLOAT64 | 24-hour price change % |
| `ingestion_timestamp` | TIMESTAMP | When data was ingested |

**Partitioning**: DAY partitioning on `price_timestamp` with 90-day expiration

## 🔄 Scheduled Ingestion

### Using cron (Linux/Mac)

```bash
# Add to crontab (run hourly)
crontab -e

# Add this line:
0 * * * * cd /path/to/bitcoin-tracker && /usr/bin/python3 ingest_bitcoin_prices.py
```

### Using Cloud Scheduler

```bash
# Deploy as Cloud Function first
gcloud functions deploy bitcoin-price-ingestion \
  --runtime python310 \
  --trigger-http \
  --entry-point main \
  --source . \
  --set-env-vars GCP_PROJECT_ID=your-project-id \
  --region us-central1

# Create scheduler job (runs hourly)
gcloud scheduler jobs create http bitcoin-hourly-ingest \
  --schedule="0 * * * *" \
  --uri="https://us-central1-your-project-id.cloudfunctions.net/bitcoin-price-ingestion" \
  --http-method=GET \
  --location=us-central1
```

## 💰 Cost Estimation

With hourly ingestion:
- **Storage**: ~0.0004 GB (90 days × 24 hours × 200 bytes/row) = **$0.00001/month**
- **Ingestion**: Free (streaming insert)
- **Queries**: First 1 TB/month free
- **Total**: **< $0.01/month**

## 🧪 Testing

Run a quick test without deploying:

```bash
# Test CoinGecko API
python -c "
import requests
r = requests.get('https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd')
print(r.json())
"

# Test BigQuery connection
bq ls --project_id=your-project-id
```

## 🐛 Troubleshooting

### "Permission denied" errors

```bash
# Grant BigQuery Admin role
gcloud projects add-iam-policy-binding your-project-id \
  --member="user:your-email@example.com" \
  --role="roles/bigquery.admin"
```

### "Dataset already exists"

This is OK! The scripts handle existing resources gracefully.

### CoinGecko API rate limits

Free tier: 10-50 calls/minute. For production:
- Space out ingestion (hourly is plenty)
- Add retry logic with exponential backoff
- Consider CoinGecko Pro for higher limits

### Data in wrong region

Use the migration script:

```bash
./migrate-us-to-germany.sh your-project-id
```

## 🧹 Cleanup

Remove all resources:

```bash
# Delete dataset (US)
bq rm -r -f -d your-project-id:crypto_data

# Delete dataset (Germany)
bq rm -r -f -d your-project-id:crypto_data_de

# Or delete entire project
gcloud projects delete your-project-id
```

## 📚 Next Steps

1. **Add more analytics**: Extend with moving averages, volatility indicators
2. **Multi-asset tracking**: Add Ethereum, Litecoin, etc.
3. **Alerting**: Set up price movement alerts
4. **Dashboard**: Connect to Looker, Tableau, or Data Studio
5. **ML predictions**: Use BigQuery ML for price forecasting

## 🔗 Links

- [Full Documentation](../../docs/walkthrough/gcp.md)
- [CoinGecko API Docs](https://www.coingecko.com/en/api/documentation)
- [BigQuery Docs](https://cloud.google.com/bigquery/docs)
- [Fluid Forge GitHub](https://github.com/your-org/fluid-forge)

---

**Built with ❤️ using Fluid Forge - Declarative Data Products for Modern Teams**
