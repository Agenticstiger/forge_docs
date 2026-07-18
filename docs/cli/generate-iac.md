# `fluid generate iac`

Review-only emit of an OpenTofu module from a FLUID contract. `fluid apply` against a cloud provider auto-runs the same generator and hands the result to `tofu apply` — no flag needed; engine selection is per-provider (`local` keeps its native apply, `aws` / `gcp` / `snowflake` route through OpenTofu).

::: tip Available in 0.8.3 (PR #140)
`v0.8.3` introduces the **OpenTofu autogenerator**: `fluid apply` for cloud providers now compiles the contract to a deterministic OpenTofu `main.tf.json` and delegates apply / state / drift / idempotency to the `tofu` binary. `local` keeps its native DuckDB apply — no `tofu` needed for the local-first onboarding path.
:::

## Syntax

```bash
fluid generate iac <contract> [--provider PROVIDER] [--out DIR] [--env NAME] [--shadow] [--validate]
```

| Option | Description |
|---|---|
| `<contract>` | Path to FLUID contract file (YAML/JSON). |
| `--provider {auto,aws,gcp,snowflake}` | Target cloud. Default `auto` — inferred from the contract. |
| `--out`, `-o DIR` | Output directory for the emitted module. Default `runtime/iac`. |
| `--env NAME` | Environment overlay name (matches your contract's overlay block, e.g. `dev` / `staging` / `prod`). |
| `--shadow` | After emitting, shadow-compare resource parity against the native planner. Catches a divergence between the OpenTofu emission and what `fluid plan` would have produced. |
| `--validate` | After emitting, run `tofu validate` on the module (requires `tofu` on `PATH`). |

## Examples

```bash
# Review what fluid apply would emit for AWS
fluid generate iac contract.fluid.yaml --provider aws --out ./review

# Per-environment review
fluid generate iac contract.fluid.yaml --env staging --out ./review/staging

# Emit + validate against the planner + tofu validate in one pass
fluid generate iac contract.fluid.yaml --shadow --validate
```

The emitted directory contains `main.tf.json` (the compiled module), provider blocks, and a `manifest.json` describing how the contract mapped to resources. Inspect it before you run `fluid apply`.

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
| `aws` | S3 buckets / IAM roles + policies / Glue databases + tables + column comments / Athena workgroups |
| `gcp` | BigQuery datasets + tables / IAM bindings / GCS buckets |
| `snowflake` | Databases / schemas / tables / column comments (Horizon-aware) / file formats / stages |

Catalog metadata that previously lived in the retired `glue` and `snowflake_horizon` publish-side registrars is now emitted into `aws_glue_catalog_table.parameters` and `snowflake_table` column comments directly — one source of truth, drift-detected by `tofu plan`. See [catalog overview](./catalogs/overview.md#retired-registrars-glue-snowflake-horizon).

## Packaging modes

::: tip Opt-in, new in `0.13.0`
The `packaging` block lives in the **`0.7.6` preview** schema. `0.7.5` remains the stable default — a contract must declare `fluidVersion: "0.7.6"` to use it. **A contract with no `packaging` block emits byte-identically to pre-`0.13.0` releases** (that path is a distinct LEGACY sentinel, golden-pinned — not a re-derivation), so nothing existing changes.
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
| `gcp` | Dataset and bucket become data sources. A shared dataset **drops its authoritative `access[]` block** (it would rewrite the pool's whole ACL and evict other tenants) in favour of per-table `google_bigquery_table_iam_member`. A shared bucket's IAM members gain an object-prefix CEL condition. |
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
- A packaging-bearing contract defaults its backend state key to `fluid/<safe-id>/terraform.tfstate`. Contracts with no packaging block keep today's key exactly.

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
- **`local` provider.** `local` keeps its native DuckDB apply path. `fluid generate iac --provider local` is a no-op.

## See also

- [Catalog overview](./catalogs/overview.md) — where the retired Glue + Snowflake Horizon registrars now live
- [Providers vs Platforms](/forge_docs/concepts/providers-vs-platforms.html) — engine column added in `v0.8.3`
- [`fluid apply`](./apply.md) — the user-facing apply command that auto-routes through OpenTofu
- [Network safety](/forge_docs/advanced/network-safety.html) — outbound HTTP posture for cloud SDK calls
