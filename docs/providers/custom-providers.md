# Creating Custom Providers

This guide walks you through building a custom Fluid Forge provider — from a minimal working example to a fully tested, distributable package.

A provider teaches Fluid Forge how to deploy contracts to a new platform. If you can express the deployment as "create these resources, run this SQL, write these outputs," you can build a provider for it.

::: tip Prerequisites
You should be familiar with [how the provider system works](./architecture.md) before building one. The key concept: a provider implements `plan()` to convert a contract into actions, and `apply()` to execute those actions.
:::

## Quick Start: A Working Provider in 40 Lines

Let's build a provider that deploys to a hypothetical database platform called "MyDB."

**Step 1:** Create the provider class:

```python
# my_provider/provider.py
import time
import datetime
from fluid_provider_sdk import ApplyResult, BaseProvider, ProviderError

class MyDbProvider(BaseProvider):
    name = "mydb"

    def plan(self, contract):
        """Convert a FLUID contract into a list of actions."""
        actions = []
        for expose in contract.get("exposes", []):
            table = expose.get("id", "output")
            actions.append({
                "op": "create_table",
                "table": table,
                "schema": expose.get("schema", []),
            })
        return actions

    def apply(self, actions, **kwargs):
        """Execute the planned actions."""
        t0 = time.time()
        results = []

        for i, action in enumerate(actions):
            # Replace this with your actual platform SDK calls
            self.info_kv(evt="deploying", op=action["op"], table=action.get("table"))
            results.append({"i": i, "status": "ok", "op": action["op"]})

        return ApplyResult(
            provider=self.name,
            applied=len(results),
            failed=0,
            duration_sec=round(time.time() - t0, 3),
            timestamp=datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            results=results,
        )
```

**Step 2:** Register it so Fluid Forge can find it:

```toml
# pyproject.toml
[project.entry-points."fluid_build.providers"]
mydb = "my_provider.provider:MyDbProvider"
```

**Step 3:** Use it:

```bash
pip install -e .
fluid --provider mydb plan contract.fluid.yaml
fluid --provider mydb apply contract.fluid.yaml --yes
```

That's it. Your provider is functional. The rest of this guide covers how to make it robust, testable, and distributable.

## The BaseProvider Interface

Every provider extends `BaseProvider`. Here's the full interface:

### Required Methods

| Method | Signature | Purpose |
|--------|-----------|---------|
| `plan()` | `plan(contract: Mapping) → List[Dict]` | Generate actions from a contract. Must be **pure** — no network calls, no side effects. |
| `apply()` | `apply(actions: Iterable[Mapping]) → ApplyResult` | Execute actions and return results. Should be **idempotent** where possible. |

### Optional Methods

| Method | Signature | Purpose |
|--------|-----------|---------|
| `render()` | `render(src, *, out=None, fmt=None) → Dict` | Export/render to an external format. |
| `capabilities()` | `→ ProviderCapabilities` | Declare what your provider supports. |
| `get_provider_info()` | `→ ProviderMetadata` (classmethod) | Static metadata for `fluid providers` output. |

### Inherited Helpers

Every provider gets these for free:

```python
# Structured logging (preferred over print())
self.info_kv(evt="table_created", table="customers", rows=1500)
self.warn_kv(evt="deprecated_format", format="0.4.0")
self.err_kv(evt="connection_failed", host="db.example.com")
self.debug_kv(evt="query_plan", sql="SELECT ...")

# Validation shorthand — raises ProviderError if condition is false
self.require(len(actions) > 0, "No actions to apply")
```

### Constructor

```python
def __init__(self, *, project=None, region=None, logger=None, **kwargs):
    super().__init__(project=project, region=region, logger=logger, **kwargs)
    # Your setup here — read config, initialize SDK clients
```

The CLI passes `project`, `region`, and `logger` automatically. Access them as `self.project`, `self.region`, `self.logger`.

## Writing `plan()`

The planner reads the contract and produces a list of action dicts. Each action must have an `op` field.

```python
def plan(self, contract):
    actions = []

    # Process each 'expose' section — these define what the contract outputs
    for expose in contract.get("exposes", []):
        location = expose.get("location", {})
        props = location.get("properties", {})

        actions.append({
            "op": "ensure_schema",
            "database": props.get("database", "default"),
            "schema": props.get("schema", "public"),
        })
        actions.append({
            "op": "create_table",
            "database": props.get("database", "default"),
            "schema": props.get("schema", "public"),
            "table": props.get("table") or expose.get("id"),
            "columns": expose.get("schema", []),
        })

    # Process 'builds' — these define SQL transformations
    for build in contract.get("builds", []):
        sql = build.get("sql")
        if sql:
            actions.append({
                "op": "execute_sql",
                "sql": sql,
                "output_table": build.get("id"),
            })

    return actions
```

::: warning Planning Rules
- **No side effects.** Planning must never make API calls, write files, or modify state.
- **Deterministic.** The same contract must always produce the same actions in the same order.
- **Serializable.** Actions must be plain dicts (JSON-serializable). The CLI may serialize them for `plan.json` output.
:::

## Writing `apply()`

The apply method executes planned actions and returns a structured result reporting what happened:

```python
def apply(self, actions, **kwargs):
    t0 = time.time()
    results = []
    ok, failed = 0, 0

    for i, action in enumerate(actions):
        op = action.get("op")
        try:
            if op == "ensure_schema":
                self._ensure_schema(action)
            elif op == "create_table":
                self._create_table(action)
            elif op == "execute_sql":
                self._execute_sql(action)
            else:
                self.warn_kv(evt="unknown_op", op=op)
                continue

            results.append({"i": i, "status": "ok", "op": op})
            ok += 1
        except ProviderError as e:
            results.append({"i": i, "status": "error", "op": op, "error": str(e)})
            failed += 1

    return ApplyResult(
        provider=self.name,
        applied=ok,
        failed=failed,
        duration_sec=round(time.time() - t0, 3),
        timestamp=datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        results=results,
    )
```

::: tip
Always capture partial progress in the results list — even if an action fails, previous successes should be reported. The CLI uses per-action status to show users exactly what worked and what didn't.
:::

## Declaring Capabilities

Tell the CLI what your provider supports:

```python
from fluid_provider_sdk import ProviderCapabilities

def capabilities(self):
    return ProviderCapabilities(
        planning=True,       # Supports plan()
        apply=True,          # Supports apply()
        render=False,        # No export/render support
        graph=False,         # No lineage graph generation
        auth=True,           # Requires authentication
    )
```

The CLI checks these to decide which features to enable. For example, it won't offer `--render` if `render=False`.

## Provider Metadata

Metadata appears in `fluid providers` output and helps users discover providers:

```python
from fluid_provider_sdk import ProviderMetadata

@classmethod
def get_provider_info(cls):
    return ProviderMetadata(
        name="mydb",
        display_name="MyDB",
        description="Deploy FLUID contracts to MyDB",
        version="1.0.0",
        author="Data Platform Team",
        tags=["database", "sql"],
    )
```

## Registration

Fluid Forge needs to know your provider exists. There are two ways to register.

### Option 1: Entry Points (Recommended)

If you're distributing your provider as a standalone package, use Python entry points. This lets Fluid Forge discover your provider automatically after `pip install`:

```toml
# pyproject.toml
[project.entry-points."fluid_build.providers"]
mydb = "my_provider.provider:MyDbProvider"
```

After installation, your provider appears automatically:

```bash
pip install my-fluid-provider
fluid providers    # Shows "mydb" in the list
```

### Option 2: Explicit Registration (For In-Tree Providers)

If you're bundling a provider inside the CLI repo or another in-process integration, you can register it at import time:

```python
# my_provider/__init__.py
from fluid_build.providers import register_provider
from .provider import MyDbProvider

register_provider("mydb", MyDbProvider)
```

### Name Rules

Provider names are normalized on registration:
- Lowercased: `"MyDB"` → `"mydb"`
- Hyphens become underscores: `"my-db"` → `"my_db"`
- Must match `[a-z0-9_]+`
- The names `unknown` and `stub` are reserved

**First-write-wins:** If two providers register the same name, the first one keeps it. Pass `override=True` to explicitly replace an existing registration.

## Error Handling

Use the two-tier error model:

```python
from fluid_provider_sdk import ProviderError, ProviderInternalError

# User-fixable problems — shown as friendly messages
raise ProviderError("Table 'orders' does not exist in schema 'analytics'")

# Internal failures — shown with full context in debug mode
raise ProviderInternalError(f"Unexpected API response: {status_code}")
```

**Guidelines:**
- Always raise `ProviderError` or `ProviderInternalError` — never bare `Exception`
- Log context before raising: `self.err_kv(evt="table_missing", table="orders")`
- Capture partial progress in `ApplyResult.results` even when something fails

## Testing Your Provider

### Unit Tests for `plan()`

Planning is pure, so it's easy to test:

```python
import pytest
from my_provider.provider import MyDbProvider

@pytest.fixture
def provider():
    return MyDbProvider(project="test", region="us-east-1")

def test_plan_generates_actions(provider):
    contract = {
        "id": "test-product",
        "exposes": [{"id": "output", "schema": [{"name": "id", "type": "integer"}]}],
    }
    actions = provider.plan(contract)
    assert len(actions) >= 1
    assert actions[0]["op"] == "create_table"
    assert actions[0]["table"] == "output"

def test_plan_empty_contract(provider):
    actions = provider.plan({"id": "empty"})
    assert actions == []

def test_plan_is_deterministic(provider):
    contract = {"id": "test", "exposes": [{"id": "a"}, {"id": "b"}]}
    assert provider.plan(contract) == provider.plan(contract)
```

### Integration Tests for `apply()`

```python
def test_apply_returns_result(provider):
    actions = [{"op": "create_table", "table": "test", "schema": []}]
    result = provider.apply(actions)

    assert result.applied >= 1
    assert result.failed == 0
    assert result.results[0]["status"] == "ok"
```

### Conformance Test Harness

Fluid Forge includes a built-in test harness that runs conformance checks against any provider. It validates constructor signatures, capabilities format, plan output shape, apply result structure, and metadata:

```python
from tests.providers.test_phase3_harness_scaffold import ProviderTestHarness

class TestMyDb(ProviderTestHarness):
    @pytest.fixture
    def provider(self):
        return MyDbProvider(project="test")

    @pytest.fixture
    def sample_contract(self):
        return {
            "id": "harness-test",
            "name": "Harness Test",
            "fluidVersion": "0.7.1",
            "exposes": [{"id": "output"}],
        }
```

## Distributing as a Pip Package

For providers meant to be shared, package them as a standard Python project:

```
fluid-provider-mydb/
├── pyproject.toml
├── README.md
├── src/
│   └── my_provider/
│       ├── __init__.py
│       └── provider.py
└── tests/
    └── test_provider.py
```

The `pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "fluid-provider-mydb"
version = "1.0.0"
description = "Fluid Forge provider for MyDB"
requires-python = ">=3.9"
dependencies = ["fluid-forge>=0.7.0"]

[project.entry-points."fluid_build.providers"]
mydb = "my_provider.provider:MyDbProvider"
```

Users install and use it with zero configuration:

```bash
pip install fluid-provider-mydb
fluid --provider mydb plan contract.fluid.yaml   # Just works
```

## Security Best Practices

### Never Log Secrets

```python
# ❌ Bad — password will appear in logs
self.info_kv(evt="connecting", password=password)

# ✅ Good
self.info_kv(evt="connecting", host=host, user=user)
```

### Validate SQL Identifiers

If your provider executes SQL, validate all identifiers to prevent injection:

```python
import re
_SAFE_IDENT = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')

def _validate_ident(name):
    if not _SAFE_IDENT.match(name):
        raise ProviderError(f"Unsafe SQL identifier: {name!r}")
    return name

sql = f"CREATE TABLE {_validate_ident(table)} AS SELECT * FROM {_validate_ident(source)}"
```

### Authenticate Securely

Recommended authentication precedence:
1. Workload identity / managed identity (no stored credentials)
2. Environment variables (CI/CD injection)
3. Local config files (`~/.fluid/providers.yaml`)
4. Interactive authentication (development only)

## Extension Points

The Provider SDK defines lifecycle hooks for advanced use cases. These are optional interfaces you can implement for richer integration:

| Hook | When it runs | Purpose |
|------|-------------|---------|
| `pre_plan(contract)` | Before `plan()` | Enrich or validate the contract |
| `post_plan(actions)` | After `plan()` | Filter or reorder actions |
| `pre_apply(actions)` | Before `apply()` | Add audit metadata, last-chance validation |
| `post_apply(result)` | After `apply()` | Send notifications, log audit events |
| `on_error(error, context)` | On any exception | Error reporting, alerting |
| `estimate_cost(actions)` | On demand | Return a `CostEstimate` for the plan |
| `validate_sovereignty(contract)` | On demand | Check data residency constraints |

```python
from fluid_provider_sdk import ProviderHookSpec

class MyDbProvider(BaseProvider, ProviderHookSpec):
    name = "mydb"

    def pre_plan(self, contract):
        # Inject defaults before planning
        contract.setdefault("metadata", {}).setdefault("region", "us-east-1")
        return contract

    def on_error(self, error, context):
        # context["phase"] is "plan" or "apply"
        send_alert(f"FLUID error in {context['phase']}: {error}")
```

::: info
Hooks are safety-wrapped — if a hook raises an exception, the plan/apply flow continues uninterrupted. Missing hooks are silently skipped.
:::

## Render/Export Providers

Some providers don't deploy to a cloud — they export to a standardized format (like ODPS or ODCS). These implement `render()`:

```python
class MyExporter(BaseProvider):
    name = "my_export"

    def capabilities(self):
        return ProviderCapabilities(planning=True, apply=True, render=True)

    def render(self, src, *, out=None, fmt=None):
        import json
        from pathlib import Path

        doc = {
            "format": "my_format",
            "version": "1.0",
            "product_id": src.get("id"),
            "product_name": src.get("name"),
        }

        if out and out != "-":
            Path(out).parent.mkdir(parents=True, exist_ok=True)
            Path(out).write_text(json.dumps(doc, indent=2))

        return doc
```

## Checklist: Definition of Done

Before shipping a provider, verify:

- [ ] `plan()` is pure — no network calls, deterministic output
- [ ] `apply()` returns `ApplyResult` with per-action status
- [ ] `apply()` is idempotent — safe to run twice
- [ ] Registered via `register_provider()` or entry points
- [ ] Uses structured logging (`self.info_kv()`) — no secrets in logs
- [ ] Raises `ProviderError` (user errors) or `ProviderInternalError` (bugs)
- [ ] Unit tests for `plan()` with known inputs/outputs
- [ ] Integration tests for `apply()`
- [ ] `capabilities()` returns accurate feature flags
- [ ] `get_provider_info()` returns valid metadata
- [ ] Appears in `fluid providers` output

## Next Steps

- **Understand the architecture:** [Provider Architecture](./architecture.md)
- **See real providers:** [Local](./local.md) · [GCP](./gcp.md) · [AWS](./aws.md) · [Snowflake](./snowflake.md)
- **See what's planned:** [Provider Roadmap](./roadmap.md)
