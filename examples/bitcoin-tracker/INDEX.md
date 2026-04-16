# Bitcoin Price Tracker - Documentation Index

**Quick Links:** [Getting Started](#getting-started) | [Airflow Setup](#airflow-setup) | [File Reference](#file-reference) | [Troubleshooting](#troubleshooting)

---

## 📚 Documentation Structure

### 🚀 Getting Started (Choose Your Path)

**Path 1: Just Want to See It Work** (5 minutes)
```bash
./validate-complete.sh  # Runs all tests
```

**Path 2: Deploy to GCP** (15 minutes)
1. Read: [README.md](README.md) - Sections 1-5
2. Set environment variables
3. Run: `fluid apply contract.fluid.yaml`

**Path 3: Setup Production Orchestration** (30 minutes)
1. Read: [AIRFLOW_INTEGRATION.md](AIRFLOW_INTEGRATION.md)
2. Run: `./airflow-quickstart.sh`
3. Access UI and trigger DAG

---

## 📖 Complete Documentation Map

### Core Documentation

| Document | Purpose | When to Use |
|----------|---------|-------------|
| [README.md](README.md) | Full example walkthrough | First-time setup, GCP deployment |
| [QUICK_REFERENCE.md](QUICK_REFERENCE.md) | Command cheatsheet | Quick command lookup |
| [AIRFLOW_INTEGRATION.md](AIRFLOW_INTEGRATION.md) | Comprehensive Airflow guide | Production orchestration setup |
| [COMPLETE_SUMMARY.md](COMPLETE_SUMMARY.md) | Full project overview | Understanding entire project |
| **This File (INDEX.md)** | Navigation hub | Finding the right documentation |

### Upstream Documentation

| Document | Location | Description |
|----------|----------|-------------|
| GCP Walkthrough | [docs/walkthrough/gcp.md](../../docs/walkthrough/gcp.md) | Step-by-step GCP deployment guide |
| FLUID CLI Reference | [docs/cli/](../../docs/cli/) | Complete CLI command reference |
| FLUID Spec | Contract schema reference |

---

## 🔧 File Reference

### Core Files

```
contract.fluid.yaml              # FLUID 0.7.1 data product contract
ingest_bitcoin_prices.py         # CoinGecko API → BigQuery ingestion
requirements.txt                 # Python dependencies
```

**Use When:**
- Deploying to GCP BigQuery
- Understanding data schema
- Testing API integration

### Airflow Files

```
airflow/dags/
├── crypto_bitcoin_prices_gcp.py      # Basic auto-generated DAG
├── bitcoin_tracker_enhanced.py       # Production DAG with monitoring
└── ingest_bitcoin_prices.py          # Copy for Airflow imports

airflow-quickstart.sh                 # Automated Airflow setup
```

**Use When:**
- Setting up automated scheduling
- Production deployment
- Need monitoring and retries

### dbt Transformations

```
dbt/
├── dbt_project.yml
└── models/
    ├── daily_price_summary.sql       # Daily price aggregations
    ├── price_trends.sql              # 7-day and 30-day moving averages
    └── schema.yml                    # Model documentation
```

**Use When:**
- Need analytics and aggregations
- Building dashboards
- Analyzing price trends

### Export Formats

```
bitcoin-tracker.odps.json        # ODPS v4.1 (9,511 bytes)
bitcoin-tracker.odcs.yaml        # ODCS v3.1.0 (121 bytes)
```

**Use When:**
- Integrating with data catalogs (Collibra, Alation)
- Implementing data contracts
- Documenting data lineage

### Scripts

```
validate-complete.sh             # Runs all 7 validation tests
airflow-quickstart.sh            # One-command Airflow setup
```

**Use When:**
- Testing before deployment
- Automating setup
- CI/CD integration

---

## 🚀 Airflow Setup

### Quick Start (Recommended)

```bash
# One command setup
./airflow-quickstart.sh

# Start Airflow
./airflow/start-all.sh

# Access UI
open http://localhost:8080
# Login: admin/admin
```

### Manual Setup

See [AIRFLOW_INTEGRATION.md](AIRFLOW_INTEGRATION.md) - Section "Deployment Options"

### What You Get

- ✅ Hourly Bitcoin price ingestion
- ✅ Automatic retries (3x with exponential backoff)
- ✅ Data quality checks
- ✅ Email alerts on failures
- ✅ Execution metrics tracking
- ✅ dbt transformation execution

---

## 🎯 Common Tasks

### Task: Deploy to GCP for First Time

**Steps:**
1. Read: [README.md](README.md) - Prerequisites section
2. Set: `GCP_PROJECT_ID`, `FLUID_PROVIDER`, `FLUID_PROJECT`
3. Run: `gcloud auth application-default login`
4. Run: `fluid apply contract.fluid.yaml`

**Time:** 10 minutes  
**References:** [README.md](README.md), [docs/walkthrough/gcp.md](../../docs/walkthrough/gcp.md)

---

### Task: Setup Automated Hourly Ingestion

**Steps:**
1. Read: [AIRFLOW_INTEGRATION.md](AIRFLOW_INTEGRATION.md) - Option 2
2. Run: `./airflow-quickstart.sh`
3. Run: `./airflow/start-all.sh`
4. Enable DAG in UI at http://localhost:8080

**Time:** 15 minutes  
**References:** [AIRFLOW_INTEGRATION.md](AIRFLOW_INTEGRATION.md)

---

### Task: Export to Data Catalog

**Steps:**
1. Generate ODPS: `fluid odps export contract.fluid.yaml --out output.json`
2. Validate: `fluid odps validate output.json`
3. Import to catalog (Collibra, Alation, DataHub)

**Time:** 5 minutes  
**References:** [QUICK_REFERENCE.md](QUICK_REFERENCE.md) - Section 6

---

### Task: Query Bitcoin Prices

**Steps:**
```bash
# Latest 10 prices
bq query --use_legacy_sql=false '
SELECT * FROM `your-project.crypto_data.bitcoin_prices`
ORDER BY timestamp DESC LIMIT 10'

# Daily summary last 30 days
bq query --use_legacy_sql=false '
SELECT * FROM `your-project.crypto_data.daily_price_summary`
ORDER BY price_date DESC LIMIT 30'
```

**Time:** 2 minutes  
**References:** [QUICK_REFERENCE.md](QUICK_REFERENCE.md) - Section 4

---

### Task: Validate Everything Works

**Steps:**
```bash
./validate-complete.sh
```

**Time:** 1 minute  
**Expected:** All 7 tests pass ✅

---

## 🐛 Troubleshooting

### Quick Fixes

| Problem | Solution | Reference |
|---------|----------|-----------|
| "Permission denied" on BigQuery | Grant BigQuery admin role | [AIRFLOW_INTEGRATION.md](AIRFLOW_INTEGRATION.md) - Troubleshooting |
| Airflow can't import module | Copy script to dags folder | [AIRFLOW_INTEGRATION.md](AIRFLOW_INTEGRATION.md) - Issue 1 |
| CoinGecko rate limit | Use enhanced DAG (has retries) | [QUICK_REFERENCE.md](QUICK_REFERENCE.md) - Common Issues |
| GCP auth error | Run `gcloud auth application-default login` | [README.md](README.md) - Step 1 |

### Detailed Troubleshooting

See [AIRFLOW_INTEGRATION.md](AIRFLOW_INTEGRATION.md) - "Monitoring & Troubleshooting" section

---

## 📊 Architecture Overview

```
┌───────────────────────────────────────────────────────────┐
│                    Apache Airflow                         │
│                  (Hourly Scheduler)                       │
├───────────────────────────────────────────────────────────┤
│  Validate → Fetch BTC → Insert → dbt → Quality → Metrics │
└───────────────────────┬───────────────────────────────────┘
                        │
                        ▼
                ┌───────────────┐
                │  GCP BigQuery │
                ├───────────────┤
                │ • Raw Prices  │ ◄─── CoinGecko API
                │ • Daily Agg   │
                │ • Trends      │
                └───────────────┘
                        │
                        ▼
                ┌───────────────┐
                │  Analytics    │
                │ • Dashboards  │
                │ • Reports     │
                └───────────────┘
```

**Full diagram:** [COMPLETE_SUMMARY.md](COMPLETE_SUMMARY.md) - Architecture section

---

## ✅ Validation Checklist

Before deploying to production, ensure:

- [ ] `./validate-complete.sh` passes all 7 tests
- [ ] GCP authentication configured
- [ ] Environment variables set (`GCP_PROJECT_ID`, etc.)
- [ ] BigQuery API enabled
- [ ] Airflow DAG tested locally
- [ ] Email alerts configured (if using Airflow)
- [ ] Data retention policies reviewed
- [ ] Cost monitoring enabled

**See:** [COMPLETE_SUMMARY.md](COMPLETE_SUMMARY.md) - Production Checklist

---

## 🎓 Learning Paths

### Beginner (Never used FLUID before)
1. Read: [README.md](README.md)
2. Run: `./validate-complete.sh`
3. Deploy: Follow README Steps 1-6
4. Query data in BigQuery

**Time:** 30 minutes

---

### Intermediate (Want production orchestration)
1. Complete Beginner path
2. Read: [AIRFLOW_INTEGRATION.md](AIRFLOW_INTEGRATION.md)
3. Setup: Run `./airflow-quickstart.sh`
4. Monitor: Access Airflow UI
5. Customize: Edit schedule or alerts

**Time:** 1 hour

---

### Advanced (Enterprise deployment)
1. Complete Intermediate path
2. Deploy: Cloud Composer setup
3. Integrate: ODPS/ODCS to data catalog
4. Build: Looker/Tableau dashboards
5. Monitor: CloudWatch/Datadog integration

**Time:** 2-3 hours

**References:** [AIRFLOW_INTEGRATION.md](AIRFLOW_INTEGRATION.md) - Cloud Composer section

---

## 📞 Need Help?

### Documentation Order
1. **Quick lookup?** → [QUICK_REFERENCE.md](QUICK_REFERENCE.md)
2. **First time?** → [README.md](README.md)
3. **Airflow setup?** → [AIRFLOW_INTEGRATION.md](AIRFLOW_INTEGRATION.md)
4. **Full overview?** → [COMPLETE_SUMMARY.md](COMPLETE_SUMMARY.md)
5. **Step-by-step GCP?** → [docs/walkthrough/gcp.md](../../docs/walkthrough/gcp.md)

### Support Resources
- FLUID Forge Docs: [docs/](../../docs/)
- FLUID CLI Help: `fluid --help`
- Airflow Docs: https://airflow.apache.org/docs/
- GCP BigQuery Docs: https://cloud.google.com/bigquery/docs

---

## 🎯 Quick Commands

### Most Common Operations

```bash
# Validate everything
./validate-complete.sh

# Deploy to GCP
FLUID_PROVIDER=gcp FLUID_PROJECT=your-id fluid apply contract.fluid.yaml

# Setup Airflow
./airflow-quickstart.sh && ./airflow/start-all.sh

# Test ingestion
python3 ingest_bitcoin_prices.py

# Query latest prices
bq query --use_legacy_sql=false 'SELECT * FROM `project.crypto_data.bitcoin_prices` ORDER BY timestamp DESC LIMIT 10'

# Export to ODPS
fluid odps export contract.fluid.yaml --out bitcoin.odps.json

# Export to ODCS
fluid odcs export contract.fluid.yaml --out bitcoin.odcs.yaml
```

---

**Last Updated:** January 21, 2026  
**FLUID Version:** 0.7.1  
**Status:** ✅ 100% Bulletproof with Airflow Integration
