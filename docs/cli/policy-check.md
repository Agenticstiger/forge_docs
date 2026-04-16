# `fluid policy-check`

Run governance and compliance checks derived from the contract.

## Syntax

```bash
fluid policy-check CONTRACT
```

## Key options

| Option | Description |
| --- | --- |
| `--env` | Apply an environment overlay |
| `--strict` | Treat warnings as errors |
| `--category` | Restrict checks to a category |
| `--output`, `-o` | Write the policy report |
| `--format` | `rich`, `text`, or `json` |
| `--show-passed` | Show successful checks too |

Available categories include:

- `sensitivity`
- `access_control`
- `data_quality`
- `lifecycle`
- `schema_evolution`

## Examples

```bash
fluid policy-check contract.fluid.yaml
fluid policy-check contract.fluid.yaml --strict
fluid policy-check contract.fluid.yaml --category access_control
fluid policy-check contract.fluid.yaml --format json --output runtime/policy.json
```
