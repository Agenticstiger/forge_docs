# `fluid policy apply`

Stage 8 of the 11-stage pipeline. Deploy compiled IAM / GRANT bindings to the target warehouse in either dry-run (`check`) or enforcing (`enforce`) mode.

`0.8.0` promotes a unified `fluid policy {check,compile,apply}` subcommand group; the legacy `fluid policy-apply` form stays registered as a deprecation alias for one release. Both surfaces share the same argument set and behaviour.

## Syntax

```bash
# New idiomatic form
fluid policy apply BINDINGS [--mode {check,enforce}]

# Legacy alias (same behaviour)
fluid policy-apply BINDINGS [--mode {check,enforce}]
```

## Key options

| Option | Description |
| --- | --- |
| `BINDINGS` | Path to compiled bindings file, typically `runtime/policy/bindings.json` (positional, required). |
| `--mode` | `check` (default) for dry-run, `enforce` to actually apply IAM changes. |

## Pipeline ordering

Stage 8 runs **after** stage 7 apply (GRANTs need the target schema objects to exist) and **before** stage 9 verify (so transforms running on under-authorised objects surface as policy failures rather than masked build errors).

The Jenkins + 7-system CI templates from `fluid generate ci` wire this automatically. The stage is self-gated on `dist/artifacts/policy/bindings.json` existence, so reference-only contracts that don't emit policy bindings skip cleanly.

## Examples

### Dry-run (CI pre-flight)

```bash
fluid policy apply runtime/policy/bindings.json
# exit 0 if all bindings would apply cleanly; exit 1 on any rejection
```

### Enforce (actual deployment)

```bash
fluid policy apply runtime/policy/bindings.json --mode enforce
```

### Legacy hyphenated form

```bash
fluid policy-apply runtime/policy/bindings.json --mode enforce
# identical to: fluid policy apply runtime/policy/bindings.json --mode enforce
```

## Notes

- Provider and project are read from the bindings file's metadata (set by [`fluid policy compile`](./policy-compile.md) from the contract's `binding.platform` and `binding.location`). Environment variables and CLI flags act as overrides only — `FLUID_PROVIDER` is honoured when no provider is encoded in the bindings.
- If the resolved provider has no `apply_policy` method the command becomes a no-op and exits `0`.
- Returns `0` for `ok` or `noop` results, `1` otherwise.
- Compile bindings first with [`fluid policy compile`](./policy-compile.md); see [`fluid policy check`](./policy-check.md) for static linting of the access policy.
- The same argument surface is available via `fluid policy apply` (new umbrella) and `fluid policy-apply` (legacy alias). Prefer the new form in new code; keep the alias in existing CI templates until the deprecation window closes.
