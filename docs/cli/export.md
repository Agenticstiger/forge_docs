# `fluid export`

Export a FLUID contract as executable orchestration code (Airflow DAG, Dagster pipeline, or Prefect flow).

## Syntax

```bash
fluid export CONTRACT [--engine ENGINE] [--output-dir DIR] [--provider PROVIDER] [--env ENV] [-v]
```

## Key options

| Option | Description |
| --- | --- |
| `CONTRACT` | Path to FLUID contract file (YAML or JSON). |
| `--engine` | Orchestration engine: `airflow`, `mwaa`, `dagster`, or `prefect`. Default `airflow`. |
| `--output-dir`, `-o` | Output directory for generated files. Default `.` (current directory). |
| `--provider` | Override provider. *(since 0.27.0)* The flag has no fixed list of choices: a name is checked against the providers registered in your install, and one that is not, such as `azure`, is rejected with `Unknown provider 'azure'` and exit 2 (see [`fluid providers`](./providers.md#when-a-provider-cannot-be-found)). `gcp` prints `Provider 'gcp' requires --project to be specified` unless the global `--project` is set before the subcommand (`fluid --project <id> export ...`). Default auto-detected from the contract. |
| `--env` | Environment overlay to apply (e.g. `dev`, `test`, `prod`). |
| `--verbose`, `-v` | Verbose output, including file stats and next-step hints. |

## Examples

```bash
fluid export contract.yaml --engine airflow -o dags/
fluid export contract.yaml --engine dagster -o pipelines/
fluid export contract.yaml --provider aws --engine airflow -o dags/
fluid --project <gcp-project> export contract.yaml --provider gcp --engine airflow -o dags/
fluid export contract.yaml --engine airflow --env prod -o dags/prod/
```

## Notes

- The contract must contain an `orchestration.tasks` section; otherwise the command fails with `missing_orchestration` and exit 1. The quickstart contract has none.
- Code generation is delegated to the active provider's `export()` method. Providers that lack `export()` (commonly local-only providers) will fail with `export_not_supported`.
- Step Functions output is reserved for a future release and is not currently selectable.
- For exporting the contract itself in standards-compliant formats, see [`fluid odps`](./odps.md), [`fluid odps-bitol`](./odps-bitol.md), [`fluid odcs`](./odcs.md), and [`fluid export-odps`](./export-odps.md).
