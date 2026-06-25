---
title: Add agent governance
description: Declare agentPolicy on a data product so AI / LLM agents can only read it for the use cases you allow, with full audit logging. ~10 minutes.
---

# Task: Add AI / agent access governance to a data product

Your data product is being read by AI agents — for analysis, for summarization, sometimes for training that you didn't authorize. `agentPolicy` makes the access boundaries declarative, validated at deploy, and enforced at read-time.

Time: ~10 minutes for the basic shape, longer if you're integrating with an existing MCP server or side-car interceptor.

## What you're going to add

An `agentPolicy` block on an expose (`exposes[].policy.agentPolicy` — it is scoped per-expose, not at the contract root):

```yaml
exposes:
  - exposeId: customer_360_table
    # ... kind, binding, contract ...
    policy:
      agentPolicy:
        allowedModels: ["claude-sonnet-4-6", "claude-opus-4-7", "gpt-4.1-mini"]
        allowedUseCases: ["analysis", "summarization", "qa"]
        deniedUseCases: ["training", "fine_tuning"]
        maxTokensPerRequest: 4000
        canStore: false
        auditRequired: true
```

What this declaration does:
- **Allow** reads from `claude-sonnet-4-6`, `claude-opus-4-7`, or `gpt-4.1-mini` for `analysis`, `summarization`, or `qa`
- **Deny** any read tagged as `training` / `fine_tuning` — even from an allowed model
- Cap tokens per request at 4,000 — enforced as a post-hoc throttle: the read executes, the response is measured, and it is withheld with `TokenBudgetExceeded` if it exceeds the cap (bounds what the agent receives, doesn't block the query)
- Forbid storage / caching (`canStore: false` = ephemeral reads only)
- Log every read (`auditRequired: true`)

## Step 1 — add the block

Open `contract.fluid.yaml`. Add `agentPolicy` under the target expose's `policy` block (`exposes[].policy.agentPolicy`). It is **not** a contract-root key — a contract that places `agentPolicy` at the top level fails `fluid validate` (the root object is closed). `accessPolicy` (human/service grants) stays at the contract root; the per-expose `agentPolicy` is the AI/LLM gate:

```yaml
fluidVersion: "0.7.4"
kind: DataProduct
id: gold.finance.customer_360_v1
# ...
metadata:
  # ...

accessPolicy:                          # human/service grants — contract root
  grants:
    - principal: "group:analysts@company.com"
      permissions: ["read"]

exposes:
  - exposeId: customer_360_table
    # ... kind, binding, contract ...
    policy:
      agentPolicy:                     # AI/LLM grants — per-expose
        allowedModels: ["claude-sonnet-4-6", "claude-opus-4-7", "gpt-4.1-mini"]
        allowedUseCases: ["analysis", "summarization", "qa"]
        deniedUseCases: ["training", "fine_tuning"]
        maxTokensPerRequest: 4000
        canStore: false
        auditRequired: true
        purposeLimitation: "Customer-support analytics only. No marketing use."
```

## Step 2 — validate the policy shape

```bash
fluid validate contract.fluid.yaml --strict
# ✓ Schema 0.7.4 — passed
# ✓ agentPolicy.allowedModels — 3 enum values recognized
# ✓ agentPolicy.deniedUseCases — 2 values, no contradictions
# ✓ agentPolicy.maxTokensPerRequest — within int range
# ✓ Contract validation passed (strict)
```

`validate --strict` catches contradictions (e.g., a model in both `allowedModels` and `deniedModels`), unknown enum values, and missing `auditRequired` on regulated products.

## Step 3 — preview enforcement

```bash
fluid policy-check contract.fluid.yaml --category sensitivity
```

This runs the schema-driven policy engine. The **enforcement summary** shows who/what is allowed, what's denied, what's audited:

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

## Step 4 — compile, then apply the policy

`policy-apply` does not read the contract directly — it deploys a *compiled bindings file*. Compile first, then apply:

```bash
# Compile the contract (with the prod overlay) into provider-specific bindings
fluid policy compile contract.fluid.yaml --env prod --out runtime/policy/bindings.json

# Apply the compiled bindings — --mode enforce actually deploys the IAM changes
fluid policy apply runtime/policy/bindings.json --mode enforce
```

`policy compile` is a pure function (contract in, JSON out — no cloud calls). `policy apply` defaults to `--mode check` (dry-run); pass `--mode enforce` to deploy.

This emits the cloud-specific access bindings and applies them. **What gets emitted is platform-dependent — and not uniform:**

| Platform | What `policy-apply` emits |
|---|---|
| **AWS / Lake Formation** | LF grants + **cell-level filters** (`aws_lakeformation_data_cells_filter`), row- and column-scoped on the caller's identity. Shipped. |
| **Snowflake** | Masking / row-access **policy objects** are emitted, but on the default OpenTofu apply path they're created and **not yet auto-attached** (Beta — see [Snowflake provider](/forge_docs/providers/snowflake.html)); RBAC grants are fully applied. |
| **GCP / BigQuery** | Dataset/table-level IAM bindings. **Fine-grained BigQuery row-level security and column policy tags are roadmap — not emitted** (see [GCP provider](/forge_docs/providers/gcp.html)). |
| **Local (DuckDB)** | No-op (single-user, no IAM model) — `policy-check` still validates the rules. |

Because native row/column enforcement is uneven across clouds, the **reliable, portable agent-policy gate is the MCP output-port server** (next step): it enforces `agentPolicy` at read time regardless of the target platform's fine-grained-policy support. Always confirm what actually deployed with `fluid policy-check`.

## Step 5 — pick an enforcement mode

You have three options for how agents actually hit the gate. Pick one:

### Option A — Forge consumer-side MCP server (recommended for new agents)

```bash
fluid mcp output-port serve
```

Binds the expose as an MCP data port. Every read (`describe` / `sample` / `query` / `query_sql`) passes through the agentPolicy gate. Audit records ship to the platform's native audit log automatically. (This is distinct from `fluid mcp serve`, the producer/authoring tool server, which does not gate data reads against agentPolicy.)

This is the cleanest mode. Use it whenever your agent infrastructure can speak MCP.

### Option B — Side-car interceptor (for existing agents)

If your agents read directly via SQL/HTTP (not MCP), enforcement depends on what your target platform actually compiled (see the table above): **AWS Lake Formation cell-filters enforce at the platform layer today**; Snowflake masking/row-access is **Beta** (policy objects created, attachment on the native path); BigQuery fine-grained RLS is **roadmap**. Where native enforcement isn't available, route reads through the MCP output-port gate (Option A) instead — and verify what deployed with `fluid policy-check`.

Example (BigQuery):

```sql
-- The agent's connection identifies as: user@analytics-svc.iam (a service account)
-- with custom JWT claims: agent_id="bi-dashboard", model="claude-sonnet-4-6", use_case="analysis"
SELECT * FROM gold.finance.customer_360_v1
WHERE event_date >= '2026-01-01';
-- → BigQuery checks: agent in allowedModels? ✓
-- →                  use_case in allowedUseCases? ✓
-- →                  rows returned with audit log entry written
```

### Option C — Application-level (last resort)

For agents that read directly via SQL/HTTP and *can't* migrate to MCP or use platform-level enforcement, the application owns the gate. Load the contract via the FLUID Python SDK and inspect the target expose's `policy.agentPolicy` (agentPolicy is per-expose, not at the contract root) in your own code path:

```python
from fluid_build.contract import load_contract

contract = load_contract("contract.fluid.yaml")
expose = next(e for e in contract["exposes"] if e["exposeId"] == "customer_360_table")
policy = (expose.get("policy") or {}).get("agentPolicy") or {}   # how the runtime gate reads it

if "training" in policy.get("deniedUseCases", []) and use_case == "training":
    raise PermissionError("agentPolicy.deniedUseCases includes 'training'")

if model not in policy.get("allowedModels", []):
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
  deniedUseCases: ["training", "fine_tuning", "embedding"]
  canStore: false
  auditRequired: true
  purposeLimitation: "Read-only inference for analysis. Data may not leave the runtime context."
```

### "Internal vetted models only" (default for production)

```yaml
agentPolicy:
  allowedModels: ["claude-sonnet-4-6", "claude-opus-4-7"]
  allowedUseCases: ["analysis", "summarization", "qa"]
  deniedUseCases: ["training", "fine_tuning"]
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
- [`fluid mcp output-port serve`](/forge_docs/cli/mcp) — the consumer-side MCP server that enforces agentPolicy (`fluid mcp serve` is the separate producer/authoring tool server)
- [`fluid policy-apply`](/forge_docs/cli/policy-apply) — emit + apply the side-car interceptors
- [Governance & Policy](/forge_docs/concepts/governance-policy) — `accessPolicy` for human/service principals (the complementary gate)
