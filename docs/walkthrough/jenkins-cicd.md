# Jenkins CI/CD for FLUID Data Products

This walkthrough demonstrates how to implement end-to-end CI/CD for declarative data products using Jenkins and the FLUID framework.

::: warning Compatibility note
The contracts and pipeline output shown on this page reference FLUID schema `0.7.1`. The CLI validates each contract against its own declared version, so these examples remain valid. For new contracts, prefer the current `0.7.2` shape — run `fluid init my-project --quickstart` to scaffold one, and use [`fluid generate ci --system jenkins`](/cli/generate.html#fluid-generate-ci) to regenerate a matching Jenkinsfile.
:::

## 📋 Overview

The Jenkins pipeline automates the complete lifecycle of a data product:
1. **Contract Validation** - Validate FLUID contract schema
2. **Static Analysis** - Check governance policies and best practices
3. **Deployment Planning** - Generate execution plan without applying changes
4. **Testing** - Run dbt tests and data quality checks
5. **Deployment** - Apply contract and create/update resources
6. **Verification** - Validate deployment and data quality

## 🎯 Benefits of Declarative CI/CD

### Traditional Approach (Imperative)
```groovy
stage('Deploy') {
    sh 'bq mk dataset'
    sh 'bq load ...'
    sh 'dbt run'
    sh 'python update_metadata.py'
}
```
**Problems:**
- ❌ Manual resource creation
- ❌ No validation before deployment
- ❌ Hard to rollback
- ❌ No infrastructure drift detection

### FLUID Approach (Declarative)
```groovy
stage('Deploy') {
    sh 'fluid validate contract.fluid.yaml'
    sh 'fluid plan contract.fluid.yaml'
    sh 'fluid apply contract.fluid.yaml'
    sh 'fluid verify contract.fluid.yaml'
}
```
**Benefits:**
- ✅ Single source of truth (contract)
- ✅ Automatic validation
- ✅ Plan before apply (like Terraform)
- ✅ Drift detection via verify

## 🏗️ Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Source Control (Git)                      │
│              contract.fluid.yaml + dbt models                │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                   Jenkins Pipeline                           │
├─────────────────────────────────────────────────────────────┤
│  1. Setup          │ Install dependencies, verify env        │
│  2. Validate       │ fluid validate contract.fluid.yaml      │
│  3. Static Analysis│ Check policies, governance metadata     │
│  4. Plan           │ fluid plan (preview changes)            │
│  5. Test           │ dbt test + data quality checks          │
│  6. Deploy         │ dbt run + bq updates (labels)           │
│  7. Verify         │ fluid verify (check compliance)         │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              Google Cloud Platform (BigQuery)                │
│  • Tables: bitcoin_prices                                    │
│  • Views: daily_price_summary, price_trends                  │
│  • Labels: cost-center, environment, sla-tier                │
└─────────────────────────────────────────────────────────────┘
```

## 📂 Project Structure

```
bitcoin-tracker/
├── Jenkinsfile                 # Pipeline definition
├── contract.fluid.yaml         # Data product contract
├── load_bitcoin_price_batch.py # Data ingestion script
├── dbt/
│   ├── dbt_project.yml
│   ├── profiles.yml
│   └── models/
│       ├── daily_price_summary.sql
│       ├── price_trends.sql
│       └── schema.yml
└── runtime/                    # Generated artifacts
    ├── plan.json
    ├── validation-report.json
    └── test-results.json
```

## 🚀 Getting Started

### 1. Jenkins Setup

**Prerequisites:**
- Jenkins 2.x or later
- Plugins:
  - Pipeline
  - Git
  - Google Cloud SDK
  - Credentials Binding

**Configure Jenkins:**

```groovy
// In Jenkins System Configuration

// 1. Add GCP credentials
Credentials → Add Credentials
  Kind: Google Service Account from private key
  Project Name: dust-labs-485011
  ID: gcp-data-product-deployer

// 2. Configure tools
Global Tool Configuration
  Python: Python 3.9+
  Git: Latest
```

### 2. Create Jenkins Pipeline

**Option A: Pipeline from SCM**
```groovy
// In Jenkins Job Configuration
Pipeline → Definition → Pipeline script from SCM
  SCM: Git
  Repository URL: https://github.com/your-org/fluid-mono.git
  Script Path: forge_docs/examples/bitcoin-tracker/Jenkinsfile
```

**Option B: Inline Pipeline**
```groovy
// Copy Jenkinsfile content directly into Jenkins job
```

### 3. Configure GCP Authentication

**Service Account Method (Recommended for Production):**

```bash
# 1. Create service account
gcloud iam service-accounts create fluid-cicd \
  --display-name="FLUID CI/CD Service Account" \
  --project=dust-labs-485011

# 2. Grant permissions
gcloud projects add-iam-policy-binding dust-labs-485011 \
  --member="serviceAccount:fluid-cicd@dust-labs-485011.iam.gserviceaccount.com" \
  --role="roles/bigquery.admin"

# 3. Create key
gcloud iam service-accounts keys create ~/fluid-cicd-key.json \
  --iam-account=fluid-cicd@dust-labs-485011.iam.gserviceaccount.com

# 4. Add to Jenkins credentials
# Upload fluid-cicd-key.json as "Secret file" credential
```

**OAuth Method (Development):**
```bash
# In Jenkins agent, authenticate with:
gcloud auth application-default login
```

### 4. Set Environment Variables

In Jenkins job configuration:
```groovy
environment {
    GCP_PROJECT_ID = 'dust-labs-485011'
    GOOGLE_APPLICATION_CREDENTIALS = credentials('gcp-data-product-deployer')
}
```

## 📋 Pipeline Stages Explained

### Stage 1: Setup Environment

**Purpose:** Install dependencies and verify prerequisites

```groovy
stage('Setup Environment') {
    steps {
        sh '''
            # Install Python packages
            pip install dbt-core dbt-bigquery google-cloud-bigquery
            
            # Verify contract file exists
            test -f contract.fluid.yaml
            
            # Test GCP access
            bq ls --project_id=${GCP_PROJECT_ID}
        '''
    }
}
```

**Key Checks:**
- ✅ Python dependencies installed
- ✅ Contract file exists
- ✅ GCP credentials valid
- ✅ BigQuery access confirmed

### Stage 2: Validate Contract

**Purpose:** Ensure contract is syntactically correct and schema-compliant

```groovy
stage('Validate Contract') {
    steps {
        sh '''
            python3 -m fluid_build.cli validate contract.fluid.yaml
        '''
    }
}
```

**What's Validated:**
- YAML syntax correctness
- FLUID 0.7.1 schema compliance
- Required fields present
- Data types valid
- References consistent

**Sample Output:**
```
Starting validate_contract
Metric: validation_duration=0.042seconds
Metric: validation_errors=0count
Metric: validation_warnings=0count
✅ Valid FLUID contract (schema v0.7.1)
```

### Stage 3: Static Analysis

**Purpose:** Check best practices and governance policies

```groovy
stage('Static Analysis') {
    steps {
        sh '''
            # Check governance metadata
            python3 check_governance.py
            
            # Verify dbt models exist
            test -f dbt/models/daily_price_summary.sql
        '''
    }
}
```

**Checks Performed:**
1. **Governance Metadata:**
   - Product-level labels present
   - Owner information defined
   - Cost allocation tags set

2. **Data Policies:**
   - Classification defined (Public/Internal/Confidential)
   - Access control policies (readers/writers)
   - Sensitivity markers for PII fields

3. **Dependencies:**
   - dbt models exist for declared builds
   - Python scripts exist for ingestion
   - Source tables referenced exist

**Example Policy Check:**
```python
# Contract validation rules
required_labels = ['cost-center', 'data-classification', 'billing-tag']
required_policies = ['classification', 'authz']

for expose in contract['exposes']:
    if not all(label in expose['labels'] for label in required_labels):
        raise ValidationError(f"Missing required labels in {expose['exposeId']}")
```

### Stage 4: Plan Deployment

**Purpose:** Preview changes before applying (like `terraform plan`)

```groovy
stage('Plan Deployment') {
    steps {
        sh '''
            python3 -m fluid_build.cli plan contract.fluid.yaml
        '''
    }
}
```

**Output:**
```
============================================================
FLUID Execution Plan
============================================================
Total Actions: 6

1. provision_bitcoin_prices_table (provisionDataset)
2. schedule_build_1 (scheduleTask)
3. provision_daily_price_summary (provisionDataset)
...
```

**Benefits:**
- See what will change before deployment
- Catch configuration errors early
- Review resource costs
- Validate access permissions

### Stage 5: Run Tests

**Purpose:** Validate data quality and transformations

```groovy
stage('Run Tests') {
    when {
        expression { !params.SKIP_TESTS }
    }
    steps {
        sh '''
            # Run dbt tests
            cd dbt && dbt test
            
            # Custom data quality checks
            python3 data_quality_checks.py
        '''
    }
}
```

**dbt Tests:**
```yaml
# dbt/models/schema.yml
models:
  - name: daily_price_summary
    columns:
      - name: date
        tests:
          - not_null
          - unique
      - name: open_price_usd
        tests:
          - not_null
          - positive_value
```

**Custom Quality Checks:**
```python
# data_quality_checks.py
checks = [
    {
        'name': 'No NULL prices',
        'query': 'SELECT COUNT(*) FROM bitcoin_prices WHERE price_usd IS NULL',
        'expected': 0
    },
    {
        'name': 'Data freshness',
        'query': '''
            SELECT TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), MAX(price_timestamp), HOUR)
            FROM bitcoin_prices
        ''',
        'threshold': 24  # Data should be < 24 hours old
    }
]
```

### Stage 6: Deploy

**Purpose:** Apply contract and create/update resources

```groovy
stage('Deploy') {
    when {
        expression { !params.DRY_RUN }
    }
    steps {
        // Production requires manual approval
        input message: 'Deploy to Production?'
        
        sh '''
            # Run dbt models
            cd dbt && dbt run
            
            # Apply labels
            bq update --set_label environment:${ENVIRONMENT} \\
                      --set_label cost-center:engineering \\
                      ${GCP_PROJECT_ID}:crypto_data.bitcoin_prices
            
            # Load fresh data
            python3 load_bitcoin_price_batch.py
        '''
    }
}
```

**Key Actions:**
1. **Manual Approval** (for production)
2. **dbt Execution** - Create/update views
3. **Label Application** - FinOps tracking
4. **Data Loading** - Ingest fresh data

**Deployment Safety:**
```groovy
// Require approval for production
if (params.ENVIRONMENT == 'production') {
    input message: 'Deploy to Production?', 
          ok: 'Deploy',
          submitter: 'admin,release-manager'
}
```

### Stage 7: Verify Deployment

**Purpose:** Validate resources match contract specification

```groovy
stage('Verify Deployment') {
    steps {
        sh '''
            # Run FLUID verify
            python3 -m fluid_build.cli verify contract.fluid.yaml
            
            # Check labels applied
            bq show --format=json bitcoin_prices | jq '.labels'
            
            # Query sample data
            bq query "SELECT * FROM daily_price_summary LIMIT 1"
        '''
    }
}
```

**Verification Steps:**
1. **Schema Compliance** - Fields match contract
2. **Data Types** - Correct types (FLOAT64, TIMESTAMP, etc.)
3. **Labels** - Cost tracking labels applied
4. **Data Quality** - Sample queries return valid data
5. **Freshness** - Latest data within SLA

**Sample Verification Output:**
```
================================================================================
🔍 FLUID Verify - Multi-Dimensional Contract Validation
================================================================================

📋 Verifying: bitcoin_prices_table
   🔍 Dimension 1: Schema Structure
      ✅ PASS - All 8 column names match specification

   🔍 Dimension 2: Data Types
      ✅ PASS - All types match

   🔍 Dimension 3: Constraints
      ✅ PASS - All field constraints match

   🔍 Dimension 4: Location
      ✅ PASS - Region: us-central1

   🔍 Dimension 5: Labels
      ✅ PASS - All required labels present
```

## 🎛️ Pipeline Parameters

Configure deployment behavior with parameters:

```groovy
parameters {
    choice(
        name: 'ENVIRONMENT',
        choices: ['staging', 'production'],
        description: 'Deployment environment'
    )
    booleanParam(
        name: 'DRY_RUN',
        defaultValue: false,
        description: 'Plan only, do not apply'
    )
    booleanParam(
        name: 'SKIP_TESTS',
        defaultValue: false,
        description: 'Skip test execution'
    )
}
```

**Usage:**
- **Development:** `ENVIRONMENT=staging`, `DRY_RUN=false`, `SKIP_TESTS=false`
- **Production:** `ENVIRONMENT=production`, `DRY_RUN=false`, `SKIP_TESTS=false`
- **Preview:** Any environment, `DRY_RUN=true`

## 📊 Monitoring & Logging

### Console Output

The pipeline provides detailed, color-coded output:

```
═══════════════════════════════════════════════════════════
Stage 2: FLUID Contract Validation
═══════════════════════════════════════════════════════════
🔍 Validating FLUID contract...

✅ Contract validation PASSED
   Contract is compliant with FLUID 0.7.1 schema

📊 Contract Metadata:
  ID: crypto.bitcoin_prices_gcp
  Version: 0.7.1
  Exposes: 3 datasets
  Builds: 3 transformations
```

### Artifacts

The pipeline archives important artifacts:
- `validation-report.json` - Contract validation results
- `plan.json` - Deployment plan
- `dbt-test-output.log` - Test results
- `verify-output.log` - Post-deployment verification

**Access artifacts:**
```
Jenkins Job → Build #123 → Artifacts → runtime/plan.json
```

### Metrics

Key metrics tracked:
- **Build Duration** - Total pipeline execution time
- **Validation Duration** - Contract validation time
- **Test Pass Rate** - Percentage of tests passing
- **Deployment Success Rate** - % of successful deployments

## 🔒 Security Best Practices

### 1. Credentials Management

**Don't:**
```groovy
// ❌ Never hardcode credentials
environment {
    GCP_KEY = 'AKIA...'  // BAD!
}
```

**Do:**
```groovy
// ✅ Use Jenkins credentials
environment {
    GOOGLE_APPLICATION_CREDENTIALS = credentials('gcp-service-account')
}
```

### 2. Least Privilege

```bash
# Grant only required permissions
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/bigquery.dataEditor"  # Not bigquery.admin
```

### 3. Approval Gates

```groovy
// Require approval for sensitive operations
if (params.ENVIRONMENT == 'production') {
    input message: 'Proceed with production deployment?',
          submitter: 'release-managers'
}
```

### 4. Audit Logging

```groovy
post {
    always {
        // Log all deployments
        sh '''
            echo "$(date): Deployment to ${ENVIRONMENT} by ${BUILD_USER}" \
                >> /var/log/fluid-deployments.log
        '''
    }
}
```

## 🐛 Troubleshooting

### Common Issues

#### 1. Contract Validation Fails

**Error:**
```
❌ Contract validation FAILED
   Error: Missing required field 'fluidVersion'
```

**Solution:**
```yaml
# Add at top of contract.fluid.yaml
fluidVersion: "0.7.2"
kind: DataProduct
```

#### 2. GCP Authentication Fails

**Error:**
```
ERROR: (gcloud.auth.application-default.login) 
Unable to find Application Default Credentials
```

**Solution:**
```bash
# In Jenkins, set credential binding
withCredentials([file(credentialsId: 'gcp-key', variable: 'GOOGLE_APPLICATION_CREDENTIALS')]) {
    sh 'gcloud auth activate-service-account --key-file=${GOOGLE_APPLICATION_CREDENTIALS}'
}
```

#### 3. dbt Tests Fail

**Error:**
```
Failure in test not_null_bitcoin_prices_price_usd
  Got 5 results, expected 0
```

**Solution:**
```sql
-- Fix NULL values in source data
DELETE FROM bitcoin_prices WHERE price_usd IS NULL;
```

#### 4. Labels Not Applied

**Error:**
```
⚠️  Labels: null
```

**Solution:**
```bash
# FLUID apply currently has issues, use manual bq update:
bq update --set_label cost-center:engineering table_name
```

## 📈 Advanced Patterns

### Multi-Environment Deployment

```groovy
pipeline {
    stages {
        stage('Deploy to Staging') {
            environment {
                GCP_PROJECT_ID = 'project-staging'
            }
            steps {
                sh 'fluid apply contract.fluid.yaml'
            }
        }
        
        stage('Smoke Test Staging') {
            steps {
                sh 'python3 smoke_tests.py --env=staging'
            }
        }
        
        stage('Deploy to Production') {
            when {
                branch 'main'
            }
            environment {
                GCP_PROJECT_ID = 'project-production'
            }
            steps {
                input 'Deploy to production?'
                sh 'fluid apply contract.fluid.yaml'
            }
        }
    }
}
```

### Parallel Testing

```groovy
stage('Tests') {
    parallel {
        stage('Unit Tests') {
            steps {
                sh 'pytest tests/unit'
            }
        }
        stage('dbt Tests') {
            steps {
                sh 'dbt test'
            }
        }
        stage('Data Quality') {
            steps {
                sh 'python3 dq_checks.py'
            }
        }
    }
}
```

### Rollback Support

```groovy
stage('Deploy') {
    steps {
        script {
            try {
                sh 'fluid apply contract.fluid.yaml'
            } catch (Exception e) {
                echo "Deployment failed, rolling back..."
                sh 'git checkout HEAD~1 contract.fluid.yaml'
                sh 'fluid apply contract.fluid.yaml'
                throw e
            }
        }
    }
}
```

## 📚 Related Documentation

- [GCP Deployment Guide](./gcp.md)
- [Declarative Airflow Integration](./airflow-declarative.md)
- [Getting Started](/getting-started/)

## 🎯 Next Steps

1. **Set Up Jenkins Job** - Create pipeline using provided Jenkinsfile
2. **Configure GCP Access** - Set up service account credentials
3. **Test in Staging** - Run pipeline with `ENVIRONMENT=staging`
4. **Monitor First Deploy** - Review logs and artifacts
5. **Automate Triggers** - Set up Git webhook for automatic builds
6. **Add Notifications** - Configure Slack/email alerts for failures

## 💡 Best Practices Summary

✅ **DO:**
- Use declarative FLUID contracts as single source of truth
- Validate before deploying (`fluid validate` → `fluid plan` → `fluid apply`)
- Run tests in CI/CD pipeline
- Require manual approval for production
- Archive deployment artifacts
- Monitor data quality post-deployment

❌ **DON'T:**
- Hardcode credentials in pipeline
- Skip validation or tests for "quick fixes"
- Deploy directly to production without staging
- Ignore failed tests in production pipeline
- Deploy without reviewing the plan

---

**Questions or issues?** Open an issue on [GitHub](https://github.com/Agenticstiger/forge-cli/issues).
