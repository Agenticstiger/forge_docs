# `fluid generate-airflow`

Compatibility shortcut for generating an Airflow DAG from a contract.

::: warning Deprecated path
The CLI still exposes `fluid generate-airflow`, but current docs lead with [`fluid generate schedule --scheduler airflow`](./generate.md).
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

## Notes

- For contracts with an `orchestration` section, the CLI routes through the richer scheduling/export path.
- For legacy builds-only contracts, this command can still be useful as a direct shortcut.
- Prefer `fluid generate schedule --scheduler airflow` for new documentation and automation examples.
