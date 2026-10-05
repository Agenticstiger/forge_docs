# Walkthrough: MCP Output Port

**Time:** 10 minutes | **Difficulty:** Beginner | **Prerequisites:** Python 3.10+, pip, Node.js (for the MCP Inspector CLI)

> **Why it matters**
> Give an AI agent safe, read-only access to a published data product — governed by the same contract that governs people.
> `fluid mcp output-port serve` binds one expose and enforces `agentPolicy` and sensitivity-based PII/PHI redaction on every call.

<!-- CLICAST: mcp-output-port (orchestrator wires SVG + nav) -->

::: warning Compatibility note
The contract on this page uses `fluidVersion: "0.7.4"`, as the shipped example does. The CLI validates each contract against its own declared version, so it stays valid as the schema evolves. The example lives at `examples/mcp-output-port/` in the [forge-cli repo](https://github.com/Agenticstiger/forge-cli/tree/main/examples/mcp-output-port).
:::

---

## Overview

Turn a published Fluid data product into a **governed MCP server** that an AI agent can safely query — and watch the governance happen with no extra code. We serve a tiny DuckDB-backed customer-segments product over MCP, walk the agent's three core tools (`describe` → `sample` → `query`), then prove two contract-driven guarantees the gateway enforces on every call:

- **(a) PII masking** — a column marked `sensitivity: pii` keeps its name but its values come back as `[REDACTED-PII]`.
- **(b) An agentPolicy DENY** — a model that isn't on the contract's `allowedModels` list is refused.

No cloud account, no credentials, no cost. Everything runs on DuckDB reading a local CSV.

### What you'll learn

- The difference between the **producer** (`fluid mcp serve`) and **consumer** (`fluid mcp output-port serve`) MCP servers.
- The four agent tools: `describe`, `sample`, `query`, and the gated `query_sql`.
- How `sensitivity: pii` redacts **values** while keeping the column **visible**.
- How `agentPolicy.allowedModels` gates which LLM may read the product — enforced at runtime, from the contract.
- Which contract keys the gateway reads that `fluid validate` rejects (`policy.rowFilters`).
- Where to go for production HTTP + mTLS.

---

## Step 1: Setup

### Install Fluid Forge with the local extra

```bash
pip install 'data-product-forge[local]'
```

The `[local]` extra pulls in DuckDB (1.5.0 or later), which is the reference engine for the output port. Without it, `fluid mcp output-port doctor` fails its `engine_health` check with `duckdb is not installed`.

### Verify the command is wired

```bash
fluid mcp output-port --help
```

You should see the three subcommands: `serve`, `list`, and `doctor`.

---

## Step 2: The example data product

The forge-cli repo ships a minimal contract and a CSV at `examples/mcp-output-port/`. Clone it and work from that directory; every command below runs there:

```bash
git clone https://github.com/Agenticstiger/forge-cli.git
cd forge-cli/examples/mcp-output-port
```

::: warning Run from the contract's directory
The contract's `location.path: ./customers.csv` is documented as resolved against the contract's directory. As of 0.18.1 the driver resolves it against the **working directory** of the process that starts the server. From any other directory the CSV is not found, and every tool call fails with `UnsupportedBindingError`. `fluid mcp output-port doctor` does not catch this: it only runs `SELECT 1`, and reports `OK`. Start the server from the contract's directory, or put the absolute path of the CSV in `location.path`.
:::

The CSV has eight customers:

```
customer_id,email,segment,signup_date,lifetime_value_usd
C-0001,ada@enterprise.example,enterprise,2024-01-15,12500.00
C-0002,bo@smb.example,smb,2024-02-10,4500.00
...
```

The contract (`examples/mcp-output-port/contract.fluid.yaml`) binds that CSV to DuckDB and declares the governance the gateway enforces. The parts that matter:

```yaml
fluidVersion: "0.7.4"
kind: DataProduct
id: silver.demo.customer_segments_v1
exposes:
  - exposeId: customer_segments
    title: Customer Segments
    kind: table
    contract:
      schema:
        - { name: customer_id, type: STRING, required: true, sensitivity: cleartext }
        - name: email
          type: STRING
          # `sensitivity: pii` redacts this column's VALUES (→ "[REDACTED-PII]")
          # on every sample / query result while keeping the column visible.
          sensitivity: pii
        - { name: segment, type: STRING, required: true }
        - { name: signup_date, type: DATE }
        - { name: lifetime_value_usd, type: FLOAT64 }
    binding:
      platform: local
      format: csv
      location:
        path: ./customers.csv          # resolved against the contract's directory
        table: customer_segments
    semantics:                          # this block is what enables the `query` tool
      measures:
        - { name: customer_count, agg: count_distinct, expr: customer_id }
        - { name: total_ltv_usd,  agg: sum,            expr: lifetime_value_usd }
      dimensions:
        - { name: segment,     type: categorical }
        - { name: signup_date, type: time }
      metrics:
        - { name: active_customers, type: simple, measure: customer_count }
        - { name: ltv_total,        type: simple, measure: total_ltv_usd }
    mcp:
      sampling: { maxRows: 50 }
```

---

## Step 3: Preflight with `list` and `doctor`

Before wiring anything to a client, confirm the server can see and load the product.

```bash
fluid mcp output-port list contract.fluid.yaml
```

```text
Exposes in contract.fluid.yaml (1 total):

  • customer_segments  (table)
      title:  Customer Segments
      engine: local/csv → ./customers.csv
      tools:  describe, sample, query  [semantics, expose.mcp]
```

```bash
fluid mcp output-port doctor contract.fluid.yaml
```

The doctor loads the DuckDB driver and runs a `SELECT 1` health check. It does not open the CSV. Green checks mean the driver loads and DuckDB runs:

```text
✅ fluid mcp output-port doctor: expose='customer_segments' (OK)
  contract: .../contract.fluid.yaml
  binding:  local/csv → customer_segments
  tools:    describe, sample, query
  ✓ driver_load: duckdb
  ✓ engine_health: duckdb-ok
```

---

## Step 4: Serve over MCP stdio

```bash
fluid mcp output-port serve contract.fluid.yaml
```

`--expose-id` is omitted because there is exactly one expose; the server logs `auto-selected expose 'customer_segments'` to stderr and then blocks, waiting for an MCP client to drive it over stdin/stdout.

::: warning stdio is refused for a jurisdiction-pinned contract *(new in `0.15.0`)*
The contract used here declares no `sovereignty` block, so this step is unaffected.
But if a contract pins `sovereignty.jurisdiction` without
`crossBorderTransfer: true`, every tool call needs a cryptographically verified
caller jurisdiction — and stdio carries no headers, so no credential can supply one.
Rather than deny every call one at a time, `fluid mcp output-port serve` now writes a
refusal to stderr and **exits 2** before binding, naming the jurisdiction and the
command that fixes it. `--transport http` with `FLUID_MCP_AUTH_MODE` unset is refused
the same way, because the auth middleware never runs. See
[auth modes](../advanced/mcp.md#authentication-modes).
:::

Stop that server (`Ctrl-C`) and drive it with the official **MCP Inspector CLI** — no editor needed. The Inspector starts the server itself: give it the server command, then the method to call. First, list the tools:

```bash
npx -y @modelcontextprotocol/inspector@2.9.0 --cli \
  fluid mcp output-port serve contract.fluid.yaml \
  --method tools/list
```

::: tip Inspector argument order, and why the version is pinned
The Inspector's argument syntax has changed between releases. This form worked with Inspector `2.9.0` on 5 October 2026: the server command first, then `--method`, `--tool-name` and `--tool-arg`. An older `--transport stdio ... -- <command>` form is rejected by that release with `Method is required`. The commands pin `@2.9.0` because `npx -y` runs whatever release the registry serves, with your user's permissions, and `2.9.0` is the only version whose syntax this page checked. If you move the pin, run `npx @modelcontextprotocol/inspector@<version> --help` first.
:::

You should see **three** tools: `describe`, `sample`, and `query`. (`query` appears because the expose has a `semantics` block; `query_sql` is hidden because we didn't pass `--allow-sql`.)

### describe — learn the shape without touching the data

```bash
npx -y @modelcontextprotocol/inspector@2.9.0 --cli \
  fluid mcp output-port serve contract.fluid.yaml \
  --method tools/call --tool-name describe
```

`describe` returns the schema, the semantic model (measures / dimensions / metrics), the binding (platform / format / table reference / dialect), and the `agentPolicy` block. No engine round-trip — this is how an agent orients itself before spending a query.

### query — run a predeclared semantic aggregate

The agent doesn't write SQL; it picks a metric (or measure) from `expose.semantics`:

```bash
npx -y @modelcontextprotocol/inspector@2.9.0 --cli \
  fluid mcp output-port serve contract.fluid.yaml \
  --method tools/call --tool-name query --tool-arg metric=ltv_total
```

The server compiles that to a `SELECT` over the bound table, runs it on DuckDB, and returns the total lifetime value across all customers. Every identifier is validated; the agent never had a raw-SQL surface. The result carries the SQL it ran:

```json
{
  "columns": ["ltv_total"],
  "rows": [{"ltv_total": 68551.5}],
  "rowCount": 1,
  "truncated": false,
  "compiled": {
    "sql": "SELECT SUM(lifetime_value_usd) AS ltv_total\nFROM customer_segments\nLIMIT 100",
    "parameters": null
  }
}
```

To break that total down by segment, a real MCP client (Claude, Cursor) sends the `dimensions` argument as a JSON array — `{"metric": "ltv_total", "dimensions": ["segment"]}` — and the server adds `segment` to both the `SELECT` and a `GROUP BY`. For the example data it returns `enterprise` 59100.75, `smb` 6800.0 and `consumer` 2650.75, ordered by the metric. (The Inspector CLI's `--tool-arg key=value` form only sends scalars, so use a real client, or the `query` examples in the [CLI reference](../cli/mcp.md#the-four-agent-tools), to pass arrays and `filters`.)

---

## Step 5: See PII masking (guarantee a)

`email` is marked `sensitivity: pii` in the contract, so the gateway redacts its **values** on every result while keeping the column visible. Call `sample`:

```bash
npx -y @modelcontextprotocol/inspector@2.9.0 --cli \
  fluid mcp output-port serve contract.fluid.yaml \
  --method tools/call --tool-name sample --tool-arg limit=2
```

```jsonc
{
  "exposeId": "customer_segments",
  "columns": ["customer_id", "email", "segment", "signup_date", "lifetime_value_usd"],
  "rows": [
    {"customer_id": "C-0001", "email": "[REDACTED-PII]", "segment": "enterprise", "signup_date": "2024-01-15", "lifetime_value_usd": 12500.0},
    {"customer_id": "C-0002", "email": "[REDACTED-PII]", "segment": "smb", "signup_date": "2024-02-10", "lifetime_value_usd": 4500.0}
  ],
  "rowCount": 2,
  "truncated": true,
  "requestedLimit": 2,
  "effectiveLimit": 2
}
```

The agent learns the `email` field **exists** but never sees a real address. The same masking applies to `query` results. The free-form `query_sql` tool (served only with `--allow-sql`) does not return masked values at all: it refuses any statement that names the column, aliased or not.

```text
QueryValidationError: sql references column 'email' which is restricted by expose.policy.authz.columnRestrictions / expose.policy.privacy.masking. The free-form --allow-sql path enforces the same column-level deny rules as the sample / query tools — aliasing the column does not bypass them.
```

This applies to `SELECT email AS x ...` and to `SELECT COUNT(DISTINCT email) ...` alike. No flag, no proxy, no code — governance comes straight from the contract.

---

## Step 6: See an agentPolicy DENY (guarantee b)

Now gate **which model** may read the product. Add an `agentPolicy` block to the expose (or use the CLI override for a quick test). Edit `examples/mcp-output-port/contract.fluid.yaml` and add under the expose:

```yaml
    policy:
      agentPolicy:
        allowedModels:
          - claude-haiku-4-5-20251001
          - gpt-4o-mini
```

The edited contract still passes `fluid validate`. Only those two models may now call any tool. The caller declares its model id in the MCP `initialize` handshake — on `clientInfo`, or under its declared `experimental.fluid` capability, which is the only one of the two that survives MCP SDK 2.x (see below). To simulate a **disallowed** model without editing the contract again, use the operational override — `--allow-models` *replaces* the contract list for this run:

```bash
# Pin the allowlist to a single approved model for this run.
fluid mcp output-port serve contract.fluid.yaml \
  --allow-models claude-haiku-4-5-20251001
```

A client that declares a model outside the list is refused on **every** `tools/call` with a typed envelope. A client that declares **no** model, which includes the Inspector CLI used above, is refused with `missing-model-identity` instead:

```jsonc
// the client declared "gpt-4o"
{
  "error": "AgentPolicyDenied",
  "tool": "sample",
  "reason": "not-in-allowedModels",
  "message": "denied by agentPolicy (not-in-allowedModels); see audit trail for the full decision."
}
```

```jsonc
// the client declared no model
{
  "error": "AgentPolicyDenied",
  "tool": "sample",
  "reason": "missing-model-identity",
  "message": "denied by agentPolicy (missing-model-identity); see audit trail for the full decision."
}
```

The deny — like every allow — is written to `~/.fluid/store/audit/` with the tool, the model id, the reason, and `policySource: "cli"` (or `"contract"` when the gate came from the YAML). Missing model identity fails closed: the gateway never serves data under undefined identity. To see `not-in-allowedModels` you need a client that declares a model, such as the SDK-based one under Step 6's note below.

::: tip New in `0.15.0`
Every `data_access` record — allow and deny alike — now also carries `policyDigest`, a
`jcs-sha256:<hex>` hash of the rule lists that actually produced the decision.
`policySource` only says *where* the rules came from, so it cannot tell the contract
before an `allowedModels` edit from the contract after it, and a denial stopped being
reconstructable once the contract moved on. The digest is RFC 8785-canonical, so the
same rules hash identically however the YAML was written. One added key, nothing
renamed or removed — only a reader validating against a closed key set notices.
:::

::: tip Self-attested over stdio
Over stdio the model id comes from `clientInfo` and a client could lie. That's fine for a trusted desktop tool; for an untrusted network you bind identity cryptographically with a JWT (`FLUID_MCP_AUTH_MODE=jwt`). A client certificate checked by a proxy authenticates the connection but binds no model, use case or tenant — see [auth modes](../advanced/mcp.md#authentication-modes).
:::

::: warning Self-attestation moved channel on MCP SDK 2.x *(since `0.15.0`)*
`0.15.0` widens the `mcp` pin from `<2.0` to `<3.0`, so the `pip install` in Step 1
resolves the 2.x generation in a fresh environment. On 1.x a client could hang
`model`, `useCase` and tenant attributes off `clientInfo` as extra fields, because
v1's `Implementation` model allowed unknown ones; 2.x drops them at wire-parse, so
they never reach the gateway. A client relying on that shape is no longer attested and
gets no error about it — the call fails closed as `missing-model-identity` rather than
the `not-in-allowedModels` shown above.

Clients built through fluid's own helper are unaffected. The Inspector CLI used
here never attested a model in the first place, so against an allowlist it is
always refused as `missing-model-identity`. If you
hand-rolled a client that puts identity on `clientInfo`, move it to the client's
declared capabilities under `experimental.fluid`, which both SDK generations parse:

```jsonc
"capabilities": {
  "experimental": {
    "fluid": { "model": "claude-haiku-4-5-20251001", "useCase": "analytics" }
  }
}
```

An existing environment does not move until it is upgraded, and pinning
`mcp>=1.20,<2.0` still works. None of this applies once authentication is enforced:
verified JWT claims replace self-attestation outright, and with `FLUID_MCP_AUTH_TOKEN` set the self-attested values are dropped.
:::

---

## Step 7: Wire it to Claude Code

For everyday use, register the server in your MCP client. For Claude Code, add it to the project's `.mcp.json`:

```json
{
  "mcpServers": {
    "customer-segments-demo": {
      "command": "fluid",
      "args": [
        "mcp", "output-port", "serve",
        "/abs/path/to/forge-cli/examples/mcp-output-port/contract.fluid.yaml"
      ],
      "env": { "FLUID_QUIET": "1" }
    }
  }
}
```

The client starts `fluid` in its own working directory, not in the contract's. Change `location.path` in the contract to the absolute path of `customers.csv` first (see the warning in Step 2), or every tool call fails with `UnsupportedBindingError`.

Then ask Claude: *"Sample the customer_segments table and show ltv_total grouped by segment."* It will call `describe`, then `query` — and every `email` it ever sees is `[REDACTED-PII]`.

---

## What you've learned

- The **consumer** output-port server (`fluid mcp output-port serve`) is distinct from the **producer** authoring server (`fluid mcp serve`).
- The agent surface is small and bounded: `describe`, `sample`, `query`, plus gated `query_sql`.
- `sensitivity: pii` redacts **values** to `[REDACTED-PII]` while keeping the column visible — and the mask is alias-proof.
- `agentPolicy.allowedModels` gates which LLM may read the product, enforced on every call, with a full audit trail.

---

## Next steps

### Production HTTP + mTLS

For a network deployment, switch to the HTTP/SSE transport and front it with a reverse proxy that enforces mTLS + a bearer token. The repo ships a complete Docker end-to-end example (Postgres engine, real LLM driver) plus ready-to-edit **Caddy** and **nginx** templates:

```bash
cd examples/mcp-output-port-docker
cat proxy/README.md          # mTLS + bearer + agentPolicy defence-in-depth
```

```bash
# The gateway binds to localhost; only the proxy reaches it.
export FLUID_MCP_AUTH_TOKEN="$(openssl rand -hex 32)"
fluid mcp output-port serve ./contract.fluid.yaml \
  --transport http --host 127.0.0.1 --port 8765
```

::: warning mTLS and a bearer token authenticate the connection, not the model
`FLUID_MCP_AUTH_MODE` accepts `shared-token`, `jwt` and `none`, so a client certificate checked by the proxy is not an identity the gateway can use. With `FLUID_MCP_AUTH_TOKEN` set, the gateway drops the model and use case a client declares, so a contract with an `allowedModels` gate, like this walkthrough's, denies every call as `missing-model-identity`. To gate by model or tenant over HTTP, use `FLUID_MCP_AUTH_MODE=jwt` and have the token carry the `model`, `use_case` and `tenant_id` claims. With no auth mode set, the gateway is unauthenticated and the caller chooses its own. See [Authentication modes](../advanced/mcp.md#authentication-modes).
:::

### `policy.rowFilters` is read by the gateway and rejected by `fluid validate`

The gateway and the cloud IAM compiler read per-tenant `policy.rowFilters[]` from an expose. No bundled schema (0.7.1 to 0.7.6) declares that key, and `exposes[].policy` allows no other properties, so a contract that declares it fails validation, and with it `plan` and `apply`:

```text
exposes[0].policy: Additional properties are not allowed ('rowFilters' was unexpected)
```

Do not rely on `rowFilters` in a contract that goes through `fluid validate`. The restrictions that do validate and that this walkthrough used are `sensitivity` on a column and `policy.agentPolicy`. The advanced MCP page's examples that include `rowFilters` carry the same limit.

### Go deeper

- [Advanced: MCP output-port governance](../advanced/mcp.md) — the full enforcement order, auth modes (shared-token / JWT, and what an mTLS proxy does and does not bind), the five drivers, cloud-IAM compilers, rate-limit / circuit-breaker / audit internals.
- [`fluid mcp` CLI reference](../cli/mcp.md) — the flags, with copy-paste examples.
- [Governance](../advanced/governance.md) — `policy-check`, `policy-compile` and the access, classification and quality blocks.
- [Agent policy](../concepts/agent-policy.md) — `agentPolicy` and where it is enforced.
