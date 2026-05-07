---
title: Agent Policy (LLM/AI governance)
description: Declarative boundaries on which AI models can read which data fields.
---

# Agent Policy — declarative AI governance

New in `fluidVersion: "0.7.1"` — a top-level `agentPolicy` block that declares **which AI / LLM models are allowed to read this data product, for which purposes, and under what conditions**. Enforced before the model gets the row.

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
| **`fluid policy-check`** | Validates the contract surface against the agentPolicy block. |
| **`fluid policy-apply`** | Maps `allowedModels` / `deniedModels` to provider-specific row-level security where supported. |
| **Audit logging** | When `auditRequired: true`, AI reads should be logged through the platform's native audit trail. |

---

::: warning This page is a stub
Full coverage of MCP integration, the agent-audit event schema, and the FLUID-spec's "agentic governance" extension is tracked in [docs-content #concepts-agent-policy](https://github.com/Agentics-Rising/forge_docs/issues?q=is%3Aopen+label%3Adocs-content).
:::
