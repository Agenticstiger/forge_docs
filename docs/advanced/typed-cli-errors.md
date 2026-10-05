# Typed CLI Errors

Some CLI failures are raised as typed errors that carry a `what`, a `why`, a `fix` and a `doc` link, and print as a panel. This page lists those classes, which command raises each, and how they render. Other failures are a different kind of error, described in [Two kinds of error](#two-kinds-of-error) and covered by event name in [Production troubleshooting](./production-troubleshooting.md).

## What one looks like

```bash
fluid import airbyte ws-123 --yes
```

```text
╭─────────────────────── ✗ `fluid import airbyte` has no Airbyte server URL ───────────────────────╮
│ why  Importing a workspace reads it over the Airbyte REST API, and no base URL was supplied on   │
│ the command line, in the environment, or by the calling code. There is no default to fall back   │
│ on.                                                                                              │
│ fix  Pass `--server-url https://airbyte.example.com`, or set FLUID_IMPORT_AIRBYTE_URL in the     │
│ environment.                                                                                     │
│ doc  https://agenticstiger.github.io/forge_docs/cli/import.html                                  │
╰──────────────────────────────────────────────────────────────────────────────────────────────────╯
```

The panel title is the `what`. The rows are `in` (the `where`, shown only when the error has one), `why`, `fix` and `doc`. The class name is not printed. `doc` is an absolute URL on this site, chosen from the [route table](#where-the-doc-links-land).

The error is a Python object with the same fields. `as_json()` returns a JSON **string** with sorted keys:

```python
from fluid_build.cli._errors import SchemaDriftError

e = SchemaDriftError.for_diff(
    baseline_digest="sha256:aa", current_digest="sha256:bb", summary="2 columns added"
)
print(e.as_json())
```

```json
{"code": "SchemaDriftError", "doc": "https://agenticstiger.github.io/forge_docs/advanced/typed-cli-errors.html#validation-schema", "extras": {}, "fix": "Review contract.exposes[].contract.schemaPolicy; if policy=evolve_safe, this is expected. If strict/discover_and_freeze, update the contract or fix the source.", "what": "source schema drift detected", "where": null, "why": "baseline=sha256:aa current=sha256:bb; 2 columns added"}
```

| Key | Value |
|---|---|
| `code` | The class name, for example `"SchemaDriftError"`. There is no `error` key |
| `what`, `why`, `fix`, `doc` | Strings |
| `where` | A string such as `contract.fluid.yaml:12:3`, or `null` |
| `extras` | An object. The `for_*` factories leave it empty; a raise site may fill it |

When the running command has a `--json` flag and the error reaches the top-level handler, the CLI prints this string to stdout instead of the panel. Not every command has `--json`; `fluid validate`, for example, uses `--format json` and prints its own report.

## Two kinds of error

| | Typed error (this page) | Catalogued CLI error |
|---|---|---|
| Looks like | The panel above | An `<event>  [ERR_<EVENT>]` heading, key-value lines, suggestions and a documentation link |
| Raised by | Build runners, providers, secrets, imports, `fluid init --discover` | Most commands |
| Exit code | 1 | Set by the raise site, usually 1; 2 for some argument problems |
| Machine-readable | `code` is the class name | The `ERR_` slug, derived from the event name, which stays stable |

A catalogued error looks like this:

```text
❌ schedule_sync_dags_dir_not_product_scoped  [ERR_SCHEDULE_SYNC_DAGS_DIR_NOT_PRODUCT_SCOPED]
  dags_dir: .../dags
  loose_files: ['customer_360_pipeline_dag.py']
  hint: --delete-scope product (the default) mirrors each top-level directory of --dags-dir ...
```

Its `📖` link goes to a page chosen by the same route table. Both kinds are explained, by event name or class name, in [Production troubleshooting](./production-troubleshooting.md).

## The typed errors

Each class has a `for_*` factory that builds the `what`, `why`, `fix` and `doc` for its raise site. No factory fills `extras`. The classes live in `fluid_build._errors`; `fluid_build.cli._errors` re-exports them.

### Validation & schema

| Class | Raised by |
|---|---|
| `SchemaValidationError` | `fluid import` (a missing source argument, an unknown importer, a missing Airbyte server URL, or an import that fails, with the importer's reason) and `fluid init --discover` (an unsupported URI scheme). These raise sites set their own `doc` link, to the import or init page. `fluid validate` does not raise it: it prints its own validation report and exits 1 |
| `SchemaDriftError` | A build runner whose source schema changed between runs under a `schemaPolicy` that does not accept the change |

`SchemaValidationError` is also the name of a different class in the forge agent layer; see [Typed Errors](./typed-errors.md). The two are not the same type.

The route table also sends four catalogued events here: `invalid_schema_version`, `contract_version_unsupported`, `invalid_min_version` and `invalid_max_version`. Set `fluidVersion` to a version the installed CLI bundles. The latest stable contract schema is 0.7.5; 0.7.6 is a preview that a contract opts in to with `fluidVersion: "0.7.6"`. `fluid validate` reports the version it validated against.

### Capability negotiation

| Class | Raised by |
|---|---|
| `CapabilityMismatchError` | A build runner, when the build asks for a capability the runner does not declare (for example `exactly_once`). Fix: use an engine that declares it, or remove it from `build.capabilities` |
| `MissingExtraError` | The dlt runner, when an optional package is not installed. The `fix` row carries the install command, for example `pip install 'data-product-forge[litellm]'` |

### Connectivity & secrets

| Class | Raised by |
|---|---|
| `ConnectivityProbeError` | `fluid init --discover`, when discovering streams at the URI fails, for example because the source is unreachable |
| `SecretResolutionError` | `fluid secrets login` and `fluid secrets rotate`, when no secret value arrives on stdin and the prompt is cancelled |

The route table also sends three catalogued events here: `opentofu_init_failed`, `market_discovery_failed` and `copilot_llm_model_preflight_failed`. For `opentofu_init_failed`, check provider credentials and network access, then run the apply again. For the other two, check network access to the endpoint and, for the model preflight, the provider key; Ollama needs its server running and the model pulled.

### Pipeline operations

| Class | Raised by |
|---|---|
| `PartialFailureError` | The DuckDB acquisition runner, when some streams succeeded and others failed |
| `DLQOverflowError` | The runner's dead-letter queue, when `dlq.maxRecordsBeforeAbort` is exceeded and the run aborts instead of dropping records |
| `LockHeldError` | The runner state store, when another run holds the single-flight lock for the same scope and resource |
| `StaleReplayError` | The runner state store, when a replay targets a run past the `retention.runState` horizon and its manifest is gone |

### Governance

| Class | Raised by |
|---|---|
| `BudgetExceededError` | A runner's cost check, when a run's usage exceeds `properties.cost.budget.monthly` and `onExceed` is `fail` |
| `SovereigntyViolationError` | The GCP and AWS providers, when a placement is refused by the contract's `sovereignty` block (an allowed region or jurisdiction not met) |
| `ResidencyViolationError` | The AWS provider, when a binding's region is in `deniedRegions`, or an `allowedRegions` list is declared and the region is not on it |
| `SupplyChainViolationError` | The Airbyte runner, when a connector image fails Cosign verification or its signer is not in `sovereignty.allowedSigners` |
| `InfraDriftError` | Defined for infrastructure version drift. As of 0.18.1 nothing raises it |

`SupplyChainViolationError`, `CapabilityMismatchError` and `BudgetExceededError` link to the pages on [bundle signing](../cli/verify-signature.md), [capability warnings](./capability-warnings.md) and [cost tracking](./cost-tracking.md), because those are the pages the CLI's route table names. Those pages cover different features: signing there is for `fluid bundle --sign` archives, not connector images. The sections above are the ones that describe these errors. For connector images and signers, see [source-aligned acquisition](./source-aligned-acquisition.md) and [sovereignty](../concepts/sovereignty.md).

### Embedded SQL, object stores and the sandbox

These classes arrived after the original catalog. Inside a build they print as three lines (`what`, `why`, `fix`) and fail the build with exit code 1, and their `doc` link goes to [Production troubleshooting](./production-troubleshooting.md).

| Class | Raised when |
|---|---|
| `ConsumesResolutionError` | A `consumes[]` entry of an embedded-SQL build cannot be bound to a relation |
| `UnreadableBindingError` | The upstream expose resolved, but to a binding the engine cannot read |
| `EmbeddedSqlLandingError` | The build's own expose names a landing the embedded-SQL path will not perform |
| `MaskingNotAppliedError` | That expose declares `policy.privacy.masking`, which the embedded-SQL landing path does not apply |
| `EmbeddedSqlSovereigntyError` | A BigQuery read or landing that the contract's `sovereignty` block does not allow |
| `ObjectStoreEndpointError` | An `AWS_ENDPOINT_URL` override is set, but DuckDB could not be pointed at it |
| `DuckDBSandboxError` | A DuckDB connection could not be opened inside the [sandbox](./duckdb-sandbox.md) |

## Exit codes

`fluid` exits with these codes. The first two rows are what the top-level handler does; commands document any codes of their own.

| Exit code | Meaning |
|---|---|
| `0` | Success |
| `1` | A typed error reached the top-level handler, whichever class it is. Catalogued errors exit with the code their raise site chose, usually `1` |
| `2` | An uncaught Python exception (`❌ Unexpected error`; re-run with `--debug` for the traceback), or a catalogued error whose raise site chose 2 |
| `130` | `fluid apply` interrupted |

No class of this page carries its own exit code. A command that uses other codes says so on its own page: `fluid verify-signature` uses 2 for a configuration error, and `fluid mcp output-port serve` exits 2 on a jurisdiction refusal.

## Catching them in Python

```python
import json
import logging

from fluid_build.cli._errors import BudgetExceededError, FluidUserError

log = logging.getLogger("pipeline")

try:
    run_pipeline(contract)
except BudgetExceededError as e:
    log.error("budget exceeded: %s", e.why)
    raise
except FluidUserError as e:
    log.warning("typed error", extra={"fluid_error": json.loads(e.as_json())})
    raise
```

`as_json()` returns a string, so decode it before putting it in a logging `extra`. The fields are also attributes: `e.what`, `e.why`, `e.fix`, `e.doc`, `e.where`, `e.code` and `e.extras`. The factory signatures are keyword-only, for example `BudgetExceededError.for_cap(dimension=, used=, cap=)` and `SchemaDriftError.for_diff(baseline_digest=, current_digest=, summary=)`. The budget error does not set `extras`, so read `e.why`, not an invented key.

## Where the doc links land

The CLI builds each `doc` link from a fixed route table. A topic that is not in the table falls back to [Production troubleshooting](./production-troubleshooting.md).

| Topic | Page |
|---|---|
| `acquisition`, `schema-evolution` | [Validation & schema](#validation-schema) on this page |
| `installation#extras` | [Capability negotiation](#capability-negotiation) |
| `troubleshooting#connectivity` | [Connectivity & secrets](#connectivity-secrets) |
| `concurrency`, `dlq`, `replay` | [Pipeline operations](#pipeline-operations) |
| `infra#drift` | [Governance](#governance) |
| `capabilities` | [Capability warnings](./capability-warnings.md) |
| `cost` | [Cost tracking](./cost-tracking.md) |
| `providers` | [`fluid providers`](../cli/providers.md) |
| `secrets` | [`fluid secrets`](../cli/secrets.md) |
| `sovereignty`, `sovereignty#residency` | [Sovereignty](../concepts/sovereignty.md) |
| `supply-chain` | [`fluid verify-signature`](../cli/verify-signature.md) |
| `installation` | [Getting started](../getting-started/README.md) |
| anything else | [Production troubleshooting](./production-troubleshooting.md) |

A few catalogued events land on a page that does not explain them. The CLI chooses these routes, so the explanations are here:

| Event | Lands on | What it means |
|---|---|---|
| `copilot_missing_llm_api_key` | [`fluid secrets`](../cli/secrets.md) | That page covers source and pipeline secrets. LLM keys are not stored there: run `fluid ai setup`, or set `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` or `GEMINI_API_KEY`; `--llm-provider ollama` needs no key |
| `policy_compile_failed`, `policy_apply_failed` | [Sovereignty](../concepts/sovereignty.md) | The failure is in the contract's `agentPolicy` or `accessPolicy` block. Run `fluid policy check <contract>` to see the offending rule |
| `opentofu_engine_install_failed` | [Getting started](../getting-started/README.md) | `tofu` is missing or older than 1.6.0. Install OpenTofu 1.6.0 or newer, or run `fluid apply --ensure-opentofu` |

## See also

- [Production troubleshooting](./production-troubleshooting.md): errors by event name, with diagnosis and fix
- [Typed Errors](./typed-errors.md): the forge agent layer's errors (`RateLimitError`, `ContextOverflowError`, ...), a different catalog
- [Source-aligned acquisition](./source-aligned-acquisition.md): the framework most of these errors guard
- [`fluid retention sweep`](../cli/retention.md): what `StaleReplayError` is protecting
