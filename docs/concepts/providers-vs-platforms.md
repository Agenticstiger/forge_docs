---
title: Providers vs Platforms
description: The difference between a binding.platform value and the provider plugin that handles it.
---

# Providers vs Platforms

Two related but distinct ideas:

- **Platform** — a value in your contract (`binding.platform: gcp`) describing *where* the data lands.
- **Provider** — a Python plugin that knows *how* to make it land there. Each provider implements two required methods, `plan()` and `apply()`, against a specific cloud.

`fluid providers` lists the cloud-platform providers installed in your environment. For the spec-export formats a contract can be serialized to (ODCS / ODPS / ODPS-Bitol), use [`fluid exporters`](/forge_docs/cli/exporters.html) — exporters are not cloud providers. For the full installed-plugin roster across every role, use [`fluid plugins`](/forge_docs/cli/plugins.html).

## Cloud providers in `data-product-forge`

`fluid providers` prints the providers installed in your environment. On 0.18.1:

```bash
fluid providers
# {
#   "providers": [
#     "aws",
#     "datamesh_manager",
#     "gcp",
#     "local",
#     "redshift",
#     "snowflake"
#   ]
# }
```

`datamesh_manager` is a catalog publisher, not a cloud target. The cloud-platform providers:

| Provider | Lands data in | Install extra |
|----------|---------------|---------------|
| `local`     | DuckDB and local files | `pip install "data-product-forge[local]"` |
| `gcp`       | BigQuery, Cloud Storage, Pub/Sub | `pip install "data-product-forge[gcp]"` |
| `aws`       | S3, Glue, Athena, Lake Formation | `pip install "data-product-forge[aws]"` |
| `snowflake` | Snowflake | `pip install "data-product-forge[snowflake]"` |
| `redshift`  | Amazon Redshift (ships in the `aws` provider package) | `pip install "data-product-forge[aws]"` |

`azure` and `databricks` are valid `binding.platform` values with no provider behind them.

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

| Method | Called by | Pipeline stage | What it must do |
|---|---|---|---|
| `plan(contract)` | `fluid plan` | Stage 6 — *Plan* | Return the list of actions that would change the target. Same contract and same deployed state should give the same actions: `fluid apply` refuses a `plan.json` whose `planDigest` no longer matches its content. |
| `apply(actions)` | `fluid apply` | Stage 7 — *Apply* | Execute the actions against the target and report success or failure per action. Re-running an apply should be safe. |

For `aws`, `gcp` and `snowflake`, `fluid apply` compiles the contract into the OpenTofu module that `fluid generate iac` writes and runs `tofu` on it; the provider's planner still runs for checks such as the [sovereignty gate](./sovereignty.md#apply-re-checks-placements-on-aws-and-gcp-and-binds-the-plan-by-digest). On that path a plan that destroys a resource holding data is refused unless you pass `--allow-data-loss`; removing a grant or a policy tag is not counted as data loss.

Verification and policy compilation are **engine-level pipeline stages**, not provider abstract methods — the CLI drives them around the provider's `plan`/`apply` rather than calling extra methods on `BaseProvider`.

## Errors

A provider raises `ProviderError` for a failure it can explain; the CLI renders it as a typed error with a suggestion and a docs link. See [Typed CLI Errors](/forge_docs/advanced/typed-cli-errors.html) for the catalogue.

## Contract versions

`fluid validate` checks a contract against the bundled schema its `fluidVersion` names: 0.7.1 to 0.7.5, and 0.7.6 as an opt-in preview. Providers do not declare their own list of supported schema versions.

## Where to look next

- [Custom Providers walkthrough](/forge_docs/providers/custom-providers) — full step-by-step for shipping your own provider
- [Provider Architecture](/forge_docs/providers/architecture) — interface details, action types, error categories
- [Universal pipeline](/forge_docs/walkthrough/universal-pipeline) — where each provider method lands in the 11-stage flow
- [Builds, Exposes, Bindings](./builds-exposes-bindings.md) — the contract surface providers consume
