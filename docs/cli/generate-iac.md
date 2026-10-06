# `fluid generate iac`

Review-only emit of an OpenTofu module from a FLUID contract. `fluid apply` against a cloud provider auto-runs the same generator and hands the result to `tofu apply` — no flag needed; engine selection is per-provider (`local` keeps its native apply, `aws` / `gcp` / `snowflake` route through OpenTofu).

::: tip Available in 0.8.3 (PR #140)
`v0.8.3` introduces the **OpenTofu autogenerator**: `fluid apply` for cloud providers now compiles the contract to a deterministic OpenTofu `main.tf.json` and delegates apply / state / drift / idempotency to the `tofu` binary. `local` keeps its native DuckDB apply — no `tofu` needed for the local-first onboarding path.
:::

## Syntax

```bash
fluid generate iac <contract> [--provider PROVIDER] [--out DIR] [--env NAME] [--shadow] [--validate]
                             [--allow-empty]
```

| Option | Description |
|---|---|
| `<contract>` | Path to FLUID contract file (YAML/JSON). |
| `--provider {auto,aws,confluent,gcp,snowflake}` | Target cloud. Default `auto` — inferred from the contract. *(since 0.15.0)* `--provider` **disambiguates; it does not retarget.** A value that contradicts every cloud the contract's `binding` declares is a hard `generate_iac_provider_mismatch` error, raised before anything is written — see [the provider flag does not retarget](#the-provider-flag-does-not-retarget-since-0-15-0). As of 0.18.1, `--provider confluent` is refused before the command runs; see [Provider flag limits](#provider-flag-limits). |
| `--out`, `-o DIR` | Output directory for the emitted module. Default `runtime/iac`. |
| `--env NAME` | Environment overlay name (matches your contract's overlay block, e.g. `dev` / `staging` / `prod`). |
| `--shadow` | After emitting, shadow-compare resource parity against the native planner. Catches a divergence between the OpenTofu emission and what `fluid plan` would have produced. |
| `--validate` | After emitting, run `tofu validate` on the module (requires `tofu` on `PATH`). |
| `--allow-empty` | *(since 0.15.0)* Emit a module with zero resources instead of failing (default: a resource-free module is an error). The run then prints an explicit warning that it provisions nothing. See [A resource-free module is an error](#a-resource-free-module-is-an-error-since-0-15-0). |

## Examples

```bash
# Review what fluid apply would emit for AWS
fluid generate iac contract.fluid.yaml --provider aws --out ./review

# Per-environment review
fluid generate iac contract.fluid.yaml --env staging --out ./review/staging

# Emit + validate against the planner + tofu validate in one pass
fluid generate iac contract.fluid.yaml --shadow --validate

# GCP: name the project on the global flag, before the subcommand
fluid --project my-project generate iac contract.fluid.yaml --provider gcp --out ./review
```

The emitted directory contains `main.tf.json` (the compiled module), provider blocks, and a `manifest.json` describing how the contract mapped to resources. Inspect it before you run `fluid apply`.

## The provider flag does not retarget (since 0.15.0)

`--provider` exists to **disambiguate** a contract that spans clouds or declares none. Retargeting a data product is done by editing `binding` — as `examples/sovereignty-platform-swap/` does, compiling one contract against AWS, Google Cloud and Snowflake with the `binding` block as the only difference between the three files, and never passing the flag.

Since `0.15.0` the requested provider must be among the clouds the contract declares, and a contradiction raises `generate_iac_provider_mismatch`. A contract that declares no cloud at all still falls through untouched, since that is the case the flag exists for.

::: warning Behavior change in 0.15.0
On `0.14.1` and earlier, `fluid generate iac <contract> --provider gcp` against an AWS- or local-bound contract emitted a **resource-free `main.tf.json` and exited 0**. Adding `--validate` made it worse rather than catching it: `tofu validate` genuinely reports success for a configuration with no resources, so the operator generated, validated, saw green and had provisioned nothing.

Where a binding was shape-compatible across clouds the result was worse than empty — an S3-bound expose fed to the GCP emitter produced a `google_storage_bucket` named after the S3 bucket and carrying `location: us-east-1`, which is not a valid GCS location. That is why the gate sits on the **provider/binding pair** rather than on the output.

The same hole was open on [`fluid apply --provider`](./apply.md), the command that actually provisions, which reported `tofu plan: +0 ~0 -0` with exit 0. Both commands resolve through one resolver, so one gate covers both, and the OpenTofu engine's broad exception fallback now re-raises this specific error instead of quietly routing the wrong target to the native engine.
:::

## Provider flag limits

As of 0.18.1, `fluid` checks a `--provider` value against the providers it has registered (`aws`, `datamesh_manager`, `gcp`, `local`, `redshift`, `snowflake`) before it runs the subcommand, and exits 2 on a miss. `confluent` is one of this command's accepted choices and not one of those:

```text
⚠️ Unknown provider 'confluent' — installed providers: aws, datamesh_manager, gcp, local, redshift, snowflake (see `fluid providers`)
```

Leave `--provider` off for a contract bound to Confluent: `auto` detects the cloud from the binding, and `fluid generate iac contract.fluid.yaml` on a contract with `binding.platform: confluent` wrote a module with `provider: confluent`.

`--provider gcp` logs `Provider 'gcp' requires --project to be specified` unless the project is set. The error does not stop the command. Pass the global `--project` before the subcommand (`fluid --project my-project generate iac ...`) or set `FLUID_PROJECT`.

## A resource-free module is an error (since 0.15.0)

Nothing downstream can catch a module that provisions nothing — `tofu validate` calls it valid — so since `0.15.0` `fluid generate iac` fails with `generate_iac_empty_module` instead of printing a warning and exiting 0.

It is the backstop for the emit-when-derivable emitters, which can legitimately skip a resource on a *matching* provider when a required binding input is absent. The message names the `binding.location` fields to check, plus the [`fluid validate`](./validate.md) gates that name the specific missing field. Pass `--allow-empty` when a module that provisions nothing is genuinely intended.

## Apply via OpenTofu

```bash
# Cloud providers auto-route through OpenTofu on v0.8.3 — no flag needed.
fluid apply contract.fluid.yaml --provider aws --yes
# → ... [iac] tofu init
# → ... [iac] tofu plan
# → ... [iac] plan-binding verified
# → ... [iac] tofu apply -auto-approve
```

Engine selection is automatic and per-provider (`apply.py::resolve_apply_engine`) — `local` keeps its native DuckDB apply; `aws` / `gcp` / `snowflake` route through OpenTofu. There is no `--engine` flag on `fluid apply`.

## Supported providers

`v0.8.3` ships built-in IaC plugins for three cloud targets. Each is a modular `IacProviderPlugin` (dbt-adapter pattern); third parties can register their own via the [Provider SDK](/forge_docs/providers/custom-providers).

| Provider | Resources emitted |
|---|---|
| `aws` | S3 buckets / IAM roles + policies / Glue databases + tables + column comments (for an Iceberg expose, only when its catalog is Glue: [forge-cli #707](https://github.com/Agenticstiger/forge-cli/pull/707), unreleased) / Athena workgroups / Lake Formation grants, with a contract's `columnRestrictions` written as excluded columns *(0.17.0)* / KMS keys and aliases for `binding.encryption.kms` and S3 lifecycle rules for `lifecycle.expire` *(0.16.5)* |
| `gcp` | BigQuery datasets + tables / `google_bigquery_dataset_iam_member` grants *(0.17.0)* / GCS buckets / BigLake-Iceberg warehouse buckets *(0.14.0)* / Pub/Sub topics, with the binding's region as `message_storage_policy.allowed_persistence_regions` / Cloud KMS key rings and keys, Data Catalog taxonomies and policy tags, and a `terraform_data` partition-replace trigger *(0.17.0)* |
| `snowflake` | Databases / schemas / tables / column comments (Horizon-aware) / file formats / stages / external volumes + Glue catalog integrations for Iceberg exposes *(0.13.1)* |

*(since 0.15.0)* A **GCP** expose resolves to its target from the whole binding, not from `binding.format` alone: an explicit GCP `format` wins, otherwise the shape of `binding.location` decides (`dataset` → BigQuery, `bucket` → Cloud Storage, `topic` → Pub/Sub). That brings GCP in line with `aws` and `snowflake`, which already dispatch on the location shape and let `format` merely refine. Previously the emitter matched five `format` spellings only — two of which (`bigquery_view`, `gcs_bucket`) appear in no shipped `fluid-schema-*.json` — while the one schema-valid Cloud Storage spelling, `gcs_file`, matched none of them. So `{platform: gcp, format: gcs_file, location: {bucket: acme-raw}}` validated clean and emitted **nothing**, on a correctly auto-detected provider. Under [the empty-module rule](#a-resource-free-module-is-an-error-since-0-15-0) that silent no-op is now a hard failure, and [`fluid validate`](./validate.md#gcp-binding-checks-since-0-15-0) reports it earlier still.

The same class of bug affected `aws`, which filtered `exposes[]` by comparing `binding.platform` to the literal `"aws"` — so `platform: glue`, `s3`, `athena` or `redshift`, all aliases the cloud detector accepts, auto-detected as AWS and were then skipped by every AWS filter. "Which plugin runs?" and "which exposures are mine?" now read the same table.

*(since 0.16.2)* When every AWS binding names the same real region, the module's `aws` provider block carries it and it wins over the shell's `AWS_REGION`, so a contract bound to `eu-central-1` creates its resources there whichever region the shell defaults to (`{"aws": {"region": "eu-central-1"}}`). Bindings that span regions keep the environment's region, with a warning, and a jurisdiction (`EU`), a Google region or an unresolved `{{ env.AWS_REGION }}` placeholder is not pinned.

Catalog metadata that previously lived in the retired `glue` and `snowflake_horizon` publish-side registrars is now emitted into `aws_glue_catalog_table.parameters` and `snowflake_table` column comments directly — one source of truth, drift-detected by `tofu plan`. See [catalog overview](./catalogs/overview.md#retired-registrars-—-glue-snowflake-horizon).

### Refusals before a module is written

The refusals for retention, keys, column restrictions and principals are tabulated in [Governance parity](../concepts/governance-parity.md#refused-not-dropped-on-aws-and-gcp).

`generate iac` refuses these GCP cases before it writes a module, so a refusal leaves no module behind. With a `sovereignty` block, a GCP binding with no region is refused, because where the data lives cannot be checked, and so is a placement outside the allowed regions or jurisdiction:

```text
❌ generate_iac_failed  [ERR_GENERATE_IAC_FAILED]
  error: GCP placement refused by the sovereignty policy: gcpqs_output: Binding
declares no region, so where its data lives cannot be checked against the
sovereignty policy (the platform would choose); dataset_analytics: Region 'US' not in allowed regions list; ...
```

Principals are refused when they cannot be real identities. A principal in a reserved top-level domain (`.example`, `.test`, `.invalid`, `.localhost`), or one that is not an IAM member at all, fails with kind `principal-placeholder`:

```text
❌ unsupported_binding  [ERR_UNSUPPORTED_BINDING]
  kind: principal-placeholder
  error: exposes accessPolicy: principal 'group:data-platform@northwind.example'
resolves to 'group:data-platform@northwind.example', a placeholder: .example is
a reserved top-level domain (RFC 2606), so no real identity has it, and BigQuery
refuses an access entry for an identity that does not exist.
  remediation: ["Map the logical principal in this environment's
binding.principals to the real group or service account it stands for, ...
```

Other refusal kinds exist for principals and governance fields: `principal-unmapped`, `column-restriction-*` and `encryption-kms-*`. See the [GCP provider page](../providers/gcp.md) for the provider's own behaviour.

### Access grants on GCP *(0.17.0)*

[Governance parity](../concepts/governance-parity.md) lists the grants, policy tags, keys and retention each cloud receives from one contract.

`accessPolicy.grants[]` on a GCP expose compile to one non-authoritative `google_bigquery_dataset_iam_member` per role and member (a `google_storage_bucket_iam_member` for a Cloud Storage expose), for a contract with or without a `packaging` block. The dataset resource itself sets no `access`:

```json
"google_bigquery_dataset_iam_member": {
  "analytics_gcpq_analytics_roles_bigquery_dataViewer_group_data_analysts_company_example_com_4451af44f1": {
    "dataset_id": "${google_bigquery_dataset.analytics_gcpq_analytics.dataset_id}",
    "member": "group:data-analysts@company.example.com",
    "project": "your-gcp-project",
    "role": "roles/bigquery.dataViewer"
  }
}
```

The resource name ends in a hash of the role and the member, so principals that differ only in `.`, `-` or `_` keep one grant each. The grant's `permissions` map to roles:

| Permission | BigQuery dataset role | Cloud Storage role |
| --- | --- | --- |
| `read`, `select`, `query` (`view`, `list` on a bucket) | `roles/bigquery.dataViewer` | `roles/storage.objectViewer` |
| `write`, `insert`, `update` (`create` on a bucket) | `roles/bigquery.dataEditor` | `roles/storage.objectCreator` |
| `delete` | `roles/bigquery.dataEditor` | `roles/storage.objectAdmin` |
| `admin`, `owner` | `roles/bigquery.dataOwner` | `roles/storage.admin` |

On a bucket only `read`, `view`, `list`, `write`, `create`, `delete`, `admin` and `owner` map to a role; `select`, `query`, `insert` and `update` apply to BigQuery only.

What changed against an authoritative `access` list:

- BigQuery's default entries on a dataset (the project's owners, writers and readers, and the creator) stay.
- A grant made outside the contract is no longer removed by the next apply.
- `fluid verify` does not check dataset grants.

::: warning The first apply after upgrading revokes what the old list held
A dataset whose state holds the old `access` list and no member resource gets `access` set for that one apply, to the list less the entries no member covers. The provider revokes those entries and the member resources are created after it. `fluid apply` prints what it revoked, and `fluid diff` shows the same change, so run it before the apply to preview. A dataset whose every entry would be revoked is refused, and the entries have to be revoked by hand. This is taken from forge-cli's governance-parity notes and its 0.18.1 source, not from a run against a real dataset.
:::

### Iceberg prerequisites and the anti-no-op gate

An Iceberg expose needs infrastructure dbt refuses to create, and the plugins derive it from the binding. The `snowflake` plugin emits the **EXTERNAL VOLUME** for a Snowflake-managed (Horizon) catalog and a **Glue CATALOG INTEGRATION** for `location.catalog: glue` *(0.13.1, live-verified with a real `tofu apply`)*. The `gcp` plugin emits the **GCS warehouse bucket** backing a BigLake-Iceberg table *(0.14.0)* — a declared `location.path` means the product owns a *prefix* of a shared warehouse, so that bucket is emitted **without `force_destroy`**; an owned bucket (no path) keeps it.

The emitters are emit-when-derivable: an Iceberg expose missing a required input (an S3 warehouse without `iam_role_arn`, no derivable bucket name, an illegal `external_volume` override) used to emit **nothing, silently** — the failure surfaced only at `dbt run`. Since `0.14.0`, [`fluid validate`](./validate.md#iceberg-prerequisite-checks-since-0-14-0) errors on exactly those cases before any emit. One `--strict` caveat: a Snowflake catalog whose auth is secret-bearing (`polaris` / `unity` / `rest` / `nessie`) draws a *warning* — FLUID does not emit those catalog integrations because the emitted module is credential-free — and `fluid validate --strict` promotes it to an error.

With [forge-cli #707](https://github.com/Agenticstiger/forge-cli/pull/707) (unreleased), every plugin reads `location.catalog` through one table of catalog kinds. The Snowflake warning then covers every catalog Snowflake reaches over Iceberg REST (`rest`, `lakekeeper`, `polaris`, `unity`, `nessie`, `bigquery`), and `hive`, `jdbc`, `hadoop` or `dynamodb` on Snowflake is an error. The `aws` plugin keeps an Iceberg expose's S3 bucket but creates no Glue database or table for it unless its catalog is Glue, and `fluid apply` stops with `iceberg_catalog_move_blocked` when state holds Glue resources an earlier release created for such a table. See [Iceberg catalogs](../advanced/source-aligned-acquisition.md#iceberg-catalogs-location-catalog).

## Packaging modes

::: tip Opt-in, new in `0.13.0`
The `packaging` block lives in the **`0.7.6` preview** schema. `0.7.5` remains the stable default — a contract must declare `fluidVersion: "0.7.6"` to use it. A contract with no `packaging` block takes the LEGACY path, which `0.13.0` pinned byte for byte, so `packaging` itself changes nothing for an existing contract. GCP dataset grants are the exception: since `0.17.0` they are emitted as [`google_bigquery_dataset_iam_member`](#access-grants-on-gcp-0-17-0) for every contract, packaging or not.
:::

`packaging` declares, per infrastructure **container**, whether this product **owns** it or writes into a pre-existing, platform-owned **pool**:

```yaml
fluidVersion: "0.7.6"
packaging:
  mode: shared                        # isolated | shared — blanket default for every kind
  pool: analytics-pool-eu             # REQUIRED whenever any container resolves 'shared'
  poolManifest: platform/pools.yaml   # optional; snapshotted into the bundle
  containers:                         # per-kind overrides win over `mode`
    warehouse: isolated               # hybrid tier: shared database, own warehouse
```

| Mode | Emits |
| --- | --- |
| `isolated` | An **owned OpenTofu resource** — this product creates and can destroy the container. Today's exact emit. |
| `shared` | An OpenTofu **data source** referencing the platform-owned pool, plus **leaf-only** owned resources (tables, prefixed objects, scoped grants). The product writes into the pool but structurally cannot destroy it. |

Six container kinds are accepted:

| Kind | Resource |
| --- | --- |
| `bucket` | `aws_s3_bucket` / `google_storage_bucket` |
| `database` | `snowflake_database` **and** `aws_glue_catalog_database` |
| `dataset` | `google_bigquery_dataset` |
| `schema` | `snowflake_schema` |
| `warehouse` | `snowflake_warehouse` — `isolated` gives per-product cost attribution |
| `cluster` | Confluent environment/cluster — **`shared` only in v1**; the resolver rejects `isolated` (dedicated-cluster provisioning is not yet supported) |

`binding.packaging` overrides the contract-wide block per exposure. Precedence is `binding.packaging` > top-level `packaging` > absent-LEGACY. `pool` propagates as the `fluid_pool` label/tag for cost attribution.

### What `shared` changes per provider

| Provider | Referenced (shared) behaviour |
| --- | --- |
| `aws` | The bucket becomes `data.aws_s3_bucket` with **no `force_destroy`**. A referenced Glue database is addressed by literal name (`hashicorp/aws` ships `aws_glue_catalog_database` as a resource only — no data source). Lake Formation `registerLocation` scopes to `location.path`, and registers **nothing** when a pooled bucket has no prefix; the bucket policy's `ListBucket` statement gains an `s3:prefix` condition. |
| `gcp` | Dataset and bucket become data sources. A shared dataset gets no dataset-level grants (they would change the pool's ACL for other tenants), and its `accessPolicy` grants become per-table `google_bigquery_table_iam_member`. A shared bucket's IAM members gain an object-prefix CEL condition. |
| `snowflake` | A referenced database/schema emits **neither a resource nor a data source** (Snowflake's data sources are thin), so consumers inline the literal name. An `isolated` warehouse gets a dedicated `snowflake_warehouse`. |

### Ownership transitions

Changing a container's mode changes *who owns it* — but OpenTofu only sees a resource that left the configuration and plans a **destroy**. On a shared pool, that reaches every other tenant's data. So the ownership model is diffed against `tofu state list` **before** `tofu plan`, and a transition fails closed with copy-pasteable `tofu state rm` remediation.

| Transition | Behaviour |
| --- | --- |
| `isolated` → `shared` (owned → referenced) | **Always blocked.** There is no flag. Drop the resource from state first — `tofu state rm` touches zero bytes of infrastructure. |
| `shared` → `isolated` (referenced → owned) | Requires [`fluid apply --adopt-shared-container`](./apply.md#packaging-modes), which emits a structured audit event. |

Detection is deliberately conservative: over-flagging asks a human to look, under-flagging destroys a pool. LEGACY contracts resolve to the sentinel and can never transition, so the guard is a provable no-op for every pre-existing contract. Structured `packaging_transition_blocked` / `packaging_adoption_override` events are emitted for CI log scrapers.

**Import adoption is gated too.** Every provider plugin's `discover_imports` hook is gated on the packaging resolution, so a shared pool can never be `tofu import`ed into a product's state. Leaf resources inside a pool stay importable.

### Plan truthfulness and state key

- Under `packaging.mode: shared`, `plan.json` **no longer lists a create action** for a container the product does not own, and carries a packaging summary — the digest-bound artifact a human approves now tells the truth.
- With a remote backend, the state key names the provider ([OpenTofu state](../concepts/state.md#the-provider-is-part-of-the-key)), so one contract applied to two clouds through `--env` overlays keeps two states: `fluid/<id>/<provider>/terraform.tfstate` for S3, or the prefix `fluid/<id>/<provider>` for GCS *(0.17.0)*. A packaging-bearing contract gets this key, and so does any contract when the backend comes from a bucket-only `FLUID_STATE_BACKEND`, keyed by the contract id as written. The shared legacy key `fluid/terraform.tfstate`, which a contract with no packaging block and no `FLUID_STATE_BACKEND` keeps, and an explicit key are unchanged. State a previous release wrote at `fluid/<id>/terraform.tfstate` is copied to the new key on the first apply, and a key that names no provider and already holds another cloud's resources is refused with `state_shared_with_another_provider`. When a product already applied to `aws` is applied to `gcp` for the first time, the apply finds the `aws` state at the old key, logs `<old key> holds the aws provider's state (hashicorp/aws), not this provider's; left in place`, and writes the `gcp` state to `fluid/<id>/gcp/terraform.tfstate` (observed on 4 Oct 2026, in a first apply against real BigQuery). The flags are on the [`fluid apply`](./apply.md#remote-state) page, and the variables are listed under [Apply, state and OpenTofu](../advanced/environment-variables.md#apply-state-and-opentofu).

## Operational requirements

- **`tofu ≥ 1.6.0` on `PATH`.** `require_tofu_version()` catches the silent `terraform`-on-`PATH`-as-`tofu` mixup at apply time.
- **Subprocess timeout:** default `1800` seconds per `tofu` invocation. Override via `FLUID_TOFU_TIMEOUT_SECONDS=<seconds>`.

## Security gates

### Plan-binding integrity

The plan-binding gate from the native engine is replicated for OpenTofu — `_apply_opentofu_engine.py::_verify_plan_binding_for_opentofu` re-computes the `bundleDigest` and `planDigest` before any `tofu apply`. A tampered `plan.json` is rejected.

The emergency escape hatch is `--no-verify-plan-binding`; the apply logs at `WARNING` whenever it's used.

### Destructive operations

`--allow-data-loss` is the override for destructive gate. When used, the apply emits a `WARNING` log line and a structured `opentofu_destructive_gate_override` event so CI log-scrapers can pick it up.

## Brownfield: import existing resources

If the target cloud already has resources you want to fold into the IaC layer (rather than recreate), each provider plugin exposes a `discover_imports` hook that wires `tofu import` automatically. Run `fluid generate iac --out ./review` first, inspect the emitted resources against your live cloud, then `cd review && tofu init && tofu import …` for each pre-existing resource. The provider plugin's `discover_imports` produces the import commands for you.

## What didn't change

- **The contract.** No schema change — `v0.8.3` contracts are byte-identical to `v0.8.0` contracts.
- **The plan stage.** `fluid plan` still produces the canonical `Action` list; the OpenTofu engine consumes that list and compiles to `main.tf.json`.
- **`local` provider.** `local` keeps its native DuckDB apply path and has no IaC plugin, so `local` is not one of `--provider`'s choices — `fluid generate iac --provider local` is rejected by argparse, not a no-op. The parser's choices are `auto`, `aws`, `confluent`, `gcp` and `snowflake`; see [Provider flag limits](#provider-flag-limits) for `confluent`.

## See also

- [Catalog overview](./catalogs/overview.md) — where the retired Glue + Snowflake Horizon registrars now live
- [Providers vs Platforms](/forge_docs/concepts/providers-vs-platforms.html) — engine column added in `v0.8.3`
- [`fluid apply`](./apply.md) — the user-facing apply command that auto-routes through OpenTofu
- [Network safety](/forge_docs/advanced/network-safety.html) — outbound HTTP posture for cloud SDK calls
