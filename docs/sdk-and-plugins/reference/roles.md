# Roles reference

Four built-in roles, all subclasses of `BasePlugin`. Pick by what you're producing.

| Role | Role tag | What it produces | Default `apply()` does |
|---|---|---|---|
| [`CustomScaffold`](#customscaffold) | `"scaffold"` | Files on disk | Atomically writes each `write_file` action with sha256 verification + path-traversal guards |
| [`Validator`](#validator) | `"validator"` | `Finding` records | Summarizes findings by severity, sets the CLI exit code |
| [`InfraProvider`](#infraprovider) | `"provider"` | Cloud resources | (you implement — provisions per `op` in your action list) |
| [`CatalogAdapter`](#catalogadapter) | `"catalog"` | Catalog entries | (you implement — pushes to your catalog of choice) |

All four inherit the same lifecycle (`plan(contract) → list[PluginAction]` → `apply(actions) → ExecutionResult`), the same conformance harness (`PluginTestHarness` + role-specific subharnesses), and the same crash-containment guarantees from the CLI.

## `BasePlugin`

The ABC every role subclasses. Three methods, one class attribute:

```python
from fluid_sdk import BasePlugin, PluginAction, ExecutionResult, PluginMetadata
from typing import Any, List, Mapping


class MyPlugin(BasePlugin):
    """Required attributes."""

    name: str = "my-plugin"     # ← required; surfaces via `PluginMetadata.name` for any tooling that reads it
    role: str = "..."           # ← set by each Role subclass; don't override

    @classmethod
    def get_plugin_info(cls) -> PluginMetadata:
        """Optional. Override for richer metadata than the default name+role."""
        ...

    def plan(self, contract: Mapping[str, Any]) -> List[dict]:
        """Required. Inspect the contract; return action dicts.
        Must be deterministic — same contract ⇒ same actions, every time.
        """
        raise NotImplementedError

    def apply(self, actions: List[dict]) -> ExecutionResult:
        """Optional. Default implementation depends on role.
        Override only when you need custom apply semantics.
        """
        ...
```

`plan()` is **the** method you write for every plugin. `apply()` is usually inherited.

## `CustomScaffold`

For file-emitting plugins: CI configs, application code, IaC stacks, docs, anything that lives on disk.

```python
from fluid_sdk import CustomScaffold, ContractHelper, write_file_action


class MyScaffold(CustomScaffold):
    name = "my-scaffold"
    # role = "scaffold" is inherited.

    def plan(self, contract):
        c = ContractHelper(contract)
        return [
            write_file_action(
                path="README.md",
                content=f"# {c.name}\n".encode("utf-8"),
                resource_id="readme",
            ).to_dict(),
            write_file_action(
                path=".gitlab-ci.yml",
                content=self._ci_yaml(c).encode("utf-8"),
                resource_id="ci",
            ).to_dict(),
        ]

    def _ci_yaml(self, c):
        return "..."  # your rendering logic
```

### What you get from `CustomScaffold`

- **Inherited `apply(actions)`** — writes files atomically (`temp file + os.replace`) with sha256 verification, path-traversal protection (rejects absolute paths and `..` segments), and idempotency (re-running with the same bytes is a no-op).
- **`write_file_action(...)`** helper — builds a canonical action dict with sha256, base64-encoded bytes, file mode, optional description, optional `depends_on` for ordering. Returning the result of `.to_dict()` from `plan()` is the entire interface.
- **`CustomScaffoldTestHarness`** — ~20 conformance tests run against any `plugin_class` you set, no extra code needed.

### Hooks into the CLI

`fluid generate <scaffold-name>` (or `fluid generate custom-scaffold` for the canonical engine).

### Examples

- Minimal: [hello-scaffold](../examples/hello-scaffold.md) (~30 LOC)
- Realistic: [gitlab-ci-scaffold](../examples/gitlab-ci-scaffold.md) (~140 LOC)

## `Validator`

For contract-inspection plugins: governance rules, compliance gates, cost guardrails, naming-policy enforcement.

```python
from fluid_sdk import Validator, ContractHelper, Finding


class MyValidator(Validator):
    name = "my-rule"
    # role = "validator" is inherited.

    def plan(self, contract):
        c = ContractHelper(contract)
        findings = []
        if not c.metadata.get("labels", {}).get("cost-center"):
            findings.append(Finding(
                severity="error",
                code="COST_CENTER_MISSING",
                message=f"Contract {c.id!r} missing cost-center label.",
                path='metadata.labels["cost-center"]',
                remediation="Add metadata.labels['cost-center'] with your team's code.",
            ))
        return [f.to_action() for f in findings]
```

### What you get from `Validator`

- **`Finding` dataclass** — structured `severity` (`info` / `warn` / `error` / `critical`) + `code` + `message` + `path` + `remediation`. The CLI formats these uniformly.
- **Inherited `apply(actions)`** — summarizes findings by severity, writes to the validation report, sets the CLI exit code based on the maximum severity emitted.
- **`PluginTestHarness`** — 13 generic conformance tests run against your validator (subclass it in your test module). A Validator-specific subharness (`ValidatorTestHarness`) is on the SDK roadmap; until it ships, add your fixture-driven good/bad-contract assertions as additional `test_*` methods on the class.
- **Auto-discovery at `fluid validate`** — every validator registered via `fluid_build.validators` entry-point runs on every contract, no opt-in needed.

### Hooks into the CLI

`fluid validate <contract>` runs all validators automatically.

### Examples

- [steward-validator](../examples/steward-validator.md) (~90 LOC)
- Full journey: [custom-validator](../journeys/custom-validator.md)

## `InfraProvider`

For cloud-platform plugins: you're adding support for a new cloud (or warehouse, or query engine) that forge doesn't have a built-in provider for.

```python
from fluid_sdk import InfraProvider, PluginAction, ExecutionResult


class MyCloudProvider(InfraProvider):
    name = "mycloud"
    # role = "provider" is inherited.

    def plan(self, contract):
        # Translate the contract into native cloud ops.
        return [
            PluginAction(
                op="provision_dataset",
                resource_type="dataset",
                resource_id=contract["metadata"]["id"],
                params={"region": "us-east-1", ...},
            ).to_dict(),
            # ... more actions
        ]

    def apply(self, actions):
        # You implement this — the base class doesn't know how to talk to your cloud.
        results = []
        for action in actions:
            try:
                self._dispatch(action)
                results.append({"op": action["op"], "status": "ok"})
            except Exception as e:
                results.append({"op": action["op"], "status": "failed", "error": str(e)})
        return ExecutionResult(
            provider=self.name,
            applied=sum(1 for r in results if r["status"] == "ok"),
            failed=sum(1 for r in results if r["status"] == "failed"),
            duration_sec=0.0,
            timestamp="",
            results=results,
        )
```

### What you get from `InfraProvider`

- **`PluginAction` dataclass** — generic action shape with `op` (the operation), `resource_type`, `resource_id`, `params`, `depends_on`. The `op` field is free-form text — your provider knows what each op means.
- **`PluginTestHarness`** (no provider-specific subharness yet) — generic conformance tests run against your provider.

### What you implement yourself

Most of it: `apply()` is *your* code talking to *your* cloud's API. The SDK provides the shape; you provide the substance.

### Hooks into the CLI

`fluid apply` walks the action list and dispatches each action to the registered provider via the `op` field.

### Examples

- The CLI's built-in providers (`fluid_build/providers/gcp/`, `/aws/`, `/snowflake/`, `/local/`) are the canonical examples of `InfraProvider` subclasses. They're not on PyPI as separate packages, but the structure is the same — read them at [`Agenticstiger/forge-cli/fluid_build/providers/`](https://github.com/Agenticstiger/forge-cli/tree/main/fluid_build/providers).

## `CatalogAdapter`

For catalog-sync plugins: pushing contract metadata into your enterprise catalog (DataHub, Atlan, Collibra, Alation, OpenMetadata, etc.).

```python
from fluid_sdk import CatalogAdapter, ContractHelper


class MyCatalog(CatalogAdapter):
    name = "my-catalog"
    # role = "catalog" is inherited.

    def plan(self, contract):
        c = ContractHelper(contract)
        # Translate the contract into a catalog-shaped payload.
        return [{
            "op": "upsert_entity",
            "resource_type": "data-product",
            "resource_id": c.id,
            "params": {
                "name": c.name,
                "description": c.description,
                "owner": c.owner.get("email"),
                "domain": c.domain,
                # ...
            },
        }]

    def apply(self, actions):
        # POST/PUT to your catalog's REST API.
        ...
```

### Hooks into the CLI

`fluid publish --target <name>` invokes the matching `CatalogAdapter`.

### Examples

- The CLI's `datamesh_manager` and `marketplace` providers under `fluid_build/providers/` are the closest in-tree analogs. A standalone `CatalogAdapter` plugin on PyPI hasn't been published yet — when one ships, it'll be linked here.

## Shared concepts across roles

### `ContractHelper`

Read-only parser over fluid contract dicts. Tolerant of every `fluidVersion` from `0.4` through `0.7.3`. Use this instead of raw dict-walking:

```python
from fluid_sdk import ContractHelper

c = ContractHelper(contract)
c.id                   # str | None
c.name                 # str | None
c.description          # str | None
c.owner                # dict (e.g. {"email": "..."})
c.domain               # str | None
c.metadata             # full metadata dict
c.environments         # full environments dict
c.environment_names()  # list[str]
c.exposes              # list[ExposeSpec]
c.consumes             # list[ConsumeSpec]
c.builds               # list[BuildSpec]
c.extensions           # dict — the contract.extensions block
```

If a field is missing, the property returns `None` (or `[]` / `{}`) instead of raising. Your plugin can fail gracefully on partial contracts.

### `PluginAction`

Generic action dataclass. Roles use it differently:

| Role | Common `op` values |
|---|---|
| `CustomScaffold` | `write_file` |
| `Validator` | `emit_finding` |
| `InfraProvider` | provider-specific (`provision_dataset`, `create_table`, `grant_access`, …) |
| `CatalogAdapter` | provider-specific (`upsert_entity`, `link_lineage`, …) |

You can also use raw `PluginAction(op="...", ...)` for anything not covered by the helper functions.

### `ExecutionResult`

What `apply()` returns. Carries `provider`, `applied` / `failed` counts, `duration_sec`, `timestamp`, and per-action `results` for the CLI to format.

### `PluginMetadata`

Override `get_plugin_info()` if you want richer metadata than the default `PluginMetadata(name=cls.name, role=cls.role)`. Any tooling that introspects installed plugins (a future `fluid plugins list`, custom dashboards, IDE integrations) reads from this:

```python
@classmethod
def get_plugin_info(cls):
    return PluginMetadata(
        name=cls.name,
        role=cls.role,
        display_name="GitLab CI Scaffold",
        description="...",
        version="0.1.0",
        author="...",
        tags=["ci", "gitlab"],
    )
```

## Inheriting tests

Every role has a matching `*TestHarness` in `fluid_sdk.testing`:

```python
from fluid_sdk.testing import (
    PluginTestHarness,         # base — 13 generic invariants (any role)
    CustomScaffoldTestHarness, # adds 7 scaffold-specific tests (atomic write, sha256, traversal)
)


class TestMyScaffold(CustomScaffoldTestHarness):
    plugin_class = MyScaffold
    # Inherits all the tests. Add your own scenarios below if needed.
```

Four lines, 20 tests free (13 from `PluginTestHarness` + 7 role-specific in `CustomScaffoldTestHarness`).

For `Validator`, `InfraProvider`, or `CatalogAdapter` plugins, subclass `PluginTestHarness` today and add role-specific assertions as additional `test_*` methods. Dedicated subharnesses for those roles are on the SDK roadmap.

## Source

- Role definitions: [`Agenticstiger/forge-cli-sdk/src/fluid_sdk/roles/`](https://github.com/Agenticstiger/forge-cli-sdk/tree/main/src/fluid_sdk/roles)
- Test harnesses: [`Agenticstiger/forge-cli-sdk/src/fluid_sdk/testing/`](https://github.com/Agenticstiger/forge-cli-sdk/tree/main/src/fluid_sdk/testing)

These are the truth source — when in doubt, read the class.
