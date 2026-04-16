# `fluid apply`

Execute a FLUID contract or a saved plan end-to-end.

## Syntax

```bash
fluid apply CONTRACT
```

`CONTRACT` can be a FLUID contract file or a saved plan JSON file.

## Key options

### General

| Option | Description |
| --- | --- |
| `--env` | Apply an environment overlay |

### Execution control

| Option | Description |
| --- | --- |
| `--yes` | Skip confirmation |
| `--dry-run` | Show what would be executed |
| `--timeout TIMEOUT` | Global timeout in minutes |
| `--parallel-phases` | Execute independent phases in parallel |
| `--max-workers MAX_WORKERS` | Maximum workers for parallel execution |

### Safety and rollback

| Option | Description |
| --- | --- |
| `--rollback-strategy` | `none`, `immediate`, `phase_complete`, or `full_rollback` |
| `--require-approval` | Require explicit approval for destructive work |
| `--backup-state` | Create a backup before execution |
| `--validate-dependencies` | Validate dependencies before execution |

### Reporting

| Option | Description |
| --- | --- |
| `--report` | Output path for the execution report |
| `--report-format` | Report format |
| `--metrics-export` | Export metrics to monitoring backends |
| `--notify` | Send notifications to destinations such as Slack or email |

### Build execution

| Option | Description |
| --- | --- |
| `--build`, `--build-id` | Execute a specific build job |
| `--delay DELAY` | Seconds between build iterations |
| `--fail-fast` | Stop on first failure |
| `--no-output` | Suppress build script output |

### Debugging and advanced

| Option | Description |
| --- | --- |
| `--verbose` | Detailed progress output |
| `--keep-temp-files` | Keep temporary files |
| `--workspace-dir` | Custom workspace directory |
| `--state-file STATE_FILE` | Custom state file location |
| `--config-override` | Override contract config with JSON |
| `--provider-config` | Path to provider-specific configuration |

## Examples

```bash
fluid apply contract.fluid.yaml --yes
fluid apply contract.fluid.yaml --dry-run --verbose
fluid apply contract.fluid.yaml --env production --rollback-strategy immediate
fluid apply runtime/plan.json --yes
```

## Notes

- The recommended sequence is `validate -> plan -> apply`.
- For local-first onboarding, `fluid apply contract.fluid.yaml --yes` is the shortest path after a quickstart scaffold.
