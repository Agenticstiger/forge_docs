# Airflow Integration

Generate Apache Airflow DAGs from Fluid Forge contracts declaratively.

## Quick Start

FLUID can automatically generate production-ready Airflow DAGs from your data product contracts:

```bash
# Generate declarative Airflow DAG
fluid generate-airflow contract.yaml \
  -o airflow/dags/my_pipeline.py \
  --dag-id my_pipeline \
  --schedule "0 * * * *"
```

**What you get:**
- ✅ Tasks generated from your `builds` array
- ✅ Dataset provisioning from `exposes` bindings
- ✅ Retry configuration from `execution.retries`
- ✅ Provider-specific commands (GCP, AWS, Snowflake)
- ✅ Dependencies inferred from `outputs`
- ✅ No manual Python coding required

## Full Documentation

For a comprehensive guide including:
- Manual vs declarative comparison (300+ lines → 1 command)
- Step-by-step tutorial with Bitcoin tracker example
- Multi-provider migration patterns
- Customization options for schedules and environments
- Benefits and best practices

See the **[Declarative Airflow Walkthrough](/forge_docs/walkthrough/airflow-declarative)** →

## Command Reference

### Basic Usage

```bash
fluid generate-airflow contract.yaml -o dag.py
```

### With Custom Schedule

```bash
# Hourly
fluid generate-airflow contract.yaml -o dag.py --schedule "0 * * * *"

# Daily at 2 AM
fluid generate-airflow contract.yaml -o dag.py --schedule "0 2 * * *"

# Every 15 minutes
fluid generate-airflow contract.yaml -o dag.py --schedule "*/15 * * * *"
```

### With Environment Overlays

```bash
# Development environment
fluid generate-airflow contract.yaml -o dag_dev.py --env dev

# Production environment
fluid generate-airflow contract.yaml -o dag_prod.py --env prod
```

### With Custom DAG ID

```bash
fluid generate-airflow contract.yaml \
  -o dags/bitcoin_tracker.py \
  --dag-id bitcoin_tracker_prod \
  --schedule "0 * * * *" \
  --verbose
```

## Cloud Composer Deployment

Deploy generated DAGs to GCP Cloud Composer:

```bash
# Generate DAG
fluid generate-airflow contract.yaml -o my_dag.py

# Create Composer environment
gcloud composer environments create my-env \
  --location us-central1 \
  --image-version composer-2.6.0-airflow-2.6.3

# Upload DAG
BUCKET=$(gcloud composer environments describe my-env \
  --location us-central1 \
  --format="get(config.dagGcsPrefix)")

gsutil cp my_dag.py $BUCKET/dags/
```

## Local Airflow Testing

Test DAGs locally before deploying:

```bash
# Set Airflow home
export AIRFLOW_HOME=$PWD/airflow

# Initialize
airflow db init

# Create admin user
airflow users create \
  --username admin \
  --password admin \
  --role Admin \
  --email admin@example.com

# Test DAG syntax
python3 airflow/dags/my_dag.py

# Start Airflow
airflow webserver --port 8080 &
airflow scheduler &
```

Access UI at http://localhost:8080 (admin/admin)

## See Also

- **[Declarative Airflow Walkthrough](/forge_docs/walkthrough/airflow-declarative)** - Comprehensive guide
- **[CLI Reference](/forge_docs/cli/)** - All commands
- **[GCP Walkthrough](/forge_docs/walkthrough/gcp)** - Cloud Composer examples
- **[Bitcoin Tracker Example](https://github.com/Agenticstiger/forge_docs/tree/main/examples/bitcoin-tracker)** - Working code
