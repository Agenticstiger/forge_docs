# `fluid apply`

Stage 7 of the 11-stage pipeline. Execute a FLUID contract (or a saved plan) end-to-end: provision infrastructure, run transformations, apply governance, and publish to configured destinations.

`0.8.0` adds a 6-mode apply matrix (`--mode`) with explicit destruction gating (`--allow-data-loss`) and cryptographic plan-binding (`bundleDigest` / `planDigest` verification).

> **Why it matters**
> A saved plan is applied only if its digests and its mode still match what was reviewed, and a plan that destroys data-bearing resources is refused unless you pass `--allow-data-loss`.
> `fluid apply` re-verifies the `bundleDigest` + `planDigest` before any DDL and refuses a tampered plan.

## Syntax

```bash
fluid apply [CONTRACT] [--env ENV] [--mode MODE] [--yes] [options]
```

`CONTRACT` can be:

- A FLUID contract file (e.g. `contract.fluid.yaml`) — plans and applies in one shot. When omitted, `apply` uses `contract.fluid.yaml` in the current directory. The file may be the root of a [fragment layout](../concepts/fragments.md): its `$ref` pointers are resolved first, within the root contract's directory tree ([rules](../concepts/contract-refs.md)), before the contract is planned.
- A saved plan JSON file (e.g. `runtime/plan.json`) — applies the already-planned actions, with digest verification. See [Plan binding](#plan-binding).
- A bundle (`.tgz`) written by [`fluid bundle`](./bundle.md). A bundle carries its overlay already applied, so it is never re-overlaid: an `--env` that disagrees with the env the bundle was built for is refused with `bundle_env_mismatch`.

## Examples

### Preview, then apply

```bash
# Default --mode amend: additive, no destructive action
fluid apply contract.fluid.yaml --dry-run
fluid apply contract.fluid.yaml --yes
```

`--dry-run` is the same as `--mode dry-run`. On the OpenTofu engine (see [Which engine runs](#which-engine-runs)) it stops after `tofu plan`.

### Plan, review, apply the plan

```bash
# Stage 6 writes the plan with bundleDigest + planDigest
fluid plan contract.fluid.yaml --env prod --out runtime/plan.json

# Stage 7 verifies both digests before executing anything
fluid apply runtime/plan.json --yes
```

The plan records the `--env` it was made for and, when you pass `--mode`, the mode. Apply the plan with the same mode: a mismatch is refused before anything runs (see [Plan binding](#plan-binding)).

### Build-augmented apply

Plan and apply with the same `--mode`:

```bash
fluid plan contract.fluid.yaml --env dev --mode amend-and-build --out runtime/plan.json
fluid apply runtime/plan.json --mode amend-and-build --yes
```

```text
Loading pre-generated execution plan
Loading contract from execution plan: ./runtime/plan.json
...
🔷 Build 'customer_360_pipeline' (embedded-SQL / local DuckDB)
...
📈 Overall Summary
Total builds: 1
✅ Executed: 1
❌ Failed: 0
⏭️  Skipped: 0
```

A build that reads another product's expose through `consumes[]` is covered in [Consume one contract from another](../recipes/consumes-contract-to-contract.md). To land the result of an embedded-SQL build in BigQuery, see [Loading data](../providers/gcp.md#loading-data). This run was against the `customer-360` project from `fluid init --quickstart` on the `local` provider. If you plan without `--mode` and apply with `--mode amend-and-build`, apply stops before any build:

```text
❌ apply_plan_mode_mismatch  [ERR_APPLY_PLAN_MODE_MISMATCH]
  plan_mode: None
  requested_mode: amend-and-build
  hint: the plan was generated for mode=None but apply requested mode='amend-and-build'. Re-run
``fluid plan <contract> --mode amend-and-build`` to produce a mode-aware plan, or change ``--mode``
on apply to match.
```

### Destructive modes

```bash
# Replace: plan with the same mode, then apply with --allow-data-loss
fluid plan contract.fluid.yaml --env prod --mode replace --out runtime/plan.json
fluid apply runtime/plan.json --mode replace --yes --allow-data-loss

# Full rebuild (build runner with a full refresh + destructive provisioning)
fluid plan contract.fluid.yaml --env prod --mode replace-and-build --out runtime/plan.json
fluid apply runtime/plan.json --mode replace-and-build --yes --allow-data-loss
```

`replace` and `replace-and-build` need `--allow-data-loss` in every environment, `--env dev` included (see [Safety gates](#safety-gates)).

### Emergency escape hatches (audit-logged)

```bash
# Only in documented DR procedures. Emits a WARNING to the audit log.
fluid apply runtime/plan.json --no-verify-plan-binding --yes

# Skip only the federated-consumes upstream-digest check
fluid apply contract.fluid.yaml --no-verify-federation --yes
```

## Which engine runs

`fluid apply` picks its engine from the contract's provider.

| Engine | Providers | What happens |
| --- | --- | --- |
| OpenTofu | `aws`, `gcp`, `snowflake`, `confluent` | forge compiles the contract to a `.tf.json` module under `.fluid/iac/<provider>/<safe-id>/` (dots and dashes in the id become `_`), then runs `tofu init`, `tofu plan` and `tofu apply`. Needs the `tofu` binary on `PATH`, or `--ensure-opentofu`. |
| Native | `local`, and a provider outside the set above | The provider plans actions and runs them itself. |

A cloud provider registered out of tree through the `fluid_build.iac_providers` entry point also applies through OpenTofu. The OpenTofu engine prints which module, state and credentials it is using before it plans. This is real output from a dry run against an AWS contract (the credentials were test values, and the plan itself then failed against AWS, which is why no `tofu plan` summary follows):

```text
OpenTofu engine — provider: aws
  module:      .fluid/iac/aws/analytics_web_pageviews/main.tf.json
  state:       local
  credentials: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION
```

Two things differ between the engines, and the rest of this page says which one a statement is about:

- **Modes.** `--mode dry-run` stops after `tofu plan` on the OpenTofu engine. Beyond that the OpenTofu engine does not branch on `--mode`: `amend`, `create-only` and `replace` run the same `tofu apply` of the emitted module. What stays mode-specific is the [data-loss gate](#safety-gates) and the build phase of the `*-and-build` modes.
- **Options.** Some options are read only by the native engine. They are marked in the [options tables](#options).

*([forge-cli #714](https://github.com/Agenticstiger/forge-cli/pull/714), since 0.20.0)* The contract check does not differ: both engines validate the contract before they plan, in every mode. See [Contract validation](#contract-validation).

## Apply mode

| `--mode` | What it does |
| --- | --- |
| `dry-run` | Render the plan without applying it. Nothing is changed. |
| `create-only` | Intended to provision only what does not exist yet. What each engine does with it is below. |
| `amend` *(default)* | The everyday mode, with no mode gate of its own. |
| `amend-and-build` | Same as `amend`, then run the contract's `builds[]` (the build runner). |
| `replace` | Destructive. Requires `--allow-data-loss`. |
| `replace-and-build` | Same as `replace`, then the builds with a full refresh. Destructive. |
| `reconcile` | *(since 0.34.0, [forge-cli #1013](https://github.com/Agenticstiger/forge-cli/pull/1013))* Deploys nothing: keeps the contract's always-on Spark streams running. See [Reconcile mode](#reconcile-mode). |

What each engine does with the mode:

- **OpenTofu engine.** `dry-run` plans only. `create-only`, `amend` and `replace` run the same `tofu apply`. The `replace` modes are gated by `--allow-data-loss`, and the `*-and-build` modes run the builds after `tofu apply` succeeds. In every mode, a plan that destroys a resource is refused without `--allow-data-loss` (see [Safety gates](#safety-gates)).
- **Native engine.** The provider's planner decides what the mode means. On `local`, `replace` and `replace-and-build` pre-truncate each SQL build's output table before it runs, and every other mode appends. `create-only` on `local` did not refuse an existing target when measured on 0.18.1.

The build-augmented modes (`amend-and-build`, `replace-and-build`) run the configured build runner. Pass `--build-id <id>` to filter execution to a single build job from the contract's `builds[]`; when unset, every build runs. `--build-id` with a mode that runs no build (`amend`, `create-only`, `replace`, `dry-run`) is refused:

```text
❌ apply_build_id_requires_build_mode  [ERR_APPLY_BUILD_ID_REQUIRES_BUILD_MODE]
  build_id: x
  mode: amend
  hint: --build-id selects which build runs, and --mode amend runs no build. Pass --mode
amend-and-build (or replace-and-build) to run that build, or drop --build-id.
```

Before 0.16.3 the flag was accepted and dropped, so a DDL-only apply exited 0. *(since 0.34.0, [forge-cli #1013](https://github.com/Agenticstiger/forge-cli/pull/1013))* `--build-id` is accepted with `--mode reconcile` too, where it names the stream to keep running, and the hint of this refusal adds `--mode reconcile to keep that stream running`.

*(since 0.34.0, [forge-cli #1009](https://github.com/Agenticstiger/forge-cli/pull/1009))* A dbt or Python build runs once under `--mode amend-and-build` whatever its `execution.trigger.type`, `manual` and `continuous` aside: see [What the DAG does](../advanced/airflow.md#what-the-dag-does). Which dbt a dbt build runs on, and what the container fallback installs, are in [Which dbt `fluid apply` runs](./generate.md#which-dbt-fluid-apply-runs).

*(since 0.30.0, [forge-cli #861](https://github.com/Agenticstiger/forge-cli/pull/861))* On Databricks, a dbt build with `execution.runtime.platform: databricks` runs as the job the apply provisions. The build phase starts a run of the job and waits for it to end, and a failed run fails the apply. See [Running the job from `fluid apply`](../providers/databricks.md#running-the-job-from-fluid-apply).

*(since 0.30.0, [forge-cli #872](https://github.com/Agenticstiger/forge-cli/pull/872))* A build with `engine: lakeflow` runs as the Lakeflow pipeline the apply provisions. The build phase starts an update of the pipeline and waits for it to end, and a failed update fails the apply. A continuous pipeline is not started: only its table's tags are set. See [Running it from `fluid apply`](../providers/databricks.md#running-it-from-fluid-apply).

### Reconcile mode

*(since 0.34.0, [forge-cli #1013](https://github.com/Agenticstiger/forge-cli/pull/1013))* `--mode reconcile` keeps the contract's always-on Spark streams running, and deploys nothing: it runs no `tofu`, no DDL and no build, and it takes no plan. A stream that died is started again on its checkpoint, within its [restart budget](../advanced/spark-iceberg-aws.md#the-restart-budget), when what the last `fluid apply` deployed is what the contract compiles to. A scheduler task that runs it every few minutes, a keepalive, keeps a stream going between applies:

```bash
fluid apply contract.fluid.yaml --env prod --mode reconcile --build-id ingest-orders --yes
```

- **What it reads.** The contract, which goes through the same schema gate, `--build-id` check and apply-time hooks as any apply. A `plan.json` is refused with `apply_reconcile_needs_contract`. On AWS it also reads the job config that the last apply uploaded, from S3, on every run, so a missing `s3:GetObject` shows while the stream is healthy. It reads the runs from the runtime's own history, and keeps no state of its own.
- **Which streams.** With `--build-id`, that one stream. A build that is not a forge Spark build, a batch, or a stream triggered `availableNow` is refused with `apply_reconcile_not_a_stream`: its scheduler runs it with `--mode amend-and-build --build-id <id>`. Without `--build-id`, every always-on Spark stream of the contract. A contract with none prints `No always-on Spark stream in the contract: nothing to reconcile.` and exits `0`.
- **What it never does.** It does not replace a config, and it does not stop a build the contract no longer holds: a full `fluid apply` does both. It cancels only a younger second copy of the running config.
- **`--dry-run`** reads the same state and starts nothing. On a terminal, without `--yes`, it asks before it starts or cancels a run. An empty or a closed answer is a no: it starts or cancels nothing, says so (`declined`), and exits `0`.
- **The settings of the apply** reach it too: the operator's lists (`FLUID_SPARK_TARGET_ALLOWLIST`, which also lists a dead-letter topic, `FLUID_SPARK_CONTRACT_SQL_ALLOWLIST`, `FLUID_SPARK_LOCAL_NAMESPACE_ALLOWLIST` for a `runtime: local` stream, and the host allowlists) gate every reconcile, and a refused build is an error, `apply_spark_refused`. A keepalive's environment needs the ones the CI apply has. [`FLUID_SPARK_WAIT_SECONDS`](../advanced/environment-variables.md#spark-on-aws-preview), 900 seconds by default, bounds how long it waits for a started run to leave its pending states and for a cancelled one to stop.

For each stream it finds one of these, and exits `1` when any stream is an error:

| It finds | It does | Shown as | Exit |
|---|---|---|---|
| A run of the deployed config going | Nothing. | `unchanged` | `0` |
| The last run died: it ended `FAILED` or `INTERRUPTED`, was lost with its machine, node or cluster, was stopped by a signal from outside forge, or the stream stopped by itself | Starts it again on the same checkpoint, within the budget. | `restarted` | `0`, or `1` when the new run ends at once |
| The budget is spent | Starts nothing. It names the budget, the restarts and when the next one is allowed. | `failed` | `1` |
| The last run was cancelled through the runtime, or is being stopped | Leaves it stopped. A plain `fluid apply` starts a cancelled stream again. | `left-stopped` | `0` |
| What is deployed is not the contract: the uploaded job config differs, the last run ran another config, another config is running, nothing is deployed, or no run is recorded | Starts nothing, and says to run `fluid apply`. | `refused` | `1` |
| A younger second copy of the running config | Cancels it, and keeps the older run. | `unchanged` | `0` |
| The last run ended `FAILED` on EMR Serverless or EMR on EKS | Starts nothing: the service's own retries are spent. | `failed` | `1` |
| An EMR on EC2 cluster that ended | Starts nothing, and names the cluster's state and reason. | `failed` | `1` |
| A topic or a cluster other than the one that the stream's checkpoint was written for | Starts nothing: a checkpoint holds the offsets of one topic on one cluster. See [Starting and reconciling runs](../advanced/spark-iceberg-aws.md#starting-and-reconciling-runs). | `refused` | `1` |
| An AWS error while it reads the runs or starts one | Says what failed, and what it had done before it. | `failed` | `1` |

A stream of a local build on this machine, killed from outside, then reconciled, from a real run (the paths are shortened to `<project>`):

```text
Spark ingest-orders (local): unchanged run 20261119T075039Z-181dd129 RUNNING on this machine (.fluid/commerce.orders-stream/runtime/spark/ingest-orders)
```

```text
Spark ingest-orders (local): restarted run 20261119T075054Z-157881b9 RUNNING on this machine (.fluid/commerce.orders-stream/runtime/spark/ingest-orders). run 20261119T075039Z-181dd129 ended FAILED (exit -9): log <project>/.fluid/commerce.orders-stream/runtime/spark/ingest-orders/runs/20261119T075039Z-181dd129/driver.log: stand-in spark-submit; started again on the same checkpoint (restart 1 of 5 allowed per rolling hour)
```

With the contract changed since the last apply, it starts nothing and exits `1`:

```text
Spark ingest-orders (local): refused on this machine (.fluid/commerce.orders-stream/runtime/spark/ingest-orders). the last run 20261119T075106Z-5dd7554c ran config b2daa0daab82, and the contract compiles to f79cf67ae81e. --mode reconcile changes no config: run fluid apply to start the new config
```

`--dry-run` on a stream that died:

```text
Spark ingest-orders (local): planned on this machine (.fluid/commerce.orders-stream/runtime/spark/ingest-orders). would start it again on the same checkpoint: run 20261119T075129Z-cc92dd21 ended FAILED (exit -9): log <project>/.fluid/commerce.orders-stream/runtime/spark/ingest-orders/runs/20261119T075129Z-cc92dd21/driver.log: stand-in spark-submit (restart 1 of 5 allowed per rolling hour)
```

A plan is not a contract:

```text
❌ apply_reconcile_needs_contract  [ERR_APPLY_RECONCILE_NEEDS_CONTRACT]
  path: <project>/plan.json
  hint: --mode reconcile applies no plan: it reads the contract, what the last fluid apply deployed and how the runs are doing. Pass the contract (contract.fluid.yaml).
```

These outputs are from the real `fluid apply` on `main`, on a stream of `runtime: local` with a stand-in `spark-submit` that sleeps, killed with `kill -9`: no Spark, no cloud and no AWS call. The runs on AWS go through the same code with the runtime's own history: [the restart budget](../advanced/spark-iceberg-aws.md#the-restart-budget) shows them with AWS answered by botocore's test stubs.

## Contract validation

*([forge-cli #714](https://github.com/Agenticstiger/forge-cli/pull/714), since 0.20.0)* `fluid apply` checks the contract against its schema before it plans anything, on both engines and in every mode, `--dry-run` and the build modes included. A GCP contract that still carries the deprecated `metadata.policies` mapping stops before `tofu` runs:

```bash
fluid apply contract.fluid.yaml --dry-run --yes
```

```text
❌ apply_contract_invalid  [ERR_APPLY_CONTRACT_INVALID]
  command: apply
  error_count: 1
  errors: ["metadata: Additional properties are not allowed ('policies' was unexpected)"]
  message: Contract validation failed with 1 error(s); ``fluid apply`` will not proceed on a schema-invalid contract. Run ``fluid validate`` for the full report.
```

It is the check `fluid validate` and `fluid plan` run: a `fluidVersion` below 0.7 is refused, then the contract is validated against the schema its `fluidVersion` names.

| The input | Event | Exit |
|---|---|---|
| A contract whose `fluidVersion` is below 0.7 | `contract_version_unsupported` | 1 |
| A contract that is not valid against its schema | `apply_contract_invalid` | 1 |
| A `plan.json` that embeds no contract | `apply_plan_missing_contract` | 1 |

Before this change only the native engine ran the check, and not in the build modes. On the OpenTofu engine (`aws`, `gcp`, `snowflake`, `confluent` and IaC plugin clouds), and under `--mode amend-and-build` or `replace-and-build` on either engine, a contract `fluid validate` rejects reached `tofu` or the build runner and could apply with exit 0.

What is checked:

- **A contract file or a bundle.** The contract with its `--env` overlay, as `fluid validate <contract> --env <env>` sees it: `{{ env.* }}` placeholders are still literal.
- **A `plan.json`.** The contract embedded in the plan, the copy its `planDigest` covers. Every plan `fluid plan` writes embeds it (see [What `plan.json` records](./plan.md#what-plan-json-records)).

A plan whose `contract` is missing, empty or not an object is refused, with or without `--no-verify-plan-binding`. There is nothing to check, and the `planDigest` is an unkeyed hash: it proves the file has not changed since it was written, not who wrote it. Before this change such a plan fell back to the native engine and ran its actions unchecked.

```text
❌ apply_plan_missing_contract  [ERR_APPLY_PLAN_MISSING_CONTRACT]
  path: .../runtime/plan.json
  hint: plan.json embeds no contract, so there is nothing to validate before applying it. Re-run ``fluid plan <contract> --out <plan>.json`` with a current forge-cli.
```

The check runs after the [plan binding](#plan-binding) checks and the [mode gate](#the-mode-gate), and before the [apply hooks](#extension-point-apply-hooks), `tofu`, the native provider and any build, so a hook never sees a refused contract. `fluid apply` reads its input once, and the engine choice, the hooks, `tofu`, the build runner and the native provider all take that copy: the contract that is applied is the contract that was checked, even if the file changes while the apply runs.

There is no flag to skip the check. Run `fluid validate <contract> --env <env>` to see every error, fix them, and apply again.

### Build ids

*(since 0.27.0, [forge-cli #803](https://github.com/Agenticstiger/forge-cli/pull/803))* Under `--mode amend-and-build` or `replace-and-build`, `fluid apply` also checks `id` and every `builds[].id` right after the schema check. This happens on both engines, before the apply hooks, `tofu` and any build.

The build phase keeps each build's run records, cursors and watermarks under `.fluid/runs/<id>/<build id>/`, so its rule is narrower than the schema's. An id must start with a letter or `_`, use only letters, digits, `_`, `.` and `-`, and be at most 128 characters. The schema also accepts a leading digit and any length. So `fluid validate` and `fluid plan` pass an id such as `1orders`, though from 0.27.0 both [warn about it](./validate.md#an-id-the-build-phase-refuses) ([forge-cli #813](https://github.com/Agenticstiger/forge-cli/pull/813)), and `fluid apply` refuses it:

```bash
fluid apply contract.fluid.yaml --mode amend-and-build --yes
```

```text
❌ apply_build_identifier_invalid  [ERR_APPLY_BUILD_IDENTIFIER_INVALID]
  field: contract.id
  value: '1orders'
  hint: The build phase keeps each build's run records, cursors and watermarks under .fluid/runs/<contract.id>/<build.id>/, so both ids must start with a letter or underscore, use only letters, digits, '_', '.' and '-', and be at most 128 characters. The contract schema allows more, so fluid validate and fluid plan only warn about it. Nothing was applied.

💡 Suggestions:
  • Rename the id to fit, for example orders_v1 instead of 1orders, and apply again
  • A renamed id starts over: its builds get new cursors and watermarks under .fluid/runs/, and a renamed contract.id gets a new OpenTofu workdir under .fluid/iac/<provider>/
```

Before this change only the build runner checked these ids. On the OpenTofu engine the runner starts after `tofu apply`, so the product was provisioned first, and the run then stopped with "Unexpected error". A mode without a build phase is not checked, and neither is a contract without `builds`.

*(since 0.27.0, [forge-cli #808](https://github.com/Agenticstiger/forge-cli/pull/808))* Right after that check, `fluid apply` makes sure a `--build-id` names one of the contract's builds. Ids match exactly, case and spaces included, as they do in the build runner. A `--build-id` that matches no `builds[].id` is refused on both engines, before the apply hooks, `tofu` and any build, and the refusal lists the ids the contract has:

```bash
fluid apply contract.fluid.yaml --mode amend-and-build --build-id make_row --yes
```

```text
❌ apply_build_id_not_found  [ERR_APPLY_BUILD_ID_NOT_FOUND]
  build_id: 'make_row'
  available: ['make_rows']
  hint: --build-id selects the build whose id equals it exactly, case and spaces included, and no build of the contract has that id. Pass one of the available ids, or drop --build-id to run every build. Nothing was applied.

💡 Suggestions:
  • Pass one of the available build ids as --build-id: ids match exactly, case included
  • Run 'fluid apply <contract> --mode amend-and-build' without --build-id to run every build
```

Before this change the build runner was the only check. On the OpenTofu engine it starts after `tofu apply`, so a mistyped `--build-id` provisioned the product, and the run then stopped with `Build not found` and exit 1. An empty `--build-id` still runs every build, and a contract without `builds` is still not checked.

## Plan binding

When you pass a saved plan (`runtime/plan.json`) instead of a contract, `apply` runs three gates on it before it builds or provisions anything, on both engines:

| Gate | Refusal | What it compares |
| --- | --- | --- |
| Digests | `apply_plan_digest_plan_tamper` | `planDigest` in `plan.json` against a re-computed digest of the plan body. |
| | `apply_plan_digest_bundle_mismatch` | `bundleDigest` in `plan.json` against the MANIFEST SHA-256 of the tgz bundle the plan was built from. *(since 0.33.0, [forge-cli #972](https://github.com/Agenticstiger/forge-cli/pull/972))* It also names the dbt files that differ between the checkout and the bundle's copy; see [The dbt project](#the-dbt-project). |
| | `apply_plan_digest_packet_mismatch` | *(since 0.33.0, [forge-cli #985](https://github.com/Agenticstiger/forge-cli/pull/985))* `packetDigest` in `plan.json` against the sha256 of the bundle file: the same contract in other bytes (rebuilt with another `--env`, or another `SOURCE_DATE_EPOCH`). |
| | `apply_plan_digest_packet_missing` | *(since 0.33.0, [forge-cli #985](https://github.com/Agenticstiger/forge-cli/pull/985))* A plan bound to a bundle that records no `packetDigest`, because `fluid plan` 0.32.0 or earlier made it. Run `fluid plan` on the bundle again. |
| | `apply_plan_digest_bundle_missing` | A plan that carries a `bundleDigest` but has no locatable bundle. It fails closed instead of skipping the check. |
| Mode | `apply_plan_mode_mismatch` | The `mode` recorded in `plan.json` against `--mode`. A plan made without `--mode` and `amend` count as the same. |
| Saved OpenTofu plan | `apply_plan_digest_tofu_plan_invalid`, `_missing`, `_mismatch`, `_target`, `_stale` | *(since 0.31.0, [forge-cli #898](https://github.com/Agenticstiger/forge-cli/pull/898))* The `opentofuPlan` record of a plan made with `fluid plan --tofu`. *(since 0.33.0, [forge-cli #999](https://github.com/Agenticstiger/forge-cli/pull/999))* It also covers `_target_mismatch`, `_target_unverified`, `_target_missing`, `_toolchain`, `_lock_missing`, `_lock_mismatch` and `_state_missing`. See [Applying a saved OpenTofu plan](#applying-a-saved-opentofu-plan). |
| Environment | `plan_env_mismatch` | The `contract_metadata.env` recorded in `plan.json` against `--env`. Checked for the build modes (`amend-and-build`, `replace-and-build`). |

This is the Terraform-style "apply consumes exact plan" guarantee, enforced cryptographically. A tampered plan stops here:

```text
❌ apply_plan_digest_plan_tamper  [ERR_APPLY_PLAN_DIGEST_PLAN_TAMPER]
  kind: plan-tamper
  error: plan.json has been modified since it was generated: stored planDigest='sha256:c9b3...', recomputed='sha256:666e...'. Re-run ``fluid plan`` to produce a fresh binding, ...
```

Pass the bundle with `--bundle <path-to.tgz>`: the tgz this `plan.json` was generated against. When omitted, `apply` auto-discovers a single sibling `.tgz` / `.tar.gz` next to the `plan.json`. If several are present it logs a warning and leaves the bundle unresolved, so pass `--bundle` to disambiguate. A `plan.json` made from a raw contract has an empty `bundleDigest`, so only `planDigest` is verified; see [`fluid plan`](./plan.md#plan-binding).

### The packet

*(since 0.33.0, [forge-cli #985](https://github.com/Agenticstiger/forge-cli/pull/985))*
`fluid plan <bundle>` records `packetDigest` in `plan.json`: the sha256 of the bundle file, not the merkle digest in `bundleDigest`. It is part of the plan body, so editing it is a `plan-tamper`. `fluid apply` hashes the bundle file it is given and refuses other bytes. A bundle rebuilt from the same checkout with another `SOURCE_DATE_EPOCH` still has the `bundleDigest` the plan holds, and the packet check is what refuses it:

```console
$ SOURCE_DATE_EPOCH=1700000000 fluid bundle contract.fluid.yaml --format tgz --out runtime/epoch.tgz
...
$ fluid apply runtime/plan.json --bundle runtime/epoch.tgz --dry-run --yes
Loading pre-generated execution plan
CLI command error
❌ apply_plan_digest_packet_mismatch  [ERR_APPLY_PLAN_DIGEST_PACKET_MISMATCH]
  kind: packet-mismatch
  error: plan.json was made from the packet sha256:b92783ba770db2b65e7934cb7a56330c7760fb2fb203afe877bf9026c491543f but /work/orders/runtime/epoch.tgz is sha256:5f27836b44eb2046e8d4ceb7142d0beb841e4df4ac6c7e6c6dbbe42c45a55055. It holds the same contract (bundleDigest matches) in other bytes, e.g. rebuilt with another --env or SOURCE_DATE_EPOCH. Apply the packet the plan was made from, or re-run ``fluid plan`` on this one.
```

Apply the bundle the plan was made from, or run `fluid plan` on the one you mean to apply. A plan made by `fluid plan` 0.32.0 or earlier carries no `packetDigest` and is refused with `apply_plan_digest_packet_missing`. A plan edited by hand, `packetDigest` included, is refused as `plan-tamper`. A plan made from a contract file has no bundle, so it has no packet check. See [The packet digest](./bundle.md#the-packet-digest).

### The dbt project

*(since 0.33.0, [forge-cli #972](https://github.com/Agenticstiger/forge-cli/pull/972))*
A dbt build reads its models from the checkout when it runs, so a model edited after `fluid plan` would run unreviewed. A bundle now packs the dbt project of each dbt build (see [The dbt project of a dbt build](./bundle.md#the-dbt-project-of-a-dbt-build)), `fluid plan <bundle>` lists each project's files in `plan.json` as `dbtProjects`, and the checks run in this order:

1. Before anything runs, `fluid apply` refuses a dbt build the bundle packs no project for, with `apply_plan_digest_bundle_mismatch`. A bundle made by 0.32.0 or earlier packs none, so a contract with a dbt build needs `fluid bundle` and `fluid plan` run again.
2. Then it reads each project the way the dbt runner will and compares it with the bundle's copy. A changed, added or removed file fails with the same error, and the message names the files.
3. The dbt runner compares the directory again, just before dbt starts, and refuses with the same event if a file changed while the apply was provisioning.

```console
$ fluid apply runtime/plan.json --dry-run --yes
...
❌ apply_plan_digest_bundle_mismatch  [ERR_APPLY_PLAN_DIGEST_BUNDLE_MISMATCH]
  kind: bundle-mismatch
  error: the dbt project of build 'transform' at /work/orders/dbt differs from the copy /work/orders/runtime/bundle.tgz packs: changed models/orders.sql; added models/extra.sql. Re-run ``fluid bundle`` and ``fluid plan`` to bind the files as they are now, or restore them.
```

`--dry-run` does not skip the check. `fluid apply <bundle.tgz>`, without a plan, runs the same comparison. In 0.32.0 and earlier none of this ran, and a changed model applied as it was in the checkout.

What the check does not cover:

- `--no-verify-plan-binding` skips it and logs a `WARNING`, as it skips the digests.
- Installed packages are not bound. dbt reads whatever `packages-install-path` holds, and `fluid apply` neither installs nor checks it. Run `dbt deps` from `package-lock.yml` in the job that applies.
- A plan made from a contract file binds no dbt project. A build whose `repository` is a Git URL is not packed, because its ref pins it.
- Plan and apply must run in the same checkout path. The plan records the absolute path of the source contract, and `fluid apply` compares the project at that path, whatever checkout you run it from. If the path is gone, it refuses with the same event and says the checkout cannot be found. *(since 0.33.0, [forge-cli #985](https://github.com/Agenticstiger/forge-cli/pull/985))* A bundle copied without its [provenance file](./bundle.md#the-provenance-file) is refused the same way.

*([forge-cli #714](https://github.com/Agenticstiger/forge-cli/pull/714), since 0.20.0)* After these gates the contract the plan embeds is validated against its schema, and a plan that embeds none is refused with `apply_plan_missing_contract`. See [Contract validation](#contract-validation).

### The plan's mode

`fluid plan --mode X` records `X` in `plan.json`. `fluid apply plan.json --mode Y` with a different `Y` is refused with `apply_plan_mode_mismatch` and exit 1, before any build runs. This is why every non-default example above plans with the same `--mode`. See [`fluid plan --mode`](./plan.md#key-options).

### The plan's environment

`fluid plan --env X` records `contract_metadata.env: X` in `plan.json`. What `apply` does with it:

- **Build modes.** Without `--env`, the builds run in `X`. A different `--env` is refused before any build:

  ```text
  ❌ plan_env_mismatch  [ERR_PLAN_ENV_MISMATCH]
    plan: ./runtime/plan-dev.json
    plan_env: dev
    requested_env: prod
    hint: the plan was made with --env dev and carries that overlay; apply it with --env dev (or without --env), or re-plan with --env prod.
  ```

- **Other modes.** As of 0.18.1 the check does not run: `fluid apply plan.json --env prod` on a plan made with `--env dev` and no build mode applied without error when measured. The plan's own contract, with its `dev` overlay, is what runs, so pass the `--env` the plan was made with.

When the plan records no env but was made from a bundle, the bundle's own env is used. A bundle is never re-overlaid, so an `--env` that disagrees with the env a bundle was built for is refused with `bundle_env_mismatch`, at `plan` and `apply` alike:

```text
❌ bundle_env_mismatch  [ERR_BUNDLE_ENV_MISMATCH]
  bundle: ./runtime/dev.tgz
  bundle_env: dev
  requested_env: prod
  hint: the bundle was built for env 'dev' but this stage was asked for env 'prod'. A bundle is never re-overlaid; rebuild it with `fluid bundle <contract> --env prod --format tgz`, or pass the env it was built for.
```

Relative local paths in a contract (`binding.location.path` on the `local` provider, for example) resolve against the directory of the source contract, not the directory you run `fluid` from. For a plan or a bundle, that is the source contract the plan or bundle was made from.

### Applying a saved OpenTofu plan

*(since 0.31.0, [forge-cli #898](https://github.com/Agenticstiger/forge-cli/pull/898))* A `plan.json` made with [`fluid plan --tofu`](./plan.md#saving-the-opentofu-plan-tofu) binds a saved OpenTofu plan, `plan.tfplan`, in its `opentofuPlan` record. `fluid apply plan.json` then runs exactly that plan. It does not plan again:

1. It reads `plan.tfplan` from the directory of `plan.json`, once, and checks its sha256 against the record. The bytes that matched are the bytes applied.
2. Before `tofu init`, it refuses a plan made for another provider or another state than this apply resolves.
3. It writes the verified bytes to the work directory.
4. Before any step that acts outside OpenTofu (a Databricks `prepare_destroys` drop, say), it compares the state lineage and serial the plan recorded with the state now, and refuses a stale plan.
5. The [data-loss gate](#opentofu-data-loss-gate) reads the saved plan. `--allow-data-loss` on this apply decides, as for any apply.
6. It runs `tofu apply` of the saved plan, with no plan of its own. It never resumes destroys that the gate blocked, because that would need a second plan nobody reviewed.

OpenTofu's own check stays as the backstop: it refuses a saved plan whose state serial moved ("Saved plan is stale") or whose lineage differs. A `plan.json` with no `opentofuPlan` record takes the earlier path, which plans and applies in one step. `--dry-run` applies nothing from a saved plan.

*(since 0.33.0, [forge-cli #999](https://github.com/Agenticstiger/forge-cli/pull/999))* The apply also checks the plan's target and carries its provider lock:

- **The lock.** When the plan has a lock (`lockFile`), the apply reads `<stem>.terraform.lock.hcl` from the directory of `plan.json`, checks its sha256 against `lockSha256`, and writes it to the work directory before `tofu init`. This runner then installs the providers the plan was reviewed with, not a newer release.
- **The target.** After `tofu init`, and before the state-key migration, any hook or `tofu apply`, it reads the target again and compares it with the plan's [`target`](./plan.md#the-target-a-plan-is-bound-to). It refuses, in this order: another `tofu` or provider version, another state backend configuration, another target (account, project, region or host), and a recorded field this run cannot read. A field the plan's runner could not read is not compared. The apply prints it again, for example `target account not bound by the plan, not compared: boto3 is not installed (pip install 'data-product-forge[aws]')`, and does the same for a field that only this run can read. `--dry-run` makes the same check.

*(since 0.33.0, [forge-cli #1002](https://github.com/Agenticstiger/forge-cli/pull/1002))* Each such field is also logged at WARNING (not under `--no-verify-plan-binding`) as `apply_tofu_plan_target_field_unbound`, with the `provider`, the `field` and the `reason`, for CI logs and audit trails. A plan for a provider that forge reads no target for, such as `confluent`, prints `target: forge reads no account, project or host for <provider>, so the saved plan is not bound to one` and logs `apply_tofu_plan_target_provider_unbound`, because nothing then stops it being applied to another account, project or host.

| Error | Meaning | What to do |
| --- | --- | --- |
| `apply_plan_digest_tofu_plan_invalid` | The `opentofuPlan` record is malformed: no `sha256:` digest, or a `planFile` (or, since 0.33.0, a `lockFile`) that is not a bare file name | Re-run `fluid plan --tofu` |
| `apply_plan_digest_tofu_plan_missing` | `plan.tfplan` is not next to `plan.json` | Keep the plan's files together: in CI, pass every file `fluid plan --tofu` wrote as artifacts |
| `apply_plan_digest_tofu_plan_mismatch` | The saved plan's sha256 differs from the bound one: it is not the plan that was reviewed | Re-run `fluid plan --tofu` and approve the new plan |
| `apply_plan_digest_tofu_plan_target` | The plan was made for another provider or state. *(since 0.33.0, [forge-cli #999](https://github.com/Agenticstiger/forge-cli/pull/999))* Also for another state backend configuration | Apply with the `--state-backend` (or `FLUID_STATE_BACKEND`) and the work directory the plan was made with, or re-run `fluid plan --tofu` |
| `apply_plan_digest_tofu_plan_stale` | The state changed after the plan was made, for example another apply ran in between. Nothing was applied | Re-run `fluid plan --tofu`, review the new plan, apply that one |
| `apply_plan_digest_tofu_plan_target_mismatch` | *(since 0.33.0, [forge-cli #999](https://github.com/Agenticstiger/forge-cli/pull/999))* The target the plan was made for is not the one this apply reaches. The message names both, as `aws account 111111111111, region eu-west-1` against the other, and lists the fields that differ. Nothing was applied | Apply with the credentials and region the plan was made for, or re-run `fluid plan --tofu` for this target and review that plan |
| `apply_plan_digest_tofu_plan_target_unverified` | *(since 0.33.0, [forge-cli #999](https://github.com/Agenticstiger/forge-cli/pull/999))* The plan is bound to a field this run cannot read, such as the AWS account without `boto3` or credentials. The message gives the reason | Give this run what the plan's runner had (credentials, the SDK the message names), or pass `--no-verify-plan-binding` for an emergency apply |
| `apply_plan_digest_tofu_plan_target_missing` | *(since 0.33.0, [forge-cli #999](https://github.com/Agenticstiger/forge-cli/pull/999))* The plan records no target, or an identity that is not an object. A plan made by `fluid plan --tofu` 0.32.0 or earlier records none | Re-run `fluid plan --tofu` and apply that plan |
| `apply_plan_digest_tofu_plan_toolchain` | *(since 0.33.0, [forge-cli #999](https://github.com/Agenticstiger/forge-cli/pull/999))* Another `tofu` or provider version than the plan's. The message lists each, as `tofu 1.13.1 -> 1.13.2` | Apply with the versions the plan was made with (its lock and `tofu`), or re-run `fluid plan --tofu` here |
| `apply_plan_digest_tofu_plan_lock_missing` | *(since 0.33.0, [forge-cli #999](https://github.com/Agenticstiger/forge-cli/pull/999))* The plan's `<stem>.terraform.lock.hcl` is not next to `plan.json` | Hand it over with `plan.json` and the saved plan, or re-run `fluid plan --tofu` |
| `apply_plan_digest_tofu_plan_lock_mismatch` | *(since 0.33.0, [forge-cli #999](https://github.com/Agenticstiger/forge-cli/pull/999))* The lock's sha256 is not the `lockSha256` the plan binds | Hand over the lock written with the plan, or re-run `fluid plan --tofu` |
| `apply_plan_digest_tofu_plan_state_missing` | *(since 0.33.0, [forge-cli #999](https://github.com/Agenticstiger/forge-cli/pull/999))* The plan was made against existing state, and this run finds none there. Local state stays in the workspace that holds it. Nothing was applied | Apply in the workspace the plan was made in, or keep state in a backend both runners reach (`--state-backend s3://...` or `gcs://...`). With a remote backend, check its credentials and key |
| `apply_tofu_plan_unreadable` | `tofu show -json` could not read the saved plan | Apply where the plan was made: the plan needs the OpenTofu version and providers it was made with. A plan made with `FLUID_STATE_ENCRYPTION` set is read only with the same setting, and one made without it only without it |

Each of the first five carries a stable `kind` tag in the error (`tofu-plan-invalid`, `tofu-plan-missing`, `tofu-plan-mismatch`, `tofu-plan-target`, `tofu-plan-stale`), and the event is the code. `--no-verify-plan-binding` skips the digest comparison and logs at WARNING, but the saved plan still has to be there: without it there is nothing reviewed to run. *(since 0.33.0, [forge-cli #999](https://github.com/Agenticstiger/forge-cli/pull/999))* It also skips the comparison of the plan's target, which it logs at WARNING as `apply_tofu_plan_target_unverified_by_flag`, and the comparison of the lock's digest. It does not skip the lock file: without it there is no reviewed provider set to install. The new codes carry the kinds `tofu-plan-target-mismatch`, `tofu-plan-target-unverified`, `tofu-plan-target-missing`, `tofu-plan-toolchain`, `tofu-plan-lock-missing`, `tofu-plan-lock-mismatch` and `tofu-plan-state-missing`.

## Safety gates

| Option | Description |
| --- | --- |
| `--allow-data-loss` | Required to run `replace` / `replace-and-build`, and to apply an OpenTofu plan that destroys data-bearing resources. |
| `--no-verify-plan-binding` | **Emergency escape hatch.** Skip the `bundleDigest` / `planDigest` verification that stage 7 normally enforces on a saved plan. Logged at `WARNING` so audit trails catch it. *(since 0.33.0, [forge-cli #972](https://github.com/Agenticstiger/forge-cli/pull/972), [#985](https://github.com/Agenticstiger/forge-cli/pull/985))* It also skips the packet check and the check of the bundle's [dbt projects](#the-dbt-project). Use only during documented DR procedures. *(since 0.33.0, [forge-cli #999](https://github.com/Agenticstiger/forge-cli/pull/999))* For a saved OpenTofu plan it also skips the comparison of the plan's target and the lock's digest. |
| `--no-verify-federation` | Skip the federated-`consumes[]` upstream-digest check. Logged at `WARNING`. Unlike plan binding, this check only warns (`apply_consumes_drift`, exit code unchanged), so the flag silences a warning and does not remove a refusal. The digest a downstream product pins comes from [`fluid contract digest`](./contract.md#fluid-contract-digest), which covers only the upstream's root file for a fragment-layout product. `upstreamWorkspace` and `upstreamDigest` exist only in schema 0.7.6; see [preview fields](../reference/preview-fields.md#federated-upstreams). See [Federated upstream check](#federated-upstream-check), [Federated upstreams](../concepts/federation.md) and [Consume one contract from another](../recipes/consumes-contract-to-contract.md). |
| `--adopt-shared-container` | *(since 0.13.0)* Confirm taking **ownership** of a container this contract previously referenced as a shared pool (`packaging` `shared` → `isolated`). Emits a structured `packaging_adoption_override` audit event; the data-loss gate still applies. See [Packaging modes](#packaging-modes). |

Since `0.13.1`, the structured override events these gates emit — `opentofu_destructive_gate_override` (`--allow-data-loss`) and `packaging_adoption_override` (`--adopt-shared-container`) — log at `WARNING`, so audit pipelines filtering at WARNING-and-above catch them. On `0.13.0` and earlier they logged at `INFO`; event names and payloads are unchanged.

### The mode gate

`replace` and `replace-and-build` are refused unless `--allow-data-loss` is set:

```text
❌ apply_mode_data_loss_blocked  [ERR_APPLY_MODE_DATA_LOSS_BLOCKED]
  mode: replace
  env: dev
  reason: --mode replace is destructive (env='dev'; target row count unknown (treating as populated)). Pass --allow-data-loss to confirm the drop. ...
```

As of 0.18.1 the gate never learns a row count, so it treats every target as populated and the flag is needed in every environment, `--env dev` included. It does not read `FLUID_ENV`. The refusal comes before any build or DDL, on both engines.

On the native engine the message promises a pre-replace snapshot that `fluid rollback` can restore. On the OpenTofu engine the message says instead that no snapshot is taken, because `tofu` has no copy-the-table step: back the target up yourself before you proceed, since [`fluid rollback`](./rollback.md) has no restore point there.

### OpenTofu data-loss gate

A second gate runs on the OpenTofu engine, after `tofu plan`, in every mode including `amend`. It refuses a plan that destroys a resource unless `--allow-data-loss` is set:

```text
❌ opentofu_data_loss_gate  [ERR_OPENTOFU_DATA_LOSS_GATE]
  error: plan destroys <n> resource(s); `tofu` does not snapshot data — re-run with --allow-data-loss to proceed
```

Removing a resource that only grants access is a revocation, not a loss, and passes without the flag. Since 0.17.0 these resource types are exempt, and `apply` lists them (`<n> access grant(s) or policy tag(s) removed (access revoked, no data lost; not gated)`):

- `google_bigquery_dataset_iam_member`, `google_bigquery_table_iam_member`, `google_storage_bucket_iam_member`
- `google_data_catalog_policy_tag_iam_member`, `google_data_catalog_policy_tag`, `google_data_catalog_taxonomy`
- `aws_lakeformation_permissions`

A Cloud KMS key's IAM grant is not exempt: without it BigQuery cannot decrypt the table. Any removal of a type not in the list counts, so removing a bucket's lifecycle or server-side-encryption configuration, or a product's KMS key, needs `--allow-data-loss` even though no object is deleted. See [AWS](../providers/aws.md). If the plan's per-resource events do not account for every removal in its summary (an older `tofu`, a truncated stream), the gate counts every removal.

*(since 0.34.0, [forge-cli #1007](https://github.com/Agenticstiger/forge-cli/pull/1007))* On AWS the list is by type and, for what a forge Spark build ran with, by the end of the resource's name too. Its artifacts, role, log group and the key that encrypts the log groups, jobs and the product's own EMR Serverless application hold no data, so removing a Spark build is not a data loss. `apply` lists them (`<n> resource(s) a removed build ran with (its artifacts, role, log group and job; no table data lost; not gated; its logs go with them)`) and passes without the flag. An output table, a bucket and a bucket's own key still count, and so does a stream's dead-letter table (`sink: table`), which goes with the build: removing that build needs the flag. See [When a build leaves the contract](../advanced/spark-iceberg-aws.md#when-a-build-leaves-the-contract).

Some governance changes cannot be made to a live BigQuery table in place and plan its replacement, which this gate refuses without the flag: adding retention (`expire: true`) to a table that exists, adding or changing its Cloud KMS key, and removing `expire`. Roll these out as: plan, review the replacement, apply with `--allow-data-loss`, then run the build again to land the data. See [GCP](../providers/gcp.md).

*(since 0.27.0, [forge-cli #793](https://github.com/Agenticstiger/forge-cli/pull/793))* The gate also holds a plan that destroys nothing but changes existing data in place. On AWS, a Glue table whose column types change plans as a plain update, yet the Parquet files written under the old type may stop reading until they are rewritten. `fluid apply`, its `--dry-run` included, refuses until `--allow-data-loss` is set, and names each table and each `column: old -> new`:

```text
❌ opentofu_data_loss_gate  [ERR_OPENTOFU_DATA_LOSS_GATE]
  error: plan changes existing data in place (Glue table <database>.<table>: column types change in place (<column>: string -> smallint); files written under the old type may stop reading until they are rewritten, and reverting the column type restores reads); `tofu` does not snapshot data — re-run with --allow-data-loss to proceed
```

Reverting the column type in the contract restores reads. A difference in spacing alone, such as `decimal(10, 2)` and `decimal(10,2)`, is no change and never trips the gate. When an AWS plan has in-place updates and its change list cannot be read back, the gate fails closed and needs the flag as well. Why a table gets new column types after an upgrade is in [AWS column types](../providers/aws.md#column-types).

### Region-move guard

Before it plans, an OpenTofu apply reads the regions recorded in the contract's existing state. If they differ from the region the contract's bindings pin, it stops:

```text
❌ opentofu_region_moved  [ERR_OPENTOFU_REGION_MOVED]
  error: state holds this contract's resources in <old-region>, but its bindings name <new-region>. Applying would create them again in <new-region> and leave the originals unmanaged
  state: .fluid/iac/aws/<safe-id>
```

Without the guard `tofu` would find nothing in the new region, create the resources again there and leave the originals behind with no destroy planned, so the data-loss gate could not fire. To keep the resources, set `location.region` back to the old region. To move them, run `tofu destroy` in the state directory with `AWS_REGION=<old-region>` set, then apply again.

### Iceberg catalog-move guard

*([forge-cli #707](https://github.com/Agenticstiger/forge-cli/pull/707), since 0.20.0)* An AWS Iceberg expose whose `location.catalog` names a catalog other than Glue no longer gets a Glue database and table. When the contract's state still holds the ones an earlier release created, an OpenTofu apply stops before it plans, because the plan would destroy them, and destroying a Glue database deletes every table in it:

```text
❌ iceberg_catalog_move_blocked  [ERR_ICEBERG_CATALOG_MOVE_BLOCKED]
  kind: iceberg-catalog-move
  error: iceberg catalog move blocked — this contract's OpenTofu state holds 2 Glue catalog resource(s) for Iceberg table(s) that now live in another catalog:

  exposes[orders]: location.catalog lakekeeper

  aws_glue_catalog_database.bronze_orders_stream_streaming
  aws_glue_catalog_table.bronze_orders_stream_streaming_orders
...
```

The message lists the addresses and a `tofu -chdir=.fluid/iac/aws/<safe-id> state rm <address>` command for each. Run them, which changes nothing in AWS, then apply again. No flag skips the guard. The steps, and what to delete by hand afterwards, are in [Upgrading an AWS contract that names another catalog](../advanced/source-aligned-acquisition.md#upgrading-an-aws-contract-that-names-another-catalog). *([forge-cli #709](https://github.com/Agenticstiger/forge-cli/pull/709), since 0.20.0)* The expose's resources are flagged when its own Glue table is in state, so a Glue database that a since-removed expose created is left to the [data-loss gate](#opentofu-data-loss-gate) instead of blocking the apply. An expose that names a `location.database` and no `location.table` has no Glue table: an earlier release created only its Glue database, so that database is flagged when state holds it and the module no longer declares it.

*([forge-cli #709](https://github.com/Agenticstiger/forge-cli/pull/709), since 0.20.0)* The guard covers Snowflake too. 0.19.0 and earlier created a Snowflake EXTERNAL VOLUME for a `platform: snowflake` Iceberg expose whose `location.catalog` is `lakekeeper` or `bigquery`, or is spelled `iceberg-rest` (and for `hive`, `jdbc`, `hadoop` and `dynamodb`, which `fluid validate` now refuses). The module no longer creates one for those catalogs, so when state still holds the volume, the apply stops instead of dropping it:

```text
❌ iceberg_catalog_move_blocked  [ERR_ICEBERG_CATALOG_MOVE_BLOCKED]
  kind: iceberg-catalog-move
  error: iceberg catalog move blocked — this contract's OpenTofu state holds 1 Snowflake EXTERNAL VOLUME(s) that this contract's configuration no longer declares:

  snowflake_external_volume.sales_orders_lake_vol_FLUID_SALES_ORDERS_LAKE_VOL

The volume is named for the contract, not for an expose, so the state does not say which expose it was created for. Possible causes: this contract was applied by a forge-cli release that gave an Iceberg table in a catalog Snowflake does not manage an EXTERNAL VOLUME (this release gives it none, and dbt writes it as an externally cataloged table); or this change removed a Snowflake-managed Iceberg expose, or moved one to another catalog. ...

Iceberg exposes whose catalog earlier releases gave an EXTERNAL VOLUME:

  exposes[orders_iceberg]: location.catalog lakekeeper

Drop each from this contract's state, then re-run apply:

  tofu -chdir=.fluid/iac/snowflake/sales_orders_lake state rm snowflake_external_volume.sales_orders_lake_vol_FLUID_SALES_ORDERS_LAKE_VOL
...
```

*([forge-cli #710](https://github.com/Agenticstiger/forge-cli/pull/710), since 0.20.0)* The volume is named per contract, so state cannot say which expose it was created for, and the message names both possible causes: an upgrade from a release that gave a volume to an expose in a catalog Snowflake does not manage, or a Snowflake-managed Iceberg expose this change removed or moved to another catalog. It blocks the same applies as before; with #707 and #709 alone it said forge-cli no longer creates the volume and listed the moved exposes as holding it. The guard finds the volume by the name derived from the contract id, so it also stops an upgrade whose edit changed `location.warehouse` to the catalog's warehouse name or removed `location.iam_role_arn`. Run the printed `tofu -chdir=.fluid/iac/snowflake/<safe-id> state rm snowflake_external_volume.<name>`, which changes nothing in Snowflake, then apply again. Drop the volume by hand (`DROP EXTERNAL VOLUME`) only once no Iceberg table uses it: a Snowflake-managed table written onto it still does. See [Upgrading a Snowflake contract that names another catalog](../advanced/source-aligned-acquisition.md#upgrading-a-snowflake-contract-that-names-another-catalog).

*([forge-cli #709](https://github.com/Agenticstiger/forge-cli/pull/709), since 0.20.0)* When the guard cannot read the state, or its check fails, the apply goes on to plan, and logs an `iceberg_catalog_move_probe_skipped` WARNING with the reason and the exposes. The data-loss gate still stops a plan that destroys the resources; release them with `tofu state rm` rather than passing `--allow-data-loss`. On #707 alone a failed check was logged at debug level.

## Remote state

[OpenTofu state](../concepts/state.md) explains the state key, the backends and which commands read state.

On the OpenTofu engine, state is local by default: `.fluid/iac/<provider>/<safe-id>/terraform.tfstate` under `--workspace-dir`. A CI runner that wipes its workspace loses it, and the next run plans every resource as new, so a pipeline keeps state in a bucket.

```bash
# One variable serves every product a CI job applies
export FLUID_STATE_BACKEND=s3://<your-state-bucket>
fluid apply contract.fluid.yaml --yes
```

Bucket names are global: use a bucket you own. The bucket name `acme-fluid-state` in the captured output below is illustrative.

```text
  state:       remote: s3://acme-fluid-state/fluid/analytics.web.pageviews/aws/terraform.tfstate (from FLUID_STATE_BACKEND)
```

`--state-backend` takes `s3://<bucket>/<key>` or `gcs://<bucket>/<prefix>`. Its default is `$FLUID_STATE_BACKEND`, else local state. `--state-backend ""` forces local state when the environment sets the variable. *(since 0.31.0, [forge-cli #901](https://github.com/Agenticstiger/forge-cli/pull/901))* An S3 spec can end in `?region=<region>`, as in `s3://<bucket>/<key>?region=eu-west-1`. That names the region of the state bucket, which may differ from the region the resources live in, and forge writes it as the backend's `region`. Without it, `tofu` reads `AWS_REGION`. Only that exact tail is read as a region: any other `?` stays part of the key, so an existing key does not change. The `state:` line names the object the run uses and where the spec came from. When an apply or a drift check fails on state or region, [State and region errors](../advanced/production-troubleshooting.md#state-and-region-errors) lists the causes.

### Which key a bucket-only spec gets

A spec with a key (or prefix) is used as written. A bucket-only spec gets a default key, and the default depends on where the spec came from. Measured on 0.18.1 with an `aws` contract (id `analytics.web.pageviews`); the bucket name `acme-fluid-state` is illustrative:

| Spec | `state:` line |
| --- | --- |
| `FLUID_STATE_BACKEND=s3://acme-fluid-state` | `s3://acme-fluid-state/fluid/analytics.web.pageviews/aws/terraform.tfstate` |
| `FLUID_STATE_BACKEND=gcs://acme-fluid-state` | `gcs://acme-fluid-state/fluid/analytics.web.pageviews/aws` |
| `--state-backend s3://acme-fluid-state` | `s3://acme-fluid-state/fluid/terraform.tfstate` |
| `--state-backend s3://acme-fluid-state/shared/state.tfstate` | `s3://acme-fluid-state/shared/state.tfstate` |

- **From the environment variable**, every contract gets its own key `fluid/<id>/<provider>/terraform.tfstate` (the GCS prefix is `fluid/<id>/<provider>`), with the contract id exactly as written. One CI variable therefore serves every product without them sharing a state. An id outside the identifier grammar cannot name a state and is refused with `apply_state_backend_invalid`.
- **From the flag**, a contract with a `packaging` block gets `fluid/<safe-id>/<provider>/terraform.tfstate`, where `<safe-id>` folds `.` and `-` into `_`. A contract without one gets the shared legacy key `fluid/terraform.tfstate`, which is how two contracts pointed at one bucket-only flag share a state. Use the environment variable, or give the flag a key per contract, when that is not what you want.
- The `<provider>` segment keeps one contract deployed to two clouds through `--env` overlays in two states. With one shared state, each cloud's plan read the other's resources as orphans to destroy.

### Moving existing state to the provider key (since 0.17.0)

State that an earlier release wrote at `fluid/<id>/terraform.tfstate` has to follow the key change, or the first apply after upgrading plans every resource as new. `apply` moves it:

- It copies the old object to the new key with OpenTofu's own `tofu init -force-copy` (the migration path `tofu init -migrate-state` uses). It leaves the old object where it was, reads the copy back to check the resources match, and prints a `state move:` line naming both keys and the number of resources it moved.
- It copies only when the new key holds no state and the old key holds this provider's resources. A state that holds another provider's resources is left alone (`state move: ... not this provider's; left in place`): the first `gcp` apply of a contract whose old key holds the `aws` state starts a new `gcp` state and does not touch the `aws` one.
- *(since 0.31.0, [forge-cli #901](https://github.com/Agenticstiger/forge-cli/pull/901))* After a move, the summary ends with the commands that remove the old object, for you to run once you have checked the new state: `aws s3 rm <old s3 uri>` and `aws s3 rm <old s3 uri>.tflock` (the second clears a stale lock object), each with `--region <region>` when the spec names one, or `gcloud storage rm <gs uri of default.tfstate>` for GCS. The URIs are shell-quoted where they need it, and carry no wildcard and no `--recursive`. forge never deletes state: the old object is the only way back until you have checked the new key.
- `--dry-run` never moves state. While a move is pending it plans against the old key, and so do [`fluid diff`](./diff.md) and `fluid verify --state-drift`, which only read.

| Error | Meaning | What to do |
| --- | --- | --- |
| `state_migration_ambiguous` | The old key holds resources of two clouds, or of a provider this version does not recognise, and the new key is empty. Nothing was moved. | Move the state yourself with `tofu init -migrate-state` from a directory configured with the old key, or name the key to use in `--state-backend`. |
| `state_migration_raced` | The new key received a different state while the move was about to run. Nothing was moved. | Re-run once the other job has finished. |
| `state_migration_failed` | The scratch `tofu init` on the old or the new key failed. | Read the error text, which carries the tail of `tofu`'s output. |
| `state_migration_unverified` | After the copy the new key does not hold the resources that were copied. The old object is untouched. | Check the new key by hand before you re-run. |
| `state_migration_probe_failed` | The state at a key could not be read. | Check the bucket, the key and the credentials. |
| `state_shared_with_another_provider` | A remote key that does not name the provider holds another cloud's resources, and this apply would plan them as orphans to destroy. | Give each provider its own state: a key that names the provider in `--state-backend`, or a bucket-only `FLUID_STATE_BACKEND`. |

## State and plan encryption

*(since 0.31.0, [forge-cli #905](https://github.com/Agenticstiger/forge-cli/pull/905))*

The OpenTofu state of an apply holds what the resources hold: connection strings, generated passwords, ids. Encrypting it is opt-in. Set `FLUID_STATE_ENCRYPTION` in the environment of the job to name one OpenTofu key provider, and forge writes a `terraform.encryption` block into the module with `enforced = true` for both the state and the saved plan. `tofu` then refuses to write either one unencrypted.

*(since 0.31.0, [forge-cli #905](https://github.com/Agenticstiger/forge-cli/pull/905))* The variable names a key by reference. There are four forms, and each reaches its key with credentials you already have:

| `FLUID_STATE_ENCRYPTION` | Key provider | Where the key's credentials come from |
| --- | --- | --- |
| `aws-kms://<key id, key ARN or alias/name>` | `aws_kms` | The AWS credentials of the run. The region comes from a key ARN, else from `AWS_REGION` or `AWS_DEFAULT_REGION`; a bare key id or alias with neither is refused. |
| `gcp-kms://projects/<p>/locations/<l>/keyRings/<r>/cryptoKeys/<k>` | `gcp_kms` | The Google credentials of the run (application default credentials, impersonation, a workload identity). |
| `openbao://<transit mount path>/<key name>` | `openbao` | The transit engine of your OpenBao, for example `openbao://transit/fluid`. forge gives `tofu` the store's address (`BAO_ADDR` or `VAULT_ADDR`) and a token: the one forge's vault resolver finds in the environment or the token helper file, a response-wrapped token, or a CI JWT login. A token forge minted is revoked when the run ends. `BAO_NAMESPACE` and the CA bundle go along when set. |
| `pbkdf2+<secret reference>` | `pbkdf2` | A passphrase the reference names, for example `pbkdf2+env://FLUID_STATE_PASSPHRASE` or `pbkdf2+vault://kv/lab/state#passphrase`. It resolves under your [secret policy](./secrets.md), and OpenTofu needs at least 16 characters. |

*(since 0.31.0, [forge-cli #905](https://github.com/Agenticstiger/forge-cli/pull/905))* The setting applies to every command that runs `tofu` against the state: `fluid apply`, `fluid plan --tofu`, `fluid diff` and `fluid verify --state-drift`. A saved plan from `fluid plan --tofu` is encrypted too, so `fluid apply` of that plan needs the same `FLUID_STATE_ENCRYPTION`. The `encryption:` line of an apply names the provider and the key, never a value:

```text
  encryption:  pbkdf2, passphrase from env://FLUID_STATE_PASSPHRASE
```

### Where the key material goes

*(since 0.31.0, [forge-cli #905](https://github.com/Agenticstiger/forge-cli/pull/905))* The key itself is never written down. `main.tf.json` holds the key's name and no passphrase, and neither the plan nor the state carries it. forge never sets `TF_ENCRYPTION`, and an `TF_ENCRYPTION` in your environment never reaches `tofu`, because OpenTofu would let it override the module. A pbkdf2 passphrase reaches `tofu` as an ephemeral variable, `TF_VAR_fluid_state_passphrase`, in the environment of that one process: OpenTofu keeps only the variable's name in a saved plan and never puts it in the state.

*(since 0.31.0, [forge-cli #905](https://github.com/Agenticstiger/forge-cli/pull/905))* `FLUID_STATE_ENCRYPTION` is a protected name. A `.env` file in a project cannot set it, because whoever chooses the key chooses who can read the state. Set it in the job's own environment. See [project `.env` trust](../advanced/project-dotenv-trust.md).

### OpenTofu 1.13 or newer

*(since 0.31.0, [forge-cli #905](https://github.com/Agenticstiger/forge-cli/pull/905))* With the setting on, forge refuses a `tofu` older than 1.13. Before 1.13, `tofu init -backend=false`, which forge runs for local state, read an encrypted local state without the encryption configuration and failed. `--ensure-opentofu` installs a pinned build only when no `tofu` is on `PATH`, so upgrade a `tofu` you already have.

### Errors and fixes

*(since 0.31.0, [forge-cli #905](https://github.com/Agenticstiger/forge-cli/pull/905))*

| Error | Meaning | What to do |
| --- | --- | --- |
| `opentofu_state_encryption_invalid` | `FLUID_STATE_ENCRYPTION` names no provider, a provider forge does not support, or a key that does not match its form (an `aws-kms` key id with no region, a malformed GCP key path, an unparsable passphrase reference). | Set it to one of the four forms above. The message says which part is wrong. |
| `opentofu_state_encryption_unsupported` | The `tofu` on this machine is older than 1.13. | Upgrade OpenTofu to 1.13 or newer. |
| `opentofu_state_encryption_unavailable` | The key could not be reached or used: the passphrase reference does not resolve, the passphrase is shorter than 16 characters, the OpenBao address or token is missing, or `tofu` could not use the KMS key. | Fix the reference or the store, or give the run an identity that may use the key. `--debug` shows `tofu`'s full diagnostic. |
| `opentofu_state_not_encrypted` | The state is plaintext and `FLUID_STATE_ENCRYPTION` asks for encrypted state. | Migrate it once (below), or unset the variable to keep this state unencrypted. |
| `opentofu_state_encrypted_without_key` | The state is encrypted and `FLUID_STATE_ENCRYPTION` is not set. | Set it to the key that encrypted the state. |
| `opentofu_state_decrypt_failed` | The state or the plan could not be decrypted with the key the variable names. | Set it to the key that encrypted them. forge does not change keys yet, which needs the old key as a fallback. |

### Encrypting a state that already exists

*(since 0.31.0, [forge-cli #905](https://github.com/Agenticstiger/forge-cli/pull/905))* Plaintext state is refused once encryption is on, and the `opentofu_state_not_encrypted` error names the fix: run `fluid apply` once with the hidden flag `--migrate-state-encryption`. That run reads the plaintext state through OpenTofu's `unencrypted` fallback and writes it back encrypted. It needs `FLUID_STATE_ENCRYPTION` set and refuses without it. The flag is not in `--help`.

*(since 0.31.0, [forge-cli #905](https://github.com/Agenticstiger/forge-cli/pull/905))* OpenTofu forbids a fallback under `enforced`, so the state of that one run is not enforced and a warning (`opentofu_state_encryption_migration`) says so. The plan is still enforced. Later runs need no flag.

## What `tofu` gets from the environment

*(since 0.31.0, [forge-cli #905](https://github.com/Agenticstiger/forge-cli/pull/905))* Every `tofu` call of a run, from `init` to `apply`, gets an allowlist of your environment, not a copy of it. A model API key, a GitHub token or a Command Center secret in the job's environment never reaches `tofu` or the provider processes it starts.

What passes:

- The process basics: `PATH`, `HOME`, the user and locale variables, the temporary directory, the XDG directories, and the Windows system and profile directories.
- Proxies (`HTTP_PROXY`, `HTTPS_PROXY`, `NO_PROXY`, in both cases) and CA bundles (`SSL_CERT_FILE`, `SSL_CERT_DIR`).
- OpenTofu's own settings by name, such as `TF_LOG`, `TF_DATA_DIR`, `TF_WORKSPACE`, `TF_CLI_CONFIG_FILE` and `TF_PLUGIN_CACHE_DIR`, and `TF_TOKEN_*` for a private registry.
- `TOFU_CLI_PATH` and `GITHUB_OUTPUT`, which the default wrapper of `opentofu/setup-opentofu` needs. They hold paths, no credential.
- Each plugin's credential families: `AWS_` for AWS; `GOOGLE_`, `GCLOUD_`, `CLOUDSDK_` and `GCE_METADATA_` for GCP; `SNOWFLAKE_` for Snowflake; `DATABRICKS_`, `ARM_`, `AZURE_` and `GOOGLE_` for Databricks; `CONFLUENT_` and `TABLEFLOW_` for Confluent. A whole family keeps every way a provider can sign in working: a profile with a `credential_process`, a web identity token file, container credentials, application default credentials and impersonation.
- The cloud of the state backend (`s3://` is AWS, `gcs://` is GCP) and of the encryption key, whatever the plugin is. Snowflake resources with state in S3 get `AWS_`.

What never passes:

- `TF_CLI_ARGS` and `TF_CLI_ARGS_<command>`, which would add flags such as `-auto-approve`, `-target` or `-lock=false` to every command forge runs.
- `TF_VAR_*` from your environment, which would set the module's variables. forge sets the ones it needs itself.
- `TF_ENCRYPTION`, which would override the module's state encryption. Use `FLUID_STATE_ENCRYPTION`.
- `TF_INPUT` and `TF_REATTACH_PROVIDERS`.
- Model keys that sit inside a cloud's family: `GOOGLE_API_KEY`, `GOOGLE_GENERATIVE_AI_API_KEY`, `AWS_BEARER_TOKEN_BEDROCK`, `AZURE_API_KEY`, and the `AZURE_OPENAI_` and `AZURE_AI_` families.

*(since 0.31.0, [forge-cli #905](https://github.com/Agenticstiger/forge-cli/pull/905))* When a `TF_` variable is dropped, forge logs a `tofu_env_dropped` warning that names the variables and never their values. `fluid generate iac --validate` uses the same allowlist.

*(since 0.31.0, [forge-cli #905](https://github.com/Agenticstiger/forge-cli/pull/905))* An IaC plugin that lives outside forge declares what its provider reads: exact names in `credential_env_vars` and whole families in `credential_env_prefixes` (for example `("MYCLOUD_",)`). A plugin that declares no prefixes is warned about once, with `tofu_env_plugin_undeclared`, and gets only its `credential_env_vars` and the basics. A job that relied on a variable the allowlist now drops needs it declared there, or set another way.

## Reporting to the Command Center (since 0.17.0)

The [Command Center page](../concepts/command-center.md#what-fluid-apply-reports) covers what the report holds and how to configure it.

Each `fluid apply` registers itself with a Command Center when one is configured, and closes the run when it ends. It is best effort: a Command Center that is down, slow or misconfigured costs at most a warning line and the request timeout, and did not change the exit code when measured. This is what the apply prints when the Command Center answers, and when it does not (measured against a local stand-in server on 5 Oct 2026):

```text
  command center: run cf9d4172-9ce2-43f6-b5b7-8c1b33c3d02f reported
```

```text
  command center: run 484fdc25-699b-4a74-8983-5be633dd9599 not fully reported (0 of 2 requests accepted); the apply's result is unaffected
```

**When it reports.** `apply` uses the Command Center configuration that `fluid publish` already uses: the `fluid-command-center` catalog in `fluid.config.yaml`, or `FLUID_CC_ENDPOINT` with `FLUID_API_KEY` or `FLUID_BEARER_TOKEN`. A pipeline that publishes therefore reports its applies with no new setting. With that configuration an organization is required: `FLUID_CC_ORG_ID`, `organization_id` or the `organization` slug in the config, or the only organization the credential belongs to. Without one the apply prints `command center: run not reported (...)` and carries on. `FLUID_COMMAND_CENTER_URL` with `FLUID_COMMAND_CENTER_API_KEY` is the fallback when no publish configuration names a Command Center; that path sends `X-Organization-Id` only when `FLUID_CC_ORG_ID` is set.

**What it sends.** `POST /api/v1/executions` when the run starts and `PATCH /api/v1/executions/<id>` when it ends:

- the product id and name and the contract's `fluidVersion`;
- the contract path as you typed it, the `--env`, the apply mode, and the CLI and Python versions;
- on the OpenTofu engine, also the provider, the contract version, the hash of the compiled contract, the state location, the number of resources planned and applied (`add`, `change`, `remove`), and the address of every resource the module declares. On the native engine the run is registered when it ends and carries the first two bullets only (measured with the `local` provider);
- for a build-augmented apply, each build's id and outcome, plus the run id, the table loaded and the rows landed when the build wrote a run record;
- the status, the exit code, the phase (`plan`, `apply` or `build`), the typed error event when the run failed, and the timings.

It sends no secret: no request header from your environment, no environment value and no `tofu` output, whose text can carry attribute values. The runner is reported as `jenkins` when `JENKINS_URL` is set, else `cli`.

*(from 0.27.0)* The reporter follows a redirect only within the endpoint's origin; a redirect to another origin is not followed and the event is reported as not sent. If `REQUESTS_CA_BUNDLE` (or, when that is unset, `CURL_CA_BUNDLE`) names a file or directory that cannot be loaded, the reporter is switched off for the run with a warning, `Command Center reporter disabled: <variable> is set to '<path>', which cannot be loaded as a CA bundle (<reason>).` The apply itself carries on, and TLS verification is never relaxed.

The Command Center's host check refuses private and cloud-metadata addresses unless `FLUID_COMMAND_CENTER_HOST_ALLOWLIST` names the host; loopback is allowed.

**Switch it off** with `FLUID_COMMAND_CENTER_ENABLED=false`; the apply then prints `command center: run not reported (FLUID_COMMAND_CENTER_ENABLED is off)` when a Command Center is configured. The [environment variables](../advanced/environment-variables.md#command-center) page lists the other settings.

## Federated upstream check

[Federated upstreams](../concepts/federation.md) covers the manifest, the pin and the digest cache.

A `consumes[]` entry that names an `upstreamWorkspace` and an `upstreamDigest` pins a product in another mesh. Both keys are part of the preview schema, so the contract declares `fluidVersion: "0.7.6"`; under `0.7.5` they are rejected. Before it runs the native apply, `fluid apply` fetches each upstream's live digest and compares it with the pin.

Since 0.16.0 this check **warns and does not abort**. The apply goes on and exits as it would have. This is real output for an entry whose workspace is not declared in `federation/upstreams.yaml`:

```text
apply_consumes_drift: 1 federated consumes[] entry could not be confirmed in sync (1 unknown-workspace). Applying anyway. Details: {"counts_by_kind": {"unknown-workspace": 1}, ...}
  consumes[0] partner-mesh/bronze.sales.raw_orders_v1 [unknown-workspace]: Federated workspace 'partner-mesh' not declared in federation/upstreams.yaml. Add it to the manifest before referencing in consumes[].
```

The `violation_kind` is `drift`, `unreachable`, `unpinned`, `unknown-workspace` or `not-wired`. A pipeline that wants a hard stop greps the log for `apply_consumes_drift`. If the check itself fails, the log carries `federation_gate_error` and the pins were not verified for that apply. Each `git` operation the fetch runs is bounded by `FLUID_FEDERATION_TIMEOUT_SECONDS` (default 30). `--no-verify-federation` skips the check and logs one warning that it was skipped. A pipeline that wants the warning counted reads [the federation check warns](../advanced/operating-in-ci.md#the-federation-check-warns).

As of 0.18.1 this check runs on the native engine only. An apply on the OpenTofu engine (`aws`, `gcp`, `snowflake`, `confluent`) does not run it, so it prints no `apply_consumes_drift` line even when a pin does not match.

It also does not run under `--mode amend-and-build` or `--mode replace-and-build`. The same contract that printed `apply_consumes_drift` under `--mode amend` applied under `--mode amend-and-build` and `--mode replace-and-build` with no such line (`local` provider, measured on 0.18.1). Use `--mode amend` in a stage that is meant to check the pin.

## Packaging modes

::: tip Opt-in, new in `0.13.0`
Only relevant to contracts that declare `fluidVersion: "0.7.6"` **and** carry a `packaging` block. A contract without one resolves to the LEGACY sentinel, can never transition, and passes no ownership guard. Changes made since `0.13.0` elsewhere on this page, such as the per-provider state key and the GCP dataset grants in [Notes](#notes), apply to it too.
:::

A `packaging` block declares whether this product **owns** each infrastructure container (`isolated`) or writes into a pre-existing, platform-owned **pool** (`shared`). Full reference: [`fluid generate iac` — Packaging modes](./generate-iac.md#packaging-modes).

Changing a container's mode changes *who owns it*, but OpenTofu only sees a resource that left the configuration and plans a **destroy** — on a shared pool that reaches every other tenant's data. So `apply` diffs the resolved ownership model against `tofu state list` **before** `tofu plan`:

| Transition | Behaviour |
| --- | --- |
| `isolated` → `shared` (owned → referenced) | **Always blocked** — there is no flag. `apply` fails closed and prints copy-pasteable `tofu -chdir=<workdir> state rm <address>` commands. State surgery touches zero bytes of infrastructure; re-run `apply` afterwards. |
| `shared` → `isolated` (referenced → owned) | Requires `--adopt-shared-container`. Without the gate, brownfield adoption would `tofu import` the platform's pool into this product's state with `force_destroy` restored — the exact blast radius the feature exists to close. |

```bash
# Blocked — drop the resource from state first, then re-run.
fluid apply runtime/plan.json --yes
# → packaging_transition_blocked: aws_s3_bucket.data (owned → referenced)
# →   tofu -chdir=.fluid/iac/aws/<safe-id> state rm aws_s3_bucket.data

# Taking ownership of a previously-shared container (audited)
fluid apply runtime/plan.json --yes --adopt-shared-container
```

The printed `tofu state rm` commands include `-chdir` pointing at the per-contract working directory (`.fluid/iac/<provider>/<safe-id>/`), so they run against the right state without you having to find it.

Structured `packaging_transition_blocked` / `packaging_adoption_override` events are emitted for CI log scrapers. This guard runs **earlier** than, and is independent of, the data-loss gate — that gate remains the unconditional last line.

## Options

Options marked *native* are read only by the native engine. As of 0.18.1 the OpenTofu engine does not read them: `--project`, `--region`, `--provider-config`, `--config-override` and `--state-file`, the reporting options, and the options that shape a native orchestration plan. For example, `--region us-east-1` on an apply whose binding names `eu-west-1` still emitted a module pinned to `eu-west-1`. The region comes from the contract's bindings.

### General

| Option | Default | Description |
| --- | --- | --- |
| `--env` | none | Apply an environment overlay (dev / staging / prod / …); see [Environments and overlays](../concepts/environments-and-overlays.md) and [per-environment overlays](../recipes/per-environment-overlays.md). A name with no matching overlay warns and uses the base. For a `plan.json` or a bundle the env is recorded in it; see [Plan binding](#plan-binding). |
| `--provider` | from the contract binding | Disambiguate the target when the contract spans several clouds or declares none. A value that contradicts the cloud the contract declares is rejected with `generate_iac_provider_mismatch` (exit 1) before anything is written. It cannot retarget a contract: change the `binding` instead, as in [Switch clouds](../recipes/switch-clouds.md). |
| `--project` *(native)* | from the contract | Override the project / account. |
| `--region` *(native)* | from the contract | Override the region / location. |

### Execution control

| Option | Default | Description |
| --- | --- | --- |
| `--mode` | `amend` | One of `dry-run`, `create-only`, `amend`, `amend-and-build`, `replace`, `replace-and-build`. *(since 0.34.0, [forge-cli #1013](https://github.com/Agenticstiger/forge-cli/pull/1013))* Also `reconcile`: see [Reconcile mode](#reconcile-mode). |
| `--yes` | off | Skip confirmation. |
| `--dry-run` | off | Alias for `--mode dry-run`. |
| `--ensure-opentofu` | off | *(since 0.8.8)* If the `tofu` binary is missing, provision a **pinned, SHA-256-verified** OpenTofu build before a cloud apply — **no root, gpg, cosign, curl, or unzip needed** (Python stdlib only). Idempotent (a usable `tofu` at/above the engine floor is left untouched) and a no-op for native / `local` applies. Pin via `FLUID_OPENTOFU_VERSION`. `fluid generate ci` bakes this into the generated apply stage so cloud applies work on locked-down / non-root runners. |
| `--timeout TIMEOUT` *(native)* | `120` | Global timeout in minutes. Read when the contract is orchestrated (it carries top-level sections such as `infrastructure` or `terraform`). |
| `--parallel-phases` *(native)* | off | Execute independent phases in parallel. Orchestrated contracts only. |
| `--max-workers MAX_WORKERS` | `4` | Accepted. Nothing in 0.18.1 reads it. |

### Safety and rollback

| Option | Default | Description |
| --- | --- | --- |
| `--rollback-strategy` *(native)* | `phase_complete` | `none`, `immediate`, `phase_complete`, or `full_rollback`. Orchestrated contracts only. |
| `--require-approval` | off | Accepted. Nothing in 0.18.1 reads it. |
| `--backup-state` | off | Accepted. Nothing in 0.18.1 reads it. |
| `--validate-dependencies` | off | Accepted. Nothing in 0.18.1 reads it. |
| `--force-pattern-drift` | off | Override apply-time plugin hooks that detect drift (for example a scaffold-bundle digest mismatch). Use with care: drift normally means the inputs have changed and a fresh generate is needed. |
| `--allow-skipped-builds` | off | Exit 0 from a build-augmented mode even when every build was skipped (missing dbt project or driver script). Without this the apply exits 1, because DDL-only success on an empty table is a broken deployment reported green. |

### Reporting

These write the native engine's execution report. The OpenTofu engine does not write one: its record is the `tofu` output in your log and the [Command Center run](#reporting-to-the-command-center-since-0-17-0).

| Option | Default | Description |
| --- | --- | --- |
| `--report` *(native)* | `runtime/apply_report.html` | Output path for the execution report. |
| `--report-format` *(native)* | `html` | `html`, `json` or `markdown`. It decides the format whatever the file extension is: `--report runtime/apply-report.json` alone still writes HTML. |
| `--metrics-export` *(native)* | `none` | `none`, `prometheus`, `datadog` or `cloudwatch`. Orchestrated contracts only. |
| `--notify` *(native)* | none | Notification destinations, such as `slack:<channel>` or `email:<address>`. Orchestrated contracts only. |

### Build execution

| Option | Default | Description |
| --- | --- | --- |
| `--build-id BUILD_ID` | none | Filter build execution to a specific build by ID from the contract's `builds[]`. Needs `--mode amend-and-build` or `--mode replace-and-build`; any other mode is refused with `apply_build_id_requires_build_mode`. When unset and the mode requires builds, every build runs. *(since 0.27.0, [forge-cli #808](https://github.com/Agenticstiger/forge-cli/pull/808))* An id that matches none of the contract's builds is refused with `apply_build_id_not_found` before anything is applied; see [Build ids](#build-ids). |
| `--delay DELAY` | `2` | Seconds between build iterations. |
| `--fail-fast` | off | Stop on first failure. |
| `--no-output` | off | Suppress build script output. |

`--build` was retired when the mode matrix replaced it. Passing it prints the migration instruction (`--mode amend-and-build`, with `--build-id` to pick one build) and exits with a usage error.

### Debugging and advanced

| Option | Default | Description |
| --- | --- | --- |
| `--verbose` | off | Detailed progress output. |
| `--debug` | off | Full logging, and the traceback of an unexpected error. |
| `--profile` | off | Performance profiling. |
| `--keep-temp-files` | off | Accepted. Nothing in 0.18.1 reads it. |
| `--workspace-dir` | `.` | Workspace directory. On the OpenTofu engine it is the parent of `.fluid/iac/`, so it decides where local state lives. |
| `--state-file STATE_FILE` *(native)* | `runtime/apply_state.json` | Custom state file location for orchestrated applies. |
| `--config-override` *(native)* | none | Override contract config with JSON. |
| `--provider-config` *(native)* | none | Path to provider-specific configuration. |
| `--state-backend` | `$FLUID_STATE_BACKEND`, else local | OpenTofu remote state, `s3://<bucket>/<key>` or `gcs://<bucket>/<prefix>`. `""` forces local state. See [Remote state](#remote-state). |

## Errors you can hit

Each failure prints the typed event name and an `[ERR_<EVENT>]` slug, and exits 1 unless noted.

| Event | Raised when |
| --- | --- |
| `apply_plan_digest_plan_tamper`, `apply_plan_digest_bundle_mismatch`, `apply_plan_digest_bundle_missing` | A saved plan fails its digest checks. See [Plan binding](#plan-binding). |
| `apply_plan_digest_packet_mismatch`, `apply_plan_digest_packet_missing` | *(since 0.33.0, [forge-cli #985](https://github.com/Agenticstiger/forge-cli/pull/985))* The bundle file has other bytes than the plan was made from, or the plan records none. See [The packet](#the-packet). |
| `apply_plan_mode_mismatch` | `--mode` differs from the mode the plan was made for. |
| `apply_contract_invalid` | *(since 0.20.0, [forge-cli #714](https://github.com/Agenticstiger/forge-cli/pull/714))* The contract, or the contract a `plan.json` embeds, is not valid against its schema. Raised on both engines and in every mode. See [Contract validation](#contract-validation). |
| `contract_version_unsupported` | *(since 0.20.0, [forge-cli #714](https://github.com/Agenticstiger/forge-cli/pull/714))* The contract's `fluidVersion` is below 0.7. Raised on both engines and in every mode. |
| `apply_plan_missing_contract` | *(since 0.20.0, [forge-cli #714](https://github.com/Agenticstiger/forge-cli/pull/714))* A `plan.json` embeds no contract. Re-run `fluid plan` and apply the new plan. |
| `plan_env_mismatch` | A build mode is given an `--env` that differs from the plan's. |
| `bundle_env_mismatch` | `--env` differs from the env a bundle was built for. |
| `apply_build_id_requires_build_mode` | `--build-id` with a mode that runs no build. |
| `apply_build_identifier_invalid` | *(since 0.27.0, [forge-cli #803](https://github.com/Agenticstiger/forge-cli/pull/803))* A build mode, and an `id` or `builds[].id` the build phase cannot use. Nothing is applied. See [Build ids](#build-ids). |
| `apply_build_id_not_found` | *(since 0.27.0, [forge-cli #808](https://github.com/Agenticstiger/forge-cli/pull/808))* A build mode, and a `--build-id` that matches no `builds[].id`. The error lists the ids the contract has. Nothing is applied. See [Build ids](#build-ids). |
| `apply_databricks_sdk_missing` | *(since 0.30.0, [forge-cli #861](https://github.com/Agenticstiger/forge-cli/pull/861))* A build mode without `--dry-run`, a selected dbt build that runs as a Databricks job and is not continuous, and no `databricks-sdk`. *(since 0.30.0, [forge-cli #872](https://github.com/Agenticstiger/forge-cli/pull/872))* Or a selected build with `engine: lakeflow`, continuous or not. Nothing is applied. Install `data-product-forge[databricks]`, or apply with `--mode amend`. See [Running the job from `fluid apply`](../providers/databricks.md#running-the-job-from-fluid-apply). |
| `apply_mode_data_loss_blocked` | `replace` or `replace-and-build` without `--allow-data-loss`. |
| `opentofu_data_loss_gate` | An OpenTofu plan destroys a resource and `--allow-data-loss` is not set. *(since 0.27.0, [forge-cli #793](https://github.com/Agenticstiger/forge-cli/pull/793))* Also a plan that changes the column types of a Glue table in place. |
| `opentofu_plan_failed` | `tofu plan` failed. *(since 0.27.0, [forge-cli #786](https://github.com/Agenticstiger/forge-cli/pull/786))* A plan that failed on a held state lock suggests `tofu force-unlock <id>`. |
| `opentofu_apply_failed` | `tofu apply` failed. See [A failed OpenTofu apply](#a-failed-opentofu-apply). |
| `opentofu_region_moved` | State holds the contract's resources in another region than its bindings name. |
| `packaging_transition_blocked` | A container's ownership flips under existing state. See [Packaging modes](#packaging-modes). |
| `iceberg_catalog_move_blocked` | *(since 0.20.0, [forge-cli #707](https://github.com/Agenticstiger/forge-cli/pull/707))* State holds Glue resources an earlier release created for an AWS Iceberg table that now lives in another catalog. *([forge-cli #709](https://github.com/Agenticstiger/forge-cli/pull/709), since 0.20.0)* Or it holds the Snowflake EXTERNAL VOLUME an earlier release created for a Snowflake Iceberg table in an external catalog. See [Iceberg catalog-move guard](#iceberg-catalog-move-guard). |
| `opentofu_dataset_access_unreconciled` | State holds a BigQuery dataset an older forge-cli applied with an authoritative access list, and every entry of it is a grant the contract no longer makes. Revoke those entries on the dataset by hand, or keep one of them in `accessPolicy` for one apply. |
| `apply_state_backend_invalid`, `state_shared_with_another_provider`, `state_migration_*` | See [Remote state](#remote-state). |
| `generate_iac_provider_mismatch` | `--provider` contradicts the contract's binding. |
| `unsupported_binding` | The OpenTofu module cannot provision part of the contract as declared, and refuses it rather than drop it; the `kind:` line says which part. *(since 0.20.0, [forge-cli #715](https://github.com/Agenticstiger/forge-cli/pull/715))* Kind `mwaa-environment-not-emitted`: an `aws` contract with `orchestration.engine: airflow` and an `orchestration.schedule` asks for an MWAA environment, which the module cannot create. See [Scheduling on AWS](../providers/aws.md#scheduling-on-aws). |
| `opentofu_engine_no_tofu` | The OpenTofu engine needs `tofu` and it is not on `PATH`. Install it, or pass `--ensure-opentofu`. |

### A failed OpenTofu apply

*(since 0.27.0, [forge-cli #786](https://github.com/Agenticstiger/forge-cli/pull/786))*

The runner calls `tofu` with `-json`, so every diagnostic arrives as one JSON line. Through 0.26.0 a failed apply printed the last 800 characters of that stream, a run of `{"@level": ...}` objects and no way forward. It now reads the first error diagnostic and prints what failed and where:

```text
❌ opentofu_apply_failed  [ERR_OPENTOFU_APPLY_FAILED]
  error: <summary> (<resource address>)
  resource: <resource address>
  detail: <the provider's explanation>

💡 Suggestions:
  • OpenTofu records state as it goes, so resources created before the failure are normally tracked
  • Fix the cause named above, then re-run 'fluid apply' to continue
  • Re-run with --debug to see the raw tofu output
  • To see what exists, run 'tofu state list' in <the contract's OpenTofu workdir>
```

- `detail` is the provider's own text, cut at 800 characters. `more_errors: <n>` follows when the run printed further error diagnostics.
- Output with no diagnostic (a crash, a timeout) falls back to the text from its first `Error:` on, cut at 800 characters, or to `tofu apply exited <exit code>` when there is none.
- Fixing the cause and re-running `fluid apply` normally continues where it stopped, because the resources created before the failure are already in state. `tofu state list` in the workdir (`.fluid/iac/<provider>/<safe-id>/`) shows which.
- A state-lock error adds a suggestion to wait for the other run or run `tofu force-unlock <id>`; see [Locking](../concepts/state.md#locking). A plan that fails on a held lock gets the same suggestion.
- The raw output tail goes to the log under `--debug`.

Everything a CLI error prints, its context values and its suggestions, now goes through the redactor the logs use. A provider message that carries an access key id, a bearer token or a URL password is masked, and control characters are spelled out.

## Notes

- The recommended sequence is `bundle → validate → plan → apply`.
- For local-first onboarding, `fluid apply contract.fluid.yaml --yes` is the shortest path after a quickstart scaffold — default `--mode amend` is safe.
- `fluid rollback` restores from a snapshot recorded in `.fluid/rollback-state.json`. A snapshot before a `replace` is a native-engine feature that depends on the provider's planner; the OpenTofu engine takes none. The `local` apply measured on 0.18.1 wrote no `rollback-state.json`.
- For Iceberg exposes, `apply` provisions the prerequisites dbt refuses to create — the Snowflake `EXTERNAL VOLUME` and AWS Glue `CATALOG INTEGRATION` *(since 0.13.1)*, and the GCS warehouse bucket on GCP *(since 0.14.0)*. Names are derived by the same deterministic helper that `fluid generate` uses for dbt's `catalogs.yml`, so the objects apply creates are exactly the ones dbt references. See the [Snowflake](../providers/snowflake.md) and [GCP](../providers/gcp.md) provider pages.
- *(since 0.14.0)* [Apply hooks](#extension-point-apply-hooks) run on the OpenTofu path too, so `--env` plumbing reaches Snowflake / AWS / GCP cloud applies. Previously hooks ran only on the native apply path.
- *(since 0.17.0)* On GCP, dataset grants are separate `google_bigquery_dataset_iam_member` resources. The first apply on a dataset an older forge-cli created sets the dataset's access list once, to the list less the entries no grant of the contract covers, and prints what it revoked. `fluid diff` shows the same change first. See [GCP](../providers/gcp.md).

## Extension point: apply hooks

As of `0.8.3`, `fluid apply` runs any **apply hook** plugins registered via Python entry-points before invoking the providers. Use apply hooks to enforce runtime invariants that can't be checked at validate time — required env vars, image signatures, bundle-digest drift, business-hours gating, anything that depends on the deploy environment rather than the contract content.

A hook that appends an error aborts the apply with exit code 1. Pass `--force-pattern-drift` to downgrade all hook errors to WARNINGs (audit-logged) and let the apply proceed.

- Author a hook: [SDK & Plugins → Apply hook journey](/forge_docs/sdk-and-plugins/journeys/apply-hook.html)
- Reference: [Entry points → `fluid_build.apply_hooks`](/forge_docs/sdk-and-plugins/reference/entry-points.html)
- Example: [`prod-key-guard`](/forge_docs/sdk-and-plugins/examples/apply-hook-prod-key-guard.html)
