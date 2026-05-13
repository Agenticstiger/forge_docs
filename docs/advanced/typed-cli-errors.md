# Typed CLI Errors

The upcoming `0.7.3` release introduces a 14-class typed-error catalog at `fluid_build.cli._errors`. Every user-facing CLI error renders the same five-field shape: **what**, **where**, **why**, **fix**, **doc**. JSON output is stable so CI log parsers and IDE integrations can consume it without regex.

::: tip Where this fits
This is the **CLI-level** error catalog, distinct from the **agent-layer** typed errors (`RateLimitError`, `ContextOverflowError`, etc.) documented at [Typed Errors](/forge_docs/advanced/typed-errors.html). CLI errors fire from user-facing commands; agent errors fire inside the LLM provider stack.
:::

## The five-field shape

Every typed error renders like this when printed to a terminal:

```text
✗ SchemaDriftError [code: schema_drift]
  what:  Source schema added 2 columns since last run.
  where: build=ingest_orders product=bronze.crm_orders run=2026-04-30T14-22-08
  why:   schemaEvolution.policy=strict — additive changes are not allowed.
  fix:   Set schemaEvolution.policy=evolve_safe to accept additive changes,
         or update the contract's schema block to declare the new columns.
  doc:   /advanced/source-aligned-acquisition.html#schema-evolution
```

And like this when the calling command was given `--json`:

```json
{
  "error": "SchemaDriftError",
  "code": "schema_drift",
  "what": "Source schema added 2 columns since last run.",
  "where": { "build": "ingest_orders", "product": "bronze.crm_orders", "run": "2026-04-30T14-22-08" },
  "why": "schemaEvolution.policy=strict — additive changes are not allowed.",
  "fix": "Set schemaEvolution.policy=evolve_safe to accept additive changes...",
  "doc": "/advanced/source-aligned-acquisition.html#schema-evolution",
  "extras": { "addedColumns": ["customer_tier", "loyalty_points"] }
}
```

The `extras` field carries error-class-specific structured detail (added columns, retry-after seconds, secret reference, etc.).

## The 14 typed errors

All inherit from `FluidUserError` (which subclasses `Exception`). Each has a `for_*` factory that constructs the right `where`/`extras` for the calling context.

### Validation & schema

| Class | When it fires |
|---|---|
| `SchemaValidationError` | A contract field didn't satisfy the v0.7.3 JSON schema. The `what` field cites the JSON-pointer path. |
| `SchemaDriftError` | The source schema changed between runs and the policy doesn't accept the kind of change. |

### Capability negotiation

| Class | When it fires |
|---|---|
| `CapabilityMismatchError` | The contract requires a capability (e.g. `exactly_once`) that the resolved runner doesn't declare. |
| `MissingExtraError` | An optional package isn't installed (`pip install 'data-product-forge[litellm]'`, etc.). |

### Connectivity & secrets

| Class | When it fires |
|---|---|
| `ConnectivityProbeError` | `--probe` was set on `fluid validate` and a source connectivity test failed (e.g. Postgres unreachable). |
| `SecretResolutionError` | A `${SECRET:...}` placeholder couldn't be resolved from the keychain at apply time. |

### Pipeline operations

| Class | When it fires |
|---|---|
| `PartialFailureError` | Some streams in the run succeeded; others failed. Exit code 2 (the partial-failure signal). |
| `DLQOverflowError` | `dlq.maxRecordsBeforeAbort` exceeded — the run aborted instead of dropping records silently. |
| `LockHeldError` | The single-flight lock for `(product, build, env)` is held by another run; this one was rejected. |
| `StaleReplayError` | A replay was requested past the `retention.runState` horizon — the manifest is no longer available. |

### Governance

| Class | When it fires |
|---|---|
| `BudgetExceededError` | The projected run cost would exceed the contract's monthly budget cap; `cost.onExceed=fail`. |
| `SovereigntyViolationError` | A connector / sink combination is not allowed in the declared jurisdiction. |
| `ResidencyViolationError` | A data transfer would violate `metadata.dataResidency.region` / `prohibitTransferTo`. |
| `InfraDriftError` | The live infrastructure version doesn't match what was declared (e.g. Helm chart drift). |

## Exit-code contract

The CLI exit-code contract is **uniform across all 14 error classes** so CI matrices stay simple:

| Exit code | Meaning |
|---|---|
| `0` | Success |
| `1` | User error — fix the contract or arguments and rerun |
| `2` | Partial — some work completed, some failed (e.g. `PartialFailureError`) |
| `3` | Transient — retry might succeed (`ConnectivityProbeError`, `LockHeldError`) |
| `4` | Internal — file an issue with the JSON output and traceback |

`SchemaValidationError`, `CapabilityMismatchError`, `MissingExtraError`, `BudgetExceededError`, `SovereigntyViolationError`, `ResidencyViolationError`, `SecretResolutionError`, `DLQOverflowError`, `SchemaDriftError`, `InfraDriftError` → exit code `1`.

`PartialFailureError` → exit code `2`.

`ConnectivityProbeError`, `LockHeldError`, `StaleReplayError` → exit code `3`.

Anything else (uncaught Python exceptions in the CLI) → exit code `4`.

## Catching them programmatically

```python
from fluid_build.cli._errors import (
    FluidUserError,
    SchemaValidationError,
    BudgetExceededError,
    PartialFailureError,
)

try:
    run_pipeline(contract)
except SchemaValidationError as e:
    log.warning("validation failed", extra=e.as_json())
    raise
except BudgetExceededError as e:
    notify_finance(e.extras["projected_usd"], e.extras["budget_usd"])
    raise
except FluidUserError as e:
    # Catch-all for unexpected typed errors
    log.error("typed error", extra=e.as_json())
    raise
```

`as_json()` returns the same JSON shape as `--json` mode, so error-handling code can rely on the stable structure regardless of which class fired.

## See also

- [Source-Aligned Acquisition](/forge_docs/advanced/source-aligned-acquisition.html) — the framework these errors guard
- [Typed Errors](/forge_docs/advanced/typed-errors.html) — the **agent-layer** typed errors (LLM-side; distinct catalog)
- [`fluid validate --probe`](/forge_docs/cli/validate.html#probe) — what triggers `ConnectivityProbeError`
- [`fluid retention sweep`](/forge_docs/cli/retention.html) — what `StaleReplayError` is preventing
