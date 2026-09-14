# `fluid test`

Validate a contract against live resources and optionally publish the results.

## Syntax

```bash
fluid test CONTRACT
```

## Key options

| Option | Description |
| --- | --- |
| `--env` | Apply an environment overlay |
| `--provider` | Override the provider |
| `--server` | Provider connection string or server identifier |
| `--strict` | Treat warnings as errors |
| `--no-data` | Skip live data validation |
| `--output` | Output format |
| `--output-file` | Write output to a file |
| `--no-cache` | Disable schema caching |
| `--cache-ttl CACHE_TTL` | Cache TTL |
| `--cache-clear` | Clear the cache first |
| `--check-drift` | Compare against historical results |
| `--publish URL` | Publish test results to a remote endpoint |
| `--engine` | Validation engine. Default is the built-in checker; `soda` runs the contract's quality rules through Soda. |
| `--datasource` | Soda data source to run against. Required with `--engine soda`. |
| `--soda-config` | Path to Soda `configuration.yml`. Defaults to Soda's auto-discovery. |
| `--project` | Override the project / account ID from the contract. |
| `--region` | Override the region / location from the contract. |

## Examples

```bash
fluid test contract.fluid.yaml
fluid test contract.fluid.yaml --env prod
fluid test contract.fluid.yaml --provider snowflake
fluid test contract.fluid.yaml --output json --output-file results.json
fluid test contract.fluid.yaml --strict
```

## Soda quality engine

`--engine soda` runs the contract's quality rules through [Soda](https://www.soda.io/) instead of the built-in checker:

```bash
fluid test contract.fluid.yaml --engine soda --datasource warehouse
fluid test contract.fluid.yaml --engine soda --datasource warehouse --output junit --output-file results.xml
```

- Forge renders the contract's quality rules to **SodaCL**, then shells out to the `soda` binary.
- The binary is resolved from `$SODA_EXECUTABLE`, then `PATH` — if neither resolves, the command fails with an install hint instead of a stack trace.
- `--datasource` names the Soda data source and is required in this mode.
- `--output` accepts `text`, `json`, or `junit` (JUnit XML) — the JUnit form drops straight into a CI test report.
- Soda's `stderr` is secret-redacted before it is printed or embedded in a JUnit failure body.

## Notes

- Use `test` when you want live-resource checks.
- Use [`fluid verify`](./verify.md) when you only need contract-to-deployed-state verification.
