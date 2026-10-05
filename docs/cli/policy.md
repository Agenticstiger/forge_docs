# `fluid policy`

Unified subcommand group for the three policy verbs: `check` (static lint), `compile` (emit IAM bindings), and `apply` (hand the compiled bindings to the provider). Added in `0.8.0`.

Before this group, the three verbs lived as top-level hyphenated commands (`policy-check`, `policy-compile`, `policy-apply`). The names differ by one word but do different things, so `fluid policy` groups them under one umbrella, mirroring `fluid auth {login,status,logout}` / `fluid generate {transformation,schedule,ci,standard,artifacts}`.

The hyphenated forms are still registered in 0.18.1, take the same arguments, and print no deprecation notice. Prefer `fluid policy ...` in new scripts.

## Syntax

```bash
fluid policy                              # interactive guide (no subcommand → friendly panel)
fluid policy {check|compile|apply} ...
```

::: tip Bare invocation is friendly
Running `fluid policy` with no subcommand renders a Rich panel listing
`check`, `compile`, and `apply` with one-line descriptions and example
invocations. When `contract.fluid.yaml` exists in the cwd the guide
highlights `check` as the right starting move.
:::

## Subcommands

| Subcommand | What it does | Doc |
| --- | --- | --- |
| `fluid policy check` | Static lint of the contract's policy declarations. No cloud calls. | [policy-check.md](./policy-check.md) |
| `fluid policy compile` | Compile `accessPolicy` → provider IAM bindings (`runtime/policy/bindings.json`). | [policy-compile.md](./policy-compile.md) |
| `fluid policy apply` | Pass compiled IAM bindings to the provider (stage 8 of the pipeline). In 0.18.1 no provider changes permissions here: GCP reports the bindings, the others print that they have no applier. `fluid apply` provisions the access resources. | [policy-apply.md](./policy-apply.md) |

## Examples

### Typical flow

```bash
# Lint before committing
fluid policy check contract.fluid.yaml --strict

# Compile (part of stage 3 artifact fanout)
fluid policy compile contract.fluid.yaml --out runtime/policy/bindings.json

# Hand the bindings to the provider (stage 8 of the 11-stage pipeline)
fluid policy apply runtime/policy/bindings.json --mode enforce
```

### Hyphenated forms (still registered)

```bash
fluid policy-check contract.fluid.yaml --strict
fluid policy-compile contract.fluid.yaml --out runtime/policy/bindings.json
fluid policy-apply runtime/policy/bindings.json --mode enforce
```

Both surfaces share one argument set per verb.

## Pipeline ordering

Stage 8 (`policy apply`) runs **after** stage 7 apply and **before** stage 9 verify.

See the [11-stage pipeline walkthrough](../walkthrough/11-stage-pipeline.md) for the full ordering.
