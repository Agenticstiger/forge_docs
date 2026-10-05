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

- A FLUID contract file (e.g. `contract.fluid.yaml`) — plans and applies in one shot. When omitted, `apply` uses `contract.fluid.yaml` in the current directory. The file may be the root of a [fragment layout](../concepts/contract-refs.md): its `$ref` pointers are resolved before the contract is planned.
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

## Apply mode

| `--mode` | What it does |
| --- | --- |
| `dry-run` | Render the plan without applying it. Nothing is changed. |
| `create-only` | Intended to provision only what does not exist yet. What each engine does with it is below. |
| `amend` *(default)* | The everyday mode, with no mode gate of its own. |
| `amend-and-build` | Same as `amend`, then run the contract's `builds[]` (the build runner). |
| `replace` | Destructive. Requires `--allow-data-loss`. |
| `replace-and-build` | Same as `replace`, then the builds with a full refresh. Destructive. |

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

Before 0.16.3 the flag was accepted and dropped, so a DDL-only apply exited 0.

## Plan binding

When you pass a saved plan (`runtime/plan.json`) instead of a contract, `apply` runs three gates on it before it builds or provisions anything, on both engines:

| Gate | Refusal | What it compares |
| --- | --- | --- |
| Digests | `apply_plan_digest_plan_tamper` | `planDigest` in `plan.json` against a re-computed digest of the plan body. |
| | `apply_plan_digest_bundle_mismatch` | `bundleDigest` in `plan.json` against the MANIFEST SHA-256 of the tgz bundle the plan was built from. |
| | `apply_plan_digest_bundle_missing` | A plan that carries a `bundleDigest` but has no locatable bundle. It fails closed instead of skipping the check. |
| Mode | `apply_plan_mode_mismatch` | The `mode` recorded in `plan.json` against `--mode`. A plan made without `--mode` and `amend` count as the same. |
| Environment | `plan_env_mismatch` | The `contract_metadata.env` recorded in `plan.json` against `--env`. Checked for the build modes (`amend-and-build`, `replace-and-build`). |

This is the Terraform-style "apply consumes exact plan" guarantee, enforced cryptographically. A tampered plan stops here:

```text
❌ apply_plan_digest_plan_tamper  [ERR_APPLY_PLAN_DIGEST_PLAN_TAMPER]
  kind: plan-tamper
  error: plan.json has been modified since it was generated: stored planDigest='sha256:c9b3...', recomputed='sha256:666e...'. Re-run ``fluid plan`` to produce a fresh binding, ...
```

Pass the bundle with `--bundle <path-to.tgz>`: the tgz this `plan.json` was generated against. When omitted, `apply` auto-discovers a single sibling `.tgz` / `.tar.gz` next to the `plan.json`. If several are present it logs a warning and leaves the bundle unresolved, so pass `--bundle` to disambiguate. A `plan.json` made from a raw contract has an empty `bundleDigest`, so only `planDigest` is verified; see [`fluid plan`](./plan.md#plan-binding).

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

## Safety gates

| Option | Description |
| --- | --- |
| `--allow-data-loss` | Required to run `replace` / `replace-and-build`, and to apply an OpenTofu plan that destroys data-bearing resources. |
| `--no-verify-plan-binding` | **Emergency escape hatch.** Skip the `bundleDigest` / `planDigest` verification that stage 7 normally enforces on a saved plan. Logged at `WARNING` so audit trails catch it. Use only during documented DR procedures. |
| `--no-verify-federation` | Skip the federated-`consumes[]` upstream-digest check. Logged at `WARNING`. Unlike plan binding, this check only warns (`apply_consumes_drift`, exit code unchanged), so the flag silences a warning and does not remove a refusal. The digest a downstream product pins comes from [`fluid contract digest`](./contract.md#fluid-contract-digest), which covers only the upstream's root file for a fragment-layout product. See [Federated upstream check](#federated-upstream-check) and [Consume one contract from another](../recipes/consumes-contract-to-contract.md). |
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

Some governance changes cannot be made to a live BigQuery table in place and plan its replacement, which this gate refuses without the flag: adding retention (`expire: true`) to a table that exists, adding or changing its Cloud KMS key, and removing `expire`. Roll these out as: plan, review the replacement, apply with `--allow-data-loss`, then run the build again to land the data. See [GCP](../providers/gcp.md).

### Region-move guard

Before it plans, an OpenTofu apply reads the regions recorded in the contract's existing state. If they differ from the region the contract's bindings pin, it stops:

```text
❌ opentofu_region_moved  [ERR_OPENTOFU_REGION_MOVED]
  error: state holds this contract's resources in <old-region>, but its bindings name <new-region>. Applying would create them again in <new-region> and leave the originals unmanaged
  state: .fluid/iac/aws/<safe-id>
```

Without the guard `tofu` would find nothing in the new region, create the resources again there and leave the originals behind with no destroy planned, so the data-loss gate could not fire. To keep the resources, set `location.region` back to the old region. To move them, run `tofu destroy` in the state directory with `AWS_REGION=<old-region>` set, then apply again.

## Remote state

On the OpenTofu engine, state is local by default: `.fluid/iac/<provider>/<safe-id>/terraform.tfstate` under `--workspace-dir`. A CI runner that wipes its workspace loses it, and the next run plans every resource as new, so a pipeline keeps state in a bucket.

```bash
# One variable serves every product a CI job applies
export FLUID_STATE_BACKEND=s3://acme-fluid-state
fluid apply contract.fluid.yaml --yes
```

```text
  state:       remote: s3://acme-fluid-state/fluid/analytics.web.pageviews/aws/terraform.tfstate (from FLUID_STATE_BACKEND)
```

`--state-backend` takes `s3://<bucket>/<key>` or `gcs://<bucket>/<prefix>`. Its default is `$FLUID_STATE_BACKEND`, else local state. `--state-backend ""` forces local state when the environment sets the variable. The `state:` line names the object the run uses and where the spec came from. When an apply or a drift check fails on state or region, [State and region errors](../advanced/production-troubleshooting.md#state-and-region-errors) lists the causes.

### Which key a bucket-only spec gets

A spec with a key (or prefix) is used as written. A bucket-only spec gets a default key, and the default depends on where the spec came from. Measured on 0.18.1 with an `aws` contract (id `analytics.web.pageviews`):

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
- `--dry-run` never moves state. While a move is pending it plans against the old key, and so do [`fluid diff`](./diff.md) and `fluid verify --state-drift`, which only read.

| Error | Meaning | What to do |
| --- | --- | --- |
| `state_migration_ambiguous` | The old key holds resources of two clouds, or of a provider this version does not recognise, and the new key is empty. Nothing was moved. | Move the state yourself with `tofu init -migrate-state` from a directory configured with the old key, or name the key to use in `--state-backend`. |
| `state_migration_raced` | The new key received a different state while the move was about to run. Nothing was moved. | Re-run once the other job has finished. |
| `state_migration_failed` | The scratch `tofu init` on the old or the new key failed. | Read the error text, which carries the tail of `tofu`'s output. |
| `state_migration_unverified` | After the copy the new key does not hold the resources that were copied. The old object is untouched. | Check the new key by hand before you re-run. |
| `state_migration_probe_failed` | The state at a key could not be read. | Check the bucket, the key and the credentials. |
| `state_shared_with_another_provider` | A remote key that does not name the provider holds another cloud's resources, and this apply would plan them as orphans to destroy. | Give each provider its own state: a key that names the provider in `--state-backend`, or a bucket-only `FLUID_STATE_BACKEND`. |

## Reporting to the Command Center (since 0.17.0)

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

The Command Center's host check refuses private and cloud-metadata addresses unless `FLUID_COMMAND_CENTER_HOST_ALLOWLIST` names the host; loopback is allowed.

**Switch it off** with `FLUID_COMMAND_CENTER_ENABLED=false`; the apply then prints `command center: run not reported (FLUID_COMMAND_CENTER_ENABLED is off)` when a Command Center is configured. The [environment variables](../advanced/environment-variables.md#command-center) page lists the other settings.

## Federated upstream check

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
| `--env` | none | Apply an environment overlay (dev / staging / prod / …); see [per-environment overlays](../recipes/per-environment-overlays.md). For a `plan.json` or a bundle the env is recorded in it; see [Plan binding](#plan-binding). |
| `--provider` | from the contract binding | Disambiguate the target when the contract spans several clouds or declares none. A value that contradicts the cloud the contract declares is rejected with `generate_iac_provider_mismatch` (exit 1) before anything is written. It cannot retarget a contract: change the `binding` instead, as in [Switch clouds](../recipes/switch-clouds.md). |
| `--project` *(native)* | from the contract | Override the project / account. |
| `--region` *(native)* | from the contract | Override the region / location. |

### Execution control

| Option | Default | Description |
| --- | --- | --- |
| `--mode` | `amend` | One of `dry-run`, `create-only`, `amend`, `amend-and-build`, `replace`, `replace-and-build`. |
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
| `--build-id BUILD_ID` | none | Filter build execution to a specific build by ID from the contract's `builds[]`. Needs `--mode amend-and-build` or `--mode replace-and-build`; any other mode is refused with `apply_build_id_requires_build_mode`. When unset and the mode requires builds, every build runs. |
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
| `apply_plan_mode_mismatch` | `--mode` differs from the mode the plan was made for. |
| `plan_env_mismatch` | A build mode is given an `--env` that differs from the plan's. |
| `bundle_env_mismatch` | `--env` differs from the env a bundle was built for. |
| `apply_build_id_requires_build_mode` | `--build-id` with a mode that runs no build. |
| `apply_mode_data_loss_blocked` | `replace` or `replace-and-build` without `--allow-data-loss`. |
| `opentofu_data_loss_gate` | An OpenTofu plan destroys a resource and `--allow-data-loss` is not set. |
| `opentofu_region_moved` | State holds the contract's resources in another region than its bindings name. |
| `packaging_transition_blocked` | A container's ownership flips under existing state. See [Packaging modes](#packaging-modes). |
| `opentofu_dataset_access_unreconciled` | State holds a BigQuery dataset an older forge-cli applied with an authoritative access list, and every entry of it is a grant the contract no longer makes. Revoke those entries on the dataset by hand, or keep one of them in `accessPolicy` for one apply. |
| `apply_state_backend_invalid`, `state_shared_with_another_provider`, `state_migration_*` | See [Remote state](#remote-state). |
| `generate_iac_provider_mismatch` | `--provider` contradicts the contract's binding. |
| `opentofu_engine_no_tofu` | The OpenTofu engine needs `tofu` and it is not on `PATH`. Install it, or pass `--ensure-opentofu`. |

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
