"""
Bitcoin Price Tracker - Enhanced Airflow DAG

This DAG orchestrates hourly Bitcoin price ingestion from CoinGecko API
and runs dbt transformations on GCP BigQuery.

Features:
- Hourly price ingestion
- Automatic retries with exponential backoff
- Data quality checks
- Email alerts on failures
- Execution metrics tracking

Author: FLUID Forge
Version: 1.0.0
"""

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

# Add project to Python path to import local modules
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_DIR)

# Import local ingestion script
try:
    from ingest_bitcoin_prices import fetch_bitcoin_price, insert_to_bigquery
except ImportError:
    print("WARNING: ingest_bitcoin_prices module not found. Using mock functions.")
    
    def fetch_bitcoin_price():
        """Mock function for testing."""
        return {
            "price_usd": 50000.0,
            "price_eur": 42000.0,
            "price_gbp": 36000.0,
            "market_cap_usd": 1000000000000,
            "volume_24h_usd": 50000000000,
            "price_change_24h": 2.5,
            "last_updated": datetime.now().isoformat(),
            "timestamp": datetime.now().isoformat(),
        }
    
    def insert_to_bigquery(row, project_id, dataset, table):
        """Mock function for testing."""
        print(f"MOCK: Would insert to {project_id}.{dataset}.{table}")
        return True

# Configuration from environment variables
GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "dust-labs-485011")
BQ_DATASET = os.environ.get("BQ_DATASET", "crypto_data")
BQ_TABLE = os.environ.get("BQ_TABLE", "bitcoin_prices")

# Default arguments for all tasks
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
    doc_md=__doc__,
) as dag:

    # ============================================================
    # TASK 1: Validate FLUID Contract
    # ============================================================
    validate_contract = BashOperator(
        task_id="validate_contract",
        bash_command="""
        cd {{ params.project_dir }} && \
        python3 -m fluid_build.cli validate contract.fluid.yaml
        """,
        params={"project_dir": PROJECT_DIR},
        doc_md="""
        ## Validate FLUID Contract
        
        Validates the FLUID contract syntax before execution.
        Ensures all required fields are present and properly formatted.
        """,
    )

    # ============================================================
    # TASK 2: Fetch Bitcoin Price from CoinGecko API
    # ============================================================
    def fetch_btc_price_task(**context):
        """
        Fetch current Bitcoin price from CoinGecko API.
        
        Returns:
            dict: Price data including USD, EUR, GBP, market cap, volume
        
        Raises:
            Exception: If API request fails
        """
        print("📡 Fetching Bitcoin price from CoinGecko API...")
        price_data = fetch_bitcoin_price()
        
        # Push to XCom for downstream tasks and monitoring
        context["ti"].xcom_push(key="btc_price_usd", value=price_data["price_usd"])
        context["ti"].xcom_push(key="btc_price_eur", value=price_data["price_eur"])
        context["ti"].xcom_push(key="market_cap", value=price_data["market_cap_usd"])
        context["ti"].xcom_push(key="volume_24h", value=price_data["volume_24h_usd"])
        context["ti"].xcom_push(key="price_change_24h", value=price_data.get("price_change_24h", 0))
        
        print(f"✓ Fetched BTC Price: ${price_data['price_usd']:,.2f} USD")
        print(f"  Market Cap: ${price_data['market_cap_usd']:,.0f}")
        print(f"  24h Volume: ${price_data['volume_24h_usd']:,.0f}")
        print(f"  24h Change: {price_data.get('price_change_24h', 0):.2f}%")
        
        return price_data

    fetch_price = PythonOperator(
        task_id="fetch_bitcoin_price",
        python_callable=fetch_btc_price_task,
        provide_context=True,
        doc_md="""
        ## Fetch Bitcoin Price
        
        Calls CoinGecko API to retrieve current Bitcoin price data.
        Free tier, no authentication required.
        
        **API Endpoint:** https://api.coingecko.com/api/v3/simple/price
        """,
    )

    # ============================================================
    # TASK 3: Insert Price Data to BigQuery
    # ============================================================
    def insert_to_bq_task(**context):
        """
        Insert fetched price data to BigQuery table.
        
        Returns:
            bool: True if successful
        
        Raises:
            Exception: If BigQuery insert fails
        """
        print(f"💾 Inserting to BigQuery: {GCP_PROJECT_ID}.{BQ_DATASET}.{BQ_TABLE}")
        
        # Pull price data from previous task
        price_data = context["ti"].xcom_pull(task_ids="fetch_bitcoin_price")
        
        # Insert to BigQuery
        success = insert_to_bigquery(price_data, GCP_PROJECT_ID, BQ_DATASET, BQ_TABLE)
        
        if not success:
            raise Exception(f"Failed to insert to BigQuery: {GCP_PROJECT_ID}.{BQ_DATASET}.{BQ_TABLE}")
        
        print(f"✓ Successfully inserted to {GCP_PROJECT_ID}.{BQ_DATASET}.{BQ_TABLE}")
        return True

    insert_price = PythonOperator(
        task_id="insert_to_bigquery",
        python_callable=insert_to_bq_task,
        provide_context=True,
        doc_md="""
        ## Insert to BigQuery
        
        Writes price data to BigQuery streaming insert API.
        Table schema is auto-created if it doesn't exist.
        """,
    )

    # ============================================================
    # TASK 4: Run dbt Transformations
    # ============================================================
    run_dbt = BashOperator(
        task_id="run_dbt_models",
        bash_command="""
        cd {{ params.project_dir }}/dbt && \
        dbt run --profiles-dir . --select daily_price_summary price_trends
        """,
        params={"project_dir": PROJECT_DIR},
        doc_md="""
        ## Run dbt Models
        
        Executes dbt transformations:
        1. **daily_price_summary**: Daily aggregates (avg, min, max, close)
        2. **price_trends**: 7-day and 30-day moving averages
        """,
    )

    # ============================================================
    # TASK 5: Data Quality Check - Raw Prices
    # ============================================================
    check_data_quality = BigQueryCheckOperator(
        task_id="check_data_quality",
        sql=f"""
        SELECT COUNT(*) > 0 AS has_data
        FROM `{GCP_PROJECT_ID}.{BQ_DATASET}.{BQ_TABLE}`
        WHERE DATE(timestamp) = CURRENT_DATE()
        AND price_usd > 0
        """,
        use_legacy_sql=False,
        doc_md="""
        ## Data Quality Check
        
        Verifies that price data exists for today and prices are valid (> 0).
        """,
    )

    # ============================================================
    # TASK 6: Verify dbt Transformations
    # ============================================================
    verify_transformations = BigQueryCheckOperator(
        task_id="verify_transformations",
        sql=f"""
        SELECT COUNT(*) > 0 AS has_summary
        FROM `{GCP_PROJECT_ID}.{BQ_DATASET}.daily_price_summary`
        WHERE price_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY)
        """,
        use_legacy_sql=False,
        doc_md="""
        ## Verify Transformations
        
        Confirms that dbt models ran successfully and produced output.
        """,
    )

    # ============================================================
    # TASK 7: Calculate and Log Metrics
    # ============================================================
    def send_metrics_task(**context):
        """
        Log execution metrics and send to monitoring system.
        
        Future: Integrate with Datadog, CloudWatch, Prometheus
        """
        # Pull metrics from XCom
        btc_price = context["ti"].xcom_pull(task_ids="fetch_bitcoin_price", key="btc_price_usd")
        market_cap = context["ti"].xcom_pull(task_ids="fetch_bitcoin_price", key="market_cap")
        volume_24h = context["ti"].xcom_pull(task_ids="fetch_bitcoin_price", key="volume_24h")
        price_change = context["ti"].xcom_pull(task_ids="fetch_bitcoin_price", key="price_change_24h")
        
        execution_date = context["execution_date"]
        
        print("=" * 60)
        print("📊 PIPELINE EXECUTION METRICS")
        print("=" * 60)
        print(f"Execution Date:  {execution_date}")
        print(f"BTC Price (USD): ${btc_price:,.2f}")
        print(f"Market Cap:      ${market_cap:,.0f}")
        print(f"24h Volume:      ${volume_24h:,.0f}")
        print(f"24h Change:      {price_change:.2f}%")
        print(f"Pipeline Status: ✅ SUCCESS")
        print("=" * 60)
        
        # TODO: Send to external monitoring system
        # Example: datadog.statsd.gauge('bitcoin.price.usd', btc_price)
        
        return {
            "btc_price_usd": btc_price,
            "market_cap": market_cap,
            "volume_24h": volume_24h,
            "price_change_24h": price_change,
            "status": "success",
        }

    send_metrics = PythonOperator(
        task_id="send_metrics",
        python_callable=send_metrics_task,
        provide_context=True,
        doc_md="""
        ## Send Metrics
        
        Logs execution metrics for monitoring and alerting.
        Can be extended to send to external systems like Datadog.
        """,
    )

    # ============================================================
    # TASK DEPENDENCIES
    # ============================================================
    # Linear flow: validate → fetch → insert → dbt → checks → metrics
    (
        validate_contract
        >> fetch_price
        >> insert_price
        >> run_dbt
        >> [check_data_quality, verify_transformations]  # Parallel checks
        >> send_metrics
    )

# ============================================================
# DAG DOCUMENTATION
# ============================================================
"""
## Bitcoin Tracker DAG - Execution Flow

```mermaid
graph LR
    A[Validate Contract] --> B[Fetch BTC Price]
    B --> C[Insert to BigQuery]
    C --> D[Run dbt Models]
    D --> E[Data Quality Check]
    D --> F[Verify Transformations]
    E --> G[Send Metrics]
    F --> G
```

## Schedule

- **Frequency:** Hourly (0 * * * *)
- **Start Date:** 2024-01-01
- **Catchup:** Disabled
- **Max Active Runs:** 1

## Alerts

- **Email:** alerts@yourcompany.com
- **On Failure:** Yes
- **On Retry:** No

## Retry Policy

- **Retries:** 3
- **Retry Delay:** 5 minutes
- **Exponential Backoff:** Yes
- **Max Retry Delay:** 30 minutes
"""
