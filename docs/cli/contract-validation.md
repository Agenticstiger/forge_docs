# `fluid contract-validation`

Validate that exposed data products match their FLUID contract specifications by inspecting actual deployed resources.

## Syntax

```bash
fluid contract-validation CONTRACT [--env ENV] [--provider NAME] [--project ID] [...]
```

## Key options

| Option | Description |
| --- | --- |
| `CONTRACT` | Path to `contract.fluid.(yaml|json)` (positional, required). |
| `--env` | Environment overlay (dev/test/prod). |
| `--provider` | Override the provider platform. See [Provider values](#provider-values). |
| `--project` | Override project/account ID. For `--provider gcp`, set it or `FLUID_PROJECT`; without one the command logs `requires --project` and carries on. |
| `--region` | Override region/location. |
| `--strict` | Treat warnings as errors. |
| `--no-data` | Skip data validation checks (structure only). |
| `--output-format {text,json}` | Output format for the validation report (default `text`). |
| `--output-file PATH` | Write the validation report to a file. |
| `--cache` / `--no-cache` | Enable or disable result caching (default: enabled). |
| `--cache-ttl SECONDS` | Cache time-to-live in seconds (default: 3600). |
| `--cache-clear` | Clear the validation cache before running. |
| `--cache-stats` | Show cache statistics and exit. |
| `--track-history` | Track validation history for drift detection (default: enabled). |
| `--check-drift` | Check for validation drift compared to historical results. |

## Examples

```bash
fluid contract-validation contract.fluid.yaml
fluid contract-validation contract.fluid.yaml --env prod --strict
fluid contract-validation contract.fluid.yaml --provider gcp --project my-project
fluid contract-validation contract.fluid.yaml --output-format json --output-file report.json
```

## Notes

- Connects to the live resource for the contract's provider (BigQuery, Snowflake, AWS, or local DuckDB) and verifies schema, bindings, quality specs, and metadata.
- Returns exit code `1` if any errors are found, or if `--strict` is set and any warnings are present.
- Provider is auto-detected from `exposes[].binding.platform` (or `builds[].execution.runtime.platform`) — the `--provider`, `--project`, and `--region` flags only override the detected values.
- Schema lookups are cached per `(table, provider)` for `--cache-ttl` seconds; use `--cache-clear` to force a refresh.
- With `--check-drift`, results are compared against the recorded validation history for the same contract and resource.
- Complementary to [`fluid contract-tests`](./contract-tests.md) (schema comparison against a baseline) and [`fluid validate`](./validate.md) (contract syntax).

## Provider values

`--provider` is checked against the providers registered in your install before the command runs. The test install for 0.18.1 registered `aws`, `datamesh_manager`, `gcp`, `local`, `redshift` and `snowflake`. A value outside that list exits `2`:

```text
⚠️ Unknown provider 'databricks' — installed providers: aws, datamesh_manager, gcp, local, redshift, snowflake (see `fluid providers`)
```

The option's help text still lists `databricks` and `azure`. As of 0.18.1 both are rejected this way, so leave `--provider` off and let the command detect the provider from `exposes[].binding.platform`. `--provider gcp` without `--project` (or `FLUID_PROJECT`) prints `Provider 'gcp' requires --project to be specified` and still runs.
