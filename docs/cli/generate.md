# `fluid generate`

Unified artifact generation from FLUID contracts.

## Syntax

```bash
fluid generate <transformation|schedule|ci|standard>
```

## Subcommands

### `fluid generate transformation`

Generate transformation artifacts such as dbt projects or SQL output.

Key options:

- `contract`
- `--output`, `-o`
- `--build-index`
- `--overwrite`
- `--env`
- `--list`
- `--verbose`

### `fluid generate schedule`

Generate orchestration artifacts such as Airflow DAGs, Dagster pipelines, or Prefect flows.

Key options:

- `contract`
- `--output`, `-o`
- `--scheduler`
- `--overwrite`
- `--env`
- `--list`
- `--verbose`

This is the promoted path for orchestration generation.

### `fluid generate ci`

Generate CI/CD pipeline configuration for GitHub Actions, GitLab CI, or Jenkins.

Key options:

- `contract`
- `--system`
- `--out`

### `fluid generate standard`

Export to data product standards.

Key options:

- `contract`
- `--format`, `-f`
- `--out`, `-o`
- `--env`
- `--list`

Supported formats:

- `opds`
- `odcs`
- `odps`
- `odps-bitol`

## Examples

```bash
fluid generate transformation
fluid generate transformation contract.fluid.yaml -o ./dbt_project
fluid generate schedule contract.fluid.yaml --scheduler airflow -o dags
fluid generate ci --system github
fluid generate standard contract.fluid.yaml --format opds
```

## Compatibility note

[`fluid generate-airflow`](./generate-airflow.md) still works for Airflow generation, but current docs lead with `fluid generate schedule --scheduler airflow`.
