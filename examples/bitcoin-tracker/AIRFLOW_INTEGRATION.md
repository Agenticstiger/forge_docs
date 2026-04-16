# Airflow Integration Guide - Bitcoin Price Tracker

This guide shows how to deploy and schedule the Bitcoin price tracker using Apache Airflow for production orchestration.

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Deployment Options](#deployment-options)
- [Option 1: Auto-Generated DAG (scaffold-composer)](#option-1-auto-generated-dag-scaffold-composer)
- [Option 2: Custom DAG with Python Operators](#option-2-custom-dag-with-python-operators)
- [Option 3: GCP Cloud Composer](#option-3-gcp-cloud-composer)
- [Airflow Configuration](#airflow-configuration)
- [Monitoring & Troubleshooting](#monitoring--troubleshooting)

---

## Overview

Apache Airflow provides robust scheduling, monitoring, and retry capabilities for the Bitcoin tracker data pipeline. This integration enables:

- **Automated Scheduling**: Run price ingestion at regular intervals (e.g., every hour)
- **Dependency Management**: Ensure proper execution order (ingest → transform → verify)
- **Error Handling**: Automatic retries with exponential backoff
- **Monitoring**: Track execution history, failures, and performance
- **Alerting**: Email/Slack notifications on failures

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│ Airflow Scheduler                                       │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────┐   ┌──────────────┐   ┌────────────┐ │
│  │   Validate   │──▶│  Ingest BTC  │──▶│   dbt Run  │ │
│  │   Contract   │   │    Prices    │   │   Models   │ │
│  └──────────────┘   └──────────────┘   └────────────┘ │
│         │                  │                   │       │
│         └──────────────────┴───────────────────┘       │
│                          │                             │
│                    ┌─────▼──────┐                      │
│                    │   Verify   │                      │
│                    │  BigQuery  │                      │
│                    └────────────┘                      │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
                  GCP BigQuery
```

---

## Prerequisites

### 1. Python Dependencies

```bash
pip install apache-airflow==2.8.0
pip install apache-airflow-providers-google==10.12.0
pip install requests google-cloud-bigquery dbt-bigquery
```

### 2. GCP Authentication

Set up Application Default Credentials:

```bash
gcloud auth application-default login
```

Or use a service account:

```bash
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json
```

### 3. Environment Variables

Create `.env` file:

```bash
# GCP Configuration
export GCP_PROJECT_ID=your-project-id
export GCP_REGION=us-central1
export FLUID_PROVIDER=gcp
export FLUID_PROJECT=your-project-id

# Airflow Configuration
export AIRFLOW_HOME=$HOME/airflow
export AIRFLOW__CORE__DAGS_FOLDER=$PWD/airflow/dags
export AIRFLOW__CORE__LOAD_EXAMPLES=False
```

---

## Deployment Options

## Option 1: Auto-Generated DAG (scaffold-composer)

The simplest approach - FLUID CLI generates a basic DAG automatically.

### Step 1: Generate DAG

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

### Step 2: Review Generated DAG

The auto-generated DAG includes:
- **validate**: Check contract syntax
- **plan**: Generate execution plan
- **apply**: Deploy to BigQuery

```python
# airflow/dags/crypto_bitcoin_prices_gcp.py
from airflow import DAG
from airflow.operators.bash import BashOperator
from datetime import datetime

with DAG(
    dag_id="crypto_bitcoin_prices_gcp",
    start_date=datetime(2024, 1, 1),
    schedule="0 2 * * *",  # Daily at 2 AM UTC
    catchup=False,
    default_args={"retries": 1},
    tags=["FLUID", "crypto", "bitcoin"]
) as dag:
    validate >> plan >> apply
```

### Step 3: Initialize Airflow

```bash
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

# Start webserver (in separate terminal)
airflow webserver --port 8080

# Start scheduler (in separate terminal)
airflow scheduler
```

### Step 4: Access Airflow UI

Open browser: http://localhost:8080

- Username: `admin`
- Password: `admin`

Enable the `crypto_bitcoin_prices_gcp` DAG and trigger a manual run.

---

## Option 2: Custom DAG with Python Operators

For production use, create a custom DAG with better error handling and monitoring.

### Enhanced DAG

Create `airflow/dags/bitcoin_tracker_enhanced.py`:

```python
from __future__ import annotations

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.providers.google.cloud.operators.bigquery import (
    BigQueryCheckOperator,
    BigQueryGetDataOperator,
)
from airflow.utils.dates import days_ago
from datetime import datetime, timedelta
import os
import sys

# Add project to Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/../.."))

from ingest_bitcoin_prices import fetch_bitcoin_price, insert_to_bigquery

# Default arguments
default_args = {
    "owner": "data-engineering",
    "depends_on_past": False,
    "email": ["alerts@yourcompany.com"],
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(minutes=30),
}

# DAG definition
with DAG(
    dag_id="bitcoin_tracker_enhanced",
    default_args=default_args,
    description="Hourly Bitcoin price ingestion with dbt transformations",
    schedule="0 * * * *",  # Every hour at minute 0
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["crypto", "bitcoin", "gcp", "bigquery", "FLUID"],
    max_active_runs=1,
) as dag:

    # Task 1: Validate FLUID contract
    validate_contract = BashOperator(
        task_id="validate_contract",
        bash_command="cd {{ params.project_dir }} && python3 -m fluid_build.cli validate contract.fluid.yaml",
        params={"project_dir": os.environ.get("AIRFLOW_DAGS_FOLDER", ".")},
    )

    # Task 2: Fetch Bitcoin price from CoinGecko
    def fetch_btc_price_task(**context):
        """Fetch current Bitcoin price and push to XCom."""
        price_data = fetch_bitcoin_price()
        
        # Push to XCom for monitoring
        context["ti"].xcom_push(key="btc_price_usd", value=price_data["price_usd"])
        context["ti"].xcom_push(key="market_cap", value=price_data["market_cap_usd"])
        context["ti"].xcom_push(key="volume_24h", value=price_data["volume_24h_usd"])
        
        print(f"✓ Fetched BTC: ${price_data['price_usd']:,.2f}")
        return price_data

    fetch_price = PythonOperator(
        task_id="fetch_bitcoin_price",
        python_callable=fetch_btc_price_task,
        provide_context=True,
    )

    # Task 3: Insert to BigQuery
    def insert_to_bq_task(**context):
        """Insert price data to BigQuery."""
        price_data = context["ti"].xcom_pull(task_ids="fetch_bitcoin_price")
        
        project_id = os.environ.get("GCP_PROJECT_ID", "<<YOUR_PROJECT_HERE>>")
        dataset = "crypto_data"
        table = "bitcoin_prices"
        
        success = insert_to_bigquery(price_data, project_id, dataset, table)
        
        if not success:
            raise Exception("Failed to insert to BigQuery")
        
        print(f"✓ Inserted to {project_id}.{dataset}.{table}")
        return True

    insert_price = PythonOperator(
        task_id="insert_to_bigquery",
        python_callable=insert_to_bq_task,
        provide_context=True,
    )

    # Task 4: Run dbt transformations
    run_dbt = BashOperator(
        task_id="run_dbt_models",
        bash_command="cd {{ params.project_dir }}/dbt && dbt run --profiles-dir .",
        params={"project_dir": os.environ.get("AIRFLOW_DAGS_FOLDER", ".")},
    )

    # Task 5: Data quality check
    check_data_quality = BigQueryCheckOperator(
        task_id="check_data_quality",
        sql=f"""
        SELECT COUNT(*) > 0
        FROM `{os.environ.get('GCP_PROJECT_ID', '<<YOUR_PROJECT_HERE>>')}.crypto_data.bitcoin_prices`
        WHERE DATE(timestamp) = CURRENT_DATE()
        """,
        use_legacy_sql=False,
    )

    # Task 6: Verify transformations
    verify_transformations = BigQueryCheckOperator(
        task_id="verify_transformations",
        sql=f"""
        SELECT COUNT(*) > 0
        FROM `{os.environ.get('GCP_PROJECT_ID', '<<YOUR_PROJECT_HERE>>')}.crypto_data.daily_price_summary`
        WHERE price_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY)
        """,
        use_legacy_sql=False,
    )

    # Task 7: Send metrics
    def send_metrics_task(**context):
        """Log execution metrics."""
        btc_price = context["ti"].xcom_pull(task_ids="fetch_bitcoin_price", key="btc_price_usd")
        market_cap = context["ti"].xcom_pull(task_ids="fetch_bitcoin_price", key="market_cap")
        
        print(f"📊 Pipeline Metrics:")
        print(f"   BTC Price: ${btc_price:,.2f}")
        print(f"   Market Cap: ${market_cap:,.0f}")
        print(f"   Execution Time: {datetime.now()}")
        
        # TODO: Send to monitoring system (Datadog, CloudWatch, etc.)
        return True

    send_metrics = PythonOperator(
        task_id="send_metrics",
        python_callable=send_metrics_task,
        provide_context=True,
    )

    # Define task dependencies
    (
        validate_contract
        >> fetch_price
        >> insert_price
        >> run_dbt
        >> [check_data_quality, verify_transformations]
        >> send_metrics
    )
```

### Deploy Enhanced DAG

```bash
# Copy to Airflow dags folder
cp airflow/dags/bitcoin_tracker_enhanced.py $AIRFLOW_HOME/dags/

# Test DAG
airflow dags test bitcoin_tracker_enhanced 2024-01-21

# Trigger manual run
airflow dags trigger bitcoin_tracker_enhanced
```

---

## Option 3: GCP Cloud Composer

Deploy to Google Cloud Composer (managed Airflow).

### Step 1: Create Cloud Composer Environment

```bash
gcloud composer environments create bitcoin-tracker-env \
  --location us-central1 \
  --image-version composer-2.6.0-airflow-2.6.3 \
  --machine-type n1-standard-2 \
  --node-count 3 \
  --disk-size 30GB \
  --python-version 3.10
```

### Step 2: Install Python Dependencies

```bash
gcloud composer environments update bitcoin-tracker-env \
  --location us-central1 \
  --update-pypi-packages-from-file requirements.txt
```

### Step 3: Upload DAG

```bash
# Get bucket name
BUCKET=$(gcloud composer environments describe bitcoin-tracker-env \
  --location us-central1 \
  --format="get(config.dagGcsPrefix)")

# Upload DAG
gsutil cp airflow/dags/bitcoin_tracker_enhanced.py $BUCKET/dags/

# Upload supporting files
gsutil cp ingest_bitcoin_prices.py $BUCKET/dags/
gsutil cp contract.fluid.yaml $BUCKET/data/
```

### Step 4: Configure Connections

```bash
# Set GCP connection
gcloud composer environments run bitcoin-tracker-env \
  --location us-central1 \
  connections add google_cloud_default \
  --conn-type google_cloud_platform \
  --conn-extra '{"extra__google_cloud_platform__project": "your-project-id"}'
```

### Step 5: Set Airflow Variables

```bash
gcloud composer environments run bitcoin-tracker-env \
  --location us-central1 \
  variables set -- \
  GCP_PROJECT_ID your-project-id

gcloud composer environments run bitcoin-tracker-env \
  --location us-central1 \
  variables set -- \
  BQ_DATASET crypto_data
```

---

## Airflow Configuration

### airflow.cfg

Add to `$AIRFLOW_HOME/airflow.cfg`:

```ini
[core]
dags_folder = /path/to/bitcoin-tracker/airflow/dags
load_examples = False
max_active_runs_per_dag = 1

[scheduler]
dag_dir_list_interval = 30
min_file_process_interval = 30

[email]
email_backend = airflow.utils.email.send_email_smtp

[smtp]
smtp_host = smtp.gmail.com
smtp_starttls = True
smtp_ssl = False
smtp_user = your-email@gmail.com
smtp_password = your-app-password
smtp_port = 587
smtp_mail_from = airflow@yourcompany.com
```

### Environment Variables

```bash
# .env
export AIRFLOW_HOME=$HOME/airflow
export AIRFLOW__CORE__DAGS_FOLDER=$PWD/airflow/dags
export AIRFLOW__CORE__LOAD_EXAMPLES=False
export GCP_PROJECT_ID=your-project-id
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
```

---

## Monitoring & Troubleshooting

### View DAG Logs

```bash
# List recent runs
airflow dags list-runs -d bitcoin_tracker_enhanced

# View task logs
airflow tasks logs bitcoin_tracker_enhanced fetch_bitcoin_price 2024-01-21
```

### Common Issues

#### Issue 1: Import Errors

**Error:** `ModuleNotFoundError: No module named 'ingest_bitcoin_prices'`

**Solution:**
```python
# Add to top of DAG
import sys
sys.path.insert(0, '/path/to/bitcoin-tracker')
```

#### Issue 2: GCP Authentication

**Error:** `google.auth.exceptions.DefaultCredentialsError`

**Solution:**
```bash
# Set credentials
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json

# Or login with gcloud
gcloud auth application-default login
```

#### Issue 3: BigQuery Permissions

**Error:** `Access Denied: BigQuery BigQuery: Permission denied`

**Solution:**
```bash
# Grant BigQuery permissions to service account
gcloud projects add-iam-policy-binding your-project-id \
  --member="serviceAccount:airflow@your-project.iam.gserviceaccount.com" \
  --role="roles/bigquery.dataEditor"
```

### Health Check

Test the entire pipeline:

```bash
cd /home/dustlabs/fluid-mono/forge_docs/examples/bitcoin-tracker

# Test ingestion script
python3 ingest_bitcoin_prices.py

# Test DAG syntax
python3 airflow/dags/bitcoin_tracker_enhanced.py

# Test Airflow DAG
airflow dags test bitcoin_tracker_enhanced 2024-01-21
```

---

## Next Steps

1. **Enable Alerting**: Configure email/Slack notifications
2. **Add Monitoring**: Integrate with Datadog, CloudWatch, or Prometheus
3. **Optimize Schedule**: Adjust frequency based on requirements
4. **Data Retention**: Implement BigQuery partitioning and expiration
5. **Cost Optimization**: Use Cloud Scheduler for simpler workflows

---

## Additional Resources

- [Apache Airflow Documentation](https://airflow.apache.org/docs/)
- [Cloud Composer Guide](https://cloud.google.com/composer/docs)
- [FLUID CLI Reference](../../docs/cli/README.md)
- [BigQuery Best Practices](https://cloud.google.com/bigquery/docs/best-practices)

---

**Status:** ✅ Production-Ready

Last Updated: January 21, 2026
