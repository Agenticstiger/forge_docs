# `fluid mcp`

`fluid mcp` exposes Fluid Forge over the [Model Context Protocol](https://modelcontextprotocol.io) so MCP-compatible clients (Claude Code, Claude Desktop, Cursor, Continue, VS Code, MCP Inspector, and your own agents) can talk to it. This page is the flag and subcommand reference. The [Advanced MCP server guide](../advanced/mcp.md) explains the governance model and the tool catalog, and the [walkthrough](../walkthrough/mcp-output-port.md) serves a data product end to end.

There are **two distinct servers** under this command, with two different threat models:

| Server | Audience | What it serves |
| --- | --- | --- |
| `fluid mcp serve` | **Producer** — a data engineer authoring contracts | Forge *authoring* tools: inspect, validate, and carefully edit forge artifacts, including `forge_run`. |
| `fluid mcp output-port serve` | **Consumer** — an AI agent reading a published data product | Read-only *data-access* tools (`describe` / `sample` / `query` / gated `query_sql`) bound to **one expose** of a contract, with contract-driven governance applied. |

::: tip Which one do I want?
If you are *building* a data product and want an editor's AI to help write the contract, use **`fluid mcp serve`**. If you have a *published* data product and want an agent to safely query it, use **`fluid mcp output-port serve`**.
:::

```bash
fluid mcp                       # interactive guide (no subcommand → friendly panel)
fluid mcp serve [...]           # producer-side authoring server
fluid mcp output-port serve ... # consumer-side data-access server
```

---

## Producer: `fluid mcp serve`

Runs the authoring MCP stdio server so an MCP client can inspect, validate, and edit forge artifacts. It is a foreground process — no daemon, no HTTP port, no background service.

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
| `--read-only` | Reject any tool that mutates files or store namespaces, and hide those tools from `tools/list`. In 0.18.1 the tools that disappear are `add_relationship`, `forge_from_source`, `forge_run`, `regenerate_physical` and `update_entity`. |
| `--allow-tools` | Advertise and allow only the named tools. |
| `--deny-tools` | Block the named tools; denial wins over allow. |
| `--readable-paths` | Limit path-based read tools to these roots. Default: current working directory. |
| `--writable-paths` | Limit file writes to these roots. Default: current working directory. |
| `--writable-namespaces` | Limit staged-store writes to these namespaces. Default: `history,audit`. |
| `--allow-inline-credentials` | Permit MCP clients to pass raw catalog credentials via `credentials.inline`. OFF by default — turn on only for trusted in-process CLI harnesses. |

Inline catalog credentials are blocked by default. Configure source credentials outside MCP and pass credential ids from the client.

Each tool carries an MCP `inputSchema`, so clients can offer typed autocomplete and validate arguments before dispatch. The tool catalog and the LLM sampling backchannel are in the [Advanced MCP server guide](../advanced/mcp.md#authoring-tools).

### Tool errors

`forge_run` reports an anticipated failure — an IDE that does not advertise the `sampling` capability, say — as the SDK's own `ToolError`. Its message names the capability and its two ways out: `mode='blank'`, or shelling out to `fluid forge --agent --blank`. *(since 0.15.0)* On MCP SDK 2.x an exception that is not a `ToolError` reaches the client as the generic text `Error executing tool forge_run`, so the tool raises `ToolError` to keep its message.

---

## Supported MCP SDK versions

Both servers run on the official `mcp` Python SDK.

| | |
| --- | --- |
| **Dependency pin** | `mcp>=1.20,<3.0` |
| **What a fresh install resolves** | The newest `2.x`. `mcp` is a core dependency rather than an extra, so `pip install data-product-forge` picks it up. A fresh 0.18.1 install resolved `mcp 2.3.0` on 5 Oct 2026. |
| **Existing environments** | Do not move until you upgrade them. Pinning `mcp>=1.20,<2.0` yourself remains supported. |
| **3.x** | Outside the pin. |

The protocol version is negotiated by the SDK at `initialize`, not fixed by Forge. A client built on that `mcp 2.3.0` was offered `2025-11-25` by both servers.

::: warning Client-side difference on SDK 2.x
On 1.x a client could self-attest identity (`model`, `useCase`, tenant attributes) as extra fields on `clientInfo`. SDK 2.x drops unknown `clientInfo` fields when it parses the request, so such a client stops being attested, with no error. Declare them in the client's capabilities under `experimental.fluid` instead. The walkthrough explains [why and what changes with authentication](../walkthrough/mcp-output-port.md).
:::

---

## Consumer: `fluid mcp output-port serve`

Binds **one expose** from a FLUID contract and serves it to MCP clients as a governed, read-only data port. This is distinct from `fluid mcp serve`: the output port queries production data, so its threat model and policy surface differ entirely.

The server is **read-only by default** and exposes a small surface: an agent can `describe` the data product, `sample` a few rows, and run a predeclared **semantic** `query`. Free-form SQL (`query_sql`) is OFF unless you opt in with `--allow-sql`.

### The output-port subcommands

```bash
fluid mcp output-port list   <contract>   # list the exposes this server can serve
fluid mcp output-port doctor <contract>   # preflight: load the driver, run a health check
fluid mcp output-port serve  <contract>   # run the MCP server bound to one expose
```

#### `list`

```bash
fluid mcp output-port list <contract> [--env ENVIRONMENT] [--json]
```

Prints every expose with its `kind`, binding `platform/format`, resolved table reference, and which optional tools each one exposes (`semantics` ⇒ `query` is advertised):

```text
Exposes in contract.fluid.yaml (1 total):

  • customer_segments  (table)
      title:  Customer Segments
      engine: local/csv → ./customers.csv
      tools:  describe, sample, query  [semantics, expose.mcp]
```

`--json` prints the same list as JSON, with `exposeId`, `kind`, `title`, `platform`, `format`, `tableReference`, `hasSemantics` and `hasMcpOverrides` per expose.

#### `doctor`

```bash
fluid mcp output-port doctor <contract> [--expose-id EXPOSE_ID] [--env ENVIRONMENT] [--json]
```

Loads the engine driver for one expose and runs its `health_check` (a cheap `SELECT 1` round-trip). Run it **before** wiring a client so credential, network and binding problems surface as a preflight failure instead of a failed `tools/call`. `--expose-id` is optional when the contract has a single expose.

```text
✅ fluid mcp output-port doctor: expose='customer_segments' (OK)
  contract: /work/demo/contract.fluid.yaml
  binding:  local/csv → customer_segments
  tools:    describe, sample, query
  ✓ driver_load: duckdb
  ✓ engine_health: duckdb-ok
```

With several exposes and no `--expose-id`, the check fails with `Contract has 2 exposes; pass --expose-id to pick one` and lists the available ids.

### `serve` syntax

```bash
fluid mcp output-port serve <contract> [options]
```

The only positional argument is the **path to a FLUID contract YAML**: a flat contract, or the root file of a contract composed with [`$ref`](../concepts/contract-refs.md), whose references are resolved (see [fragment-first contracts](../advanced/mcp.md#fragment-first-contracts) for the authoring tools that take a `contract_path`). An individual fragment file is not a contract: `fluid mcp output-port list fragments/exposes/<id>.yaml` printed `No exposes in ...` and exited `0`.

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
| `--readable-paths PATH[,PATH...]` | contract dir | Filesystem roots the server may read from. Every filesystem reference in the served binding (`location.path`, `location.attach`, `location.dbFile`) must resolve, after symlinks are followed, under one of the roots, or the tool call fails with `UnsupportedBindingError`. Passing the flag replaces the default root; it does not add to it. Defaults to the directory of the contract argument. See [Data outside the contract directory](#data-outside-the-contract-directory). |
| `--allow-sql` | OFF | Enable the free-form `query_sql` tool. Even when on, every statement passes through the SQL-safety allowlist. Use only with trusted internal copilots. |
| `--max-sample-rows N` | `100` | Hard cap on rows returned by `sample`. Asking for more silently returns the cap. |
| `--query-timeout-seconds SEC` | `60` | Statement timeout passed to the engine driver where supported (Snowflake, BigQuery). |
| `--transport {stdio,http}` | `stdio` | MCP transport. `stdio` for desktop tool integrations; `http` for MCP-SSE on `--host:--port`. *(since 0.15.0)* A contract that pins `sovereignty.jurisdiction` without `crossBorderTransfer: true` **refuses to serve over `stdio`** and exits 2 — a pipe carries no headers, so no credential can supply the verified caller jurisdiction the gate needs. Serve it over HTTP with auth: [caller-jurisdiction enforcement](../advanced/mcp.md#caller-jurisdiction-enforcement-since-0-15-0). |
| `--host HOST` | `127.0.0.1` | Bind host for `--transport http`. |
| `--port PORT` | `8765` | Bind port for `--transport http`. |
| `--allow-models MODEL[,MODEL...]` | contract | Override `agentPolicy.allowedModels`. The caller's `model_id` (declared at MCP `initialize`) must be in this list. When unset, the contract value is used. |
| `--deny-models MODEL[,MODEL...]` | contract | Override `agentPolicy.deniedModels`. Evaluated before the allowlist so denial wins. |
| `--allow-use-cases USE_CASE[,...]` | contract | Override `agentPolicy.allowedUseCases`. The caller's `useCase` (declared at `initialize`) must be in this list. |
| `--deny-use-cases USE_CASE[,...]` | contract | Override `agentPolicy.deniedUseCases`. Evaluated before the allowlist so denial wins. |

### Data outside the contract directory

By default the server may read only under the directory of the contract file. A binding that points elsewhere fails each tool call with `UnsupportedBindingError`, and the audit record names the path. Reproduced with a CSV in `data/` and the contract in `contract/`, started from their common parent, with `location.path: data/customers.csv`:

```text
.
├── contract/open.fluid.yaml
└── data/customers.csv
```

```bash
fluid mcp output-port serve contract/open.fluid.yaml
```

The audit record for the failed `sample` call:

```text
decision: tool_error   reason: UnsupportedBindingError
annotatedMessage: binding.location.path /work/data/customers.csv is outside --readable-paths
```

Name the directory that holds the data:

```bash
fluid mcp output-port serve contract/open.fluid.yaml --readable-paths ./data
```

Pass several roots with commas (`--readable-paths ./data,./warehouse`). The flag replaces the default, so if the contract's own directory also holds files the binding reads, list it too.

::: warning Relative paths in 0.18.1
`serve` resolved a relative `binding.location.path` against the directory it was started in, not against the contract's directory. A contract in `contract/` with `path: customers.csv` therefore worked when started from inside `contract/` and failed with `UnsupportedBindingError` when started from its parent. `doctor` resolved the same path against the contract's directory, so a green `doctor` does not prove that `serve` will find the file. Start `serve` from the directory the paths are relative to, or write absolute paths.
:::

::: warning HTTP transport has no built-in auth flag
There is **no `--auth-token` flag.** When `--transport http` is used, authentication is configured through environment variables (`FLUID_MCP_AUTH_TOKEN` for a shared bearer token, or `FLUID_MCP_AUTH_MODE=jwt` for JWT). With no auth configured the gateway binds `--host:--port` **unauthenticated** and warns loudly at startup — except *(since 0.15.0)* for a contract that pins `sovereignty.jurisdiction` without `crossBorderTransfer: true`, where it instead writes a refusal to stderr and exits 2, because the auth middleware never runs and so every call would be denied. Always front the HTTP transport with an mTLS / OAuth reverse proxy for production. The proxy authenticates the connection; only `FLUID_MCP_AUTH_MODE=jwt` binds the caller's model, use case and tenant. See the [Caddy / nginx templates](../advanced/mcp.md#http-and-sse-transport-and-the-reverse-proxy-templates) and the full auth-mode reference in the deep dive.
:::

### The agent tools

The output port advertises a bounded surface derived from the bound expose's shape. The `query` tool is only advertised when the expose declares a `semantics` block; `query_sql` is only advertised with `--allow-sql`.

| Tool | Always on? | Arguments | What it does |
| --- | --- | --- | --- |
| `describe` | yes | none | Returns the bound expose's metadata: `contract.schema`, `semantics`, `binding` (platform / format / table reference / dialect / capabilities), and the `agentPolicy` block. No engine round-trip. |
| `sample` | yes | `limit` (≤ `--max-sample-rows`) | Returns up to `--max-sample-rows` rows. Restricted columns are dropped and PII/PHI columns are redacted to `[REDACTED-PII]`. Where the expose declares `policy.rowFilters`, they are applied; see the warning below. |
| `query` | when `semantics` present | `metric` **or** `measure`, optional `dimensions[]`, optional `filters{}`, optional `limit` | Runs a **predeclared semantic query**. Pick a metric or measure from `expose.semantics`, group by zero or more dimensions, optionally filter on dimension keys. The server compiles to parameterised SQL — preferred over `query_sql`. |
| `query_sql` | only with `--allow-sql` | `sql` (SELECT only), optional `limit` | Runs caller-supplied `SELECT` SQL against the bound expose. Refuses any statement referencing a restricted or PII column (aliasing does not bypass the mask). The gateway applies a server-side row limit. |

Every tool ships an MCP `inputSchema`. Each `tools/call` is checked against the contract's `agentPolicy` (allowed/denied models + use-cases), the tool allow/deny lists, a sliding-window rate limit, a token budget, a circuit breaker, and a concurrency cap — see the [deep dive](../advanced/mcp.md) for the enforcement order.

When `allowedModels` is set and the caller declared no model at `initialize`, the call is denied. Measured against a CSV-backed expose with `allowedModels: ["claude-sonnet-4-6", "gpt-4.1-mini"]`, an anonymous `sample` returned:

```json
{
  "error": "AgentPolicyDenied",
  "tool": "sample",
  "reason": "missing-model-identity",
  "message": "denied by agentPolicy (missing-model-identity); see audit trail for the full decision."
}
```

The decision is also written to the audit trail as a `data_access` event with `decision: deny`.

::: warning `policy.rowFilters` is read by the gateway and rejected by the schema
The output port reads `exposes[].policy.rowFilters` and applies it to `sample` and `query`. No bundled schema declares that key: `exposePolicy` is a closed object. A contract that declares `rowFilters` fails `fluid validate`, and so `plan` and `apply`:

```text
exposes[0].policy: Additional properties are not allowed ('rowFilters' was unexpected)
```

This was measured against schema 0.7.5 and the 0.7.6 preview. The MCP server loads the contract without schema validation, so a contract that declares `rowFilters` can be served while it cannot be validated or deployed. Until the schema declares the key, do not rely on `rowFilters` in a contract you also validate. Other `agentPolicy` and `policy` fields are not affected. The [Advanced MCP server guide](../advanced/mcp.md#row-level-security-—-policy-rowfilters) describes how each filter compiles.
:::

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
