# `fluid scaffold-composer`

Generate a Cloud Composer (Airflow) DAG from a contract.

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

## Notes

- Writes one `<dag_id>.py` file per contract, where `dag_id` comes from `id` (or `name`) with `.` replaced by `_`.
- The generated DAG has three sequential `BashOperator` tasks: `validate`, `plan`, `apply`. The `apply` step runs against the GCP provider with `--yes`.
- Schedule is read from `build.execution.trigger.cron` in the contract; if missing, defaults to `0 2 * * *` (daily at 02:00).
- For non-Composer Airflow installs, see [`fluid generate-airflow`](./generate-airflow.md). For broader pipeline generation across orchestrators, see [`fluid generate-pipeline`](./generate-pipeline.md).
