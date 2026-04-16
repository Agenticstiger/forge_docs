# `fluid policy-apply`

Apply compiled IAM bindings to the target provider in either dry-run or enforcing mode.

## Syntax

```bash
fluid policy-apply BINDINGS [--mode {check,enforce}]
```

## Key options

| Option | Description |
| --- | --- |
| `BINDINGS` | Path to compiled bindings file, typically `runtime/policy/bindings.json` (positional, required). |
| `--mode` | `check` (default) for dry-run, `enforce` to actually apply IAM changes. |

## Examples

```bash
fluid policy-apply runtime/policy/bindings.json
fluid policy-apply runtime/policy/bindings.json --mode enforce
```

## Notes

- Provider and project are read from the bindings file's metadata (set by [`fluid policy-compile`](./policy-compile.md) from the contract's `binding.platform` and `binding.location`). Environment variables and CLI flags act as overrides only — `FLUID_PROVIDER` is honored when no provider is encoded in the bindings.
- If the resolved provider has no `apply_policy` method the command becomes a no-op and exits `0`.
- Returns `0` for `ok` or `noop` results, `1` otherwise.
- Compile bindings first with [`fluid policy-compile`](./policy-compile.md); see [`fluid policy-check`](./policy-check.md) for static linting of the access policy.
