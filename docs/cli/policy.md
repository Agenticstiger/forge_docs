# `fluid policy`

Unified subcommand group for the three policy verbs: `check` (static lint), `compile` (emit IAM bindings), and `apply` (deploy bindings to the warehouse). Added in `0.8.0`.

Before this group, the three verbs lived as top-level hyphenated commands (`policy-check`, `policy-compile`, `policy-apply`). The names differ by one word but do completely different things — `policy-check` is a static lint, `policy-apply` is a destructive deployment — which was exactly the shape of UX mistake that hits in production. `fluid policy` groups them under one umbrella, mirroring `fluid auth {login,status,logout}` / `fluid generate {speed-transformation,schedule,ci,standard,artifacts}`.

The legacy hyphenated forms remain registered as deprecation aliases for one release.

## Syntax

```bash
fluid policy {check|compile|apply} ...
```

## Subcommands

| Subcommand | What it does | Doc |
| --- | --- | --- |
| `fluid policy check` | Static lint of the contract's policy declarations. No cloud calls. | [policy-check.md](./policy-check.md) |
| `fluid policy compile` | Compile `accessPolicy` → provider IAM bindings (`runtime/policy/bindings.json`). | [policy-compile.md](./policy-compile.md) |
| `fluid policy apply` | Deploy compiled IAM bindings (stage 8 of the pipeline). `--mode check` dry-runs; `--mode enforce` applies. | [policy-apply.md](./policy-apply.md) |

## Examples

### Typical flow

```bash
# Lint before committing
fluid policy check contract.fluid.yaml --strict

# Compile (part of stage 3 artifact fanout)
fluid policy compile contract.fluid.yaml --out runtime/policy/bindings.json

# Deploy (stage 8 of the 11-stage pipeline)
fluid policy apply runtime/policy/bindings.json --mode enforce
```

### Legacy hyphenated forms (still work)

```bash
fluid policy-check contract.fluid.yaml --strict
fluid policy-compile contract.fluid.yaml --out runtime/policy/bindings.json
fluid policy-apply runtime/policy/bindings.json --mode enforce
```

Both surfaces share the same argument set because they call the same `_add_arguments(parser)` helper per-verb. Adding a flag to either form automatically surfaces on the other — no drift possible.

## Pipeline ordering

Stage 8 (`policy apply`) runs **after** stage 7 apply (GRANTs need the target schema objects to exist) and **before** stage 9 verify (so transforms running on under-authorised objects surface as policy failures rather than masked build errors).

See the [11-stage pipeline walkthrough](../walkthrough/11-stage-pipeline.md) for the full ordering.
