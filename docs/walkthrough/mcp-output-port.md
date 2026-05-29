# Walkthrough: MCP Output Port

**Time:** 10 minutes | **Difficulty:** Beginner | **Prerequisites:** Python 3.10+, pip, Node.js (for the MCP Inspector CLI)

<!-- CLICAST: mcp-output-port (orchestrator wires SVG + nav) -->

::: warning Compatibility note
The contract on this page uses `fluidVersion: "0.7.4"`. The CLI validates each contract against its own declared version, so this example stays valid as the schema evolves. The shipped example lives at `examples/mcp-output-port/` in the forge-cli repo.
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
- Where to go for production HTTP + mTLS.

---

## Step 1: Setup

### Install Fluid Forge with the local extra

```bash
pip install 'data-product-forge[local]'
```

The `[local]` extra pulls in DuckDB, which is the reference engine for the output port.

### Verify the command is wired

```bash
fluid mcp output-port --help
```

You should see the three subcommands: `serve`, `list`, and `doctor`.

---

## Step 2: The example data product

The repo ships a minimal contract and a CSV at `examples/mcp-output-port/`. The CSV has eight customers:

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
fluid mcp output-port list examples/mcp-output-port/contract.fluid.yaml
```

You should see a single expose `customer_segments` with engine `local/csv`, a `semantics` flag, and an `expose.mcp` overrides flag.

```bash
fluid mcp output-port doctor examples/mcp-output-port/contract.fluid.yaml
```

The doctor loads the DuckDB driver and runs a `SELECT 1` health check. A green check on every line means the server will start cleanly:

```
✅ fluid mcp output-port doctor: expose='customer_segments' (OK)
  contract: .../examples/mcp-output-port/contract.fluid.yaml
  binding:  local/csv → customer_segments
  tools:    describe, sample, query
  ✓ driver_load: duckdb
  ✓ engine_health: duckdb-ok
```

---

## Step 4: Serve over MCP stdio

```bash
fluid mcp output-port serve examples/mcp-output-port/contract.fluid.yaml
```

`--expose-id` is omitted because there is exactly one expose; the server logs `auto-selected expose 'customer_segments'` to stderr and then blocks, waiting for an MCP client to drive it over stdin/stdout.

In another terminal, drive it with the official **MCP Inspector CLI** — no editor needed. First, list the tools:

```bash
npx -y @modelcontextprotocol/inspector --cli --transport stdio \
  --method tools/list \
  -- fluid mcp output-port serve examples/mcp-output-port/contract.fluid.yaml
```

You should see **three** tools: `describe`, `sample`, and `query`. (`query` appears because the expose has a `semantics` block; `query_sql` is hidden because we didn't pass `--allow-sql`.)

### describe — learn the shape without touching the data

```bash
npx -y @modelcontextprotocol/inspector --cli --transport stdio \
  --method tools/call --tool-name describe \
  -- fluid mcp output-port serve examples/mcp-output-port/contract.fluid.yaml
```

`describe` returns the schema, the semantic model (measures / dimensions / metrics), the binding (platform / format / table reference / dialect), and the `agentPolicy` block. No engine round-trip — this is how an agent orients itself before spending a query.

### query — run a predeclared semantic aggregate

The agent doesn't write SQL; it picks a metric (or measure) from `expose.semantics`:

```bash
npx -y @modelcontextprotocol/inspector --cli --transport stdio \
  --method tools/call --tool-name query --tool-arg metric=ltv_total \
  -- fluid mcp output-port serve examples/mcp-output-port/contract.fluid.yaml
```

The server compiles that to a parameterised `SELECT SUM(lifetime_value_usd) AS total_ltv_usd FROM customer_segments LIMIT …`, runs it on DuckDB, and returns the total lifetime value across all customers. Every identifier is validated; the agent never had a raw-SQL surface.

To break that total down by segment, a real MCP client (Claude, Cursor) sends the `dimensions` argument as a JSON array — `{"metric": "ltv_total", "dimensions": ["segment"]}` — and the server adds `segment` to both the `SELECT` and a `GROUP BY`. (The Inspector CLI's `--tool-arg key=value` form only sends scalars, so use a real client, or the `query` examples in the [CLI reference](../cli/mcp.md#the-four-agent-tools), to pass arrays and `filters`.)

---

## Step 5: See PII masking (guarantee a)

`email` is marked `sensitivity: pii` in the contract, so the gateway redacts its **values** on every result while keeping the column visible. Call `sample`:

```bash
npx -y @modelcontextprotocol/inspector --cli --transport stdio \
  --method tools/call --tool-name sample --tool-arg limit=2 \
  -- fluid mcp output-port serve examples/mcp-output-port/contract.fluid.yaml
```

```jsonc
{
  "columns": ["customer_id", "email", "segment", "signup_date", "lifetime_value_usd"],
  "rows": [
    {"customer_id": "C-0001", "email": "[REDACTED-PII]", "segment": "enterprise", ...},
    {"customer_id": "C-0002", "email": "[REDACTED-PII]", "segment": "smb", ...}
  ]
}
```

The agent learns the `email` field **exists** — so it can still write `COUNT(DISTINCT email)` aggregates — but never sees a real address. The same masking applies to `query` and `query_sql` results, and it can't be aliased away: even with `--allow-sql`, `SELECT email AS x` is **rejected at compile time**. No flag, no proxy, no code — governance comes straight from the contract. This is the whole value proposition in one call.

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

Only those two models may now call any tool. The caller declares its model id in the MCP `initialize` handshake (`clientInfo`). To simulate a **disallowed** model from the CLI without editing the contract again, use the operational override — `--allow-models` *replaces* the contract list for this run, so serve with a list that excludes whatever your client reports:

```bash
# Pin the allowlist to a single approved model for this run.
fluid mcp output-port serve examples/mcp-output-port/contract.fluid.yaml \
  --allow-models claude-haiku-4-5-20251001
```

A client that initializes as any other model (or declares none) is refused on **every** `tools/call` with a typed envelope:

```jsonc
{
  "error": "AgentPolicyDenied",
  "tool": "sample",
  "reason": "not-in-allowedModels",
  "message": "denied by agentPolicy (not-in-allowedModels); see audit trail for the full decision."
}
```

The deny — like every allow — is written to `~/.fluid/store/audit/` with the tool, the model id, the reason, and `policySource: "cli"` (or `"contract"` when the gate came from the YAML). A missing model id fails closed (`missing-model-identity`): the gateway never serves data under undefined identity.

::: tip Self-attested over stdio
Over stdio the model id comes from `clientInfo` and a client could lie. That's fine for a trusted desktop tool; for an untrusted network you bind identity cryptographically with JWT or mTLS — see [auth modes](../advanced/mcp.md#authentication-modes).
:::

---

## Step 7: Wire it to Claude Code

For everyday use, register the server in your MCP client. Drop this into `~/.config/claude-code/mcp_servers.json`:

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

### Go deeper

- [Advanced: MCP output-port governance](../advanced/mcp.md) — the full enforcement order, auth modes (shared-token / JWT / mTLS), the five drivers, cloud-IAM compilers, rate-limit / circuit-breaker / audit internals.
- [`fluid mcp` CLI reference](../cli/mcp.md) — every flag, copy-paste examples.
- [Governance](../advanced/governance.md) — authoring contract-level policy (`rowFilters`, `columnRestrictions`, `agentPolicy`).
