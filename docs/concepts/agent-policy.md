---
title: Agent Policy (LLM/AI governance)
description: Declarative boundaries on which AI models can read which data fields.
---

# Agent Policy — declarative AI governance

Declared per-expose at `exposes[].policy.agentPolicy` — a block that declares **which AI / LLM models are allowed to read this data product, for which purposes, and under what conditions**. The fields were introduced in `fluidVersion: "0.7.1"` as declarative metadata; **runtime enforcement landed in `0.7.4`** ("Runtime agentPolicy Enforcement at the MCP Gateway"). Most dimensions (model / use-case) are checked before the read executes; the per-request token cap is a post-hoc throttle (see [`maxTokensPerRequest`](#the-shape)).

> **Why it matters**
> AI agents are often your largest data consumer — `agentPolicy` makes their access boundaries declarative, the same way `accessPolicy` governs people.
> Forge enforces those rules at the MCP output port on every agent call. An agent that queries the warehouse directly with its own credentials is governed by cloud IAM, not by `agentPolicy`.

<CliCast
  src="/forge_docs/demos/agent-policy.svg"
  title="agentPolicy — declare, validate, gate (validate → policy-check → audit)"
  caption="Watch agentPolicy enforce: the YAML block with allowedModels / deniedUseCases / canStore / auditRequired, schema validation, the policy-check enforcement summary, and a replay of agent reads — gpt-4 + analysis allowed, claude-3 + training denied, an unlisted model denied, gemini summarization allowed."
  width="920"
  insight="Declared in YAML. Enforced at read-time by the MCP output port. | Model and use case are checked before each call; the token caps apply to what is returned. | Every allow and every deny is written as a local data_access audit record."
/>

## Why declarative?

Most teams discover their data is being read by AI agents only after it's already in a vector store. `agentPolicy` makes the intent **part of the contract**, alongside the schema and the IAM grants — so it's reviewed, versioned, and audited the same way.

## The shape

Verified field list from `fluid-schema-0.7.5.json` (the current schema) — `agentPolicy` is **not** a contract-root key; it lives per-expose at `exposes[].policy.agentPolicy`, so each expose carries its own AI-access boundary. The object has these properties:

| Field | Type | Purpose |
|-------|------|---------|
| `allowedModels` | `string[]` | Whitelist of AI models permitted (e.g. `claude-sonnet-4-6`, `gpt-4.1-mini`). Free-form strings, matched literally against the requesting model id — so use the exact, non-deprecated ids your agents send. Empty array = no AI access. |
| `deniedModels` | `string[]` | Explicit denylist. Takes precedence over `allowedModels`. |
| `allowedUseCases` | `string[]` | Permitted purposes (e.g. `analysis`, `summarization`, `qa`). |
| `deniedUseCases` | `string[]` | Prohibited purposes (e.g. `training`, `fine_tuning`). |
| `maxTokensPerRequest` | `integer` | Per-request token ceiling, enforced as a **post-hoc throttle**: the read executes, the response size is measured (≈ chars / 4), and the response is *withheld* with `TokenBudgetExceeded` if it exceeds the cap. It bounds what an agent receives per call — it does not stop the underlying query from running. |
| `maxTokensPerDay` | `integer` | Daily token budget. Enforces quota. |
| `canReason` | `boolean` | Whether agents can use this data for multi-step reasoning. |
| `canStore` | `boolean` | Whether AI systems can cache/store the data. `false` = ephemeral only. |
| `retentionPolicy` | `object` | Retention requirements for caches/stores (shape per schema). |
| `auditRequired` | `boolean` | Whether AI consumption must be logged. |
| `purposeLimitation` | `string` | Free-text description of allowed purposes. |
| `tags`, `labels` | various | Categorization + automation hooks. |

## Example

```yaml
exposes:
  - exposeId: customer_360_table
    # ... kind, binding, contract ...
    policy:
      agentPolicy:
        allowedModels:
          - claude-sonnet-4-6
          - claude-opus-4-7
          - gpt-4.1-mini
        allowedUseCases:
          - analysis
          - summarization
          - qa
        deniedUseCases:
          - training
          - fine_tuning
        maxTokensPerRequest: 4000
        canStore: false
        auditRequired: true
        purposeLimitation: "Customer-support analytics only. No marketing or model training."
```

`agentPolicy` nests under `exposes[].policy` — it is scoped to the individual expose, not the contract root. A contract that puts `agentPolicy` at the top level fails schema validation.

## Combining with column-level `sensitivity`

`agentPolicy` has no `piiHandling` field. Tag PII at the column level instead:

```yaml
exposes:
  - exposeId: customers
    contract:
      schema:
        - name: customer_id
          type: STRING
        - name: email
          type: STRING
          sensitivity: pii         # redacted in every MCP output-port result
```

The MCP output port replaces the values of `pii` and `phi` columns with a redaction token in every result it serves, whatever the platform. To change what is stored, declare `policy.privacy.masking` on the expose; it is applied when the DuckDB acquisition runner lands the data. No warehouse masking policy is emitted from either field. See [Governance & Policy → Masking](./governance-policy.md#masking-policy-privacy-masking).

## Where it's enforced

| Surface | How `agentPolicy` is honored |
|---------|-------------------------------|
| **`fluid validate`** | Checks the block for consistency: a model in both `allowedModels` and `deniedModels` is an error, for example. |
| **`fluid mcp output-port serve`** | Read-time enforcement when agents speak MCP. This is the consumer-side data-access gate: every read passes through the agentPolicy gate (model / use-case checked pre-dispatch; the per-request token cap applied after). See "Enforcement modes" below. (`fluid mcp serve` is the producer/authoring tool server — it does **not** gate data reads.) |
| **Audit record** | The output port writes a local `data_access` record for every decision, allow and deny, whether or not `auditRequired` is set. See [Audit event schema](#audit-event-schema). |

## Enforcement modes

`agentPolicy` is a declaration. The MCP output port is the only forge-cli component that enforces it; the other two modes below are what you do when agents do not read through it.

### 1. MCP server (preferred for agentic workflows)

The Forge consumer-side MCP server at `fluid mcp output-port serve` binds one expose and exposes it as an MCP data port. Every read passes through the agentPolicy gate:

```
agent (claude-sonnet-4-6)  ──read──►  fluid mcp output-port serve
                                          │
                                          ▼
                                      agentPolicy gate
                                          │
                                          ├─ ALLOW ─►  fetch + return + audit
                                          └─ DENY  ─►  TextContent JSON envelope + audit (with reason)
```

A denied read does not return an HTTP 403 — the stdio gateway returns a `TextContent` JSON envelope `{error: "AgentPolicyDenied" | "TokenBudgetExceeded", reason, message}`. The server reads `agentPolicy` from the expose at startup and checks it on every request. Each decision is written to the local audit directory (see [Audit event schema](#audit-event-schema)). (`fluid mcp serve` is the producer/authoring tool server — catalog reads, contract regeneration — and does not enforce agentPolicy on data reads.)

### 2. Platform-side controls

When agents query the warehouse directly over SQL or HTTP, the gateway is not in the path, and no forge-cli command turns `agentPolicy` into a platform policy as of 0.18.1. `fluid policy-compile` reads only `accessPolicy.grants`, and `fluid policy-apply` provisions nothing. Govern those reads with the cloud's own IAM, which the contract does drive:

- **GCP:** `accessPolicy.grants` become dataset IAM members, and `policy.authz.columnRestrictions` become Data Catalog policy tags with fine-grained readers, both at `fluid apply`. Give each agent its own service account and grant or restrict it like any other principal. BigQuery row access policies are not emitted.
- **AWS:** `binding.governance.lakeFormation` grants, excluded columns and data cells filters, at `fluid apply`.
- **Snowflake:** nothing from contract fields (see the [per-cloud table](./governance-policy.md#what-gets-emitted-per-cloud)).

`fluid_build.output_ports.iam_compiler` is a Python module that compiles `agentPolicy` and `rowFilters` into Snowflake and PostgreSQL row access SQL; BigQuery and Lake Formation are stubs. No command calls it, so you run its output yourself; see "Cloud-IAM compilers" on [Advanced → MCP output port](../advanced/mcp.md).

### 3. Application-level (when neither MCP nor platform IAM fits)

For agents that read directly via SQL/HTTP and *can't* migrate to MCP or use platform-level enforcement, the application owns the gate. The pattern: load the contract with the public loading API, inspect the target expose's `policy.agentPolicy`, and decide allow or deny in your own code before issuing the read:

```python
from fluid_build.api import load_contract

loaded = load_contract("contract.fluid.yaml")
expose = next(e for e in loaded.contract["exposes"] if e["exposeId"] == "customers")
agent_policy = (expose.get("policy") or {}).get("agentPolicy") or {}
```

`load_contract` resolves `$ref` fragments and overlays the way `fluid plan` does; see [Contract loading API](../advanced/contract-loading-api.md).

This is the weakest mode (the application is the trust boundary) but useful when migrating legacy agent code incrementally.

## Audit event schema

`fluid mcp output-port serve` writes one JSON file per decision, allow or deny, whether or not `auditRequired` is set. A deny, as written by 0.18.1:

```json
{
  "event": "data_access",
  "payload": {
    "argumentSummary": {},
    "callerJurisdiction": null,
    "contractPath": "/work/crm/contract.fluid.yaml",
    "decision": "deny",
    "exposeId": "customers",
    "modelId": "claude-sonnet-4-6",
    "policyDigest": "jcs-sha256:0dbebed8540b9627faafe992ad6b575c463d2e22d4d891398dc050edb4a30ed3",
    "policySource": "contract",
    "reason": "in-deniedUseCases",
    "runId": "a481cf8fa607",
    "tool": "describe",
    "useCase": "training"
  },
  "timestamp_utc": "2026-10-05T00:18:04.213845+00:00"
}
```

- **Where:** `~/.fluid/store/audit/<timestamp>_<suffix>_data_access.json`, or under `FLUID_AUDIT_ROOT`. With `FLUID_STORE_BACKEND` set to a non-file store, each record is also written through the Store. `FLUID_MCP_AUDIT_WEBHOOK_URL` forwards each one to a SIEM; see [Advanced → MCP output port](../advanced/mcp.md#audit-trail-rotation-and-the-webhook-forwarder). Nothing is written to BigQuery audit logs, CloudTrail or Snowflake `ACCESS_HISTORY`.
- **`decision`:** `allow`, `deny`, or `tool_error` when an allowed call then failed (that record carries `annotatedMessage`, and `reason` holds the error class).
- **`policyDigest`:** `jcs-sha256:` over the effective rule set, so a decision can be tied to the rules that made it after the contract changes. Policy-gate records carry it.
- **`auditRequired: true`:** changes no record. At startup, when `FLUID_AUDIT_ROOT` is unset, the server prints where it is writing.

Policy-gate denials carry a `reason` drawn from a closed vocabulary: `tool-not-allowed`, `missing-caller-jurisdiction`, `in-denied-jurisdiction`, `not-in-allowed-jurisdictions`, `missing-model-identity`, `in-deniedModels`, `in-deniedUseCases`, `not-in-allowedModels`, `missing-use-case-with-allowlist`, `not-in-allowedUseCases`, plus `allowed` when nothing fires. The precedence order is on [Advanced → MCP](../advanced/mcp.md#decision-precedence-and-reason-codes-since-0-15-0). Rate limits, the circuit breaker and token budgets deny outside that vocabulary with a reduced key set, and say so in `policySource` (`rate-limit`, `token-budget`) with a descriptive `reason` such as `token-budget-exceeded (…)`. `canStore` is advisory and denies nothing at the gateway.

## Is the caller who it says it is?

When a model or use-case gate is active, the server prints this at startup:

```text
⚠️  fluid mcp output-port: caller model_id is self-attested via MCP clientInfo. Do not expose this gateway over an untrusted network until P3 (OAuth/mTLS identity) ships. See https://agenticstiger.github.io/forge_docs/concepts/agent-policy.html
```

Over stdio, and over HTTP with no authentication configured, the model id and use case are whatever the client sends in its MCP handshake. A client can claim `claude-sonnet-4-6` and `analysis` and pass the gate. Treat the gate as a guard against mistakes, not against an adversary, in that setup.

To bind identity, serve over HTTP with `FLUID_MCP_AUTH_MODE=jwt` (or behind a proxy that terminates mTLS). The verified claims then replace the self-attested ones: the model and use case come from the token, and a client cannot re-attest them. See [Advanced → MCP → Authentication modes](../advanced/mcp.md#authentication-modes). As of 0.18.1 the warning is printed whenever a model or use-case gate is active, including when JWT authentication is configured; its "until P3 ships" wording predates the shipped JWT mode.

See the [agent-policy demo](/forge_docs/see-it-run.html) for a frame-perfect cast of the enforcement flow: contract → validate → policy-check → 4 simulated agent reads (2 allow, 2 deny with reasons).

## Common patterns

Each fragment goes under `exposes[].policy` in the contract.

### "No training, ever" (most regulated data)

```yaml
agentPolicy:
  deniedUseCases: ["training", "fine_tuning", "embedding"]
  canStore: false
  auditRequired: true
  purposeLimitation: "Read-only inference for analysis. Data may not leave the runtime context."
```

### "Internal analytics agents only"

```yaml
agentPolicy:
  allowedModels: ["claude-sonnet-4-6", "claude-opus-4-7"]   # only the company's vetted models
  allowedUseCases: ["analysis", "summarization", "qa"]
  deniedUseCases: ["training", "fine_tuning"]
  maxTokensPerRequest: 4000
  maxTokensPerDay: 1000000
  canStore: false
  auditRequired: true
```

### "Open to any agent for QA, with caps" (low-sensitivity products)

```yaml
agentPolicy:
  allowedUseCases: ["qa"]                # any model, but only QA
  deniedUseCases: ["training"]
  maxTokensPerDay: 100000
  canStore: false
  auditRequired: false                   # the gateway still writes a record per decision
```

## Where to look next

- [Governance & Policy](./governance-policy.md) — `accessPolicy` for human/service principals (the complementary gate)
- [`fluid mcp output-port serve`](/forge_docs/cli/mcp) — the consumer-side MCP server that enforces agentPolicy at read-time (`fluid mcp serve` is the separate producer/authoring tool server)
- [Advanced → MCP output port](../advanced/mcp.md) — transports, authentication, row filters and the audit sink
- [agent-policy demo](/forge_docs/see-it-run.html) — frame-perfect cast of the full enforcement flow
