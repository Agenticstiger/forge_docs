# Declarative Airflow DAG Generation - The FLUID Way

**Learn how FLUID transforms your data product contract into production-ready Airflow DAGs without writing orchestration code.**

---

## Overview

Apache Airflow is the industry-standard tool for orchestrating data pipelines, but creating DAGs typically requires writing hundreds of lines of Python code for each workflow. FLUID changes this by **automatically generating production-ready Airflow DAGs from your data product contract**.

This walkthrough shows you how to go from a YAML contract to a fully functional Airflow DAG with a single command—reducing 300+ lines of imperative Python to just one declarative statement.

**What you'll learn:**
- Why manual DAG development is time-consuming and error-prone
- How FLUID's declarative approach works
- Step-by-step tutorial using the Bitcoin tracker example
- Advanced patterns like multi-provider deployments
- Customization options for schedules, environments, and DAG IDs

---

## 🎯 The Problem: Manual Airflow DAG Development

### Traditional Approach (Imperative)

When building data pipelines with Airflow, you typically write **300+ lines of Python code** like this:

```python
# bitcoin_tracker_manual.py - THE OLD WAY
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.providers.google.cloud.operators.bigquery import BigQueryCheckOperator
from datetime import datetime, timedelta
import sys
import os

# Add project to path
sys.path.insert(0, os.path.dirname(__file__))
from ingest_bitcoin_prices import fetch_bitcoin_price, insert_to_bigquery

# Default arguments
default_args = {
    "owner": "data-engineering",
    "depends_on_past": False,
    "email": ["alerts@example.com"],
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
    "retry_exponential_backoff": True,
}

# DAG definition
dag = DAG(
    dag_id="bitcoin_tracker_manual",
    default_args=default_args,
    description="Hourly Bitcoin price ingestion",
    schedule_interval="0 * * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["crypto", "bitcoin", "manual"],
)

# Task 1: Validate contract
validate = BashOperator(
    task_id="validate_contract",
    bash_command="cd /path/to/project && python3 -m fluid_build.cli validate contract.fluid.yaml",
    dag=dag,
)

# Task 2: Fetch price
def fetch_btc_task(**context):
    price_data = fetch_bitcoin_price()
    context["ti"].xcom_push(key="price_usd", value=price_data["price_usd"])
    return price_data

fetch_price = PythonOperator(
    task_id="fetch_bitcoin_price",
    python_callable=fetch_btc_task,
    provide_context=True,
    dag=dag,
)

# Task 3: Insert to BigQuery
def insert_task(**context):
    price_data = context["ti"].xcom_pull(task_ids="fetch_bitcoin_price")
    success = insert_to_bigquery(
        price_data,
        "your-project-id",
        "crypto_data",
        "bitcoin_prices"
    )
    if not success:
        raise Exception("Insert failed")

insert_price = PythonOperator(
    task_id="insert_to_bigquery",
    python_callable=insert_task,
    provide_context=True,
    dag=dag,
)

# Task 4: Run dbt
run_dbt = BashOperator(
    task_id="run_dbt_models",
    bash_command="cd /path/to/project/dbt && dbt run --profiles-dir .",
    dag=dag,
)

# Task 5: Quality check
check_quality = BigQueryCheckOperator(
    task_id="check_data_quality",
    sql="""
        SELECT COUNT(*) > 0
        FROM `your-project.crypto_data.bitcoin_prices`
        WHERE DATE(timestamp) = CURRENT_DATE()
    """,
    use_legacy_sql=False,
    dag=dag,
)

# Define dependencies
validate >> fetch_price >> insert_price >> run_dbt >> check_quality
```

**Problems with this approach:**
- ❌ **300+ lines of boilerplate code**
- ❌ **Hardcoded project paths and IDs**
- ❌ **Manual dependency management**
- ❌ **No single source of truth** (contract vs DAG can drift)
- ❌ **Copy-paste errors across similar DAGs**
- ❌ **Hard to maintain** (change contract, must manually update DAG)
- ❌ **Not portable** (GCP-specific, can't easily switch providers)

---

## ✨ The FLUID Solution: Declarative DAG Generation

### What You Declare (One Source of Truth)

Your **data product contract** (`contract.fluid.yaml`) already contains everything needed:

```yaml
fluidVersion: "0.7.1"
kind: DataProduct
id: crypto.bitcoin_prices_gcp
name: bitcoin-prices-gcp

# 1️⃣ Metadata drives DAG configuration
metadata:
  layer: Gold
  owner:
    team: data-engineering
    email: data-eng@example.com

tags:
  - crypto
  - bitcoin

# 2️⃣ Builds define the workflow
builds:
  - id: ingest_bitcoin_prices
    description: Fetch Bitcoin prices from CoinGecko API
    pattern: hybrid-reference
    engine: python
    repository: ./runtime
    properties:
      model: ingest_bitcoin_prices
    
    execution:
      trigger:
        type: manual
      runtime:
        resources:
          memory: "512Mi"
        timeout: "PT5M"
      retries:
        maxAttempts: 3
        backoffStrategy: exponential
    
    outputs:
      - bitcoin_prices_table

  - id: calculate_daily_summary
    description: Calculate daily price statistics
    engine: dbt
    repository: ./dbt
    properties:
      model: daily_price_summary
    outputs:
      - daily_price_summary

  - id: calculate_price_trends
    description: Calculate moving averages
    engine: dbt
    repository: ./dbt
    properties:
      model: price_trends
    outputs:
      - price_trends

# 3️⃣ Exposes define datasets and bindings
exposes:
  - exposeId: bitcoin_prices_table
    kind: table
    title: Bitcoin Prices Table
    
    binding:
      platform: gcp
      format: bigquery_table
      location:
        project: <<YOUR_PROJECT_HERE>>
        dataset: crypto_data
        table: bitcoin_prices
        region: us-central1
```

### What FLUID Generates (Automatically)

**One command:**
```bash
fluid generate-airflow contract.fluid.yaml \
  -o dags/bitcoin_tracker.py \
  --dag-id bitcoin_tracker \
  --schedule "0 * * * *"
```

**Output: Production-ready Airflow DAG**
```python
"""
Airflow DAG for FLUID Data Product: bitcoin-prices-gcp

Auto-generated from FLUID contract v0.7.1
Generated at: 2026-01-21T12:00:00

Domain: crypto
Description: Bitcoin price tracking data product
"""
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago
from datetime import datetime, timedelta

# DAG configuration (from contract metadata)
default_args = {
    'owner': 'fluid',
    'depends_on_past': False,
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 3,  # ← From contract.builds[].execution.retries
    'retry_delay': timedelta(minutes=5),
}

# DAG definition
dag = DAG(
    dag_id="bitcoin_tracker",
    description="""Bitcoin price tracking data product""",
    schedule_interval="0 * * * *",  # ← From --schedule argument
    start_date=days_ago(1),
    catchup=False,
    tags=["fluid", "crypto", "bitcoin"],  # ← From contract.tags
    default_args=default_args
)

# Provision dataset: bitcoin_prices_table (from exposes[0])
provision_bitcoin_prices_table = BashOperator(
    task_id="provision_bitcoin_prices_table",
    bash_command="bq mk --project_id=<<YOUR_PROJECT_HERE>> --dataset crypto_data || true",
    dag=dag
)

# Schedule task: ingest_bitcoin_prices (from builds[0])
schedule_ingest_bitcoin_prices = BashOperator(
    task_id="schedule_ingest_bitcoin_prices",
    bash_command="python3 runtime/ingest_bitcoin_prices.py",
    dag=dag
)

# Schedule task: calculate_daily_summary (from builds[1])
schedule_calculate_daily_summary = BashOperator(
    task_id="schedule_calculate_daily_summary",
    bash_command="dbt run --models daily_price_summary",
    dag=dag
)

# Schedule task: calculate_price_trends (from builds[2])
schedule_calculate_price_trends = BashOperator(
    task_id="schedule_calculate_price_trends",
    bash_command="dbt run --models price_trends",
    dag=dag
)

# Task dependencies (inferred from builds.outputs)
provision_bitcoin_prices_table >> schedule_ingest_bitcoin_prices
schedule_ingest_bitcoin_prices >> schedule_calculate_daily_summary
schedule_ingest_bitcoin_prices >> schedule_calculate_price_trends
```

---

## 📊 Side-by-Side Comparison

Here's how the traditional manual approach compares to FLUID's declarative generation across key development aspects:

| Aspect | Manual Approach | FLUID Declarative |
|--------|----------------|-------------------|
| **Lines of Code** | 300+ lines Python | **1 command** |
| **Maintenance** | Update DAG + Contract | **Update contract only** |
| **Portability** | GCP-specific code | **Provider-agnostic contract** |
| **Consistency** | Can drift from contract | **Contract IS source of truth** |
| **Testing** | Test Python code | **Test YAML contract** |
| **Onboarding** | Learn Airflow + Python | **Learn FLUID contracts** |
| **Multi-env** | Copy-paste DAG | **Same contract, diff env** |
| **Provider switch** | Rewrite operators | **Change binding.platform** |

---

## 🚀 Step-by-Step: Bitcoin Tracker with Declarative Airflow

Now let's put this into practice. We'll use the Bitcoin price tracker example to demonstrate how FLUID generates Airflow DAGs from contracts. This tutorial takes about 10-15 minutes and assumes you have a working FLUID installation.

::: tip What We'll Build
We'll generate an Airflow DAG that:
- Provisions BigQuery datasets and tables
- Runs Bitcoin price ingestion (Python)
- Executes dbt transformations
- Manages task dependencies automatically
- Includes retry logic and scheduling
:::

### Prerequisites

```bash
# 1. Ensure FLUID CLI is available
fluid --version  # Should show v0.7.1 or higher

# 2. Navigate to example
cd examples/bitcoin-tracker

# 3. Validate contract
fluid validate contract.fluid.yaml
```

### Step 1: Generate Airflow DAG (Declarative Way)

```bash
# Generate production-ready DAG from contract
fluid generate-airflow contract.fluid.yaml \
  -o airflow/dags/bitcoin_tracker_declarative.py \
  --dag-id bitcoin_tracker_declarative \
  --schedule "0 * * * *" \
  --verbose
```

**Output:**
```
✓ Loading contract from contract.fluid.yaml
✓ Generating Airflow DAG...
✓ DAG written to: airflow/dags/bitcoin_tracker_declarative.py
  Contract ID: crypto.bitcoin_prices_gcp
  DAG ID: bitcoin_tracker_declarative
  Schedule: 0 * * * *
```

**What just happened?**
1. ✅ FLUID read your contract
2. ✅ Parsed `builds`, `exposes`, and `execution` config
3. ✅ Generated provider-specific commands (GCP BigQuery)
4. ✅ Created task dependencies from `outputs`
5. ✅ Applied retry/schedule configuration
6. ✅ Wrote production-ready Python DAG

### Step 2: Review Generated DAG

```bash
# View the generated DAG
cat airflow/dags/bitcoin_tracker_declarative.py
```

Notice:
- ✅ Tasks match your `builds` array
- ✅ Dataset provisioning from `exposes` bindings
- ✅ Retry config from `execution.retries`
- ✅ Schedule from command argument
- ✅ Tags from contract metadata

### Step 3: Test DAG Syntax

```bash
# Validate DAG syntax without running
python3 airflow/dags/bitcoin_tracker_declarative.py
echo $?  # Should be 0 (success)
```

### Step 4: Deploy to Airflow

#### Option A: Local Airflow

```bash
# Set Airflow home
export AIRFLOW_HOME=$PWD/airflow

# Initialize Airflow
airflow db init

# Create admin user
airflow users create \
  --username admin \
  --password admin \
  --firstname Admin \
  --lastname User \
  --role Admin \
  --email admin@example.com

# Start webserver (terminal 1)
airflow webserver --port 8080

# Start scheduler (terminal 2)
airflow scheduler
```

Access UI: http://localhost:8080 (admin/admin)

#### Option B: Cloud Composer (GCP)

```bash
# Create Composer environment
gcloud composer environments create bitcoin-tracker \
  --location us-central1 \
  --image-version composer-2.6.0-airflow-2.6.3

# Upload DAG
BUCKET=$(gcloud composer environments describe bitcoin-tracker \
  --location us-central1 \
  --format="get(config.dagGcsPrefix)")

gsutil cp airflow/dags/bitcoin_tracker_declarative.py $BUCKET/dags/
```

---

## 🔄 The Declarative Workflow

The real power of FLUID's declarative approach becomes clear when you need to make changes. Instead of manually editing DAG code, you simply update your contract and regenerate. Here's the three-step workflow:

### 1. Define Once (Contract)

```yaml
# contract.fluid.yaml
builds:
  - id: new_transformation
    engine: dbt
    repository: ./dbt
    properties:
      model: price_volatility
    outputs:
      - price_volatility_view
```

### 2. Regenerate DAG

```bash
# Regenerate from updated contract
fluid generate-airflow contract.fluid.yaml \
  -o airflow/dags/bitcoin_tracker_declarative.py \
  --schedule "0 * * * *"
```

### 3. Deploy

```bash
# DAG automatically includes new task!
# No manual code changes needed
```

---

## 🎨 Advanced: Multi-Provider Example

One of FLUID's most powerful features is **provider portability**. The same contract can deploy to different cloud platforms by simply changing the `binding.platform` field. This makes migrations and multi-cloud strategies straightforward.

Let's look at migrating our Bitcoin tracker from GCP to Snowflake:

### GCP → Snowflake Migration

**Before (GCP):**
```yaml
exposes:
  - exposeId: bitcoin_prices
    binding:
      platform: gcp
      format: bigquery_table
      location:
        project: my-gcp-project
        dataset: crypto_data
```

**After (Snowflake):**
```yaml
exposes:
  - exposeId: bitcoin_prices
    binding:
      platform: snowflake
      format: snowflake_table
      location:
        account: xy12345.us-east-1
        database: CRYPTO_DB
        schema: PROD
```

**Regenerate:**
```bash
fluid generate-airflow contract.fluid.yaml -o dags/bitcoin_tracker.py
```

**Result:** DAG automatically uses Snowflake operators instead of BigQuery! 🎉

---

## ✅ Why Use Declarative DAG Generation?

FLUID's declarative approach offers several compelling advantages over manual DAG development:

### 1. Single Source of Truth
- Your contract defines **both** infrastructure **and** orchestration
- No drift between documentation, DAGs, and actual deployments
- Version control one file instead of many

### 2. Drastically Improved Maintainability
- Update contract → regenerate DAG
- No manual synchronization
- Version control the contract, not generated code

### 3. Testability
```bash
# Test contract before generating DAG
fluid validate contract.fluid.yaml

# Generate and test DAG
fluid generate-airflow contract.fluid.yaml -o test_dag.py
python3 test_dag.py  # Syntax check
```

### 4. Portability
- Same contract works on GCP, AWS, Snowflake
- Just change `binding.platform`
- Regenerate DAG with provider-specific operators

### 5. Consistency
- All data products follow same DAG structure
- Standardized retry/schedule patterns
- Centralized configuration management

### 6. Developer Experience
```bash
# Before: Write 300 lines of Python
# After: Run 1 command
fluid generate-airflow contract.yaml -o dag.py
```

---

## 🔧 Customization Options

While FLUID generates DAGs declaratively from your contract, you can customize the output for different environments and use cases using command-line flags:

### Override Schedule

```bash
# Different schedules for different environments
fluid generate-airflow contract.yaml -o dag.py --schedule "*/15 * * * *"  # Every 15 min
fluid generate-airflow contract.yaml -o dag.py --schedule "0 2 * * *"      # Daily at 2 AM
```

### Override DAG ID

```bash
# Environment-specific DAG IDs
fluid generate-airflow contract.yaml \
  -o dags/bitcoin_prod.py \
  --dag-id bitcoin_tracker_prod

fluid generate-airflow contract.yaml \
  -o dags/bitcoin_dev.py \
  --dag-id bitcoin_tracker_dev
```

### Use Environment Overlays

```bash
# Generate from dev environment
fluid generate-airflow contract.yaml \
  -o dags/bitcoin_dev.py \
  --env dev

# Generate from prod environment
fluid generate-airflow contract.yaml \
  -o dags/bitcoin_prod.py \
  --env prod
```

---

## 📚 Additional Resources

### FLUID Documentation
- [CLI Reference](../cli/README.md) - Complete command reference
- [GCP Deployment Guide](gcp.md) - Deploy to Google Cloud Platform
- [Local Development Guide](local.md) - Test with DuckDB locally
- [Advanced Topics](../advanced/airflow.md) - Airflow integration details

### Airflow Resources
- [Apache Airflow Docs](https://airflow.apache.org/docs/)
- [GCP Cloud Composer](https://cloud.google.com/composer/docs)

### Examples
- [Bitcoin Tracker Example](../../examples/bitcoin-tracker/) - Working code with this walkthrough
- [Netflix Preferences Example](../../examples/netflix-preferences-local/) - Local development example

---

## 🎓 Summary

You've learned how FLUID's declarative approach transforms Airflow DAG development from a manual, code-heavy process into a simple, contract-driven workflow.

**Traditional Airflow Development (The Old Way):**
1. Write data product contract
2. Write Python DAG manually (300+ lines)
3. Test DAG syntax and logic
4. Deploy DAG to Airflow
5. Maintain both contract **and** DAG in sync

**FLUID Declarative Approach (The New Way):**
1. Write data product contract ✅
2. Run `fluid generate-airflow contract.yaml -o dag.py` ✅
3. Deploy generated DAG ✅
4. Maintain **only** the contract ✅

**Key Takeaways:**
- **90% less code** - One command replaces 300+ lines of Python
- **100% consistency** - Contract is the single source of truth
- **Infinite portability** - Same contract works on GCP, AWS, Snowflake
- **Zero drift** - DAG always matches contract when regenerated
- **Faster development** - Minutes instead of hours per pipeline

---

**🚀 Ready to go declarative?**

```bash
cd examples/bitcoin-tracker
fluid generate-airflow contract.fluid.yaml -o airflow/dags/my_dag.py --schedule "0 * * * *"
```

**Welcome to the declarative future of data orchestration!** 🎉
