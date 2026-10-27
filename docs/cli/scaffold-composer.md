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
- Schedule is read from `builds[].execution.trigger.cron` in the contract; if missing, defaults to `0 2 * * *` (daily at 02:00). *(since 0.22.0, [forge-cli #737](https://github.com/Agenticstiger/forge-cli/pull/737))* It is the cron of the first build a scheduler starts: a build that runs outside forge-cli (`engine: flink`, `properties.language: flink_sql`) or whose trigger is `continuous` is skipped, so a Flink job's own cron does not schedule the DAG. `trigger.schedule`, the key [`generate schedule`](./generate.md#fluid-generate-schedule) reads, is not read here: a contract with `schedule: "15 3 * * *"` and no `cron` still gets `0 2 * * *`.
- *(since 0.22.0, [forge-cli #737](https://github.com/Agenticstiger/forge-cli/pull/737))* A contract whose every build runs outside forge-cli or continuously gets no DAG unless it declares `orchestration.tasks`, the test [`fluid generate schedule`](./generate.md#fluid-generate-schedule) applies before it writes no files. The command exits `0`:

  ```text
  Every build runs outside forge-cli (a Flink job, for example) or continuously
  (trigger.type: continuous), so there is nothing to schedule. No DAG written.
  ```

  A DAG the command wrote for the product before stays where it is, and the command prints its path when it finds it under the name it writes now: delete it, and remove it from Cloud Composer if you deployed it there. A file of that name that it did not write is not mentioned.
- For non-Composer Airflow installs, see [`fluid generate-airflow`](./generate-airflow.md). For Airflow, Dagster and Prefect output from one command, see [`fluid generate schedule`](./generate.md#fluid-generate-schedule).
