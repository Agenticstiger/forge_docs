# `fluid publish`

Publish one or more contracts to a configured catalog.

## Syntax

```bash
fluid publish CONTRACT_FILES
```

`CONTRACT_FILES` supports one or more paths or glob patterns.

## Key options

| Option | Description |
| --- | --- |
| `--catalog`, `-c` | Target catalog name |
| `--list-catalogs` | List configured catalogs |
| `--dry-run` | Validate and preview without publishing |
| `--verify-only` | Check whether a contract is already published |
| `--force` | Force an update |
| `--format`, `-f` | Output format |
| `--verbose`, `-v` | Detailed output |
| `--quiet`, `-q` | Minimal output |
| `--skip-health-check` | Skip catalog health checks |
| `--show-metrics` | Show detailed metrics |

## Examples

```bash
fluid publish contract.fluid.yaml
fluid publish customer-*.fluid.yaml
fluid publish contract.fluid.yaml --catalog fluid-command-center
fluid publish contract.fluid.yaml --dry-run
fluid publish contract.fluid.yaml --verify-only
```

## Notes

- A typical flow is `validate -> apply -> publish`.
- Use [`fluid market`](./market.md) to verify discoverability after publishing.
