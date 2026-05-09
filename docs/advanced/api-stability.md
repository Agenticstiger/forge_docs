# API Stability — `fluid_build.api`

The `fluid_build.api` package is the **stable extension surface** that out-of-tree runners, providers, catalog registrars, lineage emitters, and pre-land hooks target. Anything outside this package is internal and may change without notice.

::: tip Where this fits
The public API ships with the source-aligned acquisition stack in the upcoming `0.7.3` release. It's pinned at version `1.0` (`__api_version__ = "1.0"`).
:::

## SemVer policy

```python
import fluid_build.api
print(fluid_build.api.__api_version__)
# "1.0"
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
| `fluid_build.api.conformance` | `RunnerConformance` (test suite) | Verify your runner conforms to the Protocol |

## Quickstart — adding a new runner

```python
# my_runner/runner.py
from fluid_build.api.runner import Runner, RunnerCapability, RunResult, RunContext

class MyRunner:
    name = "my-engine"
    capabilities = frozenset({
        RunnerCapability.FULL_REFRESH,
        RunnerCapability.SCHEMA_DISCOVERY,
        RunnerCapability.AT_LEAST_ONCE,
    })

    def validate(self, contract, build, *, ctx: RunContext) -> None:
        ...

    def plan(self, contract, build, *, ctx: RunContext) -> dict:
        ...

    def apply(self, contract, build, *, ctx: RunContext) -> RunResult:
        ...
```

Register it via entry-point:

```toml
# pyproject.toml
[project.entry-points."fluid_build.runners"]
my-engine = "my_runner.runner:MyRunner"
```

Run the conformance suite:

```python
# tests/test_my_runner.py
from fluid_build.api.conformance import RunnerConformance
from my_runner.runner import MyRunner

class TestMyRunner(RunnerConformance):
    runner_class = MyRunner
```

The conformance suite asserts every Protocol method is implemented, signatures match, the run-record JSON shape is uniform, and the exit-code contract is honored. Pass that and your runner behaves identically to the built-in six (DuckDB, dlt, Meltano, Airbyte, Kafka Connect, Debezium) under day-2 ops.

## Quickstart — adding a catalog registrar

```python
from fluid_build.api.catalog import CatalogRegistrar, RegistrationResult

class MyCatalogRegistrar:
    name = "my-catalog"

    def register(self, contract, dataset, *, ctx) -> RegistrationResult:
        ...
```

Out-of-tree registrars work via the same entry-point pattern (`[project.entry-points."fluid_build.catalog_registrars"]`). The five built-in registrars (DataHub, OpenMetadata, Unity, Glue, Snowflake Horizon) implement the same Protocol — they're not special-cased.

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

- [Source-Aligned Acquisition](/forge_docs/advanced/source-aligned-acquisition.html) — the framework the public API supports
- [Custom Providers](/forge_docs/providers/custom-providers.html) — the same pattern for `Provider` extensions
- [Forge Tools](/forge_docs/advanced/forge-tools.html) — the `@forge_tool` decorator for in-process tool extensions (separate from the public API; lives in the copilot stack)
