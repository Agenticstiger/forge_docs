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
fluidVersion: "0.7.5"
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
```

```text
✅ Valid FLUID contract (schema v0.7.5)
```

Validation fails on a model listed in both `allowedModels` and `deniedModels`, on a use case that is not one of the recognised names, and on keys the schema does not define. Measured against 0.18.1 with all three mistakes in one contract:

```text
 1. exposes[0].policy.agentPolicy: Additional properties are not allowed
('bogusKey' was unexpected)
 2. exposes[0].policy.agentPolicy.allowedUseCases[1]: 'nonsense' is not one of
['inference', 'reasoning', 'analysis', 'summarization', 'classification', ...]
 3. ❌  Models appear in both allowedModels and deniedModels: gpt-4.1-mini
   💡 Remove duplicates from one of the lists
 4. ❌  Invalid use case names: nonsense
```

## Step 3 — lint the declarations

```bash
fluid policy-check contract.fluid.yaml --category access_control
```

`policy-check` is a static lint over the contract's policy declarations, grouped into five categories (`sensitivity`, `access_control`, `data_quality`, `lifecycle`, `schema_evolution`). It does not call a cloud and it does not print a per-model enforcement summary. With the `agentPolicy` above, the `access_control` category ends:

```text
╭──────────────────────── 📈 Policy Compliance Summary ────────────────────────╮
│         Compliance Score:  ██████████████████████████████ 🏆 100/100         │
│            Checks Passed:  ✓ 3                                               │
│            Checks Failed:  ✗ 0                                               │
╰──────────────────────────────────────────────────────────────────────────────╯
...
Policy compliance check PASSED
```

The `sensitivity` category checks fields marked `sensitivity: pii` for a masking strategy in `policy.privacy.masking`. On the quickstart contract it reports those fields and exits non-zero until you add one. Run `policy-check` in CI on every contract change. See [`fluid policy check`](../policy-check.md).

## Step 4 — compile, then apply the policy

`policy-apply` does not read the contract directly — it deploys a *compiled bindings file*. Compile first, then apply:

```bash
# Compile the contract into provider-specific bindings (add --env <name> for an overlay)
fluid policy compile contract.fluid.yaml --out runtime/policy/bindings.json

# Hand the compiled bindings to the provider (see the note below)
fluid policy apply runtime/policy/bindings.json --mode enforce
```

`policy compile` turns `accessPolicy` grants into bindings (contract in, JSON out, no cloud calls). A contract with no `accessPolicy` grants, like the one above, compiles to `{"bindings": [], "warnings": ["No grants found in accessPolicy"]}`, and `policy apply` then succeeds without doing anything. `agentPolicy` is not compiled into bindings. `policy apply` defaults to `--mode check`. As of 0.18.1, neither mode changes cloud permissions: the GCP provider reports the compiled bindings and every other provider prints that it has no standalone policy applier. See [`fluid policy apply`](../policy-apply.md#what-each-provider-does).

The access resources that enforce the policy reach the cloud through [`fluid apply`](../apply.md) (stage 7). **What `fluid apply` emits is platform-dependent, and not uniform:**

| Platform | What `fluid apply` emits for the policy |
|---|---|
| **AWS / Lake Formation** | LF grants from `binding.governance.lakeFormation.grants`, and `policy.authz.columnRestrictions` as Lake Formation excluded columns. `accessPolicy` itself is not emitted on AWS: `fluid validate` warns about it, and `--strict` fails, when the contract has no LF grants. |
| **Snowflake** | Masking / row-access **policy objects** are emitted, but on the default OpenTofu apply path they're created and **not yet auto-attached** (Beta — see [Snowflake provider](../../providers/snowflake.md)); RBAC grants are applied. |
| **GCP / BigQuery** | `accessPolicy` becomes non-authoritative dataset IAM members. `policy.authz.columnRestrictions` becomes Data Catalog policy tags with fine-grained readers, and `fluid verify` checks them. Row-level security, dynamic masking and VPC Service Controls are not emitted. The forge-cli release notes describe the policy-tag path as proven against an emulator and a stand-in, with the live GCP apply still to come; one run against real BigQuery on 4 Oct 2026 showed an analyst refused a column protected by its policy tag. See the [GCP provider](../../providers/gcp.md). |
| **Local (DuckDB)** | No-op (single-user, no IAM model) — `policy-check` still validates the rules. |

Because native row/column enforcement is uneven across clouds, the **reliable, portable agent-policy gate is the MCP output-port server** (next step): it enforces `agentPolicy` at read time regardless of the target platform's fine-grained-policy support. Confirm what actually deployed with `fluid verify`; `fluid policy-check` lints the declarations and does not inspect the cloud.

## Step 5 — pick an enforcement mode

You have three options for how agents actually hit the gate. Pick one:

### Option A — Forge consumer-side MCP server (recommended for new agents)

```bash
fluid mcp output-port serve
```

Binds the expose as an MCP data port. Every read (`describe` / `sample` / `query` / `query_sql`) passes through the agentPolicy gate. Audit records ship to the platform's native audit log automatically. (This is distinct from `fluid mcp serve`, the producer/authoring tool server, which does not gate data reads against agentPolicy.)

This is the cleanest mode. Use it whenever your agent infrastructure can speak MCP.

### Option B — Side-car interceptor (for existing agents)

If your agents read directly via SQL/HTTP (not MCP), enforcement depends on what your target platform actually compiled (see the table above): **AWS Lake Formation grants and excluded columns enforce at the platform layer**; Snowflake masking/row-access is **Beta** (policy objects created, attachment on the native path); BigQuery row-level security is **not emitted** (column policy tags are). Where native enforcement isn't available, route reads through the MCP output-port gate (Option A) instead — and verify what deployed with `fluid verify`.

Example (BigQuery column policy tag). A principal that holds neither the fine-grained reader role nor masked-read access is refused the protected column:

```text
User has neither fine-grained reader nor masked get permission to get data protected by policy tag "<taxonomy> : <tag>" on column <project>.<dataset>.<table>.<column>.
```

That refusal is the warehouse enforcing `columnRestrictions`. BigQuery does not evaluate `allowedModels` or `allowedUseCases`; those are enforced only by the MCP output-port gate (Option A) or your application (Option C).

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

Each fragment goes under `exposes[].policy` of the expose it protects, in the same place as in Step 1.

### "No training, ever" (most regulated data)

```yaml
# under exposes[].policy
agentPolicy:
  deniedUseCases: ["training", "fine_tuning", "embedding"]
  canStore: false
  auditRequired: true
  purposeLimitation: "Read-only inference for analysis. Data may not leave the runtime context."
```

### "Internal vetted models only" (default for production)

```yaml
# under exposes[].policy
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
# under exposes[].policy
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
- [`fluid policy apply`](../policy-apply.md) — what the policy stage does on each provider in 0.18.1
- [Governance & Policy](/forge_docs/concepts/governance-policy) — `accessPolicy` for human/service principals (the complementary gate)
