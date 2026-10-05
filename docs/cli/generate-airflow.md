# `fluid generate-airflow`

Compatibility shortcut for generating an Airflow DAG from a contract.

::: warning Deprecated path
The CLI still exposes `fluid generate-airflow` and logs a deprecation warning on each run. Use [`fluid generate schedule --scheduler airflow`](./generate.md#fluid-generate-schedule), which writes the DAG that runs `fluid apply` for a scheduled build.
:::

## Syntax

```bash
fluid generate-airflow CONTRACT
```

## Key options

| Option | Description |
| --- | --- |
| `--output`, `-o` | Output DAG path, default stdout |
| `--dag-id` | Override the generated DAG ID |
| `--schedule` | Override the schedule interval |
| `--env` | Apply an environment overlay |
| `--verbose`, `-v` | Verbose output |

## Examples

```bash
fluid generate-airflow contract.fluid.yaml -o dags/pipeline.py
fluid generate-airflow contract.fluid.yaml --dag-id my_custom_dag
fluid generate-airflow contract.fluid.yaml --schedule "0 2 * * *"
```

## What it writes

For a builds-only contract (no `orchestration` section), the command writes the legacy DAG. As of 0.18.1 that DAG:

- uses Airflow 2 names: `schedule_interval=` and `airflow.utils.dates.days_ago`;
- takes its schedule from `--schedule`, and falls back to `@daily`; it does not read `builds[].execution.trigger`;
- runs `echo` tasks: one per expose (`echo 'Provision <expose> on <platform>'`) and one per build (`echo 'Execute SQL: None'` for the multi-stage build tried here). The tasks print a line and run no `fluid` command.

```text
provision_customer_360_master = BashOperator(
    task_id='provision_customer_360_master',
    bash_command="echo 'Provision customer_360_master on local'",
    dag=dag
)
```

A scheduled build is run by the DAG that [`fluid generate schedule`](./generate.md#fluid-generate-schedule) writes, which calls `fluid apply`; see [Scheduled builds](./generate-artifacts.md#scheduled-builds).

For a contract with an `orchestration` section, the command delegates to `fluid export --engine airflow` and logs `'generate-airflow' is deprecated for orchestration contracts. Use 'fluid export --engine airflow' instead.` The DAG then comes from the export path, with the contract's `orchestration.schedule`.

## Notes

- Prefer `fluid generate schedule --scheduler airflow` for new documentation and automation examples.
- For Cloud Composer, see [`fluid scaffold-composer`](./scaffold-composer.md).
