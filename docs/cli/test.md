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

## Examples

```bash
fluid test contract.fluid.yaml
fluid test contract.fluid.yaml --env prod
fluid test contract.fluid.yaml --provider snowflake
fluid test contract.fluid.yaml --output json --output-file results.json
fluid test contract.fluid.yaml --strict
```

## Notes

- Use `test` when you want live-resource checks.
- Use [`fluid verify`](./verify.md) when you only need contract-to-deployed-state verification.
