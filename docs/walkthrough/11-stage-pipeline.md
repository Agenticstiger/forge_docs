# The 11-Stage Pipeline

A complete end-to-end walkthrough of the production pipeline promoted in `forge-cli` `0.8.0`. Every stage is a CI gate that exits non-zero on failure; each stage maps to exactly one `fluid` command.

## Overview

```
┌──────────── STRUCTURAL ────────────┐    ┌─ PUBLICATION ─┐
  1. bundle     → 2. validate                10. publish
        ↓                                          ↓
  3. generate   → 4. validate-artifacts       11. schedule-sync
     artifacts                                    (Path A only)
        ↓
  5. diff       → 6. plan → 7. apply
                                 ↓
  8. policy-apply → 9. verify
└────────────────────────────────────┘
```

Two structural invariants are enforced cryptographically:

- **Input integrity** — every stage after `bundle` re-verifies the bundle's MANIFEST SHA-256 before running.
- **Apply isolation** — `fluid apply` refuses to run unless the plan it was handed has matching `bundleDigest` + `planDigest`.

## Prerequisites

```bash
# Install the stable release
pip install data-product-forge

# Health check
fluid doctor
fluid version
```

For the supply-chain stages (1 with `--sign` / `--attest`; 11 with `--verify-signature`), install cosign: https://docs.sigstore.dev/cosign/installation/.

## The full flow (one product, one provider)

```bash
CONTRACT="contract.fluid.yaml"

# Stage 1 — bundle
fluid bundle $CONTRACT --format tgz --out runtime/bundle.tgz

# Stage 2 — validate
fluid validate runtime/bundle.tgz --strict --report runtime/validate-report.json

# Stage 3 — generate artifacts (catalog + DAGs + policy bindings)
fluid generate artifacts $CONTRACT --out dist/artifacts/

# Stage 4 — validate-artifacts (MANIFEST SHA-256 re-verify + per-format schemas)
fluid validate-artifacts dist/artifacts/ --manifest dist/artifacts/MANIFEST.json

# Stage 5 — drift gate
fluid diff $CONTRACT --env dev --out runtime/diff-report.json --exit-on-drift

# Stage 6 — plan (with mermaid-rendered HTML DAG + cryptographic digests)
fluid plan $CONTRACT --out runtime/plan.json --html --env dev

# Stage 7 — apply (verifies bundleDigest + planDigest before any DDL)
fluid apply runtime/plan.json --mode amend --env dev --yes --report runtime/apply-report.html

# Stage 8 — policy apply (stage between apply + verify so GRANTs land before transforms run)
fluid policy apply dist/artifacts/policy/bindings.json --mode enforce --env dev

# Stage 9 — verify (multi-dimensional schema / types / constraints / location)
fluid verify $CONTRACT --env dev --strict --out runtime/verify-report.json

# Stage 10 — publish (repeatable --target)
fluid publish $CONTRACT --target datamesh-manager --target command-center --env dev

# Stage 11 — schedule-sync (Path A only)
fluid schedule-sync \
  --scheduler airflow \
  --dags-dir dist/artifacts/schedule/ \
  --destination s3://my-airflow-dags/team-x/ \
  --env dev
```

## Stage-by-stage detail

### Stage 1 — bundle

[`fluid bundle`](../cli/bundle.md) packages the contract + its source files into a deterministic content-addressable tgz with a MANIFEST.json (SHA-256 per file + merkle root). Two independent runs produce byte-identical output.

```bash
fluid bundle contract.fluid.yaml --format tgz --out runtime/bundle.tgz
```

Optional supply-chain flags:

```bash
fluid bundle contract.fluid.yaml --format tgz --out runtime/bundle.tgz --sign           # Sigstore cosign
fluid bundle contract.fluid.yaml --format tgz --out runtime/bundle.tgz --sign --attest  # + SLSA L2 provenance
```

### Stage 2 — validate

[`fluid validate`](../cli/validate.md) checks the contract against the FLUID schema (auto-selected from `fluidVersion`) plus provider-specific rules.

```bash
fluid validate runtime/bundle.tgz --strict --report runtime/validate-report.json
```

### Stage 3 — generate artifacts

[`fluid generate artifacts`](../cli/generate-artifacts.md) produces catalog + execution artifacts:

- `odcs/` — ODCS v3.1.0 contracts per expose
- `odps-bitol/` — ODPS-Bitol v1.0.0 product files
- `schedule/` — DAG files (when `orchestration.engine` is set)
- `policy/bindings.json` — compiled IAM / GRANT bindings
- `MANIFEST.json` — SHA-256 per file + merkle root

Reference-only contracts (`builds[].pattern: hybrid-reference`) auto-skip `schedule` and `policies`.

### Stage 4 — validate-artifacts

[`fluid validate-artifacts`](../cli/validate-artifacts.md) re-hashes every file against `MANIFEST.json` and runs per-format schema validation (ODCS, ODPS-Bitol, DAG syntax, policy-bindings key-check). Self-gates on `MANIFEST.json` existence — skipped cleanly when stage 3 was off.

### Stage 5 — diff (drift gate)

[`fluid diff`](../cli/diff.md) compares the desired state against the deployed state (or a saved `apply_report.json` baseline). `--exit-on-drift` only hard-fails when a `--state` baseline was supplied — otherwise the gate downgrades to a warning, because every desired resource looks "new" on the first-ever run.

### Stage 6 — plan

[`fluid plan`](../cli/plan.md) emits `plan.json` with `bundleDigest` + `planDigest` fields. `--html` renders a mermaid DAG (colour-coded by action mode) alongside a raw-JSON drill-down.

### Stage 7 — apply

[`fluid apply`](../cli/apply.md) verifies both digests against the bundle MANIFEST before executing any DDL. `--mode` picks the dispatch semantic:

- `dry-run` — render only
- `create-only` — fail if target exists
- `amend` *(default)* — ADD COLUMN IF NOT EXISTS; non-destructive
- `amend-and-build` — amend + dbt run
- `replace` — destructive; requires `--allow-data-loss` in non-dev
- `replace-and-build` — destructive + dbt --full-refresh

Destructive modes auto-snapshot before mutating. Use [`fluid rollback`](../cli/rollback.md) to restore.

### Stage 8 — policy apply

[`fluid policy apply`](../cli/policy-apply.md) deploys the IAM bindings from `dist/artifacts/policy/bindings.json`. Runs AFTER apply (GRANTs need the target schema objects) and BEFORE verify (so transforms on under-authorised objects surface as policy failures, not build errors). Self-gated on `bindings.json` existence.

### Stage 9 — verify

[`fluid verify`](../cli/verify.md) performs four-dimensional checks against the deployed warehouse:

- Schema structure
- Data types
- Constraints (nullable / required)
- Location

Reference-only contracts downgrade "table not found" to INFO under `--strict` (external pipeline owns creation).

### Stage 10 — publish

[`fluid publish`](../cli/publish.md) ships contracts + catalog artifacts to one or more targets. The new `--target <name>[:<endpoint>]` flag is repeatable; one call can publish to multiple catalogs with a per-target result block for partial-failure visibility.

### Stage 11 — schedule-sync (Path A only)

[`fluid schedule-sync`](../cli/schedule-sync.md) pushes DAG files to the scheduler control plane (Airflow / MWAA / Composer / Astronomer / Prefect / Dagster). Path-B engines (EventBridge / Snowflake Tasks) apply their schedules inside stage-7 `apply` via `SchedulePlanner`, so stage 11 is a no-op for those contracts. Self-gated on `dist/artifacts/schedule/` presence.

## Generating a CI pipeline

The easiest way to run the 11 stages end-to-end is to let `fluid generate ci` emit a parameterised pipeline for your CI system:

```bash
fluid generate ci --system jenkins --install-mode pypi
# emits Jenkinsfile with all 11 stages + per-stage RUN_STAGE_N_X toggles
```

Supported systems: `jenkins`, `github`, `gitlab`, `azure`, `bitbucket`, `circle`, `tekton`.

Each template exposes the full surface as build parameters:

- `CONTRACT`, `FLUID_ENV`
- `RUN_STAGE_1_BUNDLE` … `RUN_STAGE_11_SCHEDULE_SYNC` (booleans)
- `BUNDLE_FORMAT`, `APPLY_MODE`, `APPLY_BUILD_ID`, `ALLOW_DATA_LOSS`, `NO_VERIFY_DIGEST`, `POLICY_APPLY_MODE`, `VERIFY_STRICT`, `DIFF_EXIT_ON_DRIFT`, `PUBLISH_TARGETS`, `SCHEDULER`, `SCHEDULER_DESTINATION`, …

Operators run selected stages for a deploy (e.g. only 1–9 for a dev smoke) by flipping the booleans in Jenkins Build-With-Parameters.

## Failure posture

Per stage, the exit code semantics are:

| Exit | Meaning |
| --- | --- |
| `0` | Stage passed (or legitimately skipped — e.g. ref-only contract at stage 3/8/11). |
| `1` | Gate fired — drift detected, schema mismatch, policy violation, etc. |
| `2` | Config error — missing file, bad flag value, etc. |

Stages exit fast with clear error events (`apply_mode_data_loss_blocked`, `schedule_sync_dags_dir_missing`, `validate_artifacts_sha_mismatch`, …). CI log parsers can key off the event slugs for red/amber/green dashboards.

## Related

- [`fluid generate ci`](../cli/generate.md) — generate a 7-system parameterised pipeline with all 11 stages wired
- [`fluid rollback`](../cli/rollback.md) — restore from the auto-snapshot when stage 7 replaces went wrong
- [`fluid verify-signature`](../cli/verify-signature.md) — verify supply-chain signatures on a bundle before letting stage 11 push DAGs
