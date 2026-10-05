# `fluid ship`

Happy-path macro that chains `validate → bundle → plan → apply` in one command. Use it when you've already iterated on a contract locally and just want to push it through.

::: tip Where this fits
`fluid ship` landed in `0.8.3` alongside the day-2 ops surface.
:::

## Syntax

```bash
fluid ship [contract-path] [options]
```

## Examples

```bash
# Local dev: validate + apply only
fluid ship --skip-bundle --skip-plan --yes

# Production-style: validate strictly, then deploy the prod overlay
fluid ship contract.fluid.yaml --strict --env prod --yes

# Render the apply without writing anything
fluid ship contract.fluid.yaml --env dev --dry-run
```

The last command runs all four stages. Each stage line shows the command `ship` ran:

```text
🚢 fluid ship — running 4 stage(s)
...
[ship validate] $ fluid validate /.../contract.fluid.yaml
[ship bundle] $ fluid bundle /.../contract.fluid.yaml --format tgz
[ship plan] $ fluid plan /.../contract.fluid.yaml --env dev
[ship apply] $ fluid apply /.../contract.fluid.yaml --env dev --dry-run
...
🎉 Ship complete — all 4 stage(s) passed
```

## Behavior

`fluid ship` runs the four core stages in sequence, stopping at the first failure and relaying that stage's exit code:

```text
1. fluid validate <contract>                [--strict if --strict is set]
2. fluid bundle <contract> --format tgz     (skipped if --skip-bundle)
3. fluid plan <contract>                    [--env]  (skipped if --skip-plan)
4. fluid apply <contract>                   [--env] [--yes] [--dry-run]
```

Each stage runs as a separate process (`python -m fluid_build.cli <stage>`), so a stage's own flag handling and errors are unchanged.

Three things `ship` does not do, which differ from the [11-stage pipeline](../walkthrough/11-stage-pipeline.md):

- **`--env` reaches only `plan` and `apply`.** `validate` and `bundle` run against the base contract, so the bundle is not built for the environment you apply.
- **`apply` gets the contract path, not the bundle or `plan.json`.** `ship` therefore has no bundle or plan digest binding between the reviewed plan and the apply. For a chain that binds them, use [`fluid generate ci`](./generate.md#fluid-generate-ci) or run the stages yourself.
- **`--dry-run` does not stop before `apply`.** It passes `--dry-run` to `fluid apply`, which renders what it would do and writes nothing. The run still reports every stage as passed.

## Options

| Option | Description |
|---|---|
| `[contract-path]` | Path to the contract. Auto-discovered from the current directory if omitted. |
| `--env <env>` | Environment overlay, passed to `plan` and `apply` only. |
| `--strict` | Pass `--strict` to `fluid validate` (treat warnings as errors). |
| `--yes`, `-y` | Pass `--yes` to `fluid apply` (skip the interactive confirmation). Needed in CI. |
| `--skip-bundle` | Skip the bundle stage. |
| `--skip-plan` | Skip the plan stage. |
| `--dry-run` | Pass `--dry-run` to `fluid apply`. |

## Files `ship` writes

The bundle stage runs `fluid bundle <contract> --format tgz` with no `--out`, so the bundle goes next to the contract as `<contract id>.fluid.bundle.tgz`. The plan stage writes `plan.json` in the current directory. Neither is read by `apply`. Add them to `.gitignore`, or pass `--skip-bundle` and `--skip-plan`.

As of 0.18.1, a contract with a `fragments/` directory next to it changes where that bundle goes. [`fluid bundle`](./bundle.md) redirects a no-`--out` run to `<contract dir>/contract.bundled.fluid.yaml`, and for `--format tgz` it writes the gzip tarball under that `.yaml` name. `ship` then reports success, `fluid validate` and `fluid plan` cannot read the file as a contract, and `file contract.bundled.fluid.yaml` says `gzip compressed data`. Use `--skip-bundle` for a fragment layout, or run `fluid bundle --format tgz --out runtime/bundle.tgz` yourself.

## When to use the macro vs. the individual stages

| Use `fluid ship` when | Use individual stages when |
|---|---|
| You've already iterated and want a clean push | You're debugging a failing stage |
| For demo and quickstart speed | You need stage-specific flags `ship` doesn't expose (per-stage `--out` paths, `bundle --format`, `plan --html`) |
| | You want to inspect `plan.json` before apply, or bind the apply to the plan |

For the production-grade 11-stage pipeline (cryptographic plan binding, drift gating, supply-chain signing), use [`fluid generate ci`](./generate.md#fluid-generate-ci) to emit the full pipeline for your CI system instead of `fluid ship`.

## Exit codes

`fluid ship` relays the exit code of the **first failing stage**:

| Code | Meaning |
|---|---|
| `0` | All stages passed |
| Non-zero | Exit code of the failing stage (e.g. `1` from `validate` for a schema error) |

With no contract path and no `contract.fluid.yaml` in the current directory, `ship` exits `1` with `contract_required`. Stage logs are written to stdout and stderr unmodified: the macro doesn't buffer or reformat them. Pipe to `tee` or to your CI system's log capture as usual.

## See also

- [`fluid validate`](./validate.md), [`fluid bundle`](./bundle.md), [`fluid plan`](./plan.md), [`fluid apply`](./apply.md): the stages `ship` chains
- [`fluid generate ci`](./generate.md#fluid-generate-ci): production-grade 11-stage pipeline generator
- [11-stage pipeline walkthrough](../walkthrough/11-stage-pipeline.md): when you need more than the four core stages
