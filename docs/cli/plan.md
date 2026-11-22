# `fluid plan`

Stage 6 of the 11-stage pipeline. Generate an execution plan without applying changes, and emit the cryptographic digests (`bundleDigest` / `planDigest`) that stage 7 apply verifies before executing any DDL.

> **Why it matters**
> See exactly what will change — and prove it's what gets applied — before you touch production.
> `fluid plan` emits the action list plus a `planDigest` that `fluid apply` re-verifies, and records the `--mode` and `--env` it was made for, so the plan you reviewed is the plan that runs.

## Plan, then apply

```bash
# Plan, then apply the plan with the same mode
fluid plan contract.fluid.yaml --env prod --out runtime/plan.json
fluid apply runtime/plan.json --yes

# A build-augmented or destructive apply needs a plan made for that mode
fluid plan contract.fluid.yaml --env prod --mode amend-and-build --out runtime/plan.json
fluid apply runtime/plan.json --mode amend-and-build --yes
```

`CONTRACT` may also be a bundle (`.tgz`) written by [`fluid bundle`](./bundle.md).

## Syntax

```bash
fluid plan CONTRACT [--env ENV] [--mode MODE] [--out PATH]
                    [--provider NAME] [--project PROJECT] [--region REGION]
                    [--validate-actions] [--estimate-cost]
                    [--check-sovereignty | --no-check-sovereignty]
                    [--tofu [--state-backend SPEC] [--adopt-shared-container]
                     [--ensure-opentofu]]
                    [--html [PATH]] [--verbose]
```

`CONTRACT` is optional — when omitted, `plan` auto-finds `contract.fluid.yaml` in the current directory.

## Key options

| Option | Description |
| --- | --- |
| `--env` | Apply an environment overlay (dev, staging, prod). An environment with no overlay logs `overlay_not_found` and runs on the base contract; [`--env` and environment overlays](./validate.md#env-and-environment-overlays) says when it fails instead. See [Environments and overlays](../concepts/environments-and-overlays.md#when-no-overlay-matches). |
| `--mode` | Apply mode the plan is generated FOR. Stamped into `plan.json` so a later `fluid apply --mode X` can detect a mismatch and refuse (`apply_plan_mode_mismatch`, exit 1). Choices: `amend` \| `amend-and-build` \| `replace` \| `replace-and-build` \| `dry-run` \| `create-only`. When unset, the plan records no mode, and apply treats that as `amend`. |
| `--out`, `--output` | Write the plan JSON, default `plan.json` in the current directory |
| `--verbose`, `-v` | Show detailed action information |
| `--validate-actions` | Validate generated provider actions against the ProviderAction SDK schema |
| `--estimate-cost` | Ask the provider to estimate cost |
| `--check-sovereignty` | *(since 0.15.0)* Resolve a real sovereignty verdict and name which source produced it — the provider's `validate_sovereignty` hook when it has one (the `gcp` provider has one since 0.17.0), otherwise the built-in policy engine (the same checker [`fluid validate`](./validate.md) runs), otherwise `NOT CHECKED`. **Exits 1 when the check fails.** *([forge-cli #868](https://github.com/Agenticstiger/forge-cli/pull/868), since 0.30.0)* `plan` checks the policy without this flag too, and refuses before it writes a plan; the flag adds the provider's hook and the printed verdict. See [Sovereignty gate](#sovereignty-gate-since-0-15-0). |
| `--no-check-sovereignty` | *([forge-cli #868](https://github.com/Agenticstiger/forge-cli/pull/868), since 0.30.0)* Skip the sovereignty check `plan` runs by default, and write the plan whatever the policy says. Prints a warning and logs a WARNING (`sovereignty_check_skipped`). `fluid apply` keeps its own checks. |
| `--provider` | Override the provider from the contract |
| `--project` | Override the project / account from the contract |
| `--region` | Override the region / location from the contract |
| `--tofu` | *(since 0.31.0, [forge-cli #898](https://github.com/Agenticstiger/forge-cli/pull/898))* Also run `tofu plan` as `fluid apply` would, for the providers that apply through OpenTofu, and bind the saved plan into `plan.json`. `fluid apply plan.json` then applies exactly that plan. See [Saving the OpenTofu plan](#saving-the-opentofu-plan-tofu). |
| `--state-backend` | With `--tofu`: the OpenTofu state `fluid apply` will use, as on [`fluid apply`](./apply.md#remote-state). It belongs to `--tofu`. |
| `--adopt-shared-container` | With `--tofu`: as on apply, confirm taking ownership of a shared pool. Audited. |
| `--adopt-tables` | *(since 0.37.0)* With `--tofu`: plan the take-over of existing Glue tables that match the contract, each through an `import` block. Without `--tofu` the command exits with `plan_adopt_tables_needs_tofu`. See [Adopting existing tables](./apply.md#adopting-existing-glue-tables-since-0-37-0). |
| `--ensure-opentofu` | With `--tofu`: provision a pinned, verified `tofu` if it is missing, as on apply. |
| `--html` | Generate an HTML visualization with a mermaid-rendered action DAG (colour-coded by mode: blue=amend, red=replace, grey=skipped). Optional path argument; defaults to `plan.html` in the current directory. |

*(since 0.31.0, [forge-cli #905](https://github.com/Agenticstiger/forge-cli/pull/905))* With `--tofu`, the saved plan is encrypted when `FLUID_STATE_ENCRYPTION` is set, and `fluid apply` of that plan needs the same setting. See [State and plan encryption](./apply.md#state-and-plan-encryption).

## Plan binding

`0.8.0` plans embed two cryptographic digests:

- `bundleDigest` — SHA-256 of the tgz bundle the plan was derived from (matches `MANIFEST.json`'s merkle root). An empty string when planning from a raw YAML contract.
- `planDigest` — SHA-256 of the plan's action list itself (internal consistency check).
- `packetDigest` — *(since 0.33.0, [forge-cli #985](https://github.com/Agenticstiger/forge-cli/pull/985))* SHA-256 of the bundle file's bytes, for a plan made from a bundle. `bundleDigest` names the resolved contract and the files it packs; `packetDigest` names the exact archive, so the plan applies only with the bytes it was made from. It sits under `planDigest`. See [The packet digest](./bundle.md#the-packet-digest).

`fluid apply` re-verifies both before executing any DDL. Helpers live in `fluid_build/forge/core/plan_digest.py`:

- `compute_plan_digest(plan)` — canonical JSON → SHA-256
- `inject_digests(plan, bundle_digest)` — adds both fields
- `verify_plan_binding(plan_path, bundle_path)` — re-computes and compares; raises `PlanBindingError` on mismatch
- `PlanBindingError.kind` is a stable string (`"bundle-mismatch"`, `"plan-tamper"` or `"bundle-missing"`; *on `main`,* also `"packet-mismatch"` and `"packet-missing"`). `fluid apply` surfaces it as the event `apply_plan_digest_<kind>` with `-` written as `_` — CI log parsers can key off it.

The `--no-verify-plan-binding` flag on `apply` is the DR escape hatch for bypassing this check; see [`fluid apply`](./apply.md#safety-gates).

### What `plan.json` records

Besides the digests, `plan.json` carries what `apply` needs to refuse a plan that is being used for something it was not made for. This is a trimmed excerpt of a plan made with `fluid plan contract.fluid.yaml --env dev --mode amend-and-build`:

```json
{
  "mode": "amend-and-build",
  "bundleDigest": "",
  "planDigest": "sha256:227ff7dab5d3a...",
  "contract_metadata": {
    "env": "dev",
    "id": "gold.customer.analytics_360_v1",
    "name": "Customer 360 Analytics",
    "source_path": ".../contract.fluid.yaml",
    "version": "0.7.5"
  },
  "contract": { "...": "the resolved contract, overlay applied" },
  "actions": [ "..." ]
}
```

| Field | Written when | What `apply` does with it |
| --- | --- | --- |
| `mode` | Always; `null` without `--mode`. | `fluid apply plan.json --mode Y` with a `Y` other than the recorded mode is refused with `apply_plan_mode_mismatch`, before any build. A missing mode and `amend` count as the same. |
| `contract_metadata.env` | `--env` was given, or the plan was made from a bundle that records an env. | In a build mode (`amend-and-build`, `replace-and-build`), `apply` without `--env` runs the builds in that env, and a different `--env` is refused with `plan_env_mismatch`. See [`fluid apply`](./apply.md#the-plan-s-environment). |
| `contract_metadata.source_contract` | The plan was made from a bundle. | Names the source contract file the bundle was built from. |
| `contract` | Always. | Apply runs the embedded contract, which already has the overlay applied. *([forge-cli #714](https://github.com/Agenticstiger/forge-cli/pull/714), since 0.20.0)* It validates it against its schema first, on both engines, and refuses a plan with no embedded contract with `apply_plan_missing_contract`. See [Contract validation](./apply.md#contract-validation). |

*(since 0.33.0, [forge-cli #972](https://github.com/Agenticstiger/forge-cli/pull/972) and [#985](https://github.com/Agenticstiger/forge-cli/pull/985))*
A plan made from a bundle records two more fields. This is a trimmed excerpt of `fluid plan runtime/bundle.tgz --out runtime/plan.json` on the bundle from [The dbt project of a dbt build](./bundle.md#the-dbt-project-of-a-dbt-build):

```json
{
  "bindingMode": "bound",
  "bundleDigest": "sha256:c8e0d69396d694546601d6dfd9cc0be1b87ee6d5609b24a33092706005d78eed",
  "packetDigest": "sha256:b92783ba770db2b65e7934cb7a56330c7760fb2fb203afe877bf9026c491543f",
  "planDigest": "sha256:cfeb855c2f97cd571e8e1db9239ad3ae3b09b6c0a92cbec4f8899870d0c51c65",
  "dbtProjects": {
    "transform": {
      "digest": "sha256:e73871e51224311be6a6eee84689d8412dbfc0a6a0992331a5cb83c7d033e35e",
      "files": {
        "dbt_project.yml": "sha256:8d5d99087d75f8c1147d4e7195c15278e9b5f1d5fa8ba14dc46887b17c0af0b0",
        "models/orders.sql": "sha256:4e65c7c3c4bc6e8c6604aad92341c4f8a0dfb3a8c3c7ef8c4e741996140d1ee1"
      }
    }
  },
  "...": "contract, contract_metadata, actions"
}
```

| Field | Written when | What `apply` does with it |
| --- | --- | --- |
| `packetDigest` | The plan was made from a bundle. | Compares it with the sha256 of the bundle file it is given. Other bytes are refused with `apply_plan_digest_packet_mismatch`; a bound plan without one, with `apply_plan_digest_packet_missing`. See [`fluid apply`](./apply.md#the-packet). |
| `dbtProjects` | The bundle packs the dbt project of a dbt build. | Keyed by build id: the sha256 of each project file, by path inside the project, and their merkle `digest`. `fluid apply` compares the checkout's dbt files with it before anything runs. A changed, added or removed file is refused with `apply_plan_digest_bundle_mismatch`. See [`fluid apply`](./apply.md#the-dbt-project). |

Both are under `planDigest`, so editing either is a plan tamper. `fluid plan` prints one line per bound project (`dbt project bound: transform (2 files, sha256:e738...)`). A plan made from a contract file, not a bundle, has `bindingMode: "raw"` and neither field: it binds no dbt project, because there is no bundle to take the files from.

A bundle is never re-overlaid: `fluid plan bundle.tgz --env prod` on a bundle built for `dev` is refused with `bundle_env_mismatch`. Plan the bundle without `--env`, or rebuild it with `fluid bundle <contract> --env prod --format tgz`.

## Saving the OpenTofu plan (`--tofu`)

*(since 0.31.0, [forge-cli #898](https://github.com/Agenticstiger/forge-cli/pull/898))* Without `--tofu`, `fluid plan` never runs `tofu plan`, and `fluid apply` plans and applies in one step. A manual approval in CI then covers forge's abstract `plan.json`, not the OpenTofu diff that actually runs. With `--tofu`, the approval binds the OpenTofu plan:

```bash
fluid plan contract.fluid.yaml --env prod --out runtime/plan.json \
  --tofu --state-backend s3://<your-state-bucket>/fluid/sales.tfstate
fluid apply runtime/plan.json --yes
```

`--tofu` works for the providers whose apply runs OpenTofu (`aws`, `gcp`, `snowflake`, `confluent`, `databricks`). For a contract whose apply engine is `native`, such as `local`, it stops with `plan_tofu_unsupported`: plan it without `--tofu`.

It opens the OpenTofu engine the way `fluid apply` does: the same state backend, the same environment for `tofu`, the same `tofu init` (with the S3 lock), and the same guards before the plan, among them the [Iceberg catalog-move guard](./apply.md#iceberg-catalog-move-guard) and the packaging checks. It then adopts pre-existing resources and runs `tofu plan -out`. The step runs after the bundle and sovereignty gates, so a refused plan leaves no saved plan behind. Next to `plan.json` it writes three files, each readable by the owner only (mode `0600`), named after `--out`:

| File | What it is |
| --- | --- |
| `plan.tfplan` | The saved OpenTofu plan. `fluid apply` runs it unchanged. |
| `plan.tfplan.json` | `tofu show -json` of that plan |
| `plan.gitlab-tofu.json` | The summary GitLab reads as `artifacts:reports:terraform` |

With `--out runtime/plan.json` they are `runtime/plan.tfplan`, `runtime/plan.tfplan.json` and `runtime/plan.gitlab-tofu.json`. The run prints the change counts as `tofu plan: +<add> ~<change> -<remove>` and the three file names.

*(since 0.33.0, [forge-cli #999](https://github.com/Agenticstiger/forge-cli/pull/999))* The run also prints the target it bound, as `target:      aws account 111111111111, region eu-west-1`. When `tofu init` wrote a dependency lock, the plan writes it as a further file next to `plan.json`, `plan.terraform.lock.hcl` (named after `--out`, mode `0600`), and the `saved plan:` line lists it. A module that uses only built-in resources has no lock and no such file.

`plan.json` gains an `opentofuPlan` record, and `planDigest` covers it:

| Field | Holds |
| --- | --- |
| `planFile` | The file name of the saved plan, next to `plan.json` |
| `sha256` | `sha256:<hex>` of the saved plan's bytes |
| `provider`, `state` | The provider and the state location the plan was made for |
| `stateLineage`, `stateSerial` | The version of that state when the plan was made. Left out when the state could not be read |
| `changes` | The `add`, `change` and `remove` counts |
| `imports` | The addresses of pre-existing resources the plan adopts |
| `lockFile`, `lockSha256` | *(since 0.33.0, [forge-cli #999](https://github.com/Agenticstiger/forge-cli/pull/999))* The provider lock written with the plan, and its `sha256:<hex>`. Left out when there is no lock |
| `target` | *(since 0.33.0, [forge-cli #999](https://github.com/Agenticstiger/forge-cli/pull/999))* What the plan is bound to besides its state: see [The target a plan is bound to](#the-target-a-plan-is-bound-to) |

### The target a plan is bound to

*(since 0.33.0, [forge-cli #999](https://github.com/Agenticstiger/forge-cli/pull/999))* OpenTofu applies a saved plan on whatever account the apply's credentials reach, and does not check it. So the plan records its target, and `fluid apply` reads the target again, before it applies or changes anything, and refuses another one. `target` holds:

| Field | Holds |
| --- | --- |
| `identity` | What the provider reads, as `{field: value}`: the fields below |
| `unread` | Each identity field the plan's runner could not read, with the reason |
| `backend` | A sha256 of the state backend block. Empty for local state |
| `tofu` | The `tofu` version |
| `providers` | The provider versions `tofu init` locked, by source address |

The identity comes from the module's `provider` block where forge sets one (the AWS region, from the binding's region), and otherwise from the environment `tofu` gets:

| Provider | Field | Read from |
| --- | --- | --- |
| `aws` | `account` | STS `GetCallerIdentity` with the run's credentials. It needs no IAM permission, and it needs `boto3` (`pip install 'data-product-forge[aws]'`) |
| `aws` | `region` | `provider.aws.region`, else `AWS_REGION`, else `AWS_DEFAULT_REGION`, else *(on `main`, [forge-cli #1002](https://github.com/Agenticstiger/forge-cli/pull/1002))* the `region` of the profile in the shared config file (needs `boto3`) |
| `gcp` | `project` | `GOOGLE_PROJECT`, `GOOGLE_CLOUD_PROJECT`, `GCLOUD_PROJECT` or `CLOUDSDK_CORE_PROJECT`, in that order. The project of the credentials is not read |
| `gcp` | `region` | `GOOGLE_REGION`, `GCLOUD_REGION` or `CLOUDSDK_COMPUTE_REGION`, in that order. A missing region is not named as unread |
| `snowflake` | `organization`, `account` | `SNOWFLAKE_ORGANIZATION_NAME` and `SNOWFLAKE_ACCOUNT_NAME`. Forge sets both from `SNOWFLAKE_ACCOUNT` when it has the `<organization>-<account>` form, and a bare account locator leaves both unread. Stored in upper case |
| `databricks` | `host` | `DATABRICKS_HOST`. Stored in lower case, without a trailing `/` |

An identity field the run cannot read, such as the AWS account without `boto3` or credentials, is left out of `identity`, and the plan prints it, for example `account not bound: boto3 is not installed (pip install 'data-product-forge[aws]')`. A provider with no row here, `confluent` or a plugin installed through an entry point for one, binds no identity field, and still binds the backend and the `tofu` and provider versions. *(since 0.33.0, [forge-cli #1002](https://github.com/Agenticstiger/forge-cli/pull/1002))* The plan then prints `target: forge reads no account, project or host for <provider>, so the saved plan is not bound to one`, and logs it at WARNING as `plan_tofu_target_provider_unbound`.

*(since 0.33.0, [forge-cli #1002](https://github.com/Agenticstiger/forge-cli/pull/1002))* The AWS profile is `AWS_PROFILE`, else `AWS_DEFAULT_PROFILE`, the order of the SDK that the `hashicorp/aws` provider is built on. With neither set, the profile is `default`. It is the profile for the account lookup and for the region fallback in the row above. [Applying a saved OpenTofu plan](./apply.md#applying-a-saved-opentofu-plan) lists what `fluid apply` refuses.

**Brownfield adoption.** A saved plan carries the state it was made from, so planning must leave the state as it was. Adoption runs `tofu import` to confirm each resource exists, hands the import back with `state rm`, and puts it into the plan as an `import` block. The reviewer sees the resource listed as to be imported, and the apply does the import. If the hand-back fails, the plan stops with `plan_tofu_adoption_not_released` and prints the `tofu state rm` command to run.

Other errors:

| Event | Meaning |
| --- | --- |
| `plan_tofu_unsupported` | The contract's apply engine is not OpenTofu |
| `plan_tofu_show_failed` | `tofu show -json` could not read the plan it just saved |
| `plan_tofu_adoption_not_released` | An adopted resource could not be released from state; see above |

::: warning What to know before you store a saved plan
- **The plan files are plaintext.** `plan.tfplan.json` holds every sensitive value in clear, as `tofu show -json` does. Mode `0600` does not protect a CI artifact download. Keep them in protected, short-lived job artifacts. With [`FLUID_STATE_ENCRYPTION`](./apply.md#state-and-plan-encryption) set, OpenTofu encrypts the saved plan.
- **The digests are not signatures.** `planDigest` and `opentofuPlan.sha256` catch a plan that was changed by accident or by an edit. They do not prove who wrote it. Store the plan artifacts where only the plan job can write them, as for any `tofu apply <planfile>`: a forged saved plan can do anything OpenTofu can do on the apply runner.
- **Planning writes state.** `fluid plan --tofu` moves a legacy state key as `fluid apply` does, and its adoption imports and then removes. The net content of the state is unchanged, but the plan role needs write access to the state, and to the lock.
- **Plan and apply must share a remote state.** Local state in a CI workspace does not reach the apply job, and the plan is then refused as stale or as made for another state. *(since 0.33.0, [forge-cli #999](https://github.com/Agenticstiger/forge-cli/pull/999))* With a state backend that both runners reach, a plan made on one runner applies on another, at another checkout path: hand over `plan.json`, the saved plan and the lock. A plan made against existing local state that the applying runner does not have is refused as `apply_plan_digest_tofu_plan_state_missing`. A first plan on local state is not refused, but the state it creates stays on the runner that applied it.
:::

## Sovereignty gate (since 0.15.0)

*([forge-cli #868](https://github.com/Agenticstiger/forge-cli/pull/868), since 0.30.0)* `fluid plan` checks the contract's sovereignty policy by default, before it plans. It asks the built-in policy engine, the checker [`fluid validate`](./validate.md) runs, and refuses what `validate` refuses:

- Under `enforcementMode: strict`, the schema default, the findings that block include a binding outside `allowedRegions`, one in a region of another jurisdiction, and one on AWS, GCP, Azure or Databricks that declares no region (the platform would pick it).
- In every mode, a binding in a region listed in `deniedRegions` blocks.

A refusal exits 1 with `ERR_SOVEREIGNTY_VIOLATION` and writes no plan. A plan file an earlier run left at `--out` stays as it was. The check builds no provider, so it needs no cloud SDK and no credentials. When nothing blocks it prints nothing, and the plan is written as before: for a contract with no `sovereignty` block, and for one whose findings are only warnings or info lines (under `advisory` or `audit`, every finding but a denied region).

This is the refusal on 0.30.0 for a contract with `enforcementMode: strict`, `allowedRegions: [eu-central-1, eu-west-1]`, `deniedRegions: [us-west-2]` and one binding in `us-west-2`:

```text
Sovereignty check: 3 finding(s)  — source: built-in policy engine, enforcementMode=strict
  - ❌ [customer_events] Region 'us-west-2' is explicitly denied by sovereignty policy
   💡 Use one of the allowed regions: eu-central-1, eu-west-1
  - ❌ [customer_events] Region 'us-west-2' not in allowed regions list
   💡 Allowed regions: eu-central-1, eu-west-1
  - ❌ [customer_events] Region 'us-west-2' (jurisdiction: US) does not match required jurisdiction: EU
   💡 Consider using regions in EU jurisdiction

❌ Sovereignty check FAILED — enforcementMode is 'strict'.
❌ sovereignty_violation  [ERR_SOVEREIGNTY_VIOLATION]
  command: plan
  contract: .../contract.fluid.yaml
  errors: ["[customer_events] Region 'us-west-2' is explicitly denied by sovereignty policy", "[customer_events] Region 'us-west-2' not in allowed regions list", "[customer_events] Region 'us-west-2' (jurisdiction: US) does not match required jurisdiction: EU"]
  message: The contract's sovereignty policy (enforcementMode strict) blocks where it puts data, so fluid plan wrote no plan.
...
```

Each finding names its expose in brackets, and the error carries the findings as `errors`. The suggestions printed after it are listed under [`sovereignty_violation`](../advanced/error-codes.md#sovereignty-violation).

Up to 0.29.0 the check was opt-in: plain `fluid plan` wrote a plan for this contract and exited 0. To write the plan anyway now, pass [`--no-check-sovereignty`](#no-check-sovereignty).

::: warning Behavior change in 0.30.0
A script or pipeline that runs `fluid plan` on a contract `fluid validate` refuses for sovereignty now stops at plan, with exit 1 and no plan file. See [Changes in 0.30.0](../upgrading.md#changes-in-0-30-0).
:::

### `--check-sovereignty`

`--check-sovereignty` runs the same check first. If nothing blocks, plan then resolves a verdict and prints it, naming which source answered, in a fixed order:

1. The target provider's `validate_sovereignty` hook, when it returns a verdict.
2. Otherwise the **built-in policy engine** — the same sovereignty checker `fluid validate` runs, so the two stages cannot reach opposite verdicts on the same contract.
3. Otherwise `Sovereignty check: NOT CHECKED`, which is also what a contract declaring no `sovereignty` block gets. Exit code stays 0.

On `aws` the answer comes from the built-in policy engine, because the provider has no hook:

```
Sovereignty check: PASS  — source: built-in policy engine, enforcementMode=strict; the aws provider has no sovereignty hook
```

Since 0.17.0 the `gcp` provider has a hook, so a `gcp` contract is answered by the provider. The hook runs the same contract checks and then checks where the plan would put things: the planned actions and the OpenTofu resources the apply would emit, such as the BigQuery dataset and the Cloud KMS key ring. A binding with no region is checked as the placement the platform would give it, which for BigQuery is `US`. This is real output for a contract whose allowed region is `europe-west1`, first with its binding in that region and then in `us-central1`:

```
Sovereignty check: PASS  — source: gcp provider hook
```

```
Sovereignty check: 10 violation(s)  — source: gcp provider hook
  - orders: Region 'us-central1' not in allowed regions list
  - orders: Region 'us-central1' (jurisdiction: US) does not match required jurisdiction: EU
  - dataset_sales: Region 'us-central1' not in allowed regions list
  ...
  - google_kms_key_ring.gold_sales_orders_v1_sales_kms: Region 'us-central1' not in allowed regions list
  ...
❌ sovereignty_violation  [ERR_SOVEREIGNTY_VIOLATION]
```

*([forge-cli #868](https://github.com/Agenticstiger/forge-cli/pull/868), since 0.30.0)* The second output predates 0.30.0. Now the default check runs first and refuses that contract under `strict` before the hook is asked: 0.30.0 prints the built-in engine's two findings for the `us-central1` binding (`not in allowed regions list` and the jurisdiction mismatch) and writes no plan. The hook's verdict is printed when the engine finds no error.

The pipeline `fluid generate ci --system github` writes runs `fluid plan ... --check-sovereignty` in its plan job, and the Jenkins pipeline's stage 6 does the same.

A failing check prints a `Sovereignty check: N finding(s)` header naming the source, then its findings as a bulleted list, then `❌ Sovereignty check FAILED`, and **exits 1**. *([forge-cli #868](https://github.com/Agenticstiger/forge-cli/pull/868), since 0.30.0)* It writes no plan, as the default check does. Up to 0.29.0 the plan file was still written, and only the non-zero exit stopped a pipeline.

On `0.14.1` and earlier none of that happened. No shipped provider implemented `validate_sovereignty`, the hook helper returned an empty violation list for a hook that was absent (and for one that raised, because the invoker swallows the exception and hands back its first argument), and an empty list rendered as `Sovereignty check: PASS` with exit 0 — printed on contracts `fluid validate` rejects with two residency errors. The flag was also skipped outright when the provider failed to build. `PASS` is now printed only when a check actually ran and found nothing.

::: warning Behavior change in 0.15.0
A pipeline that already passes `--check-sovereignty` moves from a step that could only ever be green to one that can fail. Two rules decide whether it blocks: a region named in `deniedRegions` is an **error in every mode**, and everything else follows the contract's own `sovereignty.enforcementMode`, whose default is `strict`. Full table: [Governance → Sovereignty enforcement modes](../advanced/governance.md#sovereignty-enforcement-modes-since-0-15-0).
:::

### `--no-check-sovereignty`

*([forge-cli #868](https://github.com/Agenticstiger/forge-cli/pull/868), since 0.30.0)* `--no-check-sovereignty` skips the check and writes the plan whatever the policy says:

```bash
fluid plan contract.fluid.yaml --no-check-sovereignty --out runtime/plan.json
```

```text
⚠️  Sovereignty check skipped (--no-check-sovereignty): the plan is written whatever the contract's sovereignty policy says.
```

It also logs a WARNING with the event `sovereignty_check_skipped`, so the skip is on record. It changes nothing in `fluid apply`, which keeps its own checks; [Where sovereignty is enforced](../advanced/governance.md#where-sovereignty-is-enforced) lists them.

## Examples

### Basic plan

```bash
fluid plan contract.fluid.yaml
fluid plan contract.fluid.yaml --verbose
fluid plan contract.fluid.yaml --env prod --out runtime/prod-plan.json
```

### With HTML visualization (mermaid DAG)

```bash
fluid plan contract.fluid.yaml --html
# writes plan.json + plan.html in the current directory
```

The HTML report contains:

- A mermaid `graph TD` of the action DAG with per-mode colour coding
- A legend for the colour classes
- A collapsible raw-JSON drill-down for each action

Opening `plan.html` in a browser loads mermaid from `cdn.jsdelivr.net` (required online on first view). `securityLevel: 'strict'` is set in the mermaid init call; action ID / op strings flow through `html.escape(quote=True)` before rendering, so malicious contract values cannot smuggle `<script>` into a label.

For a richer DOT / Mermaid action-graph export, use [`fluid viz-graph`](#visualizing-the-plan-—-fluid-viz-graph) below — `plan` itself only emits the JSON plan and the optional `--html` summary.

### Hand-off to apply

```bash
fluid plan contract.fluid.yaml --env prod --mode amend --out runtime/plan.json
fluid apply runtime/plan.json --mode amend --yes
# apply re-verifies bundleDigest + planDigest, the mode and the env before any DDL
```

`amend` is the default, so `--mode amend` may be left off on both sides. For any other mode, pass the same `--mode` to both commands: `fluid apply` refuses a plan whose recorded mode differs, with `apply_plan_mode_mismatch`.

## Notes

- `plan` is the safest place to preview a provider override or environment overlay before you run `apply`.
- *(since 0.27.0, [forge-cli #813](https://github.com/Agenticstiger/forge-cli/pull/813))* For a contract with `builds`, `plan` prints the warning [`fluid validate` gives](./validate.md#an-id-the-build-phase-refuses) for an `id` or `builds[].id` the build phase refuses, and still writes the plan, whatever `--mode` says. `fluid apply` in a build mode refuses that id before it applies anything; see [Build ids](./apply.md#build-ids).
- The generated plan can be passed to [`fluid apply`](./apply.md) — the digests pin the apply to exactly this plan. Made with `--tofu`, the plan also binds the OpenTofu plan, and the apply runs that one.
- When planning from a tgz bundle directly, `bundleDigest` is populated from `MANIFEST.json`. When planning from a raw YAML contract, `bundleDigest` is an empty string and only `planDigest` is verified.

## Visualizing the plan — `fluid viz-graph`

`fluid plan --html` emits a quick HTML summary alongside `runtime/plan.json`. For richer visualization — themed lineage and build-DAG diagrams — use `fluid viz-graph`:

```bash
fluid viz-graph CONTRACT [options]
```

### Key options

**Input / output**

| Option | Description |
| --- | --- |
| `CONTRACT` | Path to `contract.fluid.yaml` (positional). Optional, and ignored, when `--mesh` is used. |
| `--env ENV` | Apply an environment overlay |
| `--plan PATH` | Overlay a saved `runtime/plan.json` so build actions are shown on the graph |
| `--out PATH`, `--output PATH` | Output file path (default: `runtime/graph/contract.svg`) |
| `--mesh` | Mesh mode: walk `**/*.fluid.yaml` under the mesh root and render the cross-product DAG (SDP→ADP→CDP) built from each contract's `consumes[]`, instead of one contract's internal DAG. |
| `--mesh-root DIR` | Root directory for the mesh-mode walk. Default `.`. Ignored without `--mesh`. |

**Format & appearance**

| Option | Description |
| --- | --- |
| `--format {dot,svg,png,html,mermaid,json}` | Output format (default: `svg`). `svg` / `png` / `html` need Graphviz; `dot` / `mermaid` / `json` are pure-text. Passing `mermaid` or `json` without `--mesh` is rejected with `ERR_VALIDATION_ERROR`. |
| `--theme NAME` | Color theme: `dark` (default), `light`, `minimal` or `blueprint` |
| `--custom-theme PATH` | Path to a custom theme JSON/YAML file |
| `--rankdir {LR,TB,RL,BT}` | Graph layout direction (default: `LR`) |
| `--title TEXT` | Custom title for the graph |

**Content**

| Option | Description |
| --- | --- |
| `--show-legend` | Add a legend explaining node types |
| `--collapse-consumes` / `--collapse-exposes` | Collapse consumed sources or exposed artifacts into one node each |
| `--show-descriptions` | Include descriptions in node labels |
| `--hide-metadata` | Hide domain / layer metadata tags |
| `--max-label-length N` | Max label length before truncation (default: `50`) |

**Behavior**

| Option | Description |
| --- | --- |
| `--open` | Open the output file in the default viewer when done |
| `--force` | Overwrite an existing output file without prompting |
| `--quiet` | Suppress non-error output |
| `--graphviz-args ...` | Extra args passed through to Graphviz `dot` |
| `--debug` | Enable debug output and keep intermediate files |

### Examples

```bash
fluid viz-graph contract.fluid.yaml
fluid viz-graph contract.fluid.yaml --format html --theme dark --open
fluid viz-graph contract.fluid.yaml --plan runtime/plan.json --show-legend
fluid viz-graph contract.fluid.yaml --out docs/graph.svg --title "Customer Churn Pipeline"
```

Requires Graphviz (`dot`) on `PATH` for `svg`, `png`, and the enhanced `html` output (`brew install graphviz` on macOS; `apt install graphviz` on Debian/Ubuntu). Without Graphviz, `fluid viz-graph --format svg` (and `png`, `html`) does not fail: it logs `graphviz_not_available_writing_dot`, writes the graph as DOT next to the requested output (`runtime/graph/contract.dot` for the default path) and exits 0. Use `--format dot` to ask for DOT directly. There is no `fluid graph` command. A compatibility entry point `fluid viz-plan` still exists for rendering a saved plan as HTML, but new work should prefer `fluid viz-graph --plan runtime/plan.json`.
