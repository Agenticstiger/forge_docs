# `fluid mcp`

`fluid mcp` exposes Fluid Forge over the [Model Context Protocol](https://modelcontextprotocol.io) so MCP-compatible clients (Claude Code, Claude Desktop, Cursor, Continue, VS Code, MCP Inspector, and your own agents) can talk to it. There are **two distinct servers** under this command, with two different threat models:

| Server | Audience | What it serves |
| --- | --- | --- |
| `fluid mcp serve` | **Producer** — a data engineer authoring contracts | Forge *authoring* tools: inspect, validate, and carefully edit forge artifacts (16 typed tools, including `forge_run`). |
| `fluid mcp output-port serve` | **Consumer** — an AI agent reading a published data product | Read-only *data-access* tools (`describe` / `sample` / `query` / gated `query_sql`) bound to **one expose** of a contract, with contract-driven governance enforced on every call. |

::: tip Which one do I want?
If you are *building* a data product and want an editor's AI to help write the contract, use **`fluid mcp serve`**. If you have a *published* data product and want an agent to safely query it, use **`fluid mcp output-port serve`**. The output port is the flagship 0.8.6 feature — see the [output-port deep dive](../advanced/mcp.md) and the [end-to-end walkthrough](../walkthrough/mcp-output-port.md).
:::

```bash
fluid mcp                       # interactive guide (no subcommand → friendly panel)
fluid mcp serve [...]           # producer-side authoring server
fluid mcp output-port serve ... # consumer-side data-access server
```

---

## Producer: `fluid mcp serve`

Run the authoring MCP stdio server so an MCP client can inspect, validate, and edit forge artifacts. It is a foreground process — no daemon, no HTTP port, no background service.

### Syntax

```bash
fluid mcp serve [--read-only]
fluid mcp serve [--allow-tools TOOL[,TOOL...]] [--deny-tools TOOL[,TOOL...]]
fluid mcp serve [--readable-paths PATH[,PATH...]] [--writable-paths PATH[,PATH...]]
fluid mcp serve [--writable-namespaces NS[,NS...]] [--allow-inline-credentials]
```

### Recommended start

For review-only client sessions:

```bash
FLUID_QUIET=1 fluid mcp serve --read-only
```

For a scoped workspace where the client may update generated model sidecars and regenerate artifacts:

```bash
FLUID_QUIET=1 fluid mcp serve \
  --readable-paths ./forge-output \
  --writable-paths ./forge-output \
  --writable-namespaces history,audit
```

`FLUID_QUIET=1` keeps stdout reserved for MCP JSON-RPC frames.

### Access controls

| Flag | Purpose |
| --- | --- |
| `--read-only` | Reject all mutating tools. |
| `--allow-tools` | Advertise and allow only the named tools. |
| `--deny-tools` | Block the named tools; denial wins over allow. |
| `--readable-paths` | Limit path-based read tools to these roots. Default: current working directory. |
| `--writable-paths` | Limit file writes to these roots. Default: current working directory. |
| `--writable-namespaces` | Limit staged-store writes to these namespaces. Default: `history,audit`. |
| `--allow-inline-credentials` | Permit MCP clients to pass raw catalog credentials via `credentials.inline`. OFF by default — turn on only for trusted in-process CLI harnesses. |

Inline catalog credentials are blocked by default. Configure source credentials outside MCP and pass credential ids from the client.

### Server internals

`fluid mcp serve` is built on the official MCP Python SDK (`FastMCP`) and speaks MCP protocol version `2025-06-18`. It advertises **16 typed tools** — including `forge_run`, which can drive a full forge from inside the client. Each tool carries an MCP `inputSchema`, so clients can offer typed autocomplete and validate arguments before dispatch. See the [Advanced MCP server guide](../advanced/mcp.md) for the complete authoring-tool catalog and the LLM sampling backchannel.

---

## Consumer: `fluid mcp output-port serve`

Bind **one expose** from a FLUID contract and serve it to MCP clients as a governed, read-only data port. This is distinct from `fluid mcp serve`, which exposes authoring tools — the output port queries production data, so its threat model and policy surface differ entirely.

The server is **read-only by default** and exposes a deliberately small surface: an agent can `describe` the data product, `sample` a few rows, and run a predeclared **semantic** `query`. Free-form SQL (`query_sql`) is OFF unless you opt in with `--allow-sql`.

### The output-port subcommands

```bash
fluid mcp output-port list   <contract>   # list the exposes this server can serve
fluid mcp output-port doctor <contract>   # preflight: load the driver, run a health check
fluid mcp output-port serve  <contract>   # run the MCP server bound to one expose
```

- **`list`** prints every expose with its `kind`, binding `platform/format`, resolved table reference, and which optional tools each one exposes (`semantics` ⇒ `query` is advertised). Add `--json` for machine-readable output.
- **`doctor`** loads the engine driver for one expose and runs its `health_check` (a cheap `SELECT 1` round-trip). Run it **before** wiring a client so credential / network / binding issues surface as a clear preflight failure instead of a failed `tools/call`. Add `--json` for machine-readable output.

### `serve` syntax

```bash
fluid mcp output-port serve <contract> [options]
```

The only positional argument is the **path to the FLUID contract YAML** (or fragment) to serve.

```bash
# Minimal — one expose in the contract, stdio transport, read-only.
fluid mcp output-port serve ./contract.fluid.yaml

# Bind a specific expose by id.
fluid mcp output-port serve ./contract.fluid.yaml --expose-id customer_segments

# Enable free-form SQL for a trusted internal copilot.
fluid mcp output-port serve ./contract.fluid.yaml --allow-sql

# Serve over HTTP/SSE for a network deployment (front with a proxy — see below).
fluid mcp output-port serve ./contract.fluid.yaml \
  --transport http --host 127.0.0.1 --port 8765
```

::: tip Auto-selected expose
`--expose-id` is **optional when the contract contains exactly one expose** — the server picks it automatically and logs `auto-selected expose '<id>'` to stderr so the choice is visible in client logs.
:::

### `serve` flags

| Flag | Default | What it does |
| --- | --- | --- |
| `--expose-id EXPOSE_ID` | auto | `exposeId` (from `contract.exposes[].exposeId`) to bind the server to. Optional with exactly one expose. |
| `--env ENVIRONMENT` | none | Environment overlay name passed to the contract loader so per-environment overrides apply (matches `fluid plan` / `fluid apply`). |
| `--allow-tools TOOL[,TOOL...]` | all | Allowlist of tool names. Tools outside the list are blocked **and hidden** from `tools/list`. |
| `--deny-tools TOOL[,TOOL...]` | none | Blocklist of tool names. Evaluated **before** `--allow-tools` so denial wins. |
| `--readable-paths PATH[,PATH...]` | contract dir | Filesystem roots the server may read from (today only the contract YAML; reserved for future tools). Defaults to the directory of the contract argument. |
| `--allow-sql` | OFF | Enable the free-form `query_sql` tool. Even when on, every statement passes through the SQL-safety allowlist. Use only with trusted internal copilots. |
| `--max-sample-rows N` | `100` | Hard cap on rows returned by `sample`. Asking for more silently returns the cap. |
| `--query-timeout-seconds SEC` | `60` | Statement timeout passed to the engine driver where supported (Snowflake, BigQuery). |
| `--transport {stdio,http}` | `stdio` | MCP transport. `stdio` for desktop tool integrations; `http` for MCP-SSE on `--host:--port`. |
| `--host HOST` | `127.0.0.1` | Bind host for `--transport http`. |
| `--port PORT` | `8765` | Bind port for `--transport http`. |
| `--allow-models MODEL[,MODEL...]` | contract | Override `agentPolicy.allowedModels`. The caller's `model_id` (declared at MCP `initialize`) must be in this list. When unset, the contract value is used. |
| `--deny-models MODEL[,MODEL...]` | contract | Override `agentPolicy.deniedModels`. Evaluated before the allowlist so denial wins. |
| `--allow-use-cases USE_CASE[,...]` | contract | Override `agentPolicy.allowedUseCases`. The caller's `useCase` (declared at `initialize`) must be in this list. |
| `--deny-use-cases USE_CASE[,...]` | contract | Override `agentPolicy.deniedUseCases`. Evaluated before the allowlist so denial wins. |

::: warning HTTP transport has no built-in auth flag
There is **no `--auth-token` flag.** When `--transport http` is used, authentication is configured through environment variables (`FLUID_MCP_AUTH_TOKEN` for a shared bearer token, or `FLUID_MCP_AUTH_MODE=jwt` for JWT). With no auth configured the gateway binds `--host:--port` **unauthenticated** and warns loudly at startup. Always front the HTTP transport with an mTLS / OAuth reverse proxy for production — see the [Caddy / nginx templates](../advanced/mcp.md#http-and-sse-transport-and-the-reverse-proxy-templates) and the full auth-mode reference in the deep dive.
:::

### The four agent tools

The output port advertises a precise, bounded surface derived from the bound expose's shape. The `query` tool is only advertised when the expose declares a `semantics` block; `query_sql` is only advertised with `--allow-sql`.

| Tool | Always on? | Arguments | What it does |
| --- | --- | --- | --- |
| `describe` | yes | none | Returns the bound expose's metadata: `contract.schema`, `semantics`, `binding` (platform / format / table reference / dialect / capabilities), and the `agentPolicy` block. No engine round-trip. |
| `sample` | yes | `limit` (≤ `--max-sample-rows`) | Returns up to `--max-sample-rows` rows. Restricted columns are dropped; PII/PHI columns are redacted to `[REDACTED-PII]`; per-tenant `rowFilters` are applied. |
| `query` | when `semantics` present | `metric` **or** `measure`, optional `dimensions[]`, optional `filters{}`, optional `limit` | Runs a **predeclared semantic query**. Pick a metric or measure from `expose.semantics`, group by zero or more dimensions, optionally filter on dimension keys. The server compiles to parameterised SQL — preferred over `query_sql`. |
| `query_sql` | only with `--allow-sql` | `sql` (SELECT only), optional `limit` | Runs caller-supplied `SELECT` SQL against the bound expose. Refuses any statement referencing a restricted or PII column (aliasing does not bypass the mask). A server-side `LIMIT` is always appended. |

Every tool ships an MCP `inputSchema`, so MCP clients can drive typed autocomplete and validate arguments before dispatch. Each `tools/call` is checked against the contract's `agentPolicy` (allowed/denied models + use-cases), the tool allow/deny lists, a sliding-window rate limit, a token budget, a circuit breaker, and a concurrency cap — see the [deep dive](../advanced/mcp.md) for the full enforcement order.

### Wire it to a client

```json
{
  "mcpServers": {
    "customer-segments": {
      "command": "fluid",
      "args": [
        "mcp", "output-port", "serve",
        "/abs/path/to/contract.fluid.yaml"
      ],
      "env": { "FLUID_QUIET": "1" }
    }
  }
}
```

`FLUID_QUIET=1` is important because stdout is reserved for MCP JSON-RPC frames; all human-facing notices go to stderr.

---

## Related guides

- [Advanced MCP server guide](../advanced/mcp.md) — runtime governance, auth modes, drivers, IAM compilers, rate-limit / circuit-breaker / audit internals.
- [Walkthrough: MCP output port](../walkthrough/mcp-output-port.md) — serve the example DuckDB product end-to-end and watch PII masking + an agentPolicy deny in action.
- [AI Forge And Data-Model Journeys](../walkthrough/ai-forge-data-model.md)
- [Forge Memory Guide](../advanced/forge-copilot-memory.md)
