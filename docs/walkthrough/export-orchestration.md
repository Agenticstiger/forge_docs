# Generating Orchestration Code from Contracts

**Docs Baseline:** CLI `0.7.9`  
**Status:** ✅ Production Ready

::: warning Compatibility note
This walkthrough preserves older `0.7.1` orchestration snippets for historical context. For current docs and new automation, prefer `fluid generate schedule --scheduler airflow`. `fluid generate-airflow` remains available as a compatibility shortcut.
:::

---

## Overview

Fluid Forge transforms your declarative contracts into production-ready orchestration code for **three engines**: Airflow, Dagster, and Prefect.

### Why Generate DAGs?

- **🚀 Fast Deployment** - Generate 100+ lines of orchestration code in <3ms
- **☁️ Multi-Cloud** - Support for AWS, GCP, and Snowflake
- **✅ Validated** - Contract validation with circular dependency detection
- **📦 Production-Ready** - Error handling, retries, logging built-in
- **🔄 Multi-Engine** - Airflow, Dagster, and Prefect all available via CLI

---

## Quick Start

### 1. Create a Contract

```yaml
# crypto-analytics.fluid.yaml
fluidVersion: "0.7.1"
kind: DataProduct
id: crypto.bitcoin_analytics
name: bitcoin-analytics

metadata:
  owner: data-engineering
  description: Bitcoin price tracking and analytics

orchestration:
  schedule: "@hourly"
  tasks:
    - taskId: fetch_prices
      action: bigquery_query
      config:
        query: "SELECT * FROM crypto.raw_prices WHERE timestamp > CURRENT_TIMESTAMP() - INTERVAL 1 HOUR"
    
    - taskId: calculate_metrics
      action: bigquery_query
      dependsOn: [fetch_prices]
      config:
        query: "INSERT INTO crypto.hourly_metrics SELECT price_timestamp, AVG(price_usd) as avg_price..."
```

### 2. Generate Airflow DAG

```bash
# Generate Airflow DAG
fluid generate-airflow crypto-analytics.fluid.yaml -o dags/crypto_bitcoin_analytics.py

# With verbose output
fluid generate-airflow crypto-analytics.fluid.yaml -o dags/pipeline.py --verbose
```

### 3. Deploy to Airflow

```bash
# Copy to Airflow DAGs folder
cp dags/crypto_bitcoin_analytics.py $AIRFLOW_HOME/dags/

# Or for Cloud Composer (GCP)
gsutil cp dags/crypto_bitcoin_analytics.py gs://your-composer-bucket/dags/

# Or for MWAA (AWS)
aws s3 cp dags/crypto_bitcoin_analytics.py s3://your-mwaa-bucket/dags/
```

---

## Provider Examples

### GCP + BigQuery

**Contract:**
```yaml
fluidVersion: "0.7.1"
kind: DataProduct
id: gcp.customer_analytics
name: customer-analytics

platform:
  provider: gcp
  project: my-project-id
  region: us-central1

orchestration:
  schedule: "@daily"
  tasks:
    - taskId: create_dataset
      action: create_bigquery_dataset
      config:
        dataset: analytics
        location: US
    
    - taskId: create_table
      action: create_bigquery_table
      dependsOn: [create_dataset]
      config:
        dataset: analytics
        table: customers
        schema:
          - name: customer_id
            type: INTEGER
          - name: name
            type: STRING
    
    - taskId: load_data
      action: bigquery_query
      dependsOn: [create_table]
      config:
        query: |
          INSERT INTO analytics.customers
          SELECT * FROM raw.customer_data
          WHERE date = CURRENT_DATE()
```

**Generate Airflow DAG:**
```bash
fluid generate-airflow gcp-analytics.yaml -o dags/gcp_customer_analytics.py
```

**Generated Airflow DAG:**
```python
from airflow import DAG
from airflow.providers.google.cloud.operators.bigquery import (
    BigQueryCreateEmptyDatasetOperator,
    BigQueryCreateEmptyTableOperator,
    BigQueryInsertJobOperator
)
from datetime import datetime, timedelta

default_args = {
    'owner': 'data-engineering',
    'retries': 3,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    dag_id='gcp_customer_analytics',
    default_args=default_args,
    description='Customer analytics pipeline',
    schedule_interval='@daily',
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=['analytics', 'customers']
) as dag:
    
    create_dataset = BigQueryCreateEmptyDatasetOperator(
        task_id='create_dataset',
        dataset_id='analytics',
        location='US',
        project_id='my-project-id'
    )
    
    create_table = BigQueryCreateEmptyTableOperator(
        task_id='create_table',
        dataset_id='analytics',
        table_id='customers',
        schema_fields=[
            {'name': 'customer_id', 'type': 'INTEGER', 'mode': 'NULLABLE'},
            {'name': 'name', 'type': 'STRING', 'mode': 'NULLABLE'}
        ],
        project_id='my-project-id'
    )
    
    load_data = BigQueryInsertJobOperator(
        task_id='load_data',
        configuration={
            'query': {
                'query': """
                    INSERT INTO analytics.customers
                    SELECT * FROM raw.customer_data
                    WHERE date = CURRENT_DATE()
                """,
                'useLegacySql': False
            }
        },
        project_id='my-project-id'
    )
    
    create_dataset >> create_table >> load_data
```

---

### AWS + S3 + Glue (Dagster Example)

**Contract:**
```yaml
fluidVersion: "0.7.1"
kind: DataProduct
id: aws.sales_analytics
name: sales-analytics

platform:
  provider: aws
  account_id: "123456789012"
  region: us-east-1

orchestration:
  schedule: "0 */6 * * *"  # Every 6 hours
  tasks:
    - taskId: create_bucket
      action: create_s3_bucket
      config:
        bucket: sales-analytics-data
        region: us-east-1
    
    - taskId: create_database
      action: create_glue_database
      dependsOn: [create_bucket]
      config:
        database: sales
    
    - taskId: create_table
      action: create_glue_table
      dependsOn: [create_database]
      config:
        database: sales
        table: transactions
        location: s3://sales-analytics-data/transactions/
        format: PARQUET
```

**Generate Dagster Pipeline:**
```bash
fluid export aws-sales.yaml --engine dagster -o pipelines/
```

**Generated Dagster Code:**
```python
from dagster import op, job, resource, In, Out
import boto3

@resource
def aws_s3_client(context):
    return boto3.client('s3', region_name='us-east-1')

@resource
def aws_glue_client(context):
    return boto3.client('glue', region_name='us-east-1')

@op(required_resource_keys={'s3_client'})
def create_bucket(context):
    s3 = context.resources.s3_client
    bucket_name = 'sales-analytics-data'
    
    try:
        s3.create_bucket(Bucket=bucket_name)
        context.log.info(f"Created S3 bucket: {bucket_name}")
        return bucket_name
    except Exception as e:
        context.log.error(f"Error creating bucket: {e}")
        raise

@op(required_resource_keys={'glue_client'}, ins={'bucket': In()})
def create_database(context, bucket):
    glue = context.resources.glue_client
    
    try:
        glue.create_database(
            DatabaseInput={
                'Name': 'sales',
                'Description': 'Sales analytics database'
            }
        )
        context.log.info("Created Glue database: sales")
        return 'sales'
    except Exception as e:
        context.log.error(f"Error creating database: {e}")
        raise

@op(required_resource_keys={'glue_client'}, ins={'database': In()})
def create_table(context, database):
    glue = context.resources.glue_client
    
    try:
        glue.create_table(
            DatabaseName=database,
            TableInput={
                'Name': 'transactions',
                'StorageDescriptor': {
                    'Location': 's3://sales-analytics-data/transactions/',
                    'InputFormat': 'org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat',
                    'OutputFormat': 'org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat'
                }
            }
        )
        context.log.info("Created Glue table: transactions")
        return 'transactions'
    except Exception as e:
        context.log.error(f"Error creating table: {e}")
        raise

@job(resource_defs={
    's3_client': aws_s3_client,
    'glue_client': aws_glue_client
})
def aws_sales_analytics():
    database = create_database(create_bucket())
    create_table(database)
```

---

### Snowflake + Data Warehousing (Prefect Example)

**Contract:**
```yaml
fluidVersion: "0.7.1"
kind: DataProduct
id: snowflake.inventory_analytics
name: inventory-analytics

platform:
  provider: snowflake
  account: xy12345.us-east-1
  warehouse: COMPUTE_WH
  database: ANALYTICS

orchestration:
  schedule: "@hourly"
  tasks:
    - taskId: create_database
      action: create_database
      config:
        database: ANALYTICS
    
    - taskId: create_schema
      action: create_schema
      dependsOn: [create_database]
      config:
        schema: INVENTORY
    
    - taskId: create_table
      action: create_table
      dependsOn: [create_schema]
      config:
        table: INVENTORY.STOCK_LEVELS
        columns:
          - product_id: NUMBER
          - quantity: NUMBER
          - last_updated: TIMESTAMP
    
    - taskId: load_data
      action: run_query
      dependsOn: [create_table]
      config:
        query: |
          INSERT INTO INVENTORY.STOCK_LEVELS
          SELECT product_id, SUM(quantity), CURRENT_TIMESTAMP()
          FROM RAW.INVENTORY_UPDATES
          WHERE update_time > DATEADD(hour, -1, CURRENT_TIMESTAMP())
          GROUP BY product_id
```

**Generate Prefect Flow:**
```bash
fluid export snowflake-inventory.yaml --engine prefect -o flows/
```

**Generated Prefect Code:**
```python
from prefect import flow, task
from prefect.deployments import Deployment
from prefect.server.schemas.schedules import CronSchedule
import snowflake.connector

def get_snowflake_connection():
    return snowflake.connector.connect(
        account='xy12345.us-east-1',
        user='...',
        password='...',
        warehouse='COMPUTE_WH',
        database='ANALYTICS'
    )

@task(retries=3, retry_delay_seconds=300)
def create_database():
    conn = get_snowflake_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('CREATE DATABASE IF NOT EXISTS ANALYTICS')
        print("Created database: ANALYTICS")
    finally:
        cursor.close()
        conn.close()

@task(retries=3, retry_delay_seconds=300)
def create_schema():
    conn = get_snowflake_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('CREATE SCHEMA IF NOT EXISTS INVENTORY')
        print("Created schema: INVENTORY")
    finally:
        cursor.close()
        conn.close()

@task(retries=3, retry_delay_seconds=300)
def create_table():
    conn = get_snowflake_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS INVENTORY.STOCK_LEVELS (
                product_id NUMBER,
                quantity NUMBER,
                last_updated TIMESTAMP
            )
        """)
        print("Created table: INVENTORY.STOCK_LEVELS")
    finally:
        cursor.close()
        conn.close()

@task(retries=3, retry_delay_seconds=300)
def load_data():
    conn = get_snowflake_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO INVENTORY.STOCK_LEVELS
            SELECT product_id, SUM(quantity), CURRENT_TIMESTAMP()
            FROM RAW.INVENTORY_UPDATES
            WHERE update_time > DATEADD(hour, -1, CURRENT_TIMESTAMP())
            GROUP BY product_id
        """)
        print(f"Loaded {cursor.rowcount} rows")
    finally:
        cursor.close()
        conn.close()

@flow(name='snowflake_inventory_analytics')
def main():
    create_database()
    create_schema()
    create_table()
    load_data()

# Create deployment
if __name__ == '__main__':
    deployment = Deployment.build_from_flow(
        flow=main,
        name='inventory-analytics-deployment',
        schedule=CronSchedule(cron='0 * * * *'),  # @hourly
        work_queue_name='default'
    )
    deployment.apply()
```

---

## Engine Comparison

::: tip All Engines Available
- **Airflow**: `fluid generate-airflow` or `fluid export --engine airflow`
- **Dagster**: `fluid export --engine dagster`
- **Prefect**: `fluid export --engine prefect`
:::

| Feature | Airflow | Dagster | Prefect |
|---------|---------|---------|---------||
| **CLI Availability** | ✅ Available | ✅ Available | ✅ Available |
| **Ease of Use** | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Type Safety** | ❌ | ✅ | ✅ |
| **Resource Management** | Manual | Built-in | Built-in |
| **Testing** | Limited | Excellent | Good |
| **UI Quality** | Good | Excellent | Excellent |
| **Community** | Largest | Growing | Growing |
| **Cloud Hosting** | Cloud Composer (GCP) | Dagster Cloud | Prefect Cloud |
| **Best For** | Traditional ETL | Data engineering teams | Modern data workflows |

### Generation Performance (Benchmarked)

All three engines are available in the CLI.

| Provider | Airflow | Dagster | Prefect |
|----------|---------------|------------------|------------------|
| **AWS** | 2.05ms | 0.38ms | 0.32ms |
| **GCP** | 1.83ms | 0.34ms | 1.91ms |
| **Snowflake** | 2.08ms | 0.35ms | 0.33ms |

### Output Size (Small Contract)

| Provider | Airflow | Dagster | Prefect |
|----------|---------|---------|---------|
| **AWS** | 1.91KB | 3.98KB | 3.84KB |
| **GCP** | 2.10KB | 2.43KB | 2.29KB |
| **Snowflake** | 1.83KB | 1.72KB | 2.52KB |

---

## Advanced Features

### Contract Validation

All exports include automatic validation:

```bash
# Invalid contract (circular dependency)
fluid export bad-contract.yaml --engine airflow

# Output:
# ❌ Export failed: Circular dependencies detected in tasks: task_a, task_b
```

**Validation Checks:**
- ✅ Orchestration section present
- ✅ Non-empty task list
- ✅ Unique task IDs
- ✅ Valid task dependencies
- ✅ No circular dependencies

### Schedule Conversion

Fluid Forge automatically converts schedule expressions:

| Fluid Schedule | Airflow | Dagster | Prefect |
|----------------|---------|---------|---------|
| `@hourly` | `@hourly` | `"0 * * * *"` | `CronSchedule(cron="0 * * * *")` |
| `@daily` | `@daily` | `"0 0 * * *"` | `CronSchedule(cron="0 0 * * *")` |
| `0 */6 * * *` | `0 */6 * * *` | `"0 */6 * * *"` | `CronSchedule(cron="0 */6 * * *")` |

### Custom Configuration

Inject custom settings into generated code:

```yaml
orchestration:
  schedule: "@daily"
  config:
    # Airflow-specific
    airflow:
      retries: 5
      retry_delay_minutes: 10
      email_on_failure: true
      email: ["ops@company.com"]
    
    # Dagster-specific
    dagster:
      max_runtime_seconds: 3600
      
    # Prefect-specific
    prefect:
      timeout_seconds: 7200
      tags: ["production", "critical"]
```

---

## Best Practices

### 1. Version Control Your Contracts

```bash
git add contracts/
git commit -m "Add customer analytics contract"

# Regenerate when contract changes
fluid export contracts/customer-analytics.yaml --engine airflow -o dags/
```

### 2. Test Generated Code

```bash
# Python syntax check
python -m py_compile dags/customer_analytics.py

# Airflow validation
airflow dags test customer_analytics 2026-01-30

# Dagster validation
dagster pipeline execute -f pipelines/customer_analytics.py
```

### 3. Use CI/CD

```yaml
# .github/workflows/generate-dags.yml
name: Generate Orchestration Code

on:
  push:
    paths:
      - 'contracts/**'

jobs:
  generate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Install Fluid Forge
        run: pip install data-product-forge
      
      - name: Generate Airflow DAGs
        run: |
          fluid export contracts/*.yaml --engine airflow -o dags/
      
      - name: Commit generated code
        run: |
          git add dags/
          git commit -m "Regenerate DAGs from contracts"
          git push
```

### 4. Monitor Generated Pipelines

All generated code includes logging:

```python
# Airflow
context.log.info("Processing task...")

# Dagster
context.log.info("Processing op...")

# Prefect
print("Processing task...")  # Captured by Prefect
```

---

## Troubleshooting

### Export Fails

**Error:** `ProviderError: Invalid contract: Contract missing 'orchestration'`

**Solution:** Add orchestration section:
```yaml
orchestration:
  schedule: "@daily"
  tasks: []
```

---

**Error:** `Circular dependencies detected in tasks: task_a, task_b`

**Solution:** Fix dependency graph:
```yaml
# Bad (circular)
tasks:
  - taskId: task_a
    dependsOn: [task_b]
  - taskId: task_b
    dependsOn: [task_a]

# Good (linear)
tasks:
  - taskId: task_a
  - taskId: task_b
    dependsOn: [task_a]
```

---

### Generated Code Errors

**Error:** `SyntaxError in generated DAG`

**Solution:** Update to latest Fluid Forge version:
```bash
pip install --upgrade data-product-forge
```

---

**Error:** `ImportError: No module named 'airflow.providers...'`

**Solution:** Install required provider packages:
```bash
pip install apache-airflow-providers-google
pip install apache-airflow-providers-amazon
pip install apache-airflow-providers-snowflake
```

---

## Next Steps

- [Airflow DAG Deployment Guide](/forge_docs/walkthrough/airflow-declarative.html)
- [GCP Integration](/forge_docs/walkthrough/gcp.html)
- [CI/CD Setup](/forge_docs/walkthrough/jenkins-cicd.html)
- [Provider Roadmap](/forge_docs/providers/roadmap.html)

---

**Questions?** Open an issue on [GitHub](https://github.com/Agenticstiger/forge-cli/issues)
