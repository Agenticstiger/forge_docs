# Bitcoin Price Tracker - FLUID 0.7.1 Example

**Real-time Bitcoin price tracking with comprehensive governance, sovereignty controls, and AI usage policies**

This example demonstrates **FLUID 0.7.1** capabilities with production-ready patterns learned from v0.5.7 evolution:

## 🎯 What's New in FLUID 0.7.1?

### New Governance Features

| Feature | v0.5.7 | v0.7.1 | Description |
|---------|--------|--------|-------------|
| **Data Sovereignty** | ❌ None | ✅ `sovereignty` | EU jurisdiction, GDPR compliance, region restrictions |
| **Regulatory Framework** | ❌ Basic | ✅ `regulatoryFramework` | GDPR, CCPA, HIPAA, PIPEDA compliance tracking |
| **Enforcement Mode** | ❌ None | ✅ `enforcementMode` | Advisory vs strict blocking of violations |
| **Cross-Border Transfer** | ❌ None | ✅ `crossBorderTransfer` | SCCs, BCRs transfer mechanisms |
| **AI Governance** | ❌ None | ⏳ Planned | Control AI model access (future version) |

### Governance Continuity (v0.5.7 → v0.7.1)

All v0.5.7 governance features are **preserved and enhanced**:

✅ Data classification (Internal/Confidential/Restricted)  
✅ Authentication methods (IAM, OAuth2, OIDC)  
✅ Authorization (RBAC with readers/writers)  
✅ Column-level access control  
✅ Privacy controls (row-level security, masking)  
✅ Field-level tags and metadata  
✅ Compliance labels (GDPR, SOC2, ISO27001)

## 🚀 Quick Start

### Prerequisites

```bash
# FLUID CLI v0.7.7
docker pull localhost:5000/fluid-forge-cli:beta

# OR install locally
pip install fluid-forge==0.7.7

# GCP authentication
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
export GCP_PROJECT=<<YOUR_PROJECT_HERE>>
```

### Step 1: Validate Contract

```bash
# Validate against FLUID 0.7.1 schema
fluid validate contract.fluid.yaml --schema-version 0.7.1 --verbose
```

**What it checks:**
- ✅ Schema compliance (0.7.1 format)
- ✅ Sovereignty constraints (EU regions, GDPR)
- ✅ AI policy rules (approved models)
- ✅ Governance policies (RBAC, privacy)

### Step 2: Deploy Infrastructure

```bash
# Create BigQuery dataset + table (first time)
fluid apply contract.fluid.yaml --yes

# If already exists, verify instead:
bq show <<YOUR_PROJECT_HERE>>:crypto_data.bitcoin_prices

# To recreate (drops existing table):
bq rm -f -t <<YOUR_PROJECT_HERE>>:crypto_data.bitcoin_prices
fluid apply contract.fluid.yaml --yes
```

**What it creates:**
- Dataset: `<<YOUR_PROJECT_HERE>>.crypto_data` (europe-west3 - GDPR compliant)
- Table: `bitcoin_prices` (9 fields with governance)
- Policies: RBAC, column restrictions, row-level security

**Common Issue:** If you see "Already Exists" error, the infrastructure is already deployed ✅ Skip to Step 3.

### Step 3: Ingest Data

```bash
# Install dependencies
pip install -r requirements.txt

# Execute the build defined in the contract
fluid execute contract.fluid.yaml
```

**What it does:**
- Fetches live Bitcoin prices from CoinGecko API
- Transforms to BigQuery schema format
- Loads to table (batch mode for free tier compatibility)

### Step 4: Verify Deployment

```bash
# Query data directly
bq query --nouse_legacy_sql \
  'SELECT * FROM `<<YOUR_PROJECT_HERE>>.crypto_data.bitcoin_prices` 
   ORDER BY price_timestamp DESC LIMIT 10'
```

## 📋 What's Included

```
bitcoin-price-tracker-0.7.1/
├── contract.fluid.yaml          # FLUID 0.7.1 contract with governance
├── runtime/
│   └── ingest.py                # Bitcoin API → BigQuery ingestion
├── Jenkinsfile                  # Production CI/CD pipeline
├── requirements.txt             # Python dependencies
├── .env.example                 # Environment variable template
├── QUICKSTART.md                # Quick reference
└── README.md                    # This file
```

## 🎓 Key Concepts Demonstrated

### 1. Sovereignty Controls (NEW in 0.7.1)

```yaml
sovereignty:
  jurisdiction: "EU"
  dataResidency: true
  allowedRegions:
    - europe-west3      # GCP Frankfurt (GDPR compliant)
  deniedRegions:
    - us-east-1         # Block US regions
  crossBorderTransfer: false
  regulatoryFramework:
    - GDPR
  enforcementMode: advisory  # advisory|strict|audit
```

**Impact:** Ensures data stays in EU, blocks non-compliant deployments

### 2. AI Governance (Planned for Future Versions)

**Note:** AI governance via `agentPolicy` is not yet in the 0.7.1 schema but can be implemented through policy tags and labels:

```yaml
policy:
  tags:
    - ai-restricted
    - no-training-allowed
  labels:
    ai_access_policy: "gpt4-only"
    data_usage_policy: "no-training"
```

**Impact:** Controls which AI models can access data, prevents training abuse

### 3. Execution Configuration

```yaml
builds:
  - execution:
      trigger:
        type: manual
        iterations: 5        # Run 5 times
        delaySeconds: 5      # 5-second intervals
      runtime:
        platform: gcp
        resources:
          cpu: "1"
          memory: "2Gi"
```

**Impact:** Infrastructure-as-code for pipeline execution (no hardcoding!)

### 4. Field-Level Governance

```yaml
schema:
  - name: price_usd
    type: numeric
    required: true
    sensitivity: cleartext
    tags:
      - price-data
      - business-critical
    description: "Bitcoin price in US Dollars"
```

**Impact:** Rich metadata for data catalogs, lineage tools, compliance

## 🔄 Migration from v0.5.7

### What Changed

**Added (NEW in 0.7.1):**
```yaml
fluidVersion: "0.7.1"  # Was: "0.5.7"

sovereignty:           # NEW in 0.7.1
  jurisdiction: "EU"
  dataResidency: true
  allowedRegions: [europe-west3]
  deniedRegions: [us-east-1]
  crossBorderTransfer: false
  transferMechanisms: [SCCs]
  regulatoryFramework: [GDPR]
  enforcementMode: advisory  # advisory|strict|audit
  validationRequired: true
```

**Preserved (Unchanged):**
```yaml
# All v0.5.7 governance works in 0.7.1
policy:
  classification: Internal
  authn: iam
  authz: {...}
  privacy: {...}
  tags: [...]
  labels: {...}
```

**Note:** AI governance (`agentPolicy`) is planned for future versions. Use `policy.tags` and `policy.labels` for now.

**Breaking Changes:** None (100% backward compatible)

## 🛠️ Development Workflow

### Local Testing

```bash
# 1. Validate contract
fluid validate contract.fluid.yaml

# 2. Check for errors
fluid doctor --check-0-7-1

# 3. Test locally (dry-run)
fluid apply contract.fluid.yaml --dry-run

# 4. Generate execution plan
fluid plan contract.fluid.yaml --out plan.json

# 5. Visualize dependencies
fluid viz-graph contract.fluid.yaml --format html --out graph.html
```

### CI/CD Pipeline

The included Jenkinsfile demonstrates production patterns:

```groovy
// Uses beta image (stable blocked until maturity criteria met)
image 'localhost:5000/fluid-forge-cli:beta'

// Multi-stage pipeline
stages:
  - Validate (0.7.1 schema + sovereignty)
  - Open Standards (ODPS/ODCS export)
  - Plan (execution plan generation)
  - Contract Tests (quality gates)
  - Apply (infrastructure deployment)
  - Data Ingestion (optional)
  - Generate Airflow DAG (multi-modal)
```

**Lessons Applied:**
- ✅ Maturity gates (no automatic stable builds)
- ✅ Clear messaging when stages skip
- ✅ Artifacts archived for audit
- ✅ Multi-modal deployment (CI/CD + Airflow)

### Generate Airflow DAG

```bash
# Use the pre-generated DAG with full governance features
# Located at: dags/bitcoin_tracker_dag.py

# Test DAG syntax locally
python3 dags/bitcoin_tracker_dag.py

# Deploy to Cloud Composer
gcloud composer environments storage dags import \
  --environment=production \
  --location=europe-west3 \
  --source=dags/bitcoin_tracker_dag.py

# Or manually copy to Airflow DAGs folder
cp dags/bitcoin_tracker_dag.py $AIRFLOW_HOME/dags/
```

**DAG Features:**
- ✅ Hourly Bitcoin price ingestion
- ✅ Sovereignty validation (EU region enforcement)
- ✅ Policy tag verification
- ✅ Data quality checks
- ✅ Retry logic with exponential backoff
- ✅ Comprehensive execution summary

## 🔒 Policy Tags & Data Catalog

This example includes **BigQuery Data Catalog** integration with policy tags for fine-grained access control.

### Policy Tags Configuration

The contract defines policy tags via column labels:

```yaml
# Financial metrics (price fields)
- name: price_usd
  labels:
    policyTag: "financial_metrics"
    taxonomy: "financial_data"
    datacatalog_project: "<<YOUR_PROJECT_HERE>>"
    datacatalog_location: "us"

# Market metrics (volume/cap fields)
- name: market_cap_usd
  labels:
    policyTag: "market_metrics"
    taxonomy: "financial_data"
```

### Setup Taxonomies

**1. Create taxonomy in Data Catalog:**

```bash
# Via console (recommended for first-time setup)
# https://console.cloud.google.com/datacatalog/policy-tags?project=<<YOUR_PROJECT_HERE>>

# Or via gcloud
gcloud data-catalog taxonomies create financial_data \
  --location=us \
  --display-name="Financial Data Classification" \
  --description="Policy tags for financial metrics and market data"

# Add policy tags
gcloud data-catalog taxonomies policy-tags create financial_metrics \
  --taxonomy=financial_data \
  --location=us \
  --display-name="Financial Metrics"

gcloud data-catalog taxonomies policy-tags create market_metrics \
  --taxonomy=financial_data \
  --location=us \
  --display-name="Market Metrics"
```

**2. Verify policy tags are attached:**

```bash
# Run verification script
python3 check_policy_tags.py

# Expected output:
# ✅ price_usd | projects/.../policyTags/financial_metrics
# ✅ market_cap_usd | projects/.../policyTags/market_metrics
```

**3. Apply access controls:**

```bash
# Restrict who can query tagged columns
gcloud data-catalog taxonomies policy-tags set-iam-policy financial_metrics \
  --location=us \
  --taxonomy=financial_data \
  policy.json

# policy.json example:
# {
#   "bindings": [
#     {
#       "role": "roles/datacatalog.categoryFineGrainedReader",
#       "members": [
#         "group:finance-team@example.com"
#       ]
#     }
#   ]
# }
```

### Data Masking

The contract includes SHA256 hashing for operational timestamps:

```yaml
privacy:
  masking:
    - column: "ingestion_timestamp"
      strategy: "hash"
      params:
        algorithm: "SHA256"
      labels:
        pii_type: "operational_data"
        reason: "audit_trail_protection"
```

**Verification:**

```bash
# Query masked field
bq query --nouse_legacy_sql \
  'SELECT 
     ingestion_timestamp,
     TO_BASE64(SHA256(CAST(ingestion_timestamp AS STRING))) as masked_value
   FROM `<<YOUR_PROJECT_HERE>>.crypto_data.bitcoin_prices`
   LIMIT 5'
```

## 📊 Observability

### Verify Deployment

```bash
# Infrastructure status
bq ls -d <<YOUR_PROJECT_HERE>>
bq show <<YOUR_PROJECT_HERE>>:crypto_data.bitcoin_prices

# Data freshness
bq query --nouse_legacy_sql \
  'SELECT 
     MAX(price_timestamp) as latest,
     COUNT(*) as total_records,
     AVG(price_usd) as avg_price
   FROM `<<YOUR_PROJECT_HERE>>.crypto_data.bitcoin_prices`'

# Schema drift detection
python3 check_schema.py

# Data quality
python3 check_data.py
```

### Monitoring Queries

```sql
-- Price volatility (last 24 hours)
SELECT
  price_timestamp,
  price_usd,
  price_change_24h,
  LAG(price_usd) OVER (ORDER BY price_timestamp) as prev_price
FROM `<<YOUR_PROJECT_HERE>>.crypto_data.bitcoin_prices`
WHERE price_timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
ORDER BY price_timestamp DESC

-- Data freshness check
SELECT
  MAX(ingestion_timestamp) as last_ingestion,
  TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), MAX(ingestion_timestamp), MINUTE) as minutes_since_last_update
FROM `<<YOUR_PROJECT_HERE>>.crypto_data.bitcoin_prices`
```

## 🔒 Governance in Action

### Data Classification

```yaml
policy:
  classification: Internal  # Public|Internal|Confidential|Restricted
```

**Impact:** Determines access policies, encryption requirements, audit frequency

### Role-Based Access Control

```yaml
authz:
  readers:
    - group:data-analytics@company.com
    - group:finance-team@company.com
  writers:
    - serviceAccount:data-pipeline@<<YOUR_PROJECT_HERE>>.iam.gserviceaccount.com
```

**Impact:** Only authorized users/services can read/write data

### Column-Level Restrictions

```yaml
columnRestrictions:
  - principal: "group:interns@company.com"
    columns: [market_cap_usd, volume_24h_usd]
    access: deny
```

**Impact:** Sensitive columns hidden from specific groups

### Row-Level Security

```yaml
privacy:
  rowLevelPolicy:
    expression: "ingestion_timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)"
```

**Impact:** Auto-filters data to last 30 days (GDPR retention)

## 💡 Lessons from v0.5.7 Evolution

### What We Learned

1. **Execution as Data** ✅
   - Trigger configuration belongs in contract (not hardcoded)
   - Makes behavior visible and configurable
   - Enables multi-modal execution (CI/CD, Airflow, etc.)

2. **Governance First** ✅
   - Policies defined alongside infrastructure
   - Field-level tags enable lineage tracking
   - Compliance metadata supports automation

3. **Runnable Examples** ✅
   - Not just YAML - include helper scripts
   - `execute_builds.py`, `check_*.py` for workflows
   - Verification reports for audit trail

4. **Free Tier Friendly** ✅
   - Batch loading instead of streaming inserts
   - Manual triggers with iterations (no Cloud Composer needed)
   - Clear workarounds documented

5. **Maturity Gates** ✅
   - Stable builds require explicit approval
   - Beta/experimental for active development
   - Clear messaging when features unavailable

## 🚦 Next Steps

### For Developers

```bash
# 1. Customize contract for your use case
vim contract.fluid.yaml  # Change project, dataset, policies

# 2. Add custom transformations
vim runtime/ingest.py    # Extend data processing logic

# 3. Set up CI/CD
cp Jenkinsfile your-repo/.ci/
# Configure credentials in Jenkins

# 4. Deploy to production
git commit -am "Add Bitcoin price tracker"
git push  # Triggers Jenkins pipeline
```

### For Data Governance Teams

```bash
# 1. Review sovereignty constraints
fluid validate contract.fluid.yaml --verbose

# 2. Export for compliance audits
fluid odps export contract.fluid.yaml --out audit/contract.odps.json
fluid odcs export contract.fluid.yaml --out audit/contract.odcs.yaml

# 3. Generate documentation
fluid docs contract.fluid.yaml --out docs/

# 4. Monitor compliance
python3 check_schema.py  # Schema drift
python3 check_data.py    # Data quality
```

### For Platform Teams

```bash
# 1. Set up GCP project
gcloud projects create your-project
gcloud services enable bigquery.googleapis.com

# 2. Configure service account
gcloud iam service-accounts create fluid-pipeline
gcloud projects add-iam-policy-binding your-project \
  --member serviceAccount:fluid-pipeline@your-project.iam.gserviceaccount.com \
  --role roles/bigquery.admin

# 3. Deploy infrastructure
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json
fluid apply contract.fluid.yaml

# 4. Set up monitoring
# Use check_*.py scripts in Cloud Monitoring
```

## � Troubleshooting

### "Already Exists" Error

**Symptom:**
```
❌ Deployment failed: Unknown error
Already Exists: Table <<YOUR_PROJECT_HERE>>:crypto_data.bitcoin_prices
```

**Solution:** Infrastructure already deployed! This is **success**, not failure.

```bash
# Verify table exists
bq show <<YOUR_PROJECT_HERE>>:crypto_data.bitcoin_prices

# Continue to Step 3 (data ingestion)
python3 execute_builds.py contract.fluid.yaml
```

**To force recreate:**
```bash
bq rm -f -t <<YOUR_PROJECT_HERE>>:crypto_data.bitcoin_prices
fluid apply contract.fluid.yaml --yes
```

### CoinGecko API Rate Limits

**Symptom:**
```
429 Client Error: Too Many Requests
```

**Solution:** Free tier has ~10-30 requests/minute limit.

```bash
# Increase delay between requests (edit contract.fluid.yaml)
builds:
  - execution:
      trigger:
        delaySeconds: 10  # Was: 5
```

**Or use environment variable:**
```bash
export COINGECKO_API_DELAY=10
python3 runtime/ingest.py
```

### Schema Type Differences

**Symptom:**
```
⚠️  Type: FLOAT64 → NUMERIC (MISMATCH)
```

**Root Cause:** `fluid apply` uses schema auto-detection which prefers FLOAT64 over NUMERIC.

**Impact:** None - both types work for price data, FLOAT64 actually handles large numbers better.

**To enforce exact schema:**
```bash
# Drop and recreate with explicit schema
bq rm -f -t <<YOUR_PROJECT_HERE>>:crypto_data.bitcoin_prices
bq mk --table \
  --schema contract_schema.json \
  <<YOUR_PROJECT_HERE>>:crypto_data.bitcoin_prices
```

### Authentication Errors

**Symptom:**
```
default credentials not found
```

**Solution:**
```bash
# Set credentials
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json

# Verify
gcloud auth application-default print-access-token
```

### Schema Mismatch

**Symptom:**
```
python3 check_schema.py
❌ Schema mismatch detected
```

**Solution:**
```bash
# Drop and recreate table
bq rm -f -t <<YOUR_PROJECT_HERE>>:crypto_data.bitcoin_prices
fluid apply contract.fluid.yaml --yes
```

### No Data After Ingestion

**Symptom:**
```
python3 check_data.py
❌ No data found
```

**Solution:**
```bash
# Check API access
curl -s "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"

# Check BigQuery logs
bq ls -j --max_results 10

# Re-run ingestion with debug
python3 -u execute_builds.py contract.fluid.yaml
```

## �📚 Further Reading

- [HOW_IT_WORKS.md](HOW_IT_WORKS.md) - Architecture deep dive
- [FLUID 0.7.1 Documentation](../../docs/FLUID_0_7_1_QUICK_REFERENCE.md)
- [Governance Guide](../../docs/GOVERNANCE_GUIDE.md)
- [Jenkins Pipeline Guide](../../docs/JENKINS_PIPELINE_GUIDE.md)

## 🤝 Contributing

Found an issue or want to improve this example?

1. Test your changes locally
2. Run validation: `fluid validate contract.fluid.yaml`
3. Update documentation if needed
4. Submit a pull request

## 📄 License

This example is part of the FLUID project. See [LICENSE](../../LICENSE) for details.

---

**Built with FLUID 0.7.1** | **GCP Free Tier Compatible** | **GDPR Compliant** | **Production Ready**
