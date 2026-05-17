# `fluid apply`

Stage 7 of the 11-stage pipeline. Execute a FLUID contract (or a saved plan) end-to-end: provision infrastructure, run transformations, apply governance, and publish to configured destinations.

`0.8.0` adds a 6-mode apply matrix (`--mode`) with explicit destruction gating (`--allow-data-loss`) and cryptographic plan-binding (`bundleDigest` / `planDigest` verification).

## Syntax

```bash
fluid apply CONTRACT
```

`CONTRACT` can be:

- A FLUID contract file (e.g. `contract.fluid.yaml`) — plans and applies in one shot.
- A saved plan JSON file (e.g. `runtime/plan.json`) — applies the already-planned actions, with digest verification.

## Apply mode (stage-7 dispatch)

| `--mode` | What it does |
| --- | --- |
| `dry-run` | Render the planned DDL without calling the warehouse. No state mutation. Safe in every environment. |
| `create-only` | `CREATE … IF NOT EXISTS`, plus a pre-check that fails if the target already exists. Use when a fresh project needs a clean provision. |
| `amend` *(default)* | `ALTER TABLE ADD COLUMN IF NOT EXISTS`; views `CREATE OR REPLACE`. Data preserved; new columns backfilled NULL. The everyday mode. |
| `amend-and-build` | Same DDL as `amend`, plus `dbt run` / `dbt test` (or the configured build runner). Transforms refreshed on top of the amended schema. |
| `replace` | Auto-snapshot the target, then `CREATE OR REPLACE TABLE` (Snowflake / BigQuery) or `DROP+CREATE` in a transaction (Redshift). **Destructive**: requires `--allow-data-loss` in non-dev environments or when the target has rows. |
| `replace-and-build` | Same as `replace`, plus a full `dbt run --full-refresh` to rebuild everything from sources. **Destructive**. |

The build-augmented modes (`amend-and-build`, `replace-and-build`) run the configured build runner. Pass `--build-id <id>` to filter execution to a single build job from the contract's `builds[]`; when unset, every build runs.

## Safety gates

| Option | Description |
| --- | --- |
| `--allow-data-loss` | Required to run `replace` / `replace-and-build` when `FLUID_ENV != dev` **or** the target already has rows. Two independent risk surfaces (env + population) → two-factor opt-in. Never default. |
| `--no-verify-plan-binding` | **Emergency escape hatch.** Skip the `bundleDigest` / `planDigest` verification that stage 7 normally enforces on a saved plan. Logged at `WARNING` so audit trails catch it. Use only during documented DR procedures. |
| `--no-verify-federation` | **Emergency escape hatch.** Skip the federated-`consumes[]` upstream-digest gate (drift between a pinned `upstreamDigest` and the live upstream). Logged at `WARNING` for audit. A distinct trust domain from plan binding — each gate has its own narrowly-scoped waiver. |

## Plan binding

When you pass a saved plan (`runtime/plan.json`) instead of a contract, `apply` verifies:

- `bundleDigest` in `plan.json` matches the MANIFEST SHA-256 of the tgz bundle the plan was built from. Mismatch → `PlanBindingError(kind="bundle-mismatch")` before any DDL executes.
- `planDigest` in `plan.json` matches a re-computed digest of the plan's action list (internal consistency check). Mismatch → `PlanBindingError(kind="plan-tamper")`.

This is the Terraform-style "apply consumes exact plan" guarantee, enforced cryptographically.

## Key options

### General

| Option | Description |
| --- | --- |
| `--env` | Apply an environment overlay (dev / staging / prod / …) |

### Execution control

| Option | Description |
| --- | --- |
| `--yes` | Skip confirmation |
| `--dry-run` | Alias for `--mode dry-run` |
| `--timeout TIMEOUT` | Global timeout in minutes |
| `--parallel-phases` | Execute independent phases in parallel |
| `--max-workers MAX_WORKERS` | Maximum workers for parallel execution |

### Safety and rollback

| Option | Description |
| --- | --- |
| `--rollback-strategy` | `none`, `immediate`, `phase_complete`, or `full_rollback` |
| `--require-approval` | Require explicit approval for destructive work |
| `--backup-state` | Create a backup before execution |
| `--validate-dependencies` | Validate dependencies before execution |

### Reporting

| Option | Description |
| --- | --- |
| `--report` | Output path for the execution report |
| `--report-format` | Report format |
| `--metrics-export` | Export metrics to monitoring backends |
| `--notify` | Send notifications to destinations such as Slack or email |

### Build execution

| Option | Description |
| --- | --- |
| `--build-id BUILD_ID` | Filter build execution to a specific build job by ID from the contract's `builds[]`. Combine with `--mode amend-and-build` or `--mode replace-and-build`. When unset and the mode requires builds, every build runs. |
| `--delay DELAY` | Seconds between build iterations |
| `--fail-fast` | Stop on first failure |
| `--no-output` | Suppress build script output |

### Debugging and advanced

| Option | Description |
| --- | --- |
| `--verbose` | Detailed progress output |
| `--keep-temp-files` | Keep temporary files |
| `--workspace-dir` | Custom workspace directory |
| `--state-file STATE_FILE` | Custom state file location |
| `--config-override` | Override contract config with JSON |
| `--provider-config` | Path to provider-specific configuration |

## Examples

### Everyday dev workflow

```bash
# Quickstart — default --mode amend, no destructive action
fluid apply contract.fluid.yaml --yes

# Preview-only
fluid apply contract.fluid.yaml --mode dry-run
fluid apply contract.fluid.yaml --dry-run   # same thing
```

### Production 11-stage pipeline (plan-bound)

```bash
# Stage 6 produces the plan with bundleDigest + planDigest
fluid plan contract.fluid.yaml --out runtime/plan.json

# Stage 7 verifies both digests before executing any DDL
fluid apply runtime/plan.json --mode amend --env prod --yes
```

### Destructive modes (explicit opt-in required)

```bash
# Prod replace — REQUIRES --allow-data-loss (two-factor opt-in)
fluid apply runtime/plan.json --mode replace --env prod --yes --allow-data-loss

# Full rebuild (dbt --full-refresh + destructive DDL)
fluid apply runtime/plan.json --mode replace-and-build --env prod --yes --allow-data-loss
```

After a `replace`, use [`fluid rollback`](./rollback.md) to restore from the auto-snapshot if something goes wrong.

### Build-augmented apply (dbt run)

```bash
fluid apply runtime/plan.json --mode amend-and-build --env dev --yes
```

### DR escape hatch (skip digest verification — audit-logged)

```bash
# Only in documented DR procedures. Emits WARNING to the audit log.
fluid apply runtime/plan.json --mode amend --no-verify-plan-binding --yes

# Skip only the federated-consumes upstream-digest gate
fluid apply runtime/plan.json --mode amend --no-verify-federation --yes
```

## Notes

- The recommended sequence is `bundle → validate → plan → apply`.
- For local-first onboarding, `fluid apply contract.fluid.yaml --yes` is the shortest path after a quickstart scaffold — default `--mode amend` is safe.
- `--mode replace` / `replace-and-build` **always** create an auto-snapshot before destructive DDL. On Snowflake this is a zero-copy `CLONE`; on BigQuery it's `bq cp --force`; on Redshift it's `CREATE TABLE _backup AS SELECT *`. Snapshot names are recorded in `.fluid/rollback-state.json`.
- If apply's provider dispatcher logs `unknown_action_op` for your contract's actions, the provider doesn't yet implement the abstract op. This is a known gap for some high-level ops (e.g. `provisionDataset`, `scheduleTask`) and is addressed by a translator layer in `providers/<platform>/`.

## Extension point: apply hooks

As of `0.8.3`, `fluid apply` runs any **apply hook** plugins registered via Python entry-points before invoking the providers. Use apply hooks to enforce runtime invariants that can't be checked at validate time — required env vars, image signatures, bundle-digest drift, business-hours gating, anything that depends on the deploy environment rather than the contract content.

A hook that appends an error aborts the apply with exit code 1. Pass `--force-pattern-drift` to downgrade all hook errors to WARNINGs (audit-logged) and let the apply proceed.

- Author a hook: [SDK & Plugins → Apply hook journey](/forge_docs/sdk-and-plugins/journeys/apply-hook.md)
- Reference: [Entry points → `fluid_build.apply_hooks`](/forge_docs/sdk-and-plugins/reference/entry-points.md)
- Example: [`prod-key-guard`](/forge_docs/sdk-and-plugins/examples/apply-hook-prod-key-guard.md)
