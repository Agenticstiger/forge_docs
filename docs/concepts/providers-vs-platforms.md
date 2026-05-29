---
title: Providers vs Platforms
description: The difference between a binding.platform value and the provider plugin that handles it.
---

# Providers vs Platforms

Two related but distinct ideas:

- **Platform** — a value in your contract (`binding.platform: gcp`) describing *where* the data lands.
- **Provider** — a Python plugin that knows *how* to make it land there. Each provider implements two required methods, `plan()` and `apply()`, against a specific cloud.

`fluid providers` lists everything installed in your environment.

## Cloud providers shipping in `data-product-forge` 0.8.6

These are the cloud-platform providers that implement `plan`/`apply` against a target cloud:

| Provider | Status | Install extra |
|----------|--------|---------------|
| `local`     | ✅ Production (DuckDB, runs anywhere) | `pip install "data-product-forge[local]"` |
| `gcp`       | ✅ Production (BigQuery + GCS + IAM)  | `pip install "data-product-forge[gcp]"` |
| `aws`       | ✅ Production (S3 + Glue + Athena)    | `pip install "data-product-forge[aws]"` |
| `snowflake` | ✅ Production (Snowflake + Snowpark)  | `pip install "data-product-forge[snowflake]"` |
| `azure`     | 🔜 Roadmap (Synapse + ADLS)           | — |
| `databricks`| 🔜 Roadmap (Unity Catalog)            | — |

How each provider materialises `apply()` — native execution vs IaC compilation — is an implementation detail; see [`fluid generate iac`](/forge_docs/cli/generate-iac.html) for the cloud-provider engine details and the `tofu` runtime requirement.

## Other valid `binding.platform` values

The schema enum also includes engines and runtime targets that aren't cloud providers in the same sense — they describe *how* the data lands, not *which cloud* it lands on:

| Value | Kind | Notes |
|-------|------|-------|
| `kafka`      | Streaming engine | Use with `format: kafka_topic`. Topic creation handled by your existing Kafka cluster, not by Fluid Forge — it just emits the binding contract. |
| `kubernetes` | Runtime target  | For long-running services / consumers, not for table-backed products. |
| `other`      | Escape hatch    | Lets you bind a contract to a custom provider you've registered via the [Provider SDK](/forge_docs/providers/custom-providers). |

## The provider plugin contract

Building a custom provider for an unsupported platform is supported — see [Custom Providers](/forge_docs/providers/custom-providers). `BaseProvider` declares exactly **two abstract methods** the plugin must implement:

```python
class MyProvider(BaseProvider):
    name = "my-cloud"

    def plan(self, contract): ...      # required (@abstractmethod)
    def apply(self, actions): ...      # required (@abstractmethod)
```

Two more methods are **optional** — `BaseProvider` ships working defaults you only override when you need them:

```python
    def capabilities(self): ...        # optional — defaults to ProviderCapabilities()
    def render(self, src, *, out=None, fmt=None): ...  # optional — default raises ProviderError
```

`capabilities()` advertises which features the provider supports (`planning`, `apply`, `render`, `graph`, `auth`); `render()` exports a contract to an external format and is unsupported unless overridden.

Register via Python entry points in your `pyproject.toml`:

```toml
[project.entry-points."fluid_build.providers"]
my-cloud = "my_provider:MyProvider"
```

After `pip install my-fluid-provider`, `fluid providers` will list it automatically and contracts can use `platform: my-cloud`.

## The provider lifecycle

The two required methods are each called at a specific point in the canonical 11-stage pipeline:

| Method | Called by | Pipeline stage | What it must do |
|---|---|---|---|
| `plan(contract)` | `fluid plan` | Stage 6 — *Plan* | Return a list of `Action` objects describing what would change. **Must be deterministic** — the same contract + same deployed state always emit the same actions. The CLI's plan binding (stage 6 ↔ stage 7) refuses to apply if the plan was tampered with. |
| `apply(actions)` | `fluid apply` | Stage 7 — *Apply* | Execute the actions against the target cloud. Idempotent. Returns success/failure per action. |

`plan()` makes no network calls and has no side effects — it's pure contract-in, action-list-out. That's how the canonical pipeline runs pre-flight checks without touching production.

Verification and policy compilation are **engine-level pipeline stages**, not provider abstract methods — the CLI drives them around the provider's `plan`/`apply` rather than calling extra methods on `BaseProvider`.

## Action semantics

`plan()` returns `Action` objects in three categories:

| Category | Examples | Apply behaviour |
|---|---|---|
| **Create** | `+ create table foo`, `+ create dataset bar`, `+ grant role/dataViewer to group:x` | Idempotent — re-applying a create that already happened is a no-op |
| **Modify** | `~ alter table foo add column bar`, `~ update grants for table foo` | Best-effort idempotent — providers may need to detect drift and reconcile |
| **Destructive** | `- drop table foo`, `- revoke grant from group:x` | **Gated by `--allow-destroy`**. The plan emits these but `apply` refuses unless the operator opts in explicitly. |

The destructive gate is the single most important safety property of the planner. Schema migrations that would drop a column require the operator to acknowledge the loss.

## Error translation

Every provider translates cloud-specific errors into typed CLI errors so the operator gets a useful message rather than a stack trace. Examples from the GCP provider:

| Cloud error | Translated to | Exit code |
|---|---|---|
| `403 Forbidden: bigquery.datasets.create` | `FluidIAMError`: "Service principal lacks BigQuery Data Editor role on project `prod`. Grant via …" | 64 (configuration) |
| `409 Conflict: dataset already exists` | (translated to a no-op create — no error) | 0 |
| `400 Bad Request: invalid schema` | `FluidSchemaError`: "Field `customer.id` declared as STRING in contract but BigQuery has it as INT64. Migration needed via …" | 65 (data) |
| `Quota exceeded: query bytes` | `FluidQuotaError`: "Project `prod` exceeded daily query bytes quota. See [GCP custom cost controls](https://cloud.google.com/bigquery/docs/custom-quotas)." | 66 (resource) |

See [Typed CLI Errors](/forge_docs/advanced/typed-cli-errors.html) for the full taxonomy.

## Version compatibility

Each provider declares the contract schema versions it can handle:

```python
class MyProvider(BaseProvider):
    name = "my-cloud"
    supported_schemas = ["0.7.1", "0.7.2", "0.7.3"]
```

`fluid validate` cross-checks the contract's `fluidVersion` against every installed provider's `supported_schemas`. Mismatch is a hard failure at validate time — the CLI refuses to load a contract that no installed provider can plan.

## Where to look next

- [Custom Providers walkthrough](/forge_docs/providers/custom-providers) — full step-by-step for shipping your own provider
- [Provider Architecture](/forge_docs/providers/architecture) — interface details, action types, error categories
- [Universal pipeline](/forge_docs/walkthrough/universal-pipeline) — where each provider method lands in the 11-stage flow
- [Builds, Exposes, Bindings](./builds-exposes-bindings.md) — the contract surface providers consume
