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

Runs the authoring MCP server so an MCP client can inspect, validate, and edit forge artifacts. It is a foreground process, with no daemon and no background service. By default it speaks stdio to the client that starts it. *On forge-cli `main`, not yet in a release ([forge-cli #879](https://github.com/Agenticstiger/forge-cli/pull/879)).* `--transport http` serves clients that connect by URL instead; see [Serve over HTTP](#serve-over-http).

Needs the `mcp` extra: `pip install 'data-product-forge[mcp]'`. *(since 0.28.0, [forge-cli #837](https://github.com/Agenticstiger/forge-cli/pull/837))* Without it the command prints that line and exits 1, with `[ERR_MCP_SDK_UNAVAILABLE]` and no traceback.

### Syntax

```bash
fluid mcp serve [--read-only]
fluid mcp serve [--allow-tools TOOL[,TOOL...]] [--deny-tools TOOL[,TOOL...]]
fluid mcp serve [--readable-paths PATH[,PATH...]] [--writable-paths PATH[,PATH...]]
fluid mcp serve [--writable-namespaces NS[,NS...]] [--allow-inline-credentials]
```

*On forge-cli `main`, not yet in a release ([forge-cli #879](https://github.com/Agenticstiger/forge-cli/pull/879)).* `--transport`, `--host` and `--port` are in [Serve over HTTP](#serve-over-http).

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

### Serve over HTTP

*On forge-cli `main`, not yet in a release ([forge-cli #879](https://github.com/Agenticstiger/forge-cli/pull/879)).*

```bash
fluid mcp serve --transport http [--host HOST] [--port PORT] [OPTIONS...]
```

`--transport http` serves the same tools over MCP Streamable HTTP, at `http://127.0.0.1:8766/mcp` by default, for a client that connects by URL: Claude Code's `claude mcp add --transport http`, or an agent harness that attaches MCP servers by URL. The access controls above apply unchanged. The default port is 8766, so the server can run beside an output port, which defaults to 8765.

| Flag | Default | What it does |
| --- | --- | --- |
| `--transport {stdio,http}` | `stdio` | `stdio` for a client that starts this process; `http` for MCP Streamable HTTP at `http://<host>:<port>/mcp`. |
| `--host HOST` | `127.0.0.1` | Bind address for `--transport http`. Any address other than loopback needs auth; see [Who can reach an HTTP server](#who-can-reach-an-http-server). |
| `--port PORT` | `8766` | Bind port for `--transport http`, from `1` to `65535`. |

Require a token, start the server, then add it to Claude Code from a shell where the token is set:

```bash
export FLUID_MCP_AUTH_TOKEN="$(openssl rand -hex 32)"
fluid mcp serve --transport http --read-only
```

```bash
claude mcp add --transport http fluid http://127.0.0.1:8766/mcp \
  --header "Authorization: Bearer $FLUID_MCP_AUTH_TOKEN"
```

The shell expands the variable, so Claude Code's MCP configuration then holds the token itself. The server prints where it listens, on stderr:

```text
fluid mcp serve: MCP Streamable HTTP at http://127.0.0.1:8766/mcp (auth: shared-token; clients send 'Authorization: Bearer <token>').
```

A hosted agent harness needs the same two things, the `/mcp` URL and the `Authorization` header. It reaches the server over the network, so serve it off loopback with a token and TLS in front, as [The HTTP transport](#the-http-transport) describes. Auth works as on the output port: a shared token or a JWT, set by the same `FLUID_MCP_AUTH_MODE`, `FLUID_MCP_AUTH_TOKEN` and `FLUID_MCP_JWT_*` variables.

Over HTTP the tool calls still run one at a time, in the order they arrive, whichever client sends them, as they do over stdio. They run on a worker thread, so the server keeps answering other requests while a call runs.

### Tool errors

`forge_run` reports an anticipated failure — an IDE that does not advertise the `sampling` capability, say — as the SDK's own `ToolError`. Its message names the capability and its two ways out: `mode='blank'`, or shelling out to `fluid forge --agent --blank`. *(since 0.15.0)* On MCP SDK 2.x an exception that is not a `ToolError` reaches the client as the generic text `Error executing tool forge_run`, so the tool raises `ToolError` to keep its message.

---

## Supported MCP SDK versions

Both servers run on the official `mcp` Python SDK.

| | |
| --- | --- |
| **Dependency pin** | `mcp>=1.22,<3.0` *(since 0.20.0, [forge-cli #710](https://github.com/Agenticstiger/forge-cli/pull/710); 0.19.0 and earlier pin `mcp>=1.20,<3.0`)*. The `mcp` extra needs `mcp>=1.30,!=2.0.*,!=2.1.*,<3.0`, because earlier releases have published advisories. *(since 0.28.0, [forge-cli #837](https://github.com/Agenticstiger/forge-cli/pull/837))* |
| **What a fresh install resolves** | The newest `2.x`. Up to 0.27.0 `mcp` was a core dependency, so `pip install data-product-forge` picked it up. *(from 0.27.0)* The `mcp` extra (and `standard`) names it. A base install does not include it, and `fluid mcp serve`, MCP output ports, `fluid scaffold-ide` and the keyless `mcp-sampling` provider need `pip install "data-product-forge[mcp]"`. *(since 0.28.0, [forge-cli #837](https://github.com/Agenticstiger/forge-cli/pull/837))* A fresh 0.18.1 install resolved `mcp 2.3.0` on 5 Oct 2026. |
| **Existing environments** | Do not move until you upgrade them. Pinning `mcp>=1.22,<2.0` yourself remains supported. mcp 1.20 and 1.21 fail to import with pydantic 2.14 or later, which removed a private helper they import; keep pydantic below 2.14 if you must stay on them. |
| **3.x** | Outside the pin. |

The protocol version is negotiated by the SDK at `initialize`, not fixed by Forge. A client built on that `mcp 2.3.0` was offered `2025-11-25` by both servers.

::: warning Client-side difference on SDK 2.x
On 1.x a client could self-attest identity (`model`, `useCase`, tenant attributes) as extra fields on `clientInfo`. SDK 2.x drops unknown `clientInfo` fields when it parses the request, so such a client stops being attested, with no error. Declare them in the client's capabilities under `experimental.fluid` instead. The walkthrough explains [why and what changes with authentication](../walkthrough/mcp-output-port.md).
:::

---

## Consumer: `fluid mcp output-port serve`

Binds **one expose** from a FLUID contract and serves it to MCP clients as a governed, read-only data port. This is distinct from `fluid mcp serve`: the output port queries production data, so its threat model and policy surface differ entirely.

Needs the `mcp` extra as well (`pip install 'data-product-forge[mcp]'`); add `local` for the DuckDB engine, as in `pip install 'data-product-forge[local,mcp]'`. *(since 0.28.0, [forge-cli #837](https://github.com/Agenticstiger/forge-cli/pull/837))*

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

# Serve over HTTP for a network deployment (front it with a proxy; see below).
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
| `--transport {stdio,http}` | `stdio` | MCP transport. `stdio` for desktop tool integrations; `http` for MCP over HTTP on `--host:--port` (see the note below this table). *(since 0.15.0)* A contract that pins `sovereignty.jurisdiction` without `crossBorderTransfer: true` **refuses to serve over `stdio`** and exits 2: a pipe carries no headers, so no credential can supply the verified caller jurisdiction the gate needs. Serve it over HTTP with auth: [caller-jurisdiction enforcement](../advanced/mcp.md#caller-jurisdiction-enforcement-since-0-15-0). |
| `--host HOST` | `127.0.0.1` | Bind host for `--transport http`. |
| `--port PORT` | `8765` | Bind port for `--transport http`. |
| `--allow-models MODEL[,MODEL...]` | contract | Override `agentPolicy.allowedModels`. The caller's `model_id` (declared at MCP `initialize`) must be in this list. When unset, the contract value is used. |
| `--deny-models MODEL[,MODEL...]` | contract | Override `agentPolicy.deniedModels`. Evaluated before the allowlist so denial wins. |
| `--allow-use-cases USE_CASE[,...]` | contract | Override `agentPolicy.allowedUseCases`. The caller's `useCase` (declared at `initialize`) must be in this list. |
| `--deny-use-cases USE_CASE[,...]` | contract | Override `agentPolicy.deniedUseCases`. Evaluated before the allowlist so denial wins. |

*On forge-cli `main`, not yet in a release ([forge-cli #879](https://github.com/Agenticstiger/forge-cli/pull/879)).* `--transport http` serves MCP Streamable HTTP at `http://<host>:<port>/mcp`. Up to 0.30.1 it served HTTP+SSE, and clients connected at `/sse`. A `--host` other than loopback now needs auth, and `--port` takes `1` to `65535`. See [The HTTP transport](#the-http-transport).

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
There is **no `--auth-token` flag.** When `--transport http` is used, authentication is configured through environment variables (`FLUID_MCP_AUTH_TOKEN` for a shared bearer token, or `FLUID_MCP_AUTH_MODE=jwt` for JWT). With no auth configured the gateway binds `--host:--port` **unauthenticated** and warns loudly at startup. *On forge-cli `main`, not yet in a release ([forge-cli #879](https://github.com/Agenticstiger/forge-cli/pull/879)).* That holds only on a loopback `--host`: anywhere else the gateway refuses to start and exits 2, as [Who can reach an HTTP server](#who-can-reach-an-http-server) shows.

*(since 0.15.0)* A contract that pins `sovereignty.jurisdiction` without `crossBorderTransfer: true` is stricter: with `FLUID_MCP_AUTH_MODE` unset or `none` the gateway writes a refusal to stderr and exits 2 on any host, because the auth middleware never runs and so every call would be denied. Always front the HTTP transport with an mTLS / OAuth reverse proxy for production. The proxy authenticates the connection; only `FLUID_MCP_AUTH_MODE=jwt` binds the caller's model, use case and tenant. See the [Caddy / nginx templates](../advanced/mcp.md#http-transport-and-the-reverse-proxy-templates) and the full auth-mode reference in the deep dive.
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

*On forge-cli `main`, not yet in a release ([forge-cli #879](https://github.com/Agenticstiger/forge-cli/pull/879)).* To use `--transport http` instead, give the client the URL `http://<host>:<port>/mcp` and the `Authorization` header, as in [Serve over HTTP](#serve-over-http).

---

## The HTTP transport

*On forge-cli `main`, not yet in a release ([forge-cli #879](https://github.com/Agenticstiger/forge-cli/pull/879)).*

`fluid mcp serve` and `fluid mcp output-port serve` serve `--transport http` the same way: MCP Streamable HTTP on one endpoint, `/mcp`. Up to 0.30.1 only the output port had an HTTP transport, and it was HTTP+SSE at `/sse` and `/messages/`, which the MCP specification deprecated in its 2025-03-26 revision. Those two paths are gone: a request that passes auth gets 404 there.

### Authentication

Auth comes from environment variables, never from a flag:

- `FLUID_MCP_AUTH_TOKEN`, in the default `shared-token` mode: every client sends the same token.
- `FLUID_MCP_AUTH_MODE=jwt`, with `FLUID_MCP_JWT_ISSUER`, `FLUID_MCP_JWT_AUDIENCE` and `FLUID_MCP_JWT_JWKS_URL`: each client sends its own JWT, checked against the issuer's keys.

The [auth-mode reference](../advanced/mcp.md#authentication-modes) covers both. A client sends `Authorization: Bearer <token>` on every request. The auth, `Origin` and `Host` checks run before a request reaches MCP, so a refused caller never gets a session:

| Request | Answer |
| --- | --- |
| No `Authorization` header, auth on | `401`, with `WWW-Authenticate: Bearer realm="fluid-mcp"` |
| A wrong token, auth on | `401`, with `WWW-Authenticate: Bearer realm="fluid-mcp", error="invalid_token"` |
| An `Origin` whose scheme is not `http` or `https`, or whose host is not loopback (`Origin: null` included), auth on or off | `403`, error `forbidden_origin` |
| Auth off: any other `Origin` than `http` or `https` on `127.0.0.1`, `localhost` or `[::1]` (or the bound address), with a port | `403 Invalid Origin header` |
| Auth off: any other `Host` than `127.0.0.1:<port>`, `localhost:<port>` or `[::1]:<port>` (or the bound address with its port) | `421 Invalid Host header` |
| An `Mcp-Session-Id` the server does not know, or one that another identity opened | `404`, and the client starts a new session |

A client that is not a browser sends no `Origin`, so the `Origin` rows do not apply to it. A page served from this machine, such as `http://localhost:3000`, passes them.

A session belongs to the identity that opened it, which is the caller attributes the server verified. Under `jwt` those are the token's mapped claims: `sub`, `model`, `use_case`, `tenant_id` and `jurisdiction`, plus any that `FLUID_MCP_JWT_CLAIM_MAPPING` adds. On the output port they also include the client certificate that a proxy listed in `FLUID_MCP_TRUSTED_PROXIES` forwards. A request from another identity that presents the session's `Mcp-Session-Id` gets 404, as if the session did not exist. A shared token by itself carries no attributes, so every client that holds it is the same caller.

### Who can reach an HTTP server

Without auth, a server listens on loopback only (`127.0.0.0/8`, `::1` or `localhost`), and any process on this machine can call it. The startup line says so:

```text
fluid mcp serve: MCP Streamable HTTP at http://127.0.0.1:8766/mcp
  Auth is off (FLUID_MCP_AUTH_MODE=shared-token but FLUID_MCP_AUTH_TOKEN is unset): any process on this machine can call these tools. Set FLUID_MCP_AUTH_TOKEN to require 'Authorization: Bearer <token>'.
```

Any other `--host` needs auth, and there a shared token must be at least 32 characters long. Otherwise the server does not start, and exits 2 with the fix:

```text
fluid mcp serve: refusing to listen on 0.0.0.0:8766 without authentication.
  Auth is off (FLUID_MCP_AUTH_MODE=shared-token but FLUID_MCP_AUTH_TOKEN is unset), so anyone who can reach 0.0.0.0:8766 could call every tool.
  Keep it on this machine:  --host 127.0.0.1
  Or require a token:       export FLUID_MCP_AUTH_TOKEN="$(openssl rand -hex 32)"
    (clients then send 'Authorization: Bearer <token>'), or set FLUID_MCP_AUTH_MODE=jwt with FLUID_MCP_JWT_ISSUER, FLUID_MCP_JWT_AUDIENCE and FLUID_MCP_JWT_JWKS_URL.
```

`FLUID_MCP_AUTH_MODE=none`, and `jwt` without its three settings, are refused the same way. Off loopback, a shared token under 32 characters gets `refusing to listen on 0.0.0.0:8766 with a short token.` The output port refuses the same binds: up to 0.30.1 it warned and served.

Without auth, a request must also carry a `Host` of `127.0.0.1:<port>`, `localhost:<port>` or `[::1]:<port>` (or the bound address with its port), or it gets 421. That is the MCP SDK's DNS-rebinding protection: a web page that points its own name at 127.0.0.1 cannot drive the server. A `Host` without a port gets 421 too, and clients leave the port out for port 80, so a server without auth needs another port. With auth on, any `Host` is accepted, so the server can sit behind a reverse proxy that forwards its public name; a rebinding page cannot send the token anyway. So a server behind a proxy needs its own token: without one, every request the proxy forwards gets 421.

The server speaks plain HTTP. Off loopback, terminate TLS in front of it (a reverse proxy or your platform's ingress), or the token crosses the network readable; the startup line says this too. The [Caddy and nginx templates](../advanced/mcp.md#http-transport-and-the-reverse-proxy-templates) are a starting point.

---

## Related guides

- [Advanced MCP server guide](../advanced/mcp.md) — runtime governance, auth modes, drivers, IAM compilers, rate-limit / circuit-breaker / audit internals.
- [Walkthrough: MCP output port](../walkthrough/mcp-output-port.md) — serve the example DuckDB product end-to-end and watch PII masking + an agentPolicy deny in action.
- [AI Forge And Data-Model Journeys](../walkthrough/ai-forge-data-model.md)
- [Forge Memory Guide](../advanced/forge-copilot-memory.md)
