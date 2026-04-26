# Agentic Primitives

Forge-cli's staged pipeline is built from a small set of reusable
primitives that any new agent or external observer can compose.
This page is the operator + contributor reference for each one.

> **Audience:** Contributors building a new staged agent, operators
> debugging unexpected pipeline behavior, integrators wiring an
> external observability dashboard.

## The seven primitives

| Primitive | Module | Purpose |
|---|---|---|
| [`StageSession`](#stagesession) | `fluid_build.copilot.agents.base` | Per-run shared state passed to every agent |
| [`Scratchpad`](#scratchpad) | `fluid_build.copilot.scratchpad` | Typed inter-agent shared state (critic findings, RAG retrievals, stage feedback) |
| [`EventBus`](#eventbus) | `fluid_build.copilot.events` | In-process pub/sub for run-level signals |
| [`RunCostTracker`](#runcosttracker) | `fluid_build.copilot.cost` | Token / cost / per-agent attribution |
| [`CriticAgent`](#criticagent) | `fluid_build.copilot.agents.critic_agent` | Heuristic reviewer between staged outputs |
| [`ConformanceAgent`](#conformanceagent) | `fluid_build.copilot.agents.conformance_agent` | Pre-emit lint against Fluid + OSI + ODCS / DCS readiness |
| [`retrieve_similar_models`](#retrieval) | `fluid_build.copilot.retrieval` | RAG helper against `memory/semantic` |

## StageSession

The session object every agent receives. Carries the store, LLM
config, capability matrix, scratchpad, and metadata flags
(`fallback_used`, `repair_used`, `tiered`, `no_cache`).

```python
from fluid_build.copilot.agents.base import StageSession
from fluid_build.copilot.store.backends.file import FileBackend

session = StageSession(
    store=FileBackend(root="~/.fluid/store", workspace_root="."),
    llm_config=...,
    active_provider="anthropic",
)
# Lazy scratchpad accessor — never construct directly.
scratchpad = session.get_scratchpad()
```

**Key invariants:**

- `active_provider` is set automatically from `llm_config.provider`
  on construction. The coordinator asserts every staged call's
  resolved provider matches `active_provider` — single-provider-per-run.
- `capability_matrix` is a free-form dict that flows through the
  cache key. Flipping any flag (extended thinking, RAG limit,
  prompt-cache mode) invalidates the cache cleanly.
- `record_fallback()` / `record_repair()` capture pipeline
  events for the audit trail without coupling agents to the
  recorder.

## Scratchpad

Typed shared state for inter-agent signal passing. **The agentic
backbone for v1.5+.** Lives on `session.scratchpad`; lazy-created
on first `session.get_scratchpad()` call.

### Slots

| Slot | Type | Used by |
|---|---|---|
| `critic_findings` | `list[CriticFinding]` | `CriticAgent` writes; modeler / builder read |
| `retrievals` | `list[RetrievalResult]` | `retrieve_similar_models` writes; modeler reads |
| `feedback` | `list[StageFeedback]` | Coordinator validator writes; rerun path reads |
| `raw` | `dict[str, Any]` | Free-form ad-hoc slots |

### Reading

```python
from fluid_build.copilot.scratchpad import CriticFinding, StageFeedback

# Critic findings addressed to a specific stage:
findings = scratchpad.critic_findings_for_stage("logical")
errors = [f for f in findings if f.severity == "error"]

# Validator feedback for the next builder run:
feedback = scratchpad.feedback_for_stage("builder")

# Top-3 retrievals from memory/semantic (sorted by similarity):
top = scratchpad.top_retrievals(limit=3, namespace="memory/semantic")
```

### Writing

```python
scratchpad.add_critic_finding(CriticFinding(
    stage="logical",
    severity="warning",
    message="hub_customer has no business_key_columns",
    suggestion="set business_key_columns to ['customer_id']",
    target="dv2.hubs.hub_customer.business_key_columns",
))

scratchpad.add_feedback(StageFeedback(
    source_stage="validator",
    target_stage="builder",
    summary="3 errors in metadata; retry with corrections",
    structured={"errors": ["domain missing", ...]},
))
```

### Thread safety

`add_*` calls take an internal lock so parallel-physical fanout
(three threads writing concurrently) doesn't drop events. Reads
return defensive snapshots — caller mutations don't pollute the
scratchpad.

## EventBus

Process-wide pub/sub for run-level signals. **Decomposes the
previously god-class `RunCostTracker`** into a publisher and N
subscribers; new observers (telemetry exporters, audit writers,
operator dashboards) subscribe without touching the tracker's
internals.

### Event types emitted today

| Event | Payload | Emitter |
|---|---|---|
| `llm.call_completed` | `provider, model, input_tokens, output_tokens, stage, agent_class, missing_usage` | `RunCostTracker.record_call` |
| `llm.usage_missing` | `{}` | `RunCostTracker.record_missing_usage` |
| `validator.variant_lint` | `variant, warning_count` | `RunCostTracker.record_variant_lint` |
| `catalog.fetch_completed` | `catalog_name, duration_ms` | `RunCostTracker.record_catalog_fetch` |

### Subscribing

```python
from fluid_build.copilot.events import Event, get_event_bus

bus = get_event_bus()

def my_observer(event: Event) -> None:
    if event.event_type == "llm.call_completed":
        print(f"{event.payload['stage']} cost: "
              f"{event.payload['input_tokens']} + "
              f"{event.payload['output_tokens']} tokens")

unsubscribe = bus.subscribe(my_observer)
# ... when done:
unsubscribe()
```

### Failure isolation

A subscriber that raises is logged at DEBUG and otherwise ignored
— one bad observer can never break the rest of the pipeline.

## RunCostTracker

Per-run token / cost accumulator. Module-level singleton because
it has to be writable from threads (parallel-physical fanout)
without threading a context object through the entire stack.

### Five state dimensions

| Dimension | Surfaced via |
|---|---|
| Per-`(provider, model)` token counts | `breakdown.rows` |
| Per-`(stage, agent_class)` attribution | `breakdown.agent_rows` (Missing #5) |
| `missing_usage_calls` counter | Footer warning |
| `variant_lint_findings` per variant | Footer warning |
| `catalog_fetch_ms` per catalog | Footer line |

### Cost ceiling

Set a per-run budget cap:

```bash
export FLUID_COST_LIMIT_USD=5.00
fluid forge data-model from-source --source snowflake --credential-id snowflake-prod ...
```

OR via `~/.fluid/config.yaml`:

```yaml
behavior:
  cost_limit_usd_per_run: 5.00
```

When the running total exceeds the limit, the forge aborts with
`CostLimitExceeded($X.XX > $Y.YY)`. Defends against runaway
agentic runs from blowing through your budget.

## CriticAgent

Heuristic (LLM-free) reviewer between staged outputs.
**Three review surfaces:**

| Method | Reviews | Sample findings |
|---|---|---|
| `review_logical(logical, scratchpad=...)` | DV2 hubs / links + dimensional facts / dimensions + conceptual orphans | "hub_X has no business_key_columns" / "fact has no measures" |
| `review_contract(contract, scratchpad=...)` | Fluid contract dict | "exposes is empty" / "metadata.domain missing" |
| `review_transform(transform_plan, logical, scratchpad=...)` | dbt build-graph cycles | "circular dependency: a → b → c → a" |

Findings land on `scratchpad.critic_findings`. Severity levels:

- `error` — critical issue. **Triggers the repair loop** via
  `_escalate_critic_errors_into_report`.
- `warning` — informational; surfaces in the receipt but doesn't
  block.
- `info` — observational; helps operator triage.

### Adding a new critic rule

```python
# In your fork or a future PR to fluid_build/copilot/agents/critic_agent.py:

def review_logical(self, logical, *, scratchpad):
    findings = []
    # ... existing rules ...
    # NEW: warn when a hub's mapped_source_tables is empty.
    for hub in (getattr(logical.dv2, "hubs", []) or []):
        if not hub.mapped_source_tables:
            findings.append(CriticFinding(
                stage="logical",
                severity="warning",
                message=f"Hub {hub.entity_name!r} has no mapped_source_tables",
                target=f"dv2.hubs.{hub.entity_name}.mapped_source_tables",
            ))
    for f in findings:
        scratchpad.add_critic_finding(f)
    return findings
```

The coordinator's `_run_logical_critic` already calls
`review_logical` after every Logical stage — your new rule
fires automatically.

## ConformanceAgent

Pre-emit lint against four standards in parallel:

| Standard | Implementation |
|---|---|
| `fluid` | Full Fluid 0.7.2 schema validator |
| `osi` | Full OSI v0.1.1 Pydantic validator |
| `odcs_translation_readiness` | Checks the contract carries the fields a future ODCS exporter needs |
| `dcs_translation_readiness` | Same shape, for DCS |

```python
from fluid_build.copilot.agents.conformance_agent import ConformanceAgent

agent = ConformanceAgent()
report = agent.run(logical=logical, contract=contract)
print(report.summary())
# "conformance: ✓ all 2 standards clean"
```

### Dialect mapper integration

`ConformanceAgent.apply_dialect_mapper(logical)` runs the
deterministic multi-dialect type mapper over OSI
`expression.dialects[]` arrays and back-fills missing dialects.
Defaults to `OSI_SUPPORTED_DIALECTS` so back-fill never produces
values that fail OSI's Literal enum.

## retrieve_similar_models (RAG helper)

Single canonical entry point for `memory/semantic` retrieval:

```python
from fluid_build.copilot.retrieval import (
    retrieve_similar_models,
    RetrievalConfig,
)

results = retrieve_similar_models(
    "customer orders data vault",
    store=session.store,
    scratchpad=session.get_scratchpad(),
    config=RetrievalConfig(limit=3, mode="hybrid"),
)
```

Best-effort:

- `NullBackend` returns empty.
- Vector index errors return empty.
- Empty query short-circuits to empty without hitting the store.

The modeler's private `_retrieve_prior_similar_models`
delegates here so there's one canonical retrieval code path.

## Unified config

Replace four scattered files with one `~/.fluid/config.yaml`:

```yaml
schema_version: 1
llm:
  provider: anthropic
  model: claude-sonnet-4-6
  tiered: false
sources:
  sources:
    snowflake-prod:
      catalog: snowflake
      auth_method: key_pair
      account: myorg-abc12345
prices:
  prices:
    claude-sonnet-4-6: [2.40, 12.00]
behavior:
  quiet: false
  deterministic: false
  cost_limit_usd_per_run: 5.00
```

Migrate from existing per-feature files:

```bash
fluid config migrate            # if shipped; otherwise:
python -c "from fluid_build.copilot.unified_config import migrate_legacy_to_unified; print(migrate_legacy_to_unified())"
```

Per-feature legacy files (`ai_config.json`, `sources.yaml`,
`prices.json`) continue to be read as fallback so v1.5 installs
work unchanged.

## Composing them: the staged pipeline

```
┌─ StageSession (per-run shared state)
│   ├─ store: Store backend
│   ├─ llm_config + active_provider
│   ├─ scratchpad: Scratchpad ───── ← typed inter-agent state
│   └─ capability_matrix
│
├─ EventBus (process-wide pub/sub)
│   ├─ llm.call_completed         ← RunCostTracker
│   ├─ catalog.fetch_completed    ← LogicalAgent (catalog path)
│   ├─ validator.variant_lint     ← FluidContractValidator
│   └─ llm.usage_missing          ← BaseStageAgent
│
└─ Pipeline order:
   LogicalAgent ──→ CriticAgent.review_logical ──→ scratchpad
       │
       ├──→ retrieve_similar_models ──→ scratchpad.retrievals
       │
   BuilderAgent (reads scratchpad → provenance)
       │
   _run_pre_emit_conformance ──→ ConformanceAgent.run
       │                          + apply_dialect_mapper
   ValidatorAgent
       │
   _escalate_critic_errors_into_report (C8)
       │
   _maybe_repair_physical (rerun stages with feedback)
       │
   _record_forge_episode ──→ memory/episodic
   write_semantic_record ──→ memory/semantic
```

## See also

- [V1.5 architecture deep-dive](v1.5-architecture.md)
- [Cost tracking details](cost-tracking.md)
- [Credential resolver](credential-resolver.md)
- [V1.5 release notes](v1.5-release-notes.md)
