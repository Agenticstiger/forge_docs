# Bitcoin Price Tracker 0.7.1 - Quick Reference

## 🚀 5-Minute Quickstart

```bash
# 1. Validate (checks 0.7.1 schema + sovereignty)
fluid validate contract.fluid.yaml

# 2. Deploy infrastructure (creates BigQuery table)
fluid apply contract.fluid.yaml --yes

# 3. Ingest data (5 runs, 5-second intervals)
python3 execute_builds.py contract.fluid.yaml

# 4. Verify
python3 check_data.py
```

## 📋 All Commands

### Validation & Planning

```bash
# Basic validation
fluid validate contract.fluid.yaml

# Verbose (shows sovereignty + AI policy checks)
fluid validate contract.fluid.yaml --verbose --schema-version 0.7.1

# Generate execution plan
fluid plan contract.fluid.yaml --out plan.json

# Dry-run (preview without executing)
fluid apply contract.fluid.yaml --dry-run
```

### Infrastructure Deployment

```bash
# Deploy to GCP BigQuery
fluid apply contract.fluid.yaml --yes

# With environment overlay
fluid apply contract.fluid.yaml --env prod --yes

# Generate HTML report
fluid apply contract.fluid.yaml --yes --report apply-report.html
```

### Data Ingestion

```bash
# Execute builds from contract config
python3 execute_builds.py contract.fluid.yaml

# Or run directly (single execution)
python3 runtime/ingest.py

# With custom environment
export GCP_PROJECT=your-project
export BQ_DATASET=your_dataset
python3 runtime/ingest.py
```

### Verification & Monitoring

```bash
# Check schema matches contract
python3 check_schema.py

# Check data was loaded
python3 check_data.py

# Query directly with bq CLI
bq query --nouse_legacy_sql \
  'SELECT * FROM `<<YOUR_PROJECT_HERE>>.crypto_data.bitcoin_prices` 
   ORDER BY price_timestamp DESC LIMIT 10'
```

### Multi-Modal Deployment

```bash
# Generate Airflow DAG
fluid generate-airflow contract.fluid.yaml \
  --out bitcoin_tracker.py \
  --dag-id bitcoin_price_tracker \
  --schedule '@hourly'

# Export to open standards
fluid odps export contract.fluid.yaml --out contract.odps.json
fluid odcs export contract.fluid.yaml --out contract.odcs.yaml

# Visualize dependencies
fluid viz-graph contract.fluid.yaml --format html --out graph.html
```

## 🔍 What's Different from v0.5.7?

### New Fields in Contract

```yaml
fluidVersion: "0.7.1"  # Was: "0.5.7"

# NEW in 0.7.1: Data Sovereignty
sovereignty:
  jurisdiction: "EU"
  dataResidency: true
  allowedRegions: [europe-west3]
  deniedRegions: [us-east-1]
  regulatoryFramework: [GDPR]
  enforcementMode: advisory  # advisory|strict|audit
  validationRequired: true

# PRESERVED from 0.5.7: All governance
policy:
  classification: Internal
  authn: iam
  authz: {...}
  privacy: {...}
  tags: [...]
  labels: {...}
```

**Note:** AI governance (`agentPolicy`) is planned for future FLUID versions.

## 📊 File Structure

```
bitcoin-price-tracker-0.7.1/
├── contract.fluid.yaml       # 0.7.1 contract with governance
├── runtime/
│   └── ingest.py            # Bitcoin API → BigQuery
├── Jenkinsfile              # CI/CD pipeline with maturity gates
├── execute_builds.py        # Execute from contract config
├── check_data.py            # Verify data loaded
├── check_schema.py          # Validate schema matches
├── README.md                # Full documentation
├── HOW_IT_WORKS.md          # Architecture deep dive
└── QUICKSTART.md            # This file
```

## 💡 Common Tasks

### Check Infrastructure Status

```bash
# List datasets
bq ls -d <<YOUR_PROJECT_HERE>>

# Show table details
bq show <<YOUR_PROJECT_HERE>>:crypto_data.bitcoin_prices

# Get row count
bq query --nouse_legacy_sql \
  'SELECT COUNT(*) as total FROM `<<YOUR_PROJECT_HERE>>.crypto_data.bitcoin_prices`'
```

### Monitor Data Freshness

```bash
# Last ingestion time
bq query --nouse_legacy_sql \
  'SELECT MAX(ingestion_timestamp) as latest 
   FROM `<<YOUR_PROJECT_HERE>>.crypto_data.bitcoin_prices`'

# Recent price changes
bq query --nouse_legacy_sql \
  'SELECT price_timestamp, price_usd, price_change_24h
   FROM `<<YOUR_PROJECT_HERE>>.crypto_data.bitcoin_prices`
   ORDER BY price_timestamp DESC
   LIMIT 5'
```

### Troubleshooting

```bash
# Check FLUID version
fluid --version

# Check GCP credentials
gcloud auth list
echo $GOOGLE_APPLICATION_CREDENTIALS

# Test BigQuery access
bq ls

# Validate contract syntax
fluid validate contract.fluid.yaml --verbose

# Check for errors
python3 -m py_compile runtime/ingest.py
```

## 🎯 CI/CD with Jenkins

### Trigger Pipeline

```bash
# Via Jenkins UI
http://localhost:8082/job/bitcoin-price-tracker-0.7.1/build

# Via curl (with parameters)
curl -X POST http://localhost:8082/job/bitcoin-price-tracker-0.7.1/buildWithParameters \
  --user admin:$(cat /home/dustlabs/fluid-mono/secret-file) \
  --data "PROFILE=beta&RUN_DATA_INGESTION=true"
```

### Pipeline Stages

1. **🔍 Environment Info** - Show versions and config
2. **🛡️ Validate** - Check 0.7.1 schema + sovereignty
3. **📜 Open Standards** - Export ODPS/ODCS
4. **📋 Plan** - Generate execution plan
5. **🧪 Contract Tests** - Quality gates
6. **🚀 Apply Infrastructure** - Deploy to GCP
7. **💾 Data Ingestion** - Optional data load
8. **🌟 Generate Airflow DAG** - Multi-modal deployment
9. **📊 Summary** - Results and next steps

## 🔒 Governance Features

### Sovereignty Controls

- ✅ **EU Jurisdiction:** Data must stay in Europe
- ✅ **Region Allowlist:** Only europe-west3, europe-west1
- ✅ **Region Denylist:** Blocks US regions
- ✅ **GDPR Compliance:** Enforced by sovereignty rules
- ✅ **Enforcement Modes:** Advisory (warn), Strict (block), Audit (log)

### AI Governance (Future)

AI governance via `agentPolicy` is planned for future FLUID versions. Currently use:
- ✅ **Policy Tags:** `ai-restricted`, `no-training-allowed`
- ✅ **Policy Labels:** `ai_access_policy: "restricted"`, `data_usage: "no-training"`

### Access Control

- ✅ **RBAC:** Separate readers and writers
- ✅ **Column Restrictions:** Hide sensitive columns from interns
- ✅ **Row-Level Security:** Auto-filter to last 30 days
- ✅ **IAM Authentication:** GCP identity-based access

## 📚 Next Steps

1. **Customize:** Edit `contract.fluid.yaml` for your use case
2. **Extend:** Modify `runtime/ingest.py` for custom transformations  
3. **Deploy:** Set up Jenkins pipeline for CI/CD
4. **Monitor:** Use `check_*.py` scripts for observability
5. **Scale:** Generate Airflow DAG for production scheduling

## 🆘 Need Help?

- **Documentation:** See [README.md](README.md) and [HOW_IT_WORKS.md](HOW_IT_WORKS.md)
- **Examples:** Browse `/forge_docs/examples/`
- **FLUID Docs:** Check `docs/FLUID_0_7_1_QUICK_REFERENCE.md`
- **Issues:** Common problems solved in README troubleshooting section

---

**Built with FLUID 0.7.1** | **5-minute setup** | **Production ready**
