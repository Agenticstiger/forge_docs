# API Stability — `fluid_build.api`

The `fluid_build.api` package is the **stable extension surface** that out-of-tree runners, providers, catalog registrars, lineage emitters, and pre-land hooks target. Anything outside this package is internal and may change without notice.

::: tip Where this fits
The public API shipped alongside the source-aligned acquisition stack (schema `0.7.3`) at version `1.0`. As of CLI `0.18.0` it is at version `1.1` (`__api_version__ = "1.1"`): 1.1 added the [contract-loading API](./contract-loading-api.md) (`load_contract`, `load_contract_from_text`, `load_contract_from_dict`).
:::

## SemVer policy

```python
import fluid_build.api
print(fluid_build.api.__api_version__)
# 1.1
```

The API version is declared in `fluid_build/api/__init__.py`. SemVer applies:

| Change | Version bump | Notice period |
|---|---|---|
| Add a new optional method or class | Minor (1.0 → 1.1) | None — additive |
| Add a required method to a Protocol | Major (1.0 → 2.0) | 2-minor-version deprecation window |
| Change a method signature | Major | 2-minor-version deprecation window |
| Remove a class or method | Major | 2-minor-version deprecation window |

A 2-minor-version deprecation window means: if 2.0 will remove a method, 1.x must mark it deprecated for at least two minor releases (1.1 and 1.2 say "this will be removed in 2.0") before the actual removal.

## What's in the public API

The package is organized by extension point. Each module exports a Protocol (PEP 544), supporting types, and (where useful) a base class implementations can subclass for convenience.

| Module | Exports | Implement when you want to |
|---|---|---|
| `fluid_build.api.runner` | `Runner`, `RunnerCapability`, `RunResult`, `RunContext`, `RunPlan`, `RunState` | Add a new ingestion / build engine |
| `fluid_build.api.provider` | `Provider`, `PlanAction`, `ApplyResult` | Add a new infrastructure provider (cloud target) |
| `fluid_build.api.source` | `SourceSpec`, `ConnectionSpec`, `SinkSpec`, `AcquisitionMode`, `DeliveryGuarantee` | Define a new source/sink type for the acquisition pattern |
| `fluid_build.api.state` | `StateStore`, `Cursor`, `Watermark`, `RunLock` | Replace the FileStateStore with Redis / Postgres / etc. |
| `fluid_build.api.lineage` | `LineageEmitter`, `RunEvent`, `DatasetFacet` | Emit OpenLineage to a custom backend |
| `fluid_build.api.hooks` | `PreLandHook`, `HookResult`, `HookChain` | Add a new pre-write hook (DLP scan, masking, custom QA) |
| `fluid_build.api.quality` | `QualityGate`, `QualityResult`, `QualityRule`, `AnomalySignal`, `AnomalyResult` | Add a new DQ rule or anomaly detector |
| `fluid_build.api.cost` | `CostTracker`, `BudgetCap`, `ChargebackTag` | Implement a custom cost tracker / chargeback hook |
| `fluid_build.api.catalog` | `CatalogRegistrar`, `RegistrationResult` | Register datasets with a non-built-in catalog |
| `fluid_build.api.schema` | `SchemaPolicy`, `SchemaFingerprint`, `SchemaEvolutionDecision` | Customize schema-evolution decisioning |
| `fluid_build.api.security` | `ImageSignatureVerifier`, `SovereigntyChecker` | Add custom image-signing / sovereignty checks |
| `fluid_build.api.contract` | `load_contract`, `load_contract_from_text`, `load_contract_from_dict`, `LoadedContract`, `ContractOrigin`, `ContractLoadError` | Read a contract from Python exactly as `fluid plan` sees it (API 1.1) |
| `fluid_build.api.conformance` | `RunnerConformance` (test suite) | Verify your runner conforms to the Protocol |

## Writing a runner

A runner is a class that satisfies the `Runner` protocol. It declares what it can do and implements four methods, each taking one `RunContext`:

```python
# my_runner/runner.py
from typing import ClassVar, FrozenSet

from fluid_build.api.runner import (
    RunContext, RunnerCapability, RunPlan, RunResult,
)
from fluid_build.api.schema import SchemaFingerprint


class MyRunner:
    name: ClassVar[str] = "my-engine"
    declared_capabilities: ClassVar[FrozenSet[RunnerCapability]] = frozenset({
        RunnerCapability.FULL_REFRESH,
        RunnerCapability.SCHEMA_DISCOVERY,
        RunnerCapability.AT_LEAST_ONCE,
    })
    declared_modes: ClassVar[FrozenSet[str]] = frozenset({"embedded"})

    def plan(self, ctx: RunContext) -> RunPlan: ...
    def run(self, ctx: RunContext) -> RunResult: ...
    def replay(self, ctx: RunContext, run_id: str) -> RunResult: ...
    def fingerprint(self, ctx: RunContext) -> SchemaFingerprint: ...
```

`declared_modes` is a subset of `embedded`, `bring-your-own` and `managed`. `plan` previews what `run` would do, `replay` re-runs a prior run id, and `fingerprint` snapshots the source schema for drift detection.

Test it with the conformance suite. Set `runner` to an instance:

```python
# tests/test_my_runner.py
from fluid_build.api.conformance import RunnerConformance
from my_runner.runner import MyRunner


class TestMyRunner(RunnerConformance):
    runner = MyRunner()
    fixtures = "fluid_build.api.conformance.fixtures.minimal"
```

The suite checks that the class variables are present and that the runner declares at least one capability. It also checks that `plan` is idempotent, `run` returns the context's run id in a terminal state, `fingerprint` is stable, and the lineage events a run emits fit the OpenLineage shape. Pass it and your runner behaves like the built-in engines under `fluid runs`.

::: warning The CLI does not discover third-party runners
As of 0.18.1, `fluid apply` dispatches the `engine` values `duckdb`, `dlt`, `meltano`, `airbyte`, `kafka-connect` and `debezium` from a fixed table in `fluid_build/build_runners/base.py`. No entry-point group registers a runner, so a runner you write is used from your own code and tests, and not through `engine:` in a contract. The plug-in roles `fluid plugins` knows are `provider`, `validator`, `catalog`, `iac_provider` and `custom_scaffold`, plus `command`, `apply_hook`, `extension_schema`, `extension_validator`, `modeling_technique`, `source_adapter` and `llm_provider`; none of them is a runner or a registrar.
:::

## Writing a catalog registrar

A registrar satisfies the `CatalogRegistrar` protocol: a `target` name, `register_payload` as the canonical publish method, and `unregister`.

```python
from fluid_build.api.catalog import CatalogRegistrar, RegistrationResult


class MyCatalogRegistrar:
    target = "my-catalog"

    def register_payload(self, payload) -> RegistrationResult: ...
    def unregister(self, product_id: str, expose_id: str) -> RegistrationResult: ...
    def register(self, product_id, expose_id, contract, classifications) -> RegistrationResult: ...
```

`register_payload` receives a `CatalogPublicationPayload` that already carries the rendered specs and normalised metadata. `register` is the older per-expose entry point, kept so existing backends keep working. Each call publishes the whole product.

The built-in targets are `datahub`, `openmetadata`, `datamesh_manager`, `unity`, `glue` and `snowflake_horizon`; the CLI treats them through the same protocol, with no special case. As with runners, the CLI does not load a registrar from an entry point: a registrar is registered in code with `register_registrar` from `fluid_build.build_runners._catalog`, which is internal.

## Internal vs. public boundary

```python
# OK — public API
from fluid_build.api.runner import Runner, RunnerCapability

# NOT OK — internal; may change between patch releases
from fluid_build.cli.forge_copilot_runtime import _run_adaptive_interview
from fluid_build.copilot.agents.base import _retry_with_backoff
```

The rule of thumb: anything imported from `fluid_build.api.*` is governed by the SemVer policy above. Anything else is internal and may change without notice — even between 0.x.y patch releases. If you find yourself reaching into `fluid_build.cli.*` or `fluid_build.copilot.*`, file an issue requesting that surface be promoted to the public API.

## See also

- [Source-Aligned Acquisition](./source-aligned-acquisition.md): the framework the public API supports
- [Contract-loading API](./contract-loading-api.md): `load_contract` and its siblings
- [Custom Providers](../providers/custom-providers.md): the same pattern for `Provider` extensions
- [Forge Tools](./forge-tools.md): the `@forge_tool` decorator for in-process tool extensions (separate from the public API; lives in the copilot stack)
