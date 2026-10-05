# The 11-Stage Pipeline

`fluid generate ci --system jenkins` writes a Jenkinsfile that takes a contract from source control to a verified, published deployment in eleven stages. Stages 1 to 11 each run one `fluid` command, and each one either passes or stops the build.

This page generates that Jenkinsfile, then runs the eleven commands by hand against a local product, so you see what each gate checks and what it prints when it fires. It was run end to end on CLI `0.18.1`; output has absolute paths shortened to `...`.

## Generate the pipeline

```bash
fluid generate ci contract.fluid.yaml --system jenkins --out Jenkinsfile
```

```text
[install-mode: pypi] Jenkinsfile written -> Jenkinsfile
  |- Jenkins installs FLUID_PACKAGE_SPEC into $WORKSPACE/.fluid-venv (stage 0)
  |  Override at build time via these Jenkins parameters:
  |    FLUID_PACKAGE_SPEC        = 'data-product-forge==X.Y.Z'  (another version)
  |    FLUID_PIP_INDEX_URL       = 'https://test.pypi.org/simple/'  (TestPyPI)
  |    FLUID_PIP_EXTRA_INDEX_URL = 'https://pypi.org/simple/'   (fallback)
  |    FLUID_ALLOW_PRERELEASE    = true  (pip --pre, alpha/rc releases)
  |- FLUID_PACKAGE_SPEC default: data-product-forge[local]==0.18.1
  |- Jenkins plugins required: workflow-aggregator, git
```

::: warning Do not pair a test or private index with PyPI
pip picks the highest version across every index it is given, so a TestPyPI index next to `FLUID_PIP_EXTRA_INDEX_URL=https://pypi.org/simple/` lets either one supply `data-product-forge` and its dependencies. Run TestPyPI pilots only on an agent that holds no deploy credentials, and for private packages use one mirror that proxies PyPI in `FLUID_PIP_INDEX_URL` with `FLUID_PIP_EXTRA_INDEX_URL` empty. See [Set up Jenkins](./jenkins-cicd.md#set-up-jenkins).
:::

On 0.18.1 `fluid generate ci` renders this 11-stage pipeline for Jenkins and Tekton; [which systems read which option](../cli/generate.md#which-systems-read-which-option) lists the other systems and what they take.

The Jenkinsfile installs the CLI itself (stage 0), then runs the stages in this table. Stages 2, 3, 5, 6 and 9 read the bundle that stage 1 wrote, and stage 7 applies the plan against it, so they work on the same bytes.

| Stage | Command | Reads | Writes |
| --- | --- | --- | --- |
| 1 | `fluid bundle` | the contract and its overlay for `FLUID_ENV` | `runtime/bundle.tgz` |
| 2 | `fluid validate` | the bundle | `runtime/validate-report.json` |
| 3 | `fluid generate artifacts` | the bundle | `dist/artifacts/` |
| 4 | `fluid validate-artifacts` | `dist/artifacts/` | `runtime/validate-artifacts-report.json` |
| 5 | `fluid diff` | the bundle and the live target | `runtime/diff-report.json` |
| 6 | `fluid plan` | the bundle | `runtime/plan.json`, `runtime/plan.html` |
| 7 | `fluid apply` | the plan and the bundle | the deployment, `runtime/apply-report.html` (non-build modes only, see [Stage 7](#stage-7-apply)) |
| 8 | `fluid policy-apply` | `dist/artifacts/policy/bindings.json` | `runtime/policy-apply-report.json` |
| 9 | `fluid verify` | the bundle and the live target | `runtime/verify-report.json` |
| 10 | `fluid publish` | the contract | `runtime/publish-report.json` |
| 11 | `fluid schedule-sync` | `dist/artifacts/schedule/` | the scheduler's DAG directory |

Two invariants hold the chain together:

- **Input integrity.** Stage 1 records a SHA-256 per file in the bundle's `MANIFEST.json`. Later stages read the bundle, and stage 4 re-verifies the artifacts against their own manifest.
- **Apply isolation.** `fluid apply` takes the plan from stage 6 and the bundle, and refuses to run unless the plan's digests match that bundle and that mode. The two refusals are shown in [Stage 7](#stage-7-apply).

::: warning The 11 stages are the Jenkins template
Generated with 0.18.1 at the default complexity, the GitHub Actions, GitLab CI, Azure DevOps, Bitbucket and CircleCI files contain no `fluid bundle`, `fluid diff`, `fluid validate-artifacts` or `fluid schedule-sync` step. They run commands such as `validate`, `plan`, `apply` and `test`, and the set differs per system. Read what `fluid generate ci --system <name>` writes for your system. See [Operating in CI](../advanced/operating-in-ci.md).
:::

### What the first build does

Jenkins registers a Pipeline job's `parameters` block when the job first runs, so the first build of a new job runs with no parameters set. The generated Jenkinsfile gives every parameter a default and every stage reads it with the same default as its fallback, so that first build behaves the way the dialog's defaults would. With the generated defaults:

- `APPLY_MODE` is `dry-run`. Stage 6 plans for `dry-run` and stage 7 renders the plan without changing anything.
- Stage 8 runs `fluid policy-apply --mode check`, and stage 9 prints that stage 7 ran as a dry run and skips.
- Stage 10 (`RUN_STAGE_10_PUBLISH`) and stage 11 (`RUN_STAGE_11_SCHEDULE_SYNC`) are off. Turned on, they print the same dry-run message and skip.
- `CONTRACT` is the path you generated from, `FLUID_ENV` is `dev`, and `FLUID_PACKAGE_SPEC` is the CLI version that generated the file with the extras the contract needs: `data-product-forge[local]==0.18.1` for this contract.

Run one plain build first, then use Build with Parameters. Jenkins refuses `buildWithParameters` for a job that has never run, because it has not learned the job's parameters yet (observed on a Jenkins controller on 4 to 5 October 2026 with a pipeline generated by this command).

Defaults you can set at generation time, so the first build is already what you want:

```bash
fluid generate ci contract.fluid.yaml --system jenkins \
  --apply-mode-default amend-and-build \
  --default-publish-target fluid-command-center \
  --publish-stage-default \
  --scheduler-default airflow \
  --scheduler-destination-default s3://my-airflow-dags/ \
  --schedule-sync-default \
  --out Jenkinsfile
```

| Flag | Sets the default of |
| --- | --- |
| `--apply-mode-default MODE` | `APPLY_MODE` (Jenkins default `dry-run`, the other systems `amend`) |
| `--fluid-env-default ENV` | `FLUID_ENV`, the overlay the stages pass to `--env` |
| `--fluid-package-spec SPEC` | `FLUID_PACKAGE_SPEC`, what stage 0 installs |
| `--default-publish-target TARGET` | `PUBLISH_TARGETS`, and the fallback stage 10 reads when a build has no parameters |
| `--publish-stage-default` | `RUN_STAGE_10_PUBLISH` |
| `--verify-strict-default` / `--no-verify-strict-default` | `VERIFY_STRICT` |
| `--schedule-sync-default`, `--scheduler-default`, `--scheduler-destination-default` | `RUN_STAGE_11_SCHEDULE_SYNC`, `SCHEDULER`, `SCHEDULER_DESTINATION` |
| `--diff-last-applied` | stage 5 compares against the plan the last successful build applied; needs the `copyartifact` plugin |

`--publish-include-env` is on by default: stage 10 runs `fluid publish --env "${FLUID_ENV:-dev}"`, so the catalog gets the contract with the overlay that stages 5 to 9 used. Pass `--no-publish-include-env` only when the pipeline installs a CLI old enough that `fluid publish` rejects `--env`.

A Jenkinsfile is generated once. After you upgrade the CLI, regenerate it and commit the result to pick up what changed: 0.16.3 moved stage 0 into a workspace virtual environment, pinned `FLUID_PACKAGE_SPEC`, and made the chain run from the bundle; 0.17.0 added `--check-sovereignty` to stage 6.

Besides the per-stage `RUN_STAGE_N_*` booleans, the Jenkinsfile that 0.18.1 generated for this page declares `CONTRACT`, `FLUID_ENV`, `FLUID_PACKAGE_SPEC`, `FLUID_PIP_INDEX_URL`, `FLUID_PIP_EXTRA_INDEX_URL`, `FLUID_ALLOW_PRERELEASE`, `VALIDATE_STRICT`, `GENERATE_EMIT`, `DIFF_EXIT_ON_DRIFT`, `PLAN_HTML`, `APPLY_MODE`, `APPLY_BUILD_ID`, `ALLOW_DATA_LOSS`, `NO_VERIFY_DIGEST`, `POLICY_APPLY_MODE`, `VERIFY_STRICT`, `PUBLISH_TARGETS`, `SCHEDULER`, `SCHEDULER_DESTINATION`, `SCHEDULER_ENVIRONMENT_NAME`, `SCHEDULER_LOCATION`, `SCHEDULER_WORKSPACE` and `SCHEDULE_SYNC_DRY_RUN`. Run only some stages by clearing the booleans in Build with Parameters.

---

## Run the stages by hand

Use the product from the [local walkthrough](./local.md) with one addition: a schedule on the build, so that stages 3 and 11 have a DAG to produce and deliver. Add this under the build in `contract.fluid.yaml`, above `outputs:`:

```yaml
    execution:
      trigger:
        type: schedule
        schedule: "0 2 * * *"
        timezone: Europe/Paris
```

Run the commands from the directory holding `contract.fluid.yaml`, with `mkdir -p runtime`. The commands are the ones the Jenkinsfile runs, with `FLUID_ENV` set to `dev`.

### Stage 1: bundle

[`fluid bundle`](../cli/bundle.md) packages the contract and its source files into a deterministic tgz with a `MANIFEST.json` (a SHA-256 per file and a Merkle root). Two runs over the same input produce the same bytes.

```bash
fluid bundle contract.fluid.yaml --env dev --format tgz --out runtime/bundle.tgz
```

```text
compile_start
compile_done
overlay_base_env: --env 'dev' has no overlay for .../contract.fluid.yaml; using the base contract (dev is the base by convention)
✅ Bundle written to .../runtime/bundle.tgz
   digest: sha256:a93f685a2ca01cc9ee39e11c11174d5b2a3f51d60adfd0c4ba92e776151303b5
   env: dev (overlay: none (base contract))
```

`dev` has no overlay here, so the bundle carries the base contract; the line says so. A contract with `overlays/<env>.yaml` is bundled with that overlay applied, and the stages that read the bundle check that it is for the `--env` they were given.

For supply-chain signing, `fluid bundle ... --sign` signs the bundle with Sigstore cosign and `--attest` adds SLSA provenance; install [cosign](https://docs.sigstore.dev/cosign/installation/) first. [`fluid verify-signature`](../cli/verify-signature.md) checks a signature before anything is pushed.

### Stage 2: validate

[`fluid validate`](../cli/validate.md) checks the bundle against the contract schema for its `fluidVersion` and runs the contract rules.

```bash
fluid validate runtime/bundle.tgz --env dev --report runtime/validate-report.json --strict
```

```text
✅ Bundle pass: .../runtime/bundle.tgz
   digest: sha256:a93f685a2ca01cc9ee39e11c11174d5b2a3f51d60adfd0c4ba92e776151303b5
   issues: 0 total (0 error, 0 warning, 0 info)
```

The template runs it with `--strict` by default (`VALIDATE_STRICT`), which also fails the stage on warnings. One warning that a contract moving to AWS meets: when an `aws` binding has `accessPolicy.grants` and no `governance.lakeFormation.grants`, validate warns that the grants are not enforced, and `--strict` turns that into a failed stage:

```text
Validation Warnings:
====================
 1. accessPolicy.grants are not enforced on aws binding(s) transactions: the AWS emitter does not write accessPolicy, and these bindings declare no governance.lakeFormation.grants, the AWS form of who may read the table. Add them to the aws overlay's binding 
(column restrictions then narrow them).
```

### Stage 3: generate artifacts

[`fluid generate artifacts`](../cli/generate-artifacts.md) writes the catalog, schedule and policy artifacts from the bundle.

```bash
fluid generate artifacts runtime/bundle.tgz --env dev --contract-path contract.fluid.yaml \
  --out dist/artifacts/ --emit odcs,odps-bitol,schedule,policies
```

```text
Exported ODPS product: .../dist/artifacts/odps-bitol/entertainment.genre_preferences_v1.odps.yaml
Exported ODCS contract: .../dist/artifacts/odps-bitol/entertainment.genre_preferences_v1.genre_preferences.odcs.yaml
Exported ODCS contract: .../dist/artifacts/odcs/product.odcs.genre_preferences.yaml

Generated 1 files (airflow scheduler):

  dist/artifacts/schedule/entertainment.genre_preferences_v1__dev/build_genre_preferences_dag.py

Tip: To regenerate after editing the contract: fluid generate schedule
generate_artifacts_policy_expose_level
   env: dev
✅ Artifacts written to dist/artifacts
   MANIFEST digest: sha256:f496e534b0f73837618643b5d1b5014672e00d6e11ff27e226ffc2c246d7742c
   files: 5
```

```text
dist/artifacts/MANIFEST.json
dist/artifacts/odcs/product.odcs.genre_preferences.yaml
dist/artifacts/odps-bitol/entertainment.genre_preferences_v1.genre_preferences.odcs.yaml
dist/artifacts/odps-bitol/entertainment.genre_preferences_v1.odps.yaml
dist/artifacts/policy/bindings.json
dist/artifacts/schedule/entertainment.genre_preferences_v1__dev/build_genre_preferences_dag.py
```

- `odcs/` and `odps-bitol/` hold the Open Data Contract Standard and ODPS-Bitol documents.
- `policy/bindings.json` holds the access bindings that stage 8 applies. This contract has no `accessPolicy` grants, so the file lists no bindings (`"warnings": ["No grants found in accessPolicy"]`).
- `schedule/<product id>__<env>/<build id>_dag.py` is one Airflow DAG per scheduled build, one directory per product and environment. The `__<env>` suffix is the `--env` you pass, or `$FLUID_ENV`.
- `MANIFEST.json` holds a SHA-256 for each file and a Merkle root.

Stage 3 writes schedule artifacts when the contract sets `orchestration.engine` to anything but `none`, or when it sets no engine and a build declares `execution.trigger.schedule` (or `cron`) with trigger `type: schedule` or no type. With `orchestration.engine: none` it logs `generate_artifacts_skip_schedule_engine_none`; with neither an engine nor a scheduled build it logs `generate_artifacts_skip_schedule_no_engine`. Either way it writes no DAG and the stage succeeds. [Declarative Airflow](./airflow-declarative.md) shows what is in the DAG file. For a contract whose builds use `pattern: hybrid-reference`, `fluid generate ci` turns stage 3 off by default.

::: warning Stage 3 reads the bundle, not a fragment root
A contract split into fragments with `$ref` (the layout [`fluid split`](../cli/split.md) writes) is accepted by `validate`, `plan`, `diff` and `bundle`. As of 0.18.1, `fluid generate artifacts <root>` on such a contract fails without `--env` with `Provider error: FLUID expose has no usable name`, because it reads the unresolved YAML. The same command succeeds with `--env <env>`, and on a stage-1 bundle, which is what the generated pipeline passes.
:::

### Stage 4: validate artifacts

[`fluid validate-artifacts`](../cli/validate-artifacts.md) re-hashes every file against `MANIFEST.json` and validates each format. The Jenkins stage runs only when `dist/artifacts/MANIFEST.json` exists, so a build with stage 3 off skips it.

```bash
fluid validate-artifacts dist/artifacts/ --manifest dist/artifacts/MANIFEST.json \
  --report runtime/validate-artifacts-report.json
```

```text
✅ Artifacts pass: dist/artifacts
   digest: sha256:f496e534b0f73837618643b5d1b5014672e00d6e11ff27e226ffc2c246d7742c
   issues: 0 total (0 error, 0 warning, 0 info)
```

Append a line to one artifact and run it again:

```text
❌ Artifacts fail: .../art-tampered
   digest: sha256:f496e534b0f73837618643b5d1b5014672e00d6e11ff27e226ffc2c246d7742c
   issues: 2 total (2 error, 0 warning, 0 info)
    manifest: odcs/product.odcs.genre_preferences.yaml: SHA-256 mismatch: expected sha256:5450b43b7ea8fa686d85baf2f7707c9e50c12e4e85e75ee340b02311c3f146d2, got sha256:a13a5ca65ce5d22f675015626500af581a54c1ac24a5e95f2016b7e607cea404
    manifest: .../art-tampered/MANIFEST.json: merkle root mismatch: expected 
sha256:f496e534b0f73837618643b5d1b5014672e00d6e11ff27e226ffc2c246d7742c, got sha256:9438db94306ace181832123f93bf4517e08dbba63ca6bb3b2cc509131bfd257e
rc=1
```

### Stage 5: diff (drift gate)

[`fluid diff`](../cli/diff.md) compares the bundle with what is actually deployed, so nothing is planned against a target that someone changed by hand. Without `--state` it reads each expose's live target: a local file or DuckDB table, a Glue table or a BigQuery table. For a cloud contract whose `fluid apply` state is reachable it also refreshes that state and reports what changed outside the apply.

```bash
fluid diff runtime/bundle.tgz --env dev --out runtime/diff-report.json --exit-on-drift
```

On the first build nothing exists yet, and that is not drift:

```text
Live drift check: 1 expose(s)
  genre_preferences [local] absent (to be created)  .../output/genre_preferences.csv
State drift check: not run (the contract runs on the local engine, which keeps no OpenTofu state). Drift comes from the live checks alone.
```

After stage 7 has applied, the same command reports the target as matching:

```text
Live drift check: 1 expose(s)
  genre_preferences [local] match  .../output/genre_preferences.csv
State drift check: not run (the contract runs on the local engine, which keeps no OpenTofu state). Drift comes from the live checks alone.
```

Each expose ends in one status:

| Status | Meaning | Fails `--exit-on-drift` |
| --- | --- | --- |
| `match` | the target exists with the declared columns | no |
| `evolved` | it differs only in ways the expose's `schemaPolicy` allows | no |
| `pending` | the contract changed since the last apply and the target is still as that apply left it; needs `--last-applied` | no |
| `drift` | the target was changed outside the contract | yes, exit 1 |
| `absent` | the target does not exist yet; apply will create it | no |
| `not_checked` | no live inspector for this binding (Snowflake, for example), or no schema declared | no |
| `error` | the inspector could not answer: credentials, network, a missing SDK | yes, exit 2 |

A target `--exit-on-drift` could not inspect exits 2. `--no-live` without `--state` has nothing to compare against, so the gate is downgraded to a warning.

For a local file or DuckDB table, which differences count as drift depends on `schemaPolicy` under `exposes[].contract`, because the build writes the file with the columns its source had. A contract that names none is judged as `evolve_safe`, so an extra column in a local CSV is `evolved`. With `schemaPolicy: strict`, the same extra column is drift and the gate stops the pipeline. A Glue or BigQuery table's columns are declared by the infrastructure code from the contract, so there any difference is drift whatever the policy says. This is the local case:

```text
Live drift check: 1 expose(s)
  genre_preferences [local] drift  .../drift/output/genre_preferences.csv
      - notes: in the target (VARCHAR) but not declared
      '.csv' files carry no column types; column names compared only
State drift check: not run (the contract runs on the local engine, which keeps no OpenTofu state). Drift comes from the live checks alone.
```

A binding can name its location through the environment, for example `path: "{{ env.FLUID_OUT_DIR }}/genre_preferences.csv"`. Since 0.18.1 the live check resolves the placeholder before it reads the target, the way `plan`, `apply` and `verify` do. On 0.18.0 a BigQuery binding whose project was `{{ env.FLUID_GCP_PROJECT }}` was refused with "the binding's BigQuery project, dataset or table is not a valid id", which failed stage 5 on every build of that product. Put the variable in the build's environment: with `FLUID_OUT_DIR` unset the placeholder resolves to nothing, and the local contract above reads `/genre_preferences.csv`, reports `absent (to be created)` and passes.

`--state` takes a JSON apply report. The file `fluid apply --report runtime/apply-report.html` writes is HTML, and `fluid diff --state` on it fails with `diff_failed` (`Expecting value: line 1 column 1`), so the generated pipeline does not pass `--state`.

Where the apply keeps OpenTofu state (the cloud providers), `diff` also runs `tofu plan -detailed-exitcode` against it; a local contract has no such state, and the output says so. [`fluid diff`](../cli/diff.md) lists the other flags: `--last-applied`, `--no-live`, `--state-backend`, `--workspace-dir`, `--no-state-drift` and `--ensure-opentofu`.

::: warning Upgrading can turn stage 5 red
Before 0.16.3 the gate compared against a `--state` baseline that the generated pipeline never supplied, so it could not fire. It now compares live targets, and a pipeline that was always green at stage 5 can fail on drift it was never looking at.
:::

### Stage 6: plan

[`fluid plan`](../cli/plan.md) writes `plan.json` with a `bundleDigest` and a `planDigest`. It plans for the same mode stage 7 applies, because the plan records the mode. `--html` also writes `plan.html`, a visualization of the plan.

```bash
fluid plan runtime/bundle.tgz --env dev --mode dry-run --out runtime/plan.json \
  --check-sovereignty --html runtime/plan.html
```

```text
============================================================
FLUID Execution Plan
============================================================
Contract: Genre Preferences
Version: 0.7.5
Total Actions: 2
============================================================

1. provision_genre_preferences (provisionDataset)
2. schedule_build_genre_preferences (scheduleTask)

✅ Plan saved to: .../runtime/plan.json


Sovereignty check: NOT CHECKED — the contract declares no 'sovereignty' policy, and the local provider has no sovereignty hook.
HTML report: .../runtime/plan.html
```

The generated Jenkins pipeline passes `--check-sovereignty` here (since 0.17.0). With no `sovereignty` block in the contract the check reports `NOT CHECKED` and passes, as above. With a `sovereignty` block whose `enforcementMode` is `strict`, a binding that violates it fails the stage with exit 1 before stage 7 reaches a cloud. Take an AWS contract with a binding in `us-east-1` and this block:

```yaml
sovereignty:
  jurisdiction: EU
  enforcementMode: strict
```

The plan stage prints:

```text
Sovereignty check: 1 finding(s)  — source: built-in policy engine, enforcementMode=strict; the aws provider has no sovereignty hook
  - ❌  Region 'us-east-1' (jurisdiction: US) does not match required jurisdiction: EU
   💡 Consider using regions in EU jurisdiction

❌ Sovereignty check FAILED — enforcementMode is 'strict'.
CLI command error
❌ sovereignty_violation  [ERR_SOVEREIGNTY_VIOLATION]
  contract: .../sov.fluid.yaml
```

The plan file is still written; the exit code is what stops the pipeline. `enforcementMode: advisory` reports without blocking. See [Sovereignty](../concepts/sovereignty.md), and [Governance](../advanced/governance.md) for how the enforcement modes apply to the plan and to apply.

### Stage 7: apply

[`fluid apply`](../cli/apply.md) checks the plan's digests against the bundle before it changes anything, then applies in the plan's mode. `--mode` picks the strategy:

| Mode | What it does |
| --- | --- |
| `dry-run` | renders the plan and changes nothing |
| `create-only` | creates what is missing and fails if the target exists |
| `amend` | additive: adds columns, replaces views; existing data is kept |
| `amend-and-build` | the same as `amend`, then runs the contract's `builds[]` |
| `replace` | drops and recreates the target; needs `--allow-data-loss` unless the environment is `dev` and the target is provably empty |
| `replace-and-build` | the same as `replace`, then runs the builds |

The first build's mode, `dry-run`, prints what would happen:

```bash
fluid apply runtime/plan.json --bundle runtime/bundle.tgz --mode dry-run --env dev --yes \
  --ensure-opentofu --report runtime/apply-report.html
```

```text
Loading pre-generated execution plan
🚀 Executing data product build (simple mode)
Detected provider: local, project: entertainment.genre_preferences_v1
🔍 Dry run mode - showing execution plan
╭──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ 🔍 Dry Run - No changes will be made                                                                                                                                                                                                                             │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
      📋 Planned Actions      
┏━━━━━━━━━━━━━━━━━━┳━━━━━━━━━┓
┃ Operation        ┃ Details ┃
┡━━━━━━━━━━━━━━━━━━╇━━━━━━━━━┩
│ provisionDataset │ {}      │
│ scheduleTask     │ {}      │
└──────────────────┴─────────┘
```

Nothing was written: there is no `output/` directory yet. To deploy, plan again for the mode you will apply, then apply that plan. `--build-id` goes only with the `*-and-build` modes:

```bash
fluid plan runtime/bundle.tgz --env dev --mode amend-and-build --out runtime/plan.json \
  --check-sovereignty --html runtime/plan.html
fluid apply runtime/plan.json --bundle runtime/bundle.tgz --mode amend-and-build --env dev --yes \
  --ensure-opentofu --report runtime/apply-report.html --build-id build_genre_preferences
```

As of 0.18.1, `--report` is written only on the non-build modes. An `amend-and-build` apply does not write `runtime/apply-report.html`; it writes run records and `runtime/out/local_apply_log.jsonl` instead. The generated Jenkinsfile archives the report with `allowEmptyArchive: true`, so the stage stays green without it.

```text
Loading pre-generated execution plan
Loading contract from execution plan: .../runtime/plan.json
Anchoring builds at source contract dir: ...

================================================================================
🚀 FLUID Build Runner
================================================================================
Contract: .../contract.fluid.yaml
Builds: 1
================================================================================

────────────────────────────────────────────────────────────
🔷 Build 'build_genre_preferences' (embedded-SQL / local DuckDB)
   ✅ Completed in 0.53s — 1 action(s) executed
   📁 .../output/genre_preferences.csv

================================================================================
📈 Overall Summary
================================================================================
Total builds: 1
✅ Executed: 1
❌ Failed: 0
⏭️  Skipped: 0
================================================================================
```

Two refusals protect the chain. A plan made for one mode cannot be applied in another:

```text
Loading pre-generated execution plan
CLI command error
❌ apply_plan_mode_mismatch  [ERR_APPLY_PLAN_MODE_MISMATCH]
  plan_mode: dry-run
  requested_mode: amend-and-build
  hint: the plan was generated for mode='dry-run' but apply requested mode='amend-and-build'. Re-run ``fluid plan <contract> --mode amend-and-build`` to produce a mode-aware plan, or change ``--mode`` on apply to match.
rc=1
```

And a bundle other than the one the plan was made from is refused. This is the plan above with a bundle built after a one-line edit:

```text
Loading pre-generated execution plan
CLI command error
❌ apply_plan_digest_bundle_mismatch  [ERR_APPLY_PLAN_DIGEST_BUNDLE_MISMATCH]
  kind: bundle-mismatch
  error: plan.json was computed against bundle 'sha256:a93f685a2ca01cc9ee39e11c11174d5b2a3f51d60adfd0c4ba92e776151303b5' but 
.../runtime/bundle2.tgz has digest 
'sha256:ca599d28c02c73a7b007144171bd7e3116bb898f0d9005e2b93568c9a9386e5f'. Re-run ``fluid plan`` against the current bundle before applying.
rc=1
```

`NO_VERIFY_DIGEST` in the Jenkinsfile is the disaster-recovery escape: it passes `--no-verify-plan-binding --no-verify-federation`, and the CLI logs a warning for the audit trail.

`--ensure-opentofu` provisions a pinned OpenTofu build if `tofu` is missing, checked against the release's `SHA256SUMS` (integrity, not a signature), which a cloud apply needs and a local apply does not.

Back the target up yourself before a destructive mode. The OpenTofu engine the cloud providers use creates no pre-replace snapshot, so [`fluid rollback`](../cli/rollback.md) has no restore point after a cloud `replace`. On the local engine the data-loss gate says the table "will be snapshotted", but as of 0.18.1 a `replace-and-build` apply of a local CSV output (with `--allow-data-loss`) wrote no `.fluid/rollback-state.json`, so there was nothing to roll back to.

**Command Center reporting** ([what it sends](../concepts/command-center.md#what-fluid-apply-reports)). Since 0.17.0 `fluid apply` reports each run to the Command Center, best effort: it registers the run when it starts and closes it with its status, and an outage costs a warning and a bounded timeout, never the exit code. It uses the credentials and organization `fluid publish --target fluid-command-center` uses (`FLUID_CC_ENDPOINT`, `FLUID_API_KEY` or `FLUID_BEARER_TOKEN`, and `FLUID_CC_ORG_ID` or the organization in `fluid.config.yaml`). Without an organization nothing is sent. It sends the product id, contract version, contract hash, environment, provider, mode, change counts, timings and the builds it ran, never a secret, a header or OpenTofu output. `FLUID_COMMAND_CENTER_ENABLED=false` turns it off.

### Stage 8: policy apply

[`fluid policy-apply`](../cli/policy-apply.md) hands the access bindings from `dist/artifacts/policy/bindings.json` to the provider. It runs after apply and before verify. In 0.18.1 it changes no cloud permissions, as described below. The Jenkins stage skips when the file is missing, and after a dry-run apply it runs with `--mode check` instead of `enforce`.

```bash
fluid policy-apply dist/artifacts/policy/bindings.json --mode enforce
```

With the empty bindings file this contract produced, the command prints nothing and exits 0.

On 0.18.1 the command provisions nothing on any provider, in either mode. For a `gcp` binding it reports the compiled bindings and returns `applied: 0`; GCP IAM is created by stage 7, `fluid apply`. For an `aws` or `snowflake` binding it prints `No policy bindings were enforced` and exits 0. On AWS the grants come from `governance.lakeFormation.grants` instead, which `fluid apply` writes: see [accessPolicy on AWS](../providers/aws.md#accesspolicy-on-aws).

### Stage 9: verify

[`fluid verify`](../cli/verify.md) reconciles the bundle with what is deployed. The Jenkins stage is skipped after a dry-run apply, because nothing was applied.

```bash
fluid verify runtime/bundle.tgz --env dev --out runtime/verify-report.json --strict
```

```text
📋 Verifying: genre_preferences
   Format: csv
   Target: .../output/genre_preferences.csv

   🟢 Severity: SUCCESS (Impact: NONE)
   📁 File: .../output/genre_preferences.csv (csv)
   📊 Rows: 14

   🔍 Dimension 1: Schema Structure
      ✅ PASS - All 7 declared columns present

   ⚪ Data types, constraints, location: not checked for local files (column names, row count and masked-value shapes only)

   💡 Remediation: NONE
      All checks passed

================================================================================
📊 Verification Summary
================================================================================
Total verified: 1
✅ Match: 1
⚠️  Mismatch: 0
❌ Error: 0
================================================================================

📄 Report saved: .../runtime/verify-report.json
```

What `verify` checks depends on the target. For a local CSV or Parquet file it is the column names and a row count. For BigQuery tables it also checks a row count against the build's run records, that masked columns do not hold cleartext, and, when the contract declares them, retention, encryption and column restrictions, with a query that needs `bigquery.jobs.create` on the project; for S3 with Glue it adds a Lake Formation column check. [`fluid verify`](../cli/verify.md) is the reference for the command. Under `--strict` a mismatch exits 1. An expose with no verifier for its binding is reported as `unsupported`, skipped and never fails the run, so a green stage does not mean every expose was checked; the per-target dimensions and the statuses are in the [`fluid verify`](../cli/verify.md) reference.

### Stage 10: publish

[`fluid publish`](../cli/publish.md) sends the contract and its catalog artifacts to one or more catalogs; the `fluid-command-center` target is described in [Publishing to the FLUID Command Center](../cli/publish.md#publishing-to-the-fluid-command-center). `--target <name>` is repeatable, and the result names each target, so a partial failure is visible:

```bash
fluid publish contract.fluid.yaml --env dev --target datamesh-manager --target fluid-command-center --format json
```

This stage needs a catalog endpoint and credentials on the agent, so it was not run for this page. The Jenkins stage is off by default, is skipped after a dry-run apply, and takes `PUBLISH_TARGETS` as catalog names; an endpoint is set on the agent (`FLUID_CC_ENDPOINT` and the like), not in the parameter.

For Data Mesh Manager and Entropy Data, ODPS product-to-product dependencies are published as Access agreements in pending status. Use `DMM_AUTO_APPROVE_ACCESS=true` or `fluid dmm publish --auto-approve-access` only in environments where those agreements should be approved automatically.

The `fluid-command-center` target keeps one catalogue product per contract id, keyed by `metadata.fluid_contract_id`, and whichever `--env` published last wins: it records `fluid_env` and overwrites the product's platform and location. See [Publishing an environment, and last-writer-wins](../concepts/command-center.md#publishing-an-environment-and-last-writer-wins). If a pipeline per environment or cloud publishes the same product, turn stage 10 off in all but one of them, for example by generating the others with `--no-publish-stage-default`.

### Stage 11: schedule sync

[`fluid schedule-sync`](../cli/schedule-sync.md) delivers the DAG files from stage 3 to the scheduler: Airflow, MWAA, Cloud Composer, Astronomer, Prefect or Dagster. The Jenkins stage skips when `SCHEDULER` is blank, when `dist/artifacts/schedule/` is empty, or after a dry-run apply. It takes no contract argument. This run delivers to a local directory:

```bash
fluid schedule-sync --scheduler airflow --dags-dir dist/artifacts/schedule/ \
  --destination "file://$PWD/airflow-dags" --env dev --delete-scope product \
  --report runtime/schedule-sync-report.json
```

```text
[schedule-sync] scheduler=airflow dags-dir=.../dist/artifacts/schedule env=dev 
delete-scope=product dry-run=False
schedule_sync_subprocess
[schedule-sync] → /usr/bin/rsync -av --delete -- 
.../dist/artifacts/schedule/entertainment.genre_preferences_v1__dev/ 
.../airflow-dags/entertainment.genre_preferences_v1__dev/
[schedule-sync] report → .../runtime/schedule-sync-report.json
[schedule-sync] ✔ airflow sync complete (1 subprocess(es))
rc=0
```

```text
airflow-dags/entertainment.genre_preferences_v1__dev/build_genre_preferences_dag.py
```

`--delete-scope product`, the default, treats each directory of `--dags-dir` as one product and mirrors it into the same-named directory of the destination. Stale DAGs are deleted in that directory only, so other products' files in a shared DAG root are left alone. [What gets deleted](../cli/schedule-sync.md#what-gets-deleted) lists the other scopes. The report records what the sync replaced:

```json
{
  "scheduler": "airflow",
  "env": "dev",
  "delete_scope": "product",
  "overall_exit": 0,
  "superseded_scopes": [
    {
      "env": "dev",
      "old_dags_retired": true,
      "replaces": "entertainment.genre_preferences_v1",
      "scope": "entertainment.genre_preferences_v1__dev"
    }
  ]
}
```

The DAG id is `<product id>__<env>__<build id>`:

```text
dag_id='entertainment.genre_preferences_v1__dev__build_genre_preferences',
```

Airflow keys run history on the DAG id, so an environment-bound DAG starts a new history. Before 0.17.0 the DAGs of a product were rendered into `<product id>/` with the id `<product id>__<build id>`. `schedule-sync` retires those for the same product and environment when the destination is a local path or `git+ssh` and the scheduler is `airflow`; `old_dags_retired` is `true` then, including on a first sync like the one above, where there was nothing to retire. For any other destination it prints a note telling you to delete them once, because Airflow would otherwise run both. `--delete-scope destination` mirrors onto the whole destination and `none` copies without deleting.

---

## Failure posture

Each gate stops the build with a non-zero exit. These are the ones shown above, as measured on 0.18.1:

| Stage | What fired | Exit | Event |
| --- | --- | --- | --- |
| 4 | an artifact differs from `MANIFEST.json` | 1 | `manifest: ... SHA-256 mismatch` |
| 5 | drift against the live target | 1 | `diff_live_drift_detected` |
| 5 | a live target could not be inspected | 2 | per the `--exit-on-drift` help |
| 6 | a strict sovereignty violation | 1 | `sovereignty_violation` |
| 7 | the plan was made for another mode | 1 | `apply_plan_mode_mismatch` |
| 7 | the bundle is not the plan's | 1 | `apply_plan_digest_bundle_mismatch` |
| 9 | a column mismatch under `--strict` | 1 | reported per expose |

Error events carry a slug and an `ERR_` code, so CI log parsers can key off them. [Typed CLI errors](../advanced/typed-cli-errors.md) lists them.

## Related

- [`fluid generate ci`](../cli/generate.md): the options and the CI systems it supports
- [Operating in CI](../advanced/operating-in-ci.md): the stage table and parameters per system
- [Jenkins CI/CD walkthrough](./jenkins-cicd.md): connect the generated pipeline to a Jenkins controller
- [Declarative Airflow](./airflow-declarative.md): what the stage-3 DAG runs
- [`fluid rollback`](../cli/rollback.md): restore from a snapshot after a destructive local apply
- [`fluid verify-signature`](../cli/verify-signature.md): verify a bundle signature before stage 11 pushes DAGs
