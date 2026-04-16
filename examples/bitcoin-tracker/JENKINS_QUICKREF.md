# Jenkins CI/CD Quick Reference

## 🚀 Quick Start Commands

### Run Complete Pipeline
```bash
# From Jenkins UI
Build with Parameters
  ENVIRONMENT: staging
  DRY_RUN: false
  SKIP_TESTS: false
```

### Test Locally Before Pushing
```bash
cd examples/bitcoin-tracker

# 1. Validate contract
python3 -m fluid_build.cli validate contract.fluid.yaml

# 2. Generate plan
python3 -m fluid_build.cli plan contract.fluid.yaml

# 3. Run tests
cd dbt && dbt test

# 4. Simulate deployment (dry run)
python3 -m fluid_build.cli plan contract.fluid.yaml  # Review changes

# 5. Deploy locally
cd dbt && dbt run
python3 load_bitcoin_price_batch.py
```

## 📋 Pipeline Stages Cheat Sheet

| Stage | Command | Purpose | Fails Build? |
|-------|---------|---------|--------------|
| **Validate** | `fluid validate` | Check contract syntax | ✅ Yes |
| **Static Analysis** | Custom Python | Check governance | ⚠️ Warning only |
| **Plan** | `fluid plan` | Preview changes | ✅ Yes |
| **Test** | `dbt test` | Data quality checks | ✅ Yes (prod only) |
| **Deploy** | `dbt run` + `bq update` | Apply changes | ✅ Yes |
| **Verify** | `fluid verify` | Check compliance | ⚠️ Warning only |

## 🎛️ Jenkins Parameters

```groovy
ENVIRONMENT       staging | production
DRY_RUN          false | true
SKIP_TESTS       false | true  (not recommended for prod)
GCP_PROJECT_ID   dust-labs-485011
```

## 🔍 Common Workflows

### Development Workflow
```
1. Create feature branch: git checkout -b feature/add-new-field
2. Update contract.fluid.yaml
3. Run locally: ./run-complete-example.sh
4. Commit & push
5. Jenkins runs automatically → deploys to staging
6. Review staging data
7. Create PR → merge to main
8. Jenkins deploys to production (with approval)
```

### Hotfix Workflow
```
1. Create hotfix branch from main
2. Fix issue in contract or dbt model
3. Run locally: python3 -m fluid_build.cli validate contract.fluid.yaml
4. Push → Jenkins deploys to staging
5. Verify: bq query "SELECT * FROM daily_price_summary LIMIT 1"
6. Merge to main → production deployment
```

### Rollback Workflow
```
1. Find last good build: Jenkins → Build History
2. Get previous commit: git log --oneline
3. Revert: git revert <commit-hash>
4. Push → Jenkins deploys previous version
```

## 🐛 Debugging Commands

### Check Contract Validation
```bash
python3 -m fluid_build.cli validate contract.fluid.yaml 2>&1 | tee validation.log
```

### View Deployment Plan
```bash
python3 -m fluid_build.cli plan contract.fluid.yaml | jq '.actions'
```

### Check BigQuery Resources
```bash
# List all resources
bq ls --project_id=dust-labs-485011 crypto_data

# Check table schema
bq show --schema dust-labs-485011:crypto_data.bitcoin_prices

# Check labels
bq show --format=json dust-labs-485011:crypto_data.bitcoin_prices | jq '.labels'
```

### Run dbt Tests
```bash
cd dbt
dbt test --project-dir . --profiles-dir .
dbt test --select daily_price_summary  # Test specific model
```

### Verify Data Quality
```bash
bq query --use_legacy_sql=false "
  SELECT 
    COUNT(*) as total_rows,
    MAX(price_timestamp) as latest_update,
    TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), MAX(price_timestamp), HOUR) as hours_old
  FROM \`dust-labs-485011.crypto_data.bitcoin_prices\`
"
```

## 🔒 Security Checklist

- [ ] GCP credentials configured in Jenkins
- [ ] Service account has minimum required permissions
- [ ] Production deployment requires manual approval
- [ ] Sensitive data marked with `sensitivity: internal`
- [ ] Access policies defined in contract (`authz.readers`)
- [ ] Cost allocation labels applied

## 📊 Monitoring

### Key Metrics to Track
```bash
# Build success rate
jenkins-cli get-job bitcoin-tracker | grep '<lastSuccessfulBuild>'

# Data freshness
bq query "SELECT TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), MAX(price_timestamp), HOUR) as hours_old FROM bitcoin_prices"

# Row counts
bq query "SELECT COUNT(*) FROM bitcoin_prices"

# Cost by labels
bq query "SELECT table_name, size_bytes FROM INFORMATION_SCHEMA.TABLES WHERE table_schema='crypto_data'"
```

### Alerts to Set Up
1. **Pipeline Failure** → Slack/email notification
2. **Data Stale** → Alert if `hours_old > 24`
3. **Test Failures** → Block production deployment
4. **Cost Spike** → Alert if daily cost > threshold

## 🎯 Best Practices

### Commit Messages
```bash
# Good
git commit -m "feat: Add EUR/GBP price fields to contract"
git commit -m "fix: Correct data type for market_cap (FLOAT64)"
git commit -m "chore: Update dbt profiles for new project"

# Bad
git commit -m "update"
git commit -m "fix bug"
```

### Contract Changes
```yaml
# DO: Add new optional fields
schema:
  - name: new_field
    type: FLOAT64
    required: false  # Safe to add

# DON'T: Remove or change existing required fields (breaking change)
schema:
  - name: price_usd
    type: STRING  # Changed from FLOAT64 - BREAKS consumers!
```

### Testing Strategy
```bash
# Local testing before push
1. Validate: fluid validate contract.fluid.yaml
2. Plan: fluid plan contract.fluid.yaml
3. dbt test: cd dbt && dbt test
4. Manual query: bq query "SELECT * FROM ... LIMIT 1"

# In CI/CD
1. All of above +
2. Data quality checks (NULL counts, freshness)
3. Integration tests (view queries)
4. Smoke tests (sample data validity)
```

## 📚 Useful Links

- [Full Jenkins Walkthrough](./jenkins-cicd.md)
- [Bitcoin Tracker Example](../../examples/bitcoin-tracker/README.md)
- [FLUID CLI Reference](../cli/reference.md)
- [dbt Documentation](https://docs.getdbt.com)
- [BigQuery CLI (bq)](https://cloud.google.com/bigquery/docs/bq-command-line-tool)

## 💡 Pro Tips

1. **Use DRY_RUN** for testing changes without deploying
2. **Archive artifacts** in Jenkins for debugging later
3. **Tag releases** in Git for easy rollback
4. **Monitor build times** - optimize slow stages
5. **Use parallel stages** for faster builds
6. **Set up webhooks** for automatic builds on push
7. **Create staging environment** separate from production
8. **Document breaking changes** in commit messages

## 🆘 Getting Help

**Pipeline Fails at Validation:**
→ Check [contract validation errors](../../examples/bitcoin-tracker/OPPORTUNITIES.md#issue-3-contract-validation-failures)

**Pipeline Fails at Tests:**
→ Review `runtime/dbt-test-output.log` artifact

**Labels Not Applied:**
→ Known issue, use manual `bq update --set_label` workaround

**Views Not Created:**
→ Check dbt run logs in `runtime/dbt-run-output.log`
