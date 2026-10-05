# `fluid scaffold-composer`

Generate a Cloud Composer (Airflow) DAG from a contract.

For a DAG that runs a scheduled build through `fluid apply` with its env and contract path fixed in the file, use [`fluid generate schedule`](./generate.md#fluid-generate-schedule). `scaffold-composer` writes a validate, plan, apply chain against the GCP provider.

## Syntax

```bash
fluid scaffold-composer CONTRACT [--env ENV] [--out-dir DIR]
```

## Key options

| Option | Description |
| --- | --- |
| `CONTRACT` | Path to `contract.fluid.yaml` (positional, required). |
| `--env` | Overlay env to apply before reading the contract. |
| `--out-dir` | DAGs output directory (default `runtime/composer/dags`). |

## Examples

```bash
fluid scaffold-composer contract.fluid.yaml
fluid scaffold-composer contract.fluid.yaml --env prod
fluid scaffold-composer contract.fluid.yaml --out-dir dags/
```

The first command writes `runtime/composer/dags/<dag_id>.py`:

```python
with DAG(
    dag_id='gold_customer_analytics_360_v1',
    start_date=datetime(2024,1,1),
    schedule='0 2 * * *',
    catchup=False,
    default_args={"retries": 1},
    tags=["FLUID"]
) as dag:
    validate = BashOperator(
        task_id="validate",
        bash_command='python -m fluid_build.cli validate contract.fluid.yaml'
    )
    plan = BashOperator(
        task_id="plan",
        bash_command='python -m fluid_build.cli --provider gcp plan contract.fluid.yaml --out /tmp/plan.json'
    )
    apply = BashOperator(
        task_id="apply",
        bash_command='python -m fluid_build.cli --provider gcp apply /tmp/plan.json --yes'
    )
    validate >> plan >> apply
```

## Notes

- Writes one `<dag_id>.py` file per contract, where `dag_id` comes from `id` (or `name`) with `.` replaced by `_`.
- The generated DAG has three sequential `BashOperator` tasks: `validate`, `plan`, `apply`. The `plan` and `apply` steps run against the GCP provider, and `apply` passes `--yes`.
- The tasks call `python -m fluid_build.cli` with the contract path as you gave it to `scaffold-composer`, relative to the Composer worker's working directory, so the contract has to be at that path on the worker. `--env` selects the overlay used to read the contract when the DAG is generated; the commands inside the DAG carry no `--env`.
- Schedule is read from `builds[].execution.trigger.cron` in the contract; if missing, defaults to `0 2 * * *` (daily at 02:00). `trigger.schedule`, the key [`generate schedule`](./generate.md#fluid-generate-schedule) reads, is not read here: a contract with `schedule: "15 3 * * *"` and no `cron` still gets `0 2 * * *`.
- For non-Composer Airflow installs, see [`fluid generate-airflow`](./generate-airflow.md). For Airflow, Dagster and Prefect output from one command, see [`fluid generate schedule`](./generate.md#fluid-generate-schedule).
