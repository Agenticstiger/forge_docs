---
title: Agent Policy (LLM/AI governance)
description: Declarative boundaries on which AI models can read which data fields.
---

# Agent Policy — declarative AI governance

New in `fluidVersion: "0.7.1"` — a top-level `agentPolicy` block that declares **which AI / LLM models are allowed to read this data product, for which purposes, and under what conditions**. Enforced before the model gets the row.

<CliCast
  src="/demos/agent-policy.svg"
  title="agentPolicy — declare, validate, gate (validate → policy-check → audit)"
  caption="Watch agentPolicy enforce: the YAML block with allowedModels / deniedUseCases / canStore / auditRequired, schema validation, the policy-check enforcement summary, and a replay of agent reads — gpt-4 + analysis allowed, claude-3 + training denied, an unlisted model denied, gemini summarization allowed."
  width="920"
  insight="Declared in YAML. Enforced at read-time. Audited natively. | Models, use-cases, storage, token limits — every dimension checked per request. | auditRequired=true means every allow + every deny lands in your platform's audit log (BigQuery audit log / Snowflake ACCESS_HISTORY / CloudTrail)."
/>

## Why declarative?

Most teams discover their data is being read by AI agents only after it's already in a vector store. `agentPolicy` makes the intent **part of the contract**, alongside the schema and the IAM grants — so it's reviewed, versioned, and audited the same way.

## The shape

Verified field list from `fluid-schema-0.7.2.json` — `agentPolicy` is a top-level object with these properties:

| Field | Type | Purpose |
|-------|------|---------|
| `allowedModels` | `string[]` | Whitelist of AI models permitted (e.g. `gpt-4`, `claude-3-opus`). Empty array = no AI access. |
| `deniedModels` | `string[]` | Explicit denylist. Takes precedence over `allowedModels`. |
| `allowedUseCases` | `string[]` | Permitted purposes (e.g. `analysis`, `summarization`, `qa`). |
| `deniedUseCases` | `string[]` | Prohibited purposes (e.g. `training`, `fine-tuning`). |
| `maxTokensPerRequest` | `integer` | Cap on tokens per AI request. Prevents excessive data exposure per call. |
| `maxTokensPerDay` | `integer` | Daily token budget. Enforces quota. |
| `canReason` | `boolean` | Whether agents can use this data for multi-step reasoning. |
| `canStore` | `boolean` | Whether AI systems can cache/store the data. `false` = ephemeral only. |
| `retentionPolicy` | `object` | Retention requirements for caches/stores (shape per schema). |
| `auditRequired` | `boolean` | Whether AI consumption must be logged. |
| `purposeLimitation` | `string` | Free-text description of allowed purposes. |
| `tags`, `labels` | various | Categorization + automation hooks. |

## Example

```yaml
agentPolicy:
  allowedModels:
    - gpt-4
    - claude-3-opus
    - claude-3-sonnet
  allowedUseCases:
    - analysis
    - summarization
    - qa
  deniedUseCases:
    - training
    - fine-tuning
  maxTokensPerRequest: 4000
  canStore: false
  auditRequired: true
  purposeLimitation: "Customer-support analytics only. No marketing or model training."
```

## Combining with column-level `sensitivity`

`agentPolicy` doesn't have a `piiHandling` field; instead, mark PII at the column level and let the governance pipeline mask it for any agent reader:

```yaml
exposes:
  - exposeId: customers
    contract:
      schema:
        - name: customer_id
          type: STRING
        - name: email
          type: STRING
          sensitivity: pii         # masked downstream
```

The exact masking behavior depends on the target platform's capabilities (BigQuery dynamic data masking, Snowflake masking policies). Verify with `fluid policy-check` before relying on it for compliance.

## Where it's enforced

| Surface | How `agentPolicy` is honored |
|---------|-------------------------------|
| **`fluid policy-check`** | Validates the contract surface against the agentPolicy block. Catches malformed enums, missing `auditRequired` on regulated products, contradictions between allowed/denied lists. |
| **`fluid policy-apply`** | Maps `allowedModels` / `deniedModels` to provider-specific row-level security where supported. Emits an audit-trail subscription for the platform's native audit log. |
| **`fluid mcp serve`** | Read-time enforcement when agents speak MCP. Every MCP read passes through the agentPolicy gate before returning rows. See "Enforcement modes" below. |
| **Native audit trail** | When `auditRequired: true`, every read is logged through BigQuery audit log / Snowflake `ACCESS_HISTORY` / CloudTrail with the agent identity, model, use-case. |

## Enforcement modes

`agentPolicy` is just a declaration; enforcement happens in one of three modes depending on how your agents read the data product.

### 1. MCP server (preferred for agentic workflows)

The Forge MCP server at `fluid mcp serve` exposes data products as MCP resources. Every MCP read passes through the agentPolicy gate:

```
agent (gpt-4)  ──read──►  fluid mcp server
                              │
                              ▼
                          agentPolicy gate
                              │
                              ├─ ALLOW ─►  fetch + return + audit
                              └─ DENY  ─►  403 + audit (with reason)
```

The MCP server reads `agentPolicy` from the contract at startup and re-validates per request. Audit records ship to the platform's audit log automatically.

### 2. Side-car interceptor

When agents read directly via SQL/HTTP (not via MCP), the side-car pattern intercepts at the platform layer:

- **BigQuery**: a row-level security policy bound to the service account's identity claims (`agent_id`, `model_id` extracted from a custom JWT). Forge emits the BigQuery RLS rules on `policy-apply`.
- **Snowflake**: a masking policy that consults a Snowflake function checking `agent_id` and `model_id` against the contract's `agentPolicy`. Forge emits the policy DDL.
- **AWS Glue / Athena**: Lake Formation cell-level filters keyed on the same identity claims.

Side-cars are platform-specific; the agentPolicy contract stays the same. Forge handles the translation in `policy-apply`.

### 3. Application-level (when neither MCP nor side-car is feasible)

For agents that read directly via SQL/HTTP and *can't* migrate to MCP or use platform-level enforcement, the application owns the gate. The pattern: load the contract via the FLUID Python SDK (`from fluid_build.contract import load_contract`), inspect `contract.agentPolicy`, and decide allow/deny in your own code path before issuing the read.

This is the weakest mode (the application is the trust boundary) but useful when migrating legacy agent code incrementally.

## Audit event schema

When `auditRequired: true`, every check (allow OR deny) emits a record:

```json
{
  "ts": "2026-04-12T14:23:01Z",
  "audit_id": "aud_8f2c4...",
  "decision": "ALLOW",
  "product": "gold.finance.customer_360_v1",
  "expose": "customer_360_table",
  "agent_id": "svc:bi-dashboard",
  "model": "gpt-4",
  "use_case": "analysis",
  "tokens_requested": 312,
  "tokens_remaining_today": 98800,
  "rows_returned": 412
}
```

Deny records include a `reason` field (`use_case_denied`, `model_not_in_allow`, `token_budget_exceeded`, `cannot_store_violation`). Records ship through the platform's native audit channel — no separate audit infrastructure to maintain.

See the [agent-policy demo](/see-it-run.html) for a frame-perfect cast of the enforcement flow: contract → validate → policy-check → 4 simulated agent reads (2 allow, 2 deny with reasons).

## Common patterns

### "No training, ever" (most regulated data)

```yaml
agentPolicy:
  deniedUseCases: ["training", "fine-tuning", "embedding-export"]
  canStore: false
  auditRequired: true
  purposeLimitation: "Read-only inference for analysis. Data may not leave the runtime context."
```

### "Internal analytics agents only"

```yaml
agentPolicy:
  allowedModels: ["gpt-4", "claude-3-opus"]   # only the company's vetted models
  allowedUseCases: ["analysis", "summarization", "qa"]
  deniedUseCases: ["training", "fine-tuning"]
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
  auditRequired: false                   # public-grade data; no audit overhead
```

## Where to look next

- [Governance & Policy](./governance-policy.md) — `accessPolicy` for human/service principals (the complementary gate)
- [`fluid mcp serve`](/forge_docs/cli/mcp) — the MCP server that enforces agentPolicy at read-time
- [`fluid policy-apply`](/forge_docs/cli/policy-apply) — emit + apply the side-car interceptors
- [agent-policy demo](/see-it-run.html) — frame-perfect cast of the full enforcement flow
