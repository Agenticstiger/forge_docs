"""
Airflow DAG for FLUID Data Product: bitcoin-prices-gcp

Auto-generated from FLUID contract v0.7.1
Generated at: 2026-01-21T12:07:17.556183

Domain: unknown
Description: FLUID data product: bitcoin-prices-gcp
"""
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago
from datetime import datetime, timedelta

# DAG configuration
default_args = {
    'owner': 'fluid',
    'depends_on_past': False,
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 3,
    'retry_delay': timedelta(minutes=5),
}

# DAG definition
dag = DAG(
    dag_id="bitcoin_tracker_gcp",
    description="""FLUID data product: bitcoin-prices-gcp""",
    schedule_interval="0 * * * *",
    start_date=days_ago(1),
    catchup=False,
    tags=["fluid", "data-product", "dataproduct", "unknown"],
    default_args=default_args
)


# Provision dataset: bitcoin_prices_table
provision_bitcoin_prices_table = BashOperator(
    task_id="provision_bitcoin_prices_table",
    bash_command="bq mk --project_id=dust-labs-485011 --dataset crypto_data || true",
    dag=dag
)


# Provision dataset: daily_price_summary
provision_daily_price_summary = BashOperator(
    task_id="provision_daily_price_summary",
    bash_command="bq mk --project_id=dust-labs-485011 --dataset crypto_data || true",
    dag=dag
)


# Provision dataset: price_trends
provision_price_trends = BashOperator(
    task_id="provision_price_trends",
    bash_command="bq mk --project_id=dust-labs-485011 --dataset crypto_data || true",
    dag=dag
)


# Schedule task: build_0
schedule_build_0 = BashOperator(
    task_id="schedule_build_0",
    bash_command="echo 'Run build_0'",
    dag=dag
)


# Schedule task: build_1
schedule_build_1 = BashOperator(
    task_id="schedule_build_1",
    bash_command="dbt run --models build_1",
    dag=dag
)


# Schedule task: build_2
schedule_build_2 = BashOperator(
    task_id="schedule_build_2",
    bash_command="dbt run --models build_2",
    dag=dag
)

# Task dependencies
# No dependencies specified
