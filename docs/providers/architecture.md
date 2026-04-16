# Provider Architecture

Providers are the execution layer of Fluid Forge. They translate your declarative YAML contract into concrete platform operations — creating tables in DuckDB locally, provisioning BigQuery datasets on GCP, or deploying schemas in Snowflake.

This page explains how the provider system works under the hood. If you want to **build your own provider**, see [Creating Custom Providers](./custom-providers.md).

## How It Works

Every Fluid Forge command follows the same flow: **contract → provider → plan → apply → result**.

```
┌─────────────────────────────────────────────────────┐
│              FLUID Contract (YAML)                  │
│  id, name, version, consumes[], builds[], exposes[] │
└──────────────────────┬──────────────────────────────┘
                       │
                 ┌─────▼─────┐
                 │  fluid    │  CLI parses the contract
                 │  plan     │  and resolves the provider
                 └─────┬─────┘
                       │
           ┌───────────▼───────────┐
           │   Provider Registry   │  Discovers all available
           │   (auto-discovery)    │  providers at startup
           └───────────┬───────────┘
                       │
     ┌─────────────────┼─────────────────┐
     ▼                 ▼                 ▼
┌─────────┐     ┌──────────┐     ┌───────────┐
│  Local   │     │   GCP    │     │ Snowflake │  ...
│ (DuckDB) │     │(BigQuery)│     │           │
└────┬────┘     └────┬─────┘     └─────┬─────┘
     │               │                 │
  plan() → actions   plan() → actions  plan() → actions
  apply() → result   apply() → result  apply() → result
```

This design gives you:

- **One contract, multiple targets** — the same YAML runs locally for development, then deploys to any cloud in production
- **Deterministic planning** — `plan()` is pure with no side effects, the same contract always produces the same actions
- **Idempotent apply** — `apply()` is safe to re-run, it converges toward the desired state
- **Extensibility** — add a new provider without changing contracts or the CLI

## The Two Required Methods

Every provider must implement exactly two methods:

### `plan(contract) → actions`

Reads the contract and returns a list of **actions** — plain Python dicts describing what needs to happen:

```python
actions = provider.plan(contract)
# [
#   {"op": "load_data", "path": "data/customers.csv", "table_name": "customers"},
#   {"op": "execute_sql", "sql": "SELECT * FROM customers WHERE active", ...},
#   {"op": "materialize", "source_table": "result", "path": "out/active.csv"}
# ]
```

Planning makes **no network calls** and has **no side effects**. It's just data transformation: contract in, action list out.

### `apply(actions) → ApplyResult`

Executes each action against the target platform and returns a structured result:

```python
result = provider.apply(actions)
# ApplyResult(
#   provider="local",
#   applied=3, failed=0,
#   duration_sec=0.142,
#   timestamp="2026-03-05T10:30:00Z",
#   results=[
#     {"i": 0, "status": "ok", "op": "load_data"},
#     {"i": 1, "status": "ok", "op": "execute_sql"},
#     {"i": 2, "status": "ok", "op": "materialize"}
#   ]
# )
```

## Provider Discovery

When you run any `fluid` command, the CLI automatically discovers all available providers. You never need to configure this — it just works.

### How Discovery Finds Providers

Discovery runs a 4-layer pipeline, in order:

| Layer | What it does | Use case |
|-------|-------------|----------|
| **1. Entry points** | Scans pip-installed packages for `fluid_build.providers` entry points | Third-party providers installed via `pip install` |
| **2. Built-in modules** | Imports the curated defaults: `local`, `gcp`, `aws`, `snowflake`, `odps` | The providers that ship with Fluid Forge |
| **3. Subpackage scan** | Scans `fluid_build/providers/*` for any remaining modules | Catches providers added to the package tree |
| **4. Fallback** | Re-attempts imports if registry is still empty | Recovers from import ordering issues |

Discovery is **lazy** (runs on first access), **idempotent** (subsequent calls are no-ops), and **thread-safe**.

### Selecting a Provider

The CLI resolves which provider to use in this order:

1. The `--provider` flag: `fluid --provider gcp plan contract.yaml`
2. The `FLUID_PROVIDER` environment variable: `export FLUID_PROVIDER=gcp`

```bash
# List all discovered providers
fluid providers

# Restrict discovery to specific providers (advanced)
FLUID_PROVIDERS="local,gcp" fluid providers
```

## Built-in Providers

Fluid Forge ships with these providers:

| Provider | Runtime | Best for |
|----------|---------|----------|
| **[Local](./local.md)** | DuckDB | Development, testing, CSV/Parquet workflows |
| **[GCP](./gcp.md)** | BigQuery + GCS | Google Cloud production deployments |
| **[AWS](./aws.md)** | S3 + Athena + Glue | Amazon Web Services deployments |
| **[Snowflake](./snowflake.md)** | Snowflake | Enterprise data warehouse deployments |
| **ODPS** | Standards export | Data product interoperability (ODPS v4.1) |

```bash
# Local development
fluid --provider local apply contract.yaml --yes

# Deploy to GCP
fluid --provider gcp apply contract.yaml --project my-gcp-project

# Deploy to Snowflake
fluid --provider snowflake apply contract.yaml

# Deploy to AWS
fluid --provider aws apply contract.yaml --region us-east-1
```

## The Action System

Actions are the intermediate representation between planning and execution. Each action is a plain dict with an `op` field that identifies the operation.

### Standard Action Types

| Op | Purpose | Key fields |
|----|---------|------------|
| `load_data` | Import a file into the query engine | `path`, `table_name`, `format` |
| `execute_sql` | Run a SQL transformation | `sql`, `output_table`, `resource_id` |
| `materialize` | Write results to an output file | `source_table`, `path`, `format` |
| `copy` | Copy or export data | `source`, `destination`, `format` |
| `noop` | Placeholder (no operation) | — |

Cloud providers define their own ops (e.g., `ensure_dataset`, `ensure_table`, `create_view`, `grant_role`).

### Dependency Resolution

The planner builds a dependency graph and uses **topological sorting** to determine execution order. Data must be loaded before transformations run, and transformations must complete before materialization:

```
load_data(customers.csv)  ──┐
                             ├──▶  execute_sql(transform)  ──▶  materialize(output.csv)
load_data(orders.csv)     ──┘
```

## Capabilities

Providers advertise what they support through a capabilities object. The CLI uses this to enable or disable features dynamically:

```python
def capabilities(self):
    return ProviderCapabilities(
        planning=True,       # Can generate execution plans
        apply=True,          # Can execute actions
        render=False,        # Can export to external formats
        graph=False,         # Can generate lineage graphs
        auth=False,          # Requires authentication
    )
```

Check capabilities from the CLI:

```bash
fluid providers         # Shows capabilities for all providers
```

## Error Handling

Providers use a two-tier error model:

| Error type | When to use | User experience |
|-----------|-------------|-----------------|
| `ProviderError` | User-fixable problems (bad contract, missing resource) | Friendly error message |
| `ProviderInternalError` | Bugs or environment failures (API outage) | Full traceback in debug mode |

```python
from fluid_provider_sdk import ProviderError, ProviderInternalError

# User error — they can fix this
raise ProviderError("Dataset 'analytics' not found in project 'my-project'")

# Internal error — something unexpected broke
raise ProviderInternalError(f"BigQuery API returned unexpected status: {status}")
```

## Environment Variables

| Variable | Purpose | Example |
|----------|---------|---------|
| `FLUID_PROVIDER` | Default provider | `local`, `gcp`, `snowflake` |
| `FLUID_PROJECT` | Cloud project/account | `my-gcp-project` |
| `FLUID_REGION` | Deployment region | `us-central1` |
| `FLUID_PROVIDERS` | Restrict which providers to discover | `local,gcp` |

## Next Steps

- **Build your own provider:** [Creating Custom Providers](./custom-providers.md)
- **Use a specific provider:** [GCP](./gcp.md) · [AWS](./aws.md) · [Snowflake](./snowflake.md) · [Local](./local.md)
- **See what's coming:** [Provider Roadmap](./roadmap.md)
