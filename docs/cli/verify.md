# `fluid verify`

Verify that deployed infrastructure still matches the FLUID contract.

## Syntax

```bash
fluid verify CONTRACT
```

## Key options

| Option | Description |
| --- | --- |
| `--expose`, `--expose-id` | Verify only a specific expose |
| `--strict` | Exit non-zero when mismatches are found |
| `--out` | Write a JSON verification report |
| `--show-diffs` | Show field-by-field differences |
| `--env` | Apply an environment overlay |

## Examples

```bash
fluid verify contract.fluid.yaml
fluid verify contract.fluid.yaml --strict
fluid verify contract.fluid.yaml --expose bitcoin_prices
fluid verify contract.fluid.yaml --show-diffs
```

## Notes

- Use `verify` after apply or in CI when you need contract-to-runtime confidence.
- Use [`fluid test`](./test.md) when you want broader live-resource validation.
