# `fluid describe`

Describe the installed CLI as data: its version, the contract schema it validates against, which providers and build engines it ships, and the full command tree. Use it when a script, a UI or a control plane needs to ask the CLI what it can do instead of hard-coding the answer.

## Syntax

```bash
fluid describe --self [--json]
```

`--self` is required. Without it, `fluid describe` prints a usage line and exits `1`, with or without `--json`:

```bash
fluid describe
```

```text
Usage: fluid describe --self [--json]
```

## Examples

Read the summary:

```bash
fluid describe --self
```

```text
FLUID forge-cli 0.18.1
Schema:    0.7.5
Python:    3.11.15
Providers: local, gcp, aws, snowflake
Engines:   airbyte, custom, dbt, debezium, dlt, duckdb, kafka-connect, meltano, python, spark, sql
Capabilities: airflow_dag_gen, engine_api, lineage
```

Gate a script on what this installation supports before it calls a stage that needs a given provider or engine. The sample below omits two larger keys, `commands` and `provider_engine_compatibility`, which are described under [Output reference](#output-reference):

```bash
fluid describe --self --json
```

```json
{
  "fluid_version": "0.18.1",
  "python_version": "3.11.15",
  "schema_version": "0.7.5",
  "providers": ["local", "gcp", "aws", "snowflake"],
  "build_engines": ["airbyte", "custom", "dbt", "debezium", "dlt", "duckdb", "kafka-connect", "meltano", "python", "spark", "sql"],
  "templates": ["starter", "analytics", "ml_pipeline", "etl_pipeline", "streaming"],
  "capabilities": {
    "lineage": true,
    "airflow_dag_gen": true,
    "engine_api": true
  },
  "warnings": []
}
```

For example, to fail fast when the installed CLI cannot run a given engine against a provider:

```bash
fluid describe --self --json | jq -e '.provider_engine_compatibility.gcp | index("dbt")'
```

## Options

| Option | Description |
| --- | --- |
| `--self` | Describe this installation. Required. |
| `--json`, `-j` | Emit JSON instead of the human-readable summary. |

## Output reference

| Key | What it holds |
| --- | --- |
| `fluid_version` | The installed CLI release. |
| `python_version` | The Python the CLI runs on. |
| `schema_version` | The contract schema version the CLI defaults to: the newest stable one. A contract can still declare an older bundled version, or the preview version, in its own `fluidVersion`; see [`fluid version`](./version.md). |
| `providers` | Provider names the CLI loaded. |
| `build_engines` | Build engines the CLI knows. |
| `provider_engine_compatibility` | For each provider, the build engines it supports. Not every engine in `build_engines` is supported on every provider. |
| `templates` | Names of the project templates. |
| `capabilities` | Booleans: `lineage`, `airflow_dag_gen`, `engine_api`. |
| `warnings` | Strings for anything the CLI could not detect while building the description, such as `capability matrix unavailable`. Empty in the sample above. |
| `commands` | The command tree, described below. |

### The `commands` tree

`commands` is a map with two keys: `options` (the global options, such as `--log-level`, `--log-file` and `--provider`) and `subcommands` (one entry per command, keyed by name, each carrying `help`, its `options` and, for commands that have them, nested `subcommands`). Every option record has the same fields:

```json
{
  "names": ["--env"],
  "dest": "env",
  "positional": false,
  "required": false,
  "help": "Overlay environment (dev/test/prod)",
  "choices": null,
  "default": null,
  "metavar": null
}
```

A positional argument has an empty `names` list and `"positional": true`. A UI can render a form for a command from this shape without keeping its own copy of the CLI's flags.

## Notes

- Pairs with [`fluid doctor`](./doctor.md): `describe` reports what is installed, `doctor` reports whether it works on this machine.
- The values change with the installed release. Read them at run time rather than copying the sample above.
