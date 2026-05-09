---
title: Add agent governance
description: Declare agentPolicy on a data product so AI / LLM agents can only read it for the use cases you allow, with full audit logging. ~10 minutes.
---

# Task: Add AI / agent access governance to a data product

Your data product is being read by AI agents — for analysis, for summarization, sometimes for training that you didn't authorize. `agentPolicy` makes the access boundaries declarative, validated at deploy, and enforced at read-time.

Time: ~10 minutes for the basic shape, longer if you're integrating with an existing MCP server or side-car interceptor.

## What you're going to add

A top-level `agentPolicy` block to your contract:

```yaml
agentPolicy:
  allowedModels: ["gpt-4", "claude-3-opus", "gemini-2.5-flash"]
  allowedUseCases: ["analysis", "summarization", "qa"]
  deniedUseCases: ["training", "fine-tuning", "profiling"]
  maxTokensPerRequest: 4000
  canStore: false
  auditRequired: true
```

What this declaration does:
- **Allow** reads from `gpt-4`, `claude-3-opus`, or `gemini-2.5-flash` for `analysis`, `summarization`, or `qa`
- **Deny** any read tagged as `training` / `fine-tuning` / `profiling` — even from an allowed model
- Cap tokens per request at 4,000 (prevents excessive data exfiltration in one call)
- Forbid storage / caching (`canStore: false` = ephemeral reads only)
- Log every read (`auditRequired: true`)

## Step 1 — add the block

Open `contract.fluid.yaml`. Add `agentPolicy` at the top level (sibling to `accessPolicy`, not nested):

```yaml
fluidVersion: "0.7.2"
kind: DataProduct
id: gold.finance.customer_360_v1
# ...
metadata:
  # ...
exposes:
  # ...

accessPolicy:                          # human/service grants
  grants:
    - principal: "group:analysts@company.com"
      permissions: ["read"]

agentPolicy:                           # AI/LLM grants — separate
  allowedModels: ["gpt-4", "claude-3-opus", "gemini-2.5-flash"]
  allowedUseCases: ["analysis", "summarization", "qa"]
  deniedUseCases: ["training", "fine-tuning"]
  maxTokensPerRequest: 4000
  canStore: false
  auditRequired: true
  purposeLimitation: "Customer-support analytics only. No marketing use."
```

## Step 2 — validate the policy shape

```bash
fluid validate contract.fluid.yaml --strict
# ✓ Schema 0.7.2 — passed
# ✓ agentPolicy.allowedModels — 3 enum values recognized
# ✓ agentPolicy.deniedUseCases — 2 values, no contradictions
# ✓ agentPolicy.maxTokensPerRequest — within int range
# ✓ Contract validation passed (strict)
```

`validate --strict` catches contradictions (e.g., a model in both `allowedModels` and `deniedModels`), unknown enum values, and missing `auditRequired` on regulated products.

## Step 3 — preview enforcement

```bash
fluid policy-check contract.fluid.yaml --report agentPolicy
```

This shows the **enforcement summary** — who/what is allowed, what's denied, what's audited:

```
🛡  agentPolicy enforcement summary
─────────────────────────────────────────────────────
Models     3 allowed, all others denied
Use cases  3 allowed, 2 explicitly denied
Storage    no caching — every read is fresh
Audit      every read logged (auditRequired=true)
Limits     maxTokensPerRequest=4000
─────────────────────────────────────────────────────
✓ All 11 schema fields covered by agentPolicy gates
✓ PII-tagged columns (email, phone, ssn) auto-masked at read
✓ agentPolicy ready to enforce
```

Run this in CI on every contract change. It's the equivalent of `fluid validate` for the AI-access surface specifically.

## Step 4 — apply the policy

```bash
fluid policy-apply contract.fluid.yaml --env prod --yes
```

This emits the cloud-specific enforcement primitives and applies them. **What gets emitted depends on the platform**:

| Platform | What `policy-apply` emits |
|---|---|
| **GCP / BigQuery** | Row-level security policy on the dataset, keyed on `agent_id` and `model_id` extracted from the agent's JWT |
| **Snowflake** | Masking policy on the table that calls a Snowflake function checking `agent_id` against the contract's `allowedModels` |
| **AWS / Athena** | Lake Formation cell-level filters keyed on the same identity claims |
| **Local (DuckDB)** | No-op (single-user, no IAM model) — but `policy-check` still validates the rules for correctness |

The enforcement is **at the platform layer**. Even if your application bypasses the MCP server, the platform's row-level filter still applies.

## Step 5 — pick an enforcement mode

You have three options for how agents actually hit the gate. Pick one:

### Option A — Forge MCP server (recommended for new agents)

```bash
fluid mcp serve --contract contract.fluid.yaml
```

Exposes the data product as an MCP resource. Every MCP read passes through the agentPolicy gate. Audit records ship to the platform's native audit log automatically.

This is the cleanest mode. Use it whenever your agent infrastructure can speak MCP.

### Option B — Side-car interceptor (for existing agents)

If your agents read directly via SQL/HTTP (not MCP), the side-car pattern intercepts at the platform layer. The bindings emitted by `policy-apply` (the BigQuery RLS rule, the Snowflake masking policy, etc.) **already** enforce the policy. No further setup needed beyond passing the agent identity in the connection string.

Example (BigQuery):

```sql
-- The agent's connection identifies as: user@analytics-svc.iam (a service account)
-- with custom JWT claims: agent_id="bi-dashboard", model="gpt-4", use_case="analysis"
SELECT * FROM gold.finance.customer_360_v1
WHERE event_date >= '2026-01-01';
-- → BigQuery checks: agent in allowedModels? ✓
-- →                  use_case in allowedUseCases? ✓
-- →                  rows returned with audit log entry written
```

### Option C — Application-level (last resort)

For agents that read directly via SQL/HTTP and *can't* migrate to MCP or use platform-level enforcement, the application owns the gate. Load the contract via the FLUID Python SDK and inspect `contract.agentPolicy` in your own code path:

```python
from fluid_build.contract import load_contract

contract = load_contract("contract.fluid.yaml")
policy = contract.agentPolicy

if "training" in policy.deniedUseCases and use_case == "training":
    raise PermissionError("agentPolicy.deniedUseCases includes 'training'")

if model not in policy.allowedModels:
    raise PermissionError(f"model {model!r} not in agentPolicy.allowedModels")

# ... proceed with the read
```

The application is the trust boundary in this mode (the weakest gate). Use it only when neither MCP nor platform-level enforcement is feasible.

## Step 6 — replay agent reads from audit log

Once `auditRequired: true` is in effect, every read produces a record in the platform's native audit channel:

| Platform | Where audit records land |
|---|---|
| **GCP / BigQuery** | BigQuery audit log (`cloudaudit.googleapis.com/data_access`) — query via Cloud Logging or export to a BigQuery sink |
| **Snowflake** | `SNOWFLAKE.ACCOUNT_USAGE.ACCESS_HISTORY` view — query directly with SQL |
| **AWS / Athena** | CloudTrail data event records — query via CloudTrail Lake or Athena over the trail S3 export |

Example query against Snowflake's `ACCESS_HISTORY` to find all agent reads of this product in the last 24h:

```sql
SELECT
  query_start_time,
  user_name,
  query_text,
  base_objects_accessed
FROM SNOWFLAKE.ACCOUNT_USAGE.ACCESS_HISTORY
WHERE query_start_time >= DATEADD(hour, -24, CURRENT_TIMESTAMP())
  AND ARRAY_CONTAINS(
    'PROD.GOLD.CUSTOMER_360_V1'::variant,
    ARRAY_AGG(base_objects_accessed:objectName::string)
  )
ORDER BY query_start_time DESC;
```

The MCP server (Option A) tags each read with the agent identity, model, and use-case in the `query_text` so you can filter further. The platform's native audit format is the authoritative record — Forge does not duplicate it.

## Common patterns

### "No training, ever" (most regulated data)

```yaml
agentPolicy:
  deniedUseCases: ["training", "fine-tuning", "embedding-export"]
  canStore: false
  auditRequired: true
  purposeLimitation: "Read-only inference for analysis. Data may not leave the runtime context."
```

### "Internal vetted models only" (default for production)

```yaml
agentPolicy:
  allowedModels: ["gpt-4", "claude-3-opus"]
  allowedUseCases: ["analysis", "summarization", "qa"]
  deniedUseCases: ["training", "fine-tuning"]
  maxTokensPerRequest: 4000
  maxTokensPerDay: 1000000
  canStore: false
  auditRequired: true
```

### "Open to any agent for QA" (low-sensitivity)

```yaml
agentPolicy:
  allowedUseCases: ["qa"]            # any model, but only QA
  deniedUseCases: ["training"]
  maxTokensPerDay: 100000
  canStore: false
  auditRequired: false               # public-grade data; no audit overhead
```

## What you DIDN'T have to do

- Build a custom proxy / gateway between your agents and your data
- Maintain a separate "AI access list" repo
- Translate the policy across cloud-specific RLS/masking systems (Forge does this)
- Wire audit logging into a separate observability platform

## See also

- [Agent Policy concept](/forge_docs/concepts/agent-policy) — full conceptual treatment + audit event schema
- [Agent policy demo](/forge_docs/see-it-run.html) — frame-perfect cast of validate → policy-check → audit replay
- [`fluid mcp serve`](/forge_docs/cli/mcp) — the MCP server
- [`fluid policy-apply`](/forge_docs/cli/policy-apply) — emit + apply the side-car interceptors
- [Governance & Policy](/forge_docs/concepts/governance-policy) — `accessPolicy` for human/service principals (the complementary gate)
