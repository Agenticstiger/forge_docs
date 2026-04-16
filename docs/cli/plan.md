# `fluid plan`

Generate an execution plan without applying changes.

## Syntax

```bash
fluid plan CONTRACT
```

## Key options

| Option | Description |
| --- | --- |
| `--env` | Apply an environment overlay |
| `--out`, `--output` | Write the plan JSON, default `runtime/plan.json` |
| `--verbose`, `-v` | Show detailed action information |
| `--validate-actions` | Validate generated provider actions |
| `--estimate-cost` | Ask the provider to estimate cost |
| `--check-sovereignty` | Ask the provider to validate sovereignty constraints |
| `--provider` | Override the provider from the contract |
| `--html` | Generate an HTML visualization |

## Examples

```bash
fluid plan contract.fluid.yaml
fluid plan contract.fluid.yaml --verbose
fluid plan contract.fluid.yaml --env prod --out runtime/prod-plan.json
fluid plan contract.fluid.yaml --html
```

## Notes

- `plan` is the safest place to preview a provider override or environment overlay before you run `apply`.
- The generated plan can be passed to [`fluid apply`](./apply.md).
