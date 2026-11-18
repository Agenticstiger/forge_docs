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
| `--output`, `-o` | Where to write. With no `-o`, the one DAG is printed to stdout. |
| `--dag-id` | Override the DAG id of the DAG rendered from an `orchestration` section |
| `--schedule` | Override its schedule: a cron expression or an Airflow keyword |
| `--env` | Apply an environment overlay |
| `--contract-path` | *(since 0.31.0, [forge-cli #923](https://github.com/Agenticstiger/forge-cli/pull/923))* The contract's path relative to `$FLUID_PROJECT_DIR` on the Airflow worker, as for [`fluid generate schedule`](./generate.md#fluid-generate-schedule) |
| `--allow-unmapped` | *(since 0.31.0, [forge-cli #923](https://github.com/Agenticstiger/forge-cli/pull/923))* Render a task whose action the provider cannot map as a log-only task, instead of refusing. `FLUID_AIRFLOW_ALLOW_UNMAPPED=1` does the same |
| `--verbose`, `-v` | Verbose output |

## Examples

```bash
fluid generate-airflow contract.fluid.yaml -o dags/pipeline.py
fluid generate-airflow contract.fluid.yaml --dag-id my_custom_dag
fluid generate-airflow contract.fluid.yaml --schedule "0 2 * * *"
```

## What it writes

*(since 0.31.0, [forge-cli #923](https://github.com/Agenticstiger/forge-cli/pull/923))* `fluid generate-airflow` is an alias of `fluid generate schedule --scheduler airflow`, and the two write the same DAG. Before, six separate generators wrote DAGs, and the same contract gave different files by the command that wrote it. Now `fluid export --engine airflow`, `fluid generate schedule` and `fluid generate-airflow` all render a contract's `orchestration` section through one renderer, and give the same DAG for the same contract and provider settings.

- **A contract with an `orchestration` section** gets one DAG, for AWS, GCP and Snowflake alike. `--dag-id` and `--schedule` override its id and schedule.
- **A contract with builds and no `orchestration` section** gets the DAGs of its builds' triggers. It no longer gets a DAG of `echo` placeholders. These are the DAGs that run `fluid apply`, described under [What the DAG does](../advanced/airflow.md#what-the-dag-does), and the command must run from the project directory (`generate_schedule_contract_outside_project`, exit 2, for a contract outside it). `--dag-id` and `--schedule` are refused there, with `generate_schedule_override_not_supported`: a scheduled build takes both from its trigger.
- **A contract whose `orchestration` section has no `provider_action` task** is refused, not rendered as an empty DAG.

Seen on 0.31.0, for a contract with one scheduled build:

```text
Generated 1 files (airflow scheduler):

  /var/folders/.../customer360_build_dag.py
```

followed by the DAG on stdout.

What the renderer does that the old generators did not do for every provider:

- **A task whose action no operator covers fails closed.** `render_dag` raises a `ValueError` that names each such task and action, instead of writing a DAG that logs the action and still succeeds. This is new for GCP and Snowflake, which used to log. `--allow-unmapped`, or `FLUID_AIRFLOW_ALLOW_UNMAPPED=1`, renders those tasks as log-only tasks, logs a WARNING that lists them, and the task logs at WARNING when it runs. Only `aws.glue.run_job` and `aws.glue.start_job_run` run a Glue job: any other `aws.glue.<operation>` is unmapped.
- **Nothing is a placeholder.** The renderer resolves the GCP project (the contract's `metadata.gcp_project`, then `GOOGLE_CLOUD_PROJECT`, `FLUID_PROJECT`, `GCLOUD_PROJECT`, then Application Default Credentials), the AWS account (`AWS_ACCOUNT_ID`) and the Snowflake account, database and warehouse (`SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_DATABASE`, `SNOWFLAKE_WAREHOUSE`), the way the provider does. Before, a value that did not resolve rendered as `my-project`, `UNKNOWN_DB` or an empty account. A task that needs a value that did not resolve is refused with a `ValueError` that names it, and so is a task with no Athena query or output location, no Snowflake database, schema, table, columns or SQL, no BigQuery dataset, table or query, no bucket, topic, subscription, Glue job name, Lambda function or Redshift SQL or cluster. No `SELECT 1` and no `unknown-bucket`. `fluid generate schedule` reads the settings from the contract's `metadata`, and `fluid export` from the provider's own settings, so give both the same.
- **The DAG id drops `.` and `-` for AWS too**: `sales.orders` is DAG `sales_orders`, as for the other providers and `generate schedule`. The file `fluid export` writes keeps its name.
- **A bare-word schedule is the Airflow keyword** (`hourly`, `daily`, `weekly`, `monthly`) for AWS too. It used to map to cron, so `daily` ran at 02:00 and now runs at 00:00.
- **Guards for every provider**: a task never takes a name the DAG module binds, ids that sanitise alike stay two tasks, an edge to a task outside the DAG is skipped instead of failing the file at import, and an operator is imported only when a task uses it.
- **Ported into the renderer**: AWS Redshift, Lambda and Glue catalog tasks, GCP Pub/Sub, Dataflow and BigQuery create-table, and Snowflake database, schema and table DDL.

`generate_airflow_dag_taskflow` (AWS TaskFlow DAGs) is removed: nothing called it. The differences from the old output are listed one by one in `tests/schedulers/golden/DIFFERENCES.md` in forge-cli.

Up to 0.30.1, for a builds-only contract the command wrote a legacy DAG that:

- used Airflow 2 names: `schedule_interval=` and `airflow.utils.dates.days_ago`;
- took its schedule from `--schedule`, and fell back to `@daily`; it did not read `builds[].execution.trigger`;
- ran `echo` tasks: one per expose and one per build. The tasks printed a line and ran no `fluid` command.

For a contract with an `orchestration` section, up to 0.30.1 the command delegated to `fluid export --engine airflow` and logged that it was deprecated for orchestration contracts.

## Notes

- Prefer `fluid generate schedule --scheduler airflow` for new documentation and automation examples.
- For Cloud Composer, see [`fluid scaffold-composer`](./scaffold-composer.md).
