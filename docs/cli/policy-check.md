# `fluid policy check`

Static lint of the contract's governance and compliance declarations. No cloud calls, no state mutation — safe to run from any branch, any environment. Pair with [`fluid validate`](./validate.md) in a pre-commit hook or stage-2 CI gate.

`0.8.0` promotes the unified `fluid policy {check,compile,apply}` subcommand group. The legacy `fluid policy-check` form stays registered as a deprecation alias for one release. Both surfaces share the same argument set.

## Syntax

```bash
# New idiomatic form
fluid policy check CONTRACT

# Legacy alias (same behaviour)
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

### New idiomatic form

```bash
fluid policy check contract.fluid.yaml
fluid policy check contract.fluid.yaml --strict
fluid policy check contract.fluid.yaml --category access_control
fluid policy check contract.fluid.yaml --format json --output runtime/policy.json
```

### Legacy hyphenated form (still works)

```bash
fluid policy-check contract.fluid.yaml
fluid policy-check contract.fluid.yaml --strict
```

## Related

- [`fluid policy compile`](./policy-compile.md) — after the lint passes, compile to `bindings.json`.
- [`fluid policy apply`](./policy-apply.md) — deploy the compiled bindings (stage 8 of the pipeline).
