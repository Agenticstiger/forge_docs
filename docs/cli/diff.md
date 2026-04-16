# `fluid diff`

Detect configuration drift between the desired contract state and deployed resources.

## Syntax

```bash
fluid diff CONTRACT
```

## Key options

| Option | Description |
| --- | --- |
| `--state` | Previous `apply_report.json` |
| `--env` | Apply an environment overlay |
| `--out` | Output file for the drift report |
| `--exit-on-drift` | Exit with code `1` when drift is detected |

## Examples

```bash
fluid diff contract.fluid.yaml
fluid diff contract.fluid.yaml --env prod
fluid diff contract.fluid.yaml --out runtime/diff.json
fluid diff contract.fluid.yaml --exit-on-drift
```
