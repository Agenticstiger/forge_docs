from __future__ import annotations
from airflow import DAG
from airflow.operators.bash import BashOperator
from datetime import datetime
with DAG(
    dag_id="crypto_bitcoin_prices_gcp",
    start_date=datetime(2024,1,1),
    schedule="0 2 * * *",
    catchup=False,
    default_args={"retries": 1},
    tags=["FLUID"]
) as dag:
    validate = BashOperator(
        task_id="validate",
        bash_command="python -m fluid_build.cli validate contract.fluid.yaml"
    )
    plan = BashOperator(
        task_id="plan",
        bash_command="python -m fluid_build.cli --provider gcp plan contract.fluid.yaml --out /tmp/plan.json"
    )
    apply = BashOperator(
        task_id="apply",
        bash_command="python -m fluid_build.cli --provider gcp apply /tmp/plan.json --yes"
    )
    validate >> plan >> apply
