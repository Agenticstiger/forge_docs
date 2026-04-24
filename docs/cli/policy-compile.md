# `fluid policy compile`

Compile a contract's `accessPolicy` into provider-specific IAM / GRANT bindings. Pure-function shape: contract in, JSON out. No cloud calls.

`0.8.0` promotes the unified `fluid policy {check,compile,apply}` subcommand group. The legacy `fluid policy-compile` form stays registered as a deprecation alias for one release. Both surfaces share the same argument set.

This command runs as part of stage 3 (`fluid generate artifacts`) but is also available standalone.

## Syntax

```bash
# New idiomatic form
fluid policy compile CONTRACT [--env ENV] [--out PATH]

# Legacy alias (same behaviour)
fluid policy-compile CONTRACT [--env ENV] [--out PATH]
```

## Key options

| Option | Description |
| --- | --- |
| `CONTRACT` | Path to `contract.fluid.yaml` (positional, required). |
| `--env` | Overlay env to apply before compiling. |
| `--out` | Output bindings path (default `runtime/policy/bindings.json`). |

## Examples

```bash
# New idiomatic form
fluid policy compile contract.fluid.yaml
fluid policy compile contract.fluid.yaml --env prod
fluid policy compile contract.fluid.yaml --out build/bindings.json

# Legacy hyphenated form (still works)
fluid policy-compile contract.fluid.yaml --env prod
```

## Notes

- Loads the contract with the requested env overlay and emits a JSON document with `bindings` and `warnings` arrays at the `--out` path.
- The compiler embeds `provider` and `project` on each binding so [`fluid policy apply`](./policy-apply.md) can target the right account without extra flags.
- Compiler failures are caught and surfaced as warnings inside the output file — the command still exits `0` so downstream automation can inspect the warnings.
- Pair with [`fluid policy check`](./policy-check.md) for static linting and [`fluid policy apply`](./policy-apply.md) for enforcement (stage 8).
