# `fluid ship`

Happy-path macro that chains `validate → bundle → plan → apply` in one command. Use when you've already iterated on a contract locally and just want to push it through.

::: tip Where this fits
`fluid ship` landed in `0.8.3` alongside the day-2 ops surface.
:::

## Syntax

```bash
fluid ship [contract-path] [options]
```

## Behavior

`fluid ship` runs the four core stages in sequence, stopping at the first failure and relaying that stage's exit code:

```text
1. fluid validate <contract>     [--strict if --strict is set]
2. fluid bundle <contract>        (skipped if --skip-bundle)
3. fluid plan <contract>          (skipped if --skip-plan)
4. fluid apply <contract>         [--yes if --yes is set]
```

Each stage runs as a separate process for clean error isolation; the spawn cost is ~50 ms per stage, negligible compared to actual stage runtime.

## Options

| Option | Description |
|---|---|
| `[contract-path]` | Path to the contract. Auto-discovered from cwd if omitted. |
| `--env <env>` | Environment overlay propagated to all stages. |
| `--strict` | Pass `--strict` to `fluid validate` (treat warnings as errors). |
| `--yes`, `-y` | Pass `--yes` to `fluid apply` (skip the interactive confirmation). |
| `--skip-bundle` | Skip stage 2. Useful for local dev when you don't want a `bundle.tgz`. |
| `--skip-plan` | Skip stage 3. Apply will compute a plan internally if needed. |
| `--dry-run` | Run validate + bundle + plan; stop before apply. |

## Examples

```bash
# Local dev: validate + apply only
fluid ship --skip-bundle --skip-plan --yes

# Production: full pipeline with strict validation
fluid ship contract.fluid.yaml --strict --env prod --yes

# Preview without applying
fluid ship contract.fluid.yaml --dry-run
```

## When to use the macro vs. the individual stages

| Use `fluid ship` when | Use individual stages when |
|---|---|
| You've already iterated and want a clean push | You're debugging a failing stage |
| In CI on a PR-merge / push to main | You need stage-specific flags `ship` doesn't expose (per-stage `--out` paths, `bundle --format`, `plan --html`) |
| For demo / quickstart speed | You want to inspect plan.json before apply |

For the production-grade 11-stage pipeline (with cryptographic plan-binding, drift gating, supply-chain signing), use [`fluid generate ci`](/forge_docs/cli/generate.html#fluid-generate-ci) to emit the full pipeline for your CI system instead of `fluid ship`.

## Exit codes

`fluid ship` relays the exit code of the **first failing stage**:

| Code | Meaning |
|---|---|
| `0` | All stages passed |
| Non-zero | Exit code of the failing stage (e.g. `1` from `validate` for a schema error, `2` from `apply` for a partial failure) |

Stage logs are written to stdout / stderr unmodified — the macro doesn't buffer or reformat. Pipe to `tee` or to your CI system's log capture as usual.

## See also

- [`fluid validate`](/forge_docs/cli/validate.html), [`fluid bundle`](/forge_docs/cli/bundle.html), [`fluid plan`](/forge_docs/cli/plan.html), [`fluid apply`](/forge_docs/cli/apply.html) — the stages `ship` chains
- [`fluid generate ci`](/forge_docs/cli/generate.html#fluid-generate-ci) — production-grade 11-stage pipeline generator
- [11-stage pipeline walkthrough](/forge_docs/walkthrough/11-stage-pipeline.html) — when you need more than the four core stages
