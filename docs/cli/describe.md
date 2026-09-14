# `fluid describe`

Print a machine-readable description of the local forge environment — the installed CLI and schema versions, and which providers, build engines, and templates are available.

## Syntax

```bash
fluid describe [--self] [--json]
```

## Key options

| Option | Description |
| --- | --- |
| `--self` | Describe this installation (providers, engines, schema version). |
| `--json`, `-j` | Emit machine-readable JSON instead of the human-readable summary. |

## Examples

```bash
fluid describe                # human-readable environment summary
fluid describe --self --json  # stable JSON for scripts / CI
```

`--self --json` emits a stable shape — gate on it for capability detection before invoking a stage that needs a given provider or engine:

```json
{
  "fluid_version": "0.15.0",
  "python_version": "3.12.13",
  "schema_version": "0.7.5",
  "providers": ["local", "gcp", "aws", "snowflake"],
  "build_engines": ["airbyte", "custom", "dbt", "debezium", "dlt", "duckdb", "kafka-connect", "meltano", "python", "spark", "sql"],
  "templates": ["starter", "analytics", "ml_pipeline", "etl_pipeline", "streaming"]
}
```

## Notes

- Pairs with [`fluid doctor`](/forge_docs/cli/doctor.html): `describe` reports *what is installed*; `doctor` reports *whether it works*.
- The block above shows the keys most scripts gate on. `--self --json` also emits four further top-level keys: `commands` (the full argparse tree), `provider_engine_compatibility` (provider name to supported build engines), `capabilities` (`lineage`, `airflow_dag_gen`, `engine_api`) and `warnings`.
- `schema_version` is the contract `fluidVersion` this CLI emits and validates — pin against it when a workflow depends on a specific schema generation.
