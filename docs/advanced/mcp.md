# MCP Server

Fluid Forge ships **two** Model Context Protocol servers under `fluid mcp`:

- **`fluid mcp serve`**: the **producer / authoring** server. Exposes the staged forge pipeline as stdio MCP tools so an editor's AI can inspect, validate, and edit contracts. *(since 0.31.0, [forge-cli #879](https://github.com/Agenticstiger/forge-cli/pull/879))* It can serve them over MCP Streamable HTTP too.
- **`fluid mcp output-port serve`**: the **consumer / data-access** server (the flagship output-port capability). Binds one expose of a published contract and serves a small, governed, read-only surface to AI agents.

The first half of this page covers the authoring server. The second half is a deep dive on the output port's runtime governance — the part that takes reading several files to learn.

---

## Authoring server — `fluid mcp serve`

`fluid mcp serve` exposes the staged forge pipeline as an MCP server for clients such as Claude Code, Cursor, Continue, and VS Code MCP integrations. It is a foreground process, with no daemon and no background service, and by default it speaks stdio to the client that starts it. *(since 0.31.0, [forge-cli #879](https://github.com/Agenticstiger/forge-cli/pull/879))* With `--transport http` it serves the same tools over MCP Streamable HTTP instead, for a client or agent harness that connects by URL; see [Serve over HTTP](../cli/mcp.md#serve-over-http). The server is built on the official MCP Python SDK (`FastMCP`), which negotiates the MCP protocol version with the client at `initialize`; see [Supported MCP SDK versions](../cli/mcp.md#supported-mcp-sdk-versions).

### Start the server

Install the MCP SDK first: `pip install 'data-product-forge[mcp]'`. The extra exists since 0.27.0. *(since 0.28.0, [forge-cli #837](https://github.com/Agenticstiger/forge-cli/pull/837))* A base install does not contain `mcp`, and `fluid mcp serve`, `fluid mcp output-port serve` and `fluid scaffold-ide` print that install line and exit 1 before they do any work. See [Upgrading](../upgrading.md#changes-in-0-28-0).

```bash
fluid mcp serve --read-only     # inspection only
fluid mcp serve                 # full surface, scoped to the working directory
```

Every `tools/call` is checked by policy before it runs. The flags that scope it (`--read-only`, `--allow-tools`, `--deny-tools`, `--readable-paths`, `--writable-paths`, `--writable-namespaces`, `--allow-inline-credentials`) are documented once, in the [`fluid mcp` CLI reference](../cli/mcp.md#access-controls). This page covers what the tools do and how the output port enforces governance.

### Authoring tools

The authoring server advertises these tools. With `--read-only`, the tools marked *write* are not advertised:

*(since 0.31.0, [forge-cli #881](https://github.com/Agenticstiger/forge-cli/pull/881))* The five rows marked removed below are gone. JDBC databases remain available through `fluid forge data-model from-source --uri`. *(since 0.31.0, [forge-cli #884](https://github.com/Agenticstiger/forge-cli/pull/884))* The five rows that read a source catalog are one tool, [`source_catalog`](#source-catalog), so the server advertises 7 tools, and 4 with `--read-only`.

| Tool | Mode | What it does |
| --- | --- | --- |
| `read_logical_model` | read | Load a `.model.json` sidecar and return the typed logical model |
| `validate_contract` | read | Validate a Fluid contract or forged model sidecar |
| `diff_models` | read | Compare two logical model sidecars |
| `search_semantic_memory` | read | *(since 0.31.0, [forge-cli #881](https://github.com/Agenticstiger/forge-cli/pull/881))* Removed. Search the semantic memory namespace for similar prior models |
| `score_contract_quality` | read | *(since 0.31.0, [forge-cli #881](https://github.com/Agenticstiger/forge-cli/pull/881))* Removed. Score a contract against the forge quality rubric |
| `enrich_contract_suggestions` | read | *(since 0.31.0, [forge-cli #881](https://github.com/Agenticstiger/forge-cli/pull/881))* Removed. Suggest contract enrichments (descriptions, semantics, policy) |
| `update_entity` | write | Rename or update one logical model entity |
| `add_relationship` | write | Add a relationship to a logical sidecar |
| `regenerate_physical` | write | Regenerate the contract and physical fanout from a logical sidecar |
| `list_source_adapters` | read | *(since 0.31.0, [forge-cli #884](https://github.com/Agenticstiger/forge-cli/pull/884))* Now `source_catalog` with `kind=adapters`. List available source-catalog adapters |
| `list_source_tables` | read | *(since 0.31.0, [forge-cli #884](https://github.com/Agenticstiger/forge-cli/pull/884))* Now `source_catalog` with `kind=tables`. Enumerate tables from a configured source catalog |
| `inspect_source_table` | read | *(since 0.31.0, [forge-cli #884](https://github.com/Agenticstiger/forge-cli/pull/884))* Now `source_catalog` with `kind=table`. Inspect a source table profile and metadata |
| `list_source_lineage` | read | *(since 0.31.0, [forge-cli #884](https://github.com/Agenticstiger/forge-cli/pull/884))* Now `source_catalog` with `kind=lineage`. Read lineage from a configured source catalog |
| `list_source_glossary` | read | *(since 0.31.0, [forge-cli #884](https://github.com/Agenticstiger/forge-cli/pull/884))* Now `source_catalog` with `kind=glossary`. Read glossary terms from a configured source catalog |
| `source_catalog` | read | *(since 0.31.0, [forge-cli #884](https://github.com/Agenticstiger/forge-cli/pull/884))* Read a source catalog's metadata: its adapters, a scope's tables, one table, a table's lineage, or glossary terms. Metadata only, never table data. See [`source_catalog`](#source-catalog) |
| `forge_from_source` | write | *(since 0.31.0, [forge-cli #881](https://github.com/Agenticstiger/forge-cli/pull/881))* Removed; run `fluid forge data-model from-source`. Forge a contract and `.model.json` sidecar from a configured source catalog |
| `forge_run` | write | *(since 0.31.0, [forge-cli #881](https://github.com/Agenticstiger/forge-cli/pull/881))* Removed; the calling agent authors the contract itself, with the FLUID skills. Run a full `fluid forge` in-process — `mode` is `blank`, `diag`, or `ai` |

Every advertised tool includes an MCP `inputSchema`, so clients can provide typed autocomplete and validate arguments before dispatch.

#### `source_catalog`

*(since 0.31.0, [forge-cli #884](https://github.com/Agenticstiger/forge-cli/pull/884))*

`source_catalog` reads a source catalog's metadata, never its data. It replaces the five tools above that read a catalog, and its `kind` argument picks what it reads. The other arguments keep the names they had on those tools.

| `kind` | Replaces | Also needs | Result |
| --- | --- | --- | --- |
| `adapters` | `list_source_adapters` | nothing | `{"kind": "adapters", "adapters": [...]}`, one entry per catalog the server can read |
| `tables` | `list_source_tables` | `source`, `credentials`, `scope` | `{"kind": "tables", "tables": [...]}` |
| `table` | `inspect_source_table` | `source`, `credentials`, `fqn` | `{"kind": "table", "table": {...}}`: the table's metadata, such as its columns, keys, owner and tags |
| `lineage` | `list_source_lineage` | `source`, `credentials`, `fqn` | `{"kind": "lineage", "lineage": {...}}`: its upstream and downstream tables |
| `glossary` | `list_source_glossary` | `source`, `credentials`; `scope` is optional | `{"kind": "glossary", "terms": [...]}` |

`source` names the catalog: `snowflake`, `unity`, `bigquery`, `dataplex`, `glue`, `datahub` or `datamesh_manager`. `credentials` is `{"credential_id": "<name>"}`, a name saved with `fluid ai setup --source <catalog> --name <name>` (see [Credential handling](#credential-handling)). `fqn` is a table's fully qualified name in the catalog's own form: `DB.SCHEMA.TABLE` on Snowflake, `project.dataset.table` on BigQuery. The arguments of a call for one table:

```json
{
  "kind": "table",
  "source": "snowflake",
  "credentials": { "credential_id": "snowflake-prod" },
  "fqn": "DEMO_DB.SEEDED.ORDERS"
}
```

A call that lacks what its `kind` needs is refused before any credential is resolved. The message names each missing argument and gives an example:

```text
source_catalog kind=tables needs scope, what to list (for example {"database": "DB", "schema": "SALES"}; Unity takes catalog and schema).
```

`response_format` is `concise` (the default) or `detailed`:

- `concise` leaves out vendor-specific payloads (`catalog_specific`), empty fields and key flags that are false, and keeps a table's `tags` whole. A `tables` result lists each table's `fqn`, `name` and `description` only, and a `lineage` result is the upstream and downstream FQNs.
- `detailed` returns every field the catalog gave, as the five tools did.

Each call writes the audit event its former tool wrote, such as `mcp_list_source_tables` for `kind=tables`; `kind=adapters` writes none. See [Audit trail](./v1.5-architecture.md#audit-trail).

#### Fragment-first contracts

A contract split into fragments keeps `$ref` stubs in its root file (see [Contract fragments](../concepts/fragments.md#which-commands-read-a-fragment-root) and [Composing a contract with `$ref`](../concepts/contract-refs.md)). `fluid validate`, `fluid plan` and `fluid mcp output-port serve` resolve those references. Since 0.25.0 ([forge-cli #760](https://github.com/Agenticstiger/forge-cli/pull/760)), so do the authoring tools when they take a `contract_path`: `validate_contract`, `score_contract_quality` and `enrich_contract_suggestions` compose the contract like every command, with fragments confined to the contract's directory unless a [workspace `ref_root` or `FLUID_REF_ROOT`](../concepts/contract-refs.md#widening-the-root-for-a-monorepo) widens it. `validate_contract` takes `contract_path` (or `logical_path`) and no inline contract; `score_contract_quality` and `enrich_contract_suggestions` accept either `contract_path` or an inline `contract` object.

In 0.24.0 and earlier these tools read the file as written, so `validate_contract` reported errors on `$ref` stubs that `fluid validate` did not, and an empty file validated nothing. On those versions, run `fluid bundle contract.fluid.yaml --out runtime/contract.bundled.yaml` and point the tool at the result.

### Large results

*(since 0.31.0, [forge-cli #884](https://github.com/Agenticstiger/forge-cli/pull/884))*

A tool result estimated at more than `FLUID_MCP_INLINE_TOKEN_LIMIT` tokens (default 6,000) is not sent inline. The call returns a short envelope instead, with an MCP `resource_link` to `fluid://artifacts/<id>`, and the client reads the full result with `resources/read`. This holds for every tool. Claude Code, for comparison, warns above 10,000 tokens of MCP tool output, and by default saves a successful result to a file once it passes 25,000 tokens or 50,000 characters. The estimate is the indented JSON text the call would send, at 4 bytes a token, so 6,000 tokens is about 24 KB. `FLUID_MCP_INLINE_TOKEN_LIMIT=0` sends every result inline.

The envelope of a `kind=adapters` call over stdio, with the limit set to 20:

```json
{
  "offloaded": true,
  "tool": "source_catalog",
  "estimated_tokens": 173,
  "bytes": 439,
  "inline_token_limit": 20,
  "resource": "fluid://artifacts/3f035f5c0c6f46cb81e5a05d0950178e",
  "path": "/tmp/fluid-mcp-artifacts-a2i9448f/3f035f5c0c6f46cb81e5a05d0950178e.json",
  "summary": {
    "kind": "adapters",
    "counts": {
      "adapters": 7
    }
  },
  "next": "The full result is too large to send inline. Read it with resources/read, or open the file at path."
}
```

`summary` keeps the result's short top-level values and counts each list. For a `source_catalog` call, `next` can also say what would make the result smaller: on a `kind=tables` call without `scope.tables`, naming the tables it needs there, and on a `detailed` call, asking for `concise`.

Over stdio the client runs on the same machine, so `path` names a file holding the same JSON, for a client that does not read resources. The file is mode 0600, in a private directory (mode 0700) in the system temporary directory. The directory is removed when the server exits normally, which includes a client closing its stdin; a server killed with SIGTERM or SIGKILL leaves it behind. Over HTTP the envelope has no `path`.

The server keeps its last 32 offloaded results, up to 64 MB, until it stops. Reading an older link fails with `No tool result fluid://artifacts/<id>: the server keeps only its last 32 large results, and only until it stops. Call the tool again.` On SDK 1.x the message is prefixed with `Error creating resource from template:`. An id is a random UUID, and any client the server admits can read any link it is given.

### Server instructions

*(since 0.31.0, [forge-cli #884](https://github.com/Agenticstiger/forge-cli/pull/884))*

At `initialize` the server sends this `instructions` text, key words first. A client that defers loading tools, such as Claude Code with tool search, starts a session with only the tool names and this text:

```text
FLUID data products: validate a contract (contract.fluid.yaml); read, diff and edit its .model.json logical model; regenerate the contract and physical files from it; read source-catalog metadata (tables, columns, keys, lineage, glossary) from Snowflake, Unity Catalog, BigQuery, Dataplex, Glue, DataHub or Data Mesh Manager. Reads catalog metadata, never table data. A result too large to send inline comes back as a fluid://artifacts/ resource.
```

### LLM sampling

*(since 0.31.0, [forge-cli #881](https://github.com/Agenticstiger/forge-cli/pull/881))* Removed with `forge_run`, and so is `--llm-provider mcp-sampling`. An agentic IDE authors with its own model: [`fluid scaffold-ide`](../cli/scaffold-ide.md) installs the FLUID skills, and the tools above stay available to it.

The `forge_run` tool's `diag` and `ai` modes need a language model. Rather than configuring a second API key for the server, Forge uses **MCP sampling**: the server sends the model request back through the MCP connection to the client (Claude Code, Cursor, …), and the client fulfils it with the LLM the user already pays for.

So an agentic IDE can run an AI-assisted forge end-to-end on its own subscription — there is no separate `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` for the MCP server. Pair this with [`fluid scaffold-ide`](../cli/scaffold-ide.md), which writes the MCP server entry straight into the editor's config.

### Client config examples

Claude Code (`mcp_servers.json`):

```json
{
  "mcpServers": {
    "fluid-forge": {
      "command": "fluid",
      "args": ["mcp", "serve", "--read-only"],
      "env": { "FLUID_QUIET": "1" }
    }
  }
}
```

Cursor (`settings.json`):

```json
{
  "mcp.servers": {
    "fluid-forge": {
      "command": "fluid",
      "args": ["mcp", "serve"],
      "env": { "FLUID_QUIET": "1" }
    }
  }
}
```

Remove `--read-only` and add both `--readable-paths` and `--writable-paths` when you want the client to patch model sidecars or regenerate artifacts inside a specific workspace directory. `FLUID_QUIET=1` is important because stdout is reserved for MCP JSON-RPC frames.

### Credential handling

The MCP wire format does not accept inline catalog credentials by default. Source-catalog tools resolve credentials from saved Fluid source configs, environment variables, or explicit credential IDs configured outside the MCP call.

```bash
fluid ai setup --source snowflake --name snowflake-prod
```

Then an MCP client can call `forge_from_source` with `source: "snowflake"` and `credentials.credential_id: "snowflake-prod"` without receiving raw secrets.

*(since 0.31.0, [forge-cli #881](https://github.com/Agenticstiger/forge-cli/pull/881))* `forge_from_source` is removed, and the catalog read tools take the same `source` and `credentials.credential_id`. *(since 0.31.0, [forge-cli #884](https://github.com/Agenticstiger/forge-cli/pull/884))* The catalog read tools are now one tool, `source_catalog`, which needs both for every `kind` but `adapters`.

### Certification

```bash
PYTHONPATH=. python scripts/mcp_client_certify.py
```

The certification script checks the JSON-RPC lifecycle, `tools/list`, `tools/call`, MCP Inspector when available, and Claude Code config health when the `claude` CLI is installed. Optional client checks are skipped when their tools are not installed; protocol failures fail the script.

---

## Output port — `fluid mcp output-port serve`

The output port is the inverse of the authoring server. Where authoring **writes** filesystem paths and store namespaces, the output port **reads** production data: it binds one expose of a contract and serves a bounded, read-only surface (`describe` / `sample` / `query` / gated `query_sql`) to an AI agent. Because it touches real data, its entire value is in the governance the contract carries — enforced at runtime, on every call, with no extra wiring.

For the flag reference and a quick start, see [`fluid mcp` in the CLI reference](../cli/mcp.md#consumer-fluid-mcp-output-port-serve). For a hands-on walkthrough, see [Walkthrough: MCP output port](../walkthrough/mcp-output-port.md). The rest of this page is the architecture.

### The contract is the policy

Nothing about the gateway's governance is configured on the command line by default — it is read from the bound expose. The CLI flags (`--allow-models`, `--max-sample-rows`, …) are *operational overrides* for incident response; the contract is the source of truth, and the audit trail records which one won via a `policySource` field (`contract`, `cli`, or `default`). The `semantics` block that enables the `query` tool is described in [Semantic layer](../concepts/semantic-layer.md).

The expose blocks the gateway reads:

```yaml
exposes:
  - exposeId: customer_segments
    contract:
      schema:
        - { name: customer_id, type: STRING, sensitivity: cleartext }
        - { name: email,       type: STRING, sensitivity: pii }      # value-redacted
        - { name: segment,     type: STRING }
    semantics:                       # enables the `query` tool
      measures:  [ { name: customer_count, agg: count_distinct, expr: customer_id } ]
      dimensions: [ { name: segment, type: categorical } ]
      metrics:   [ { name: active_customers, type: simple, measure: customer_count } ]
    binding:
      platform: local
      format: csv
      location: { path: ./customers.csv, table: customer_segments }
    policy:
      agentPolicy:                   # runtime model / use-case / token gates
        allowedModels:  [ claude-haiku-4-5-20251001, gpt-4o-mini ]
        allowedUseCases: [ analysis, qa ]
        deniedUseCases:  [ training, fine_tuning ]
        maxTokensPerRequest: 4096
        maxTokensPerDay: 50000
        canStore: false
        auditRequired: true
```

*On forge-cli `main`, not yet in a release ([forge-cli #1107](https://github.com/Agenticstiger/forge-cli/pull/1107)).* Row filters are read from `policy.authz.rowFilters`: see [Row-level security](#row-level-security-—-policy-authz-rowfilters).

### Per-`tools/call` enforcement order

Every `tools/call` runs through a fixed gauntlet. The order is deliberate: cheap, abuse-resistant gates fire first so a runaway agent can't burn audit storage hammering denied tools.

1. **Identity binding.** The caller's `model`, `useCase` and any extra attributes are read from the MCP `initialize` handshake, from the `fluid` block of the client's `capabilities.experimental` (and, on MCP SDK 1.x, from extra `clientInfo` fields), and resolved again on every tool call from that request's own context, never cached on the shared session (over HTTP one process serves many clients, so a cached identity would carry one client's `agentPolicy` principal and tenant row filter onto the next). Missing identity is treated as `missing-model-identity` (fail-closed at the model gate).
2. **Rate limit.** A sliding-window deque caps calls per window (default 60 calls / 60s). Over the cap returns a `RateLimitExceeded` envelope.
3. **agentPolicy gate.** `OutputPortPolicy.check_tool_call` evaluates first-deny-wins, in the precedence listed under [Decision precedence and reason codes](#decision-precedence-and-reason-codes-since-0-15-0). A deny returns an `AgentPolicyDenied` envelope.
4. **Circuit breaker.** If recent driver failures tripped the breaker, the call fast-fails with a `CircuitOpen` envelope instead of queueing behind another doomed connection.
5. **Token budget (pre-check).** `agentPolicy.maxTokensPerDay` is checked against a rolling 24-hour counter. Over budget returns `TokenBudgetExceeded`.
6. **Backpressure.** An `asyncio.Semaphore` bounds concurrent dispatches (default 8) so a runaway agent can't saturate the engine connection pool.
7. **Dispatch + post-checks.** The tool runs in an executor (driver SDKs are blocking). After it returns, `agentPolicy.maxTokensPerRequest` is checked against the actual response size, the daily counter is topped up, and the circuit breaker records success/failure.

**Every decision — allow and deny — is written to the audit trail**, tagged with the `policySource` that produced it (`rate-limit`, `circuit-breaker`, `token-budget`, `contract`, `cli`, …) and, *(since 0.15.0)*, with the `callerJurisdiction` the decision was made under.

::: tip Self-attested vs. cryptographic identity
Over **stdio**, the caller's `model` and `useCase` are self-attested, and a buggy or malicious client can lie. A client declares them like this in its `initialize` request:

```json
{"capabilities": {"experimental": {"fluid": {"model": "claude-haiku-4-5-20251001", "useCase": "analysis", "tenant_id": "t1"}}}}
```

Any other key in that block becomes a caller attribute. *On forge-cli `main`, not yet in a release ([forge-cli #1107](https://github.com/Agenticstiger/forge-cli/pull/1107)).* Two kinds of attribute are the exception: `principal`, which decides the rows a caller reads, binds only from a JWT claim mapped to it, and the certificate attributes bind only from the headers of a trusted proxy. A client that names its own is ignored in every auth mode. Whenever a model or use-case gate is active, the gateway prints this notice at startup:

```text
⚠️  fluid mcp output-port: caller model_id is self-attested via MCP clientInfo. Do not expose this gateway over an untrusted network until P3 (OAuth/mTLS identity) ships. See https://agenticstiger.github.io/forge_docs/concepts/agent-policy.html
```

The notice is printed whatever the transport and auth mode. *On forge-cli `main`, not yet in a release ([forge-cli #1107](https://github.com/Agenticstiger/forge-cli/pull/1107)).* The row-filter principal binds from the verified claim in the same way. Its "until P3 ships" wording predates the JWT mode: over **HTTP** with `FLUID_MCP_AUTH_MODE=jwt`, identity is cryptographically bound, because the verified JWT claims then *replace* self-attestation for the model and use-case gates, and the [caller-jurisdiction gate](#caller-jurisdiction-enforcement-since-0-15-0). A client certificate checked by a proxy does not bind identity; see [mTLS authenticates the connection](#authentication-modes) under Authentication modes.
:::

### agentPolicy runtime gates

The gateway makes the previously advisory `agentPolicy` block **load-bearing**. On every call it evaluates:

| Field | Semantics |
| --- | --- |
| `allowedModels` | The caller's `model_id` must be in this list. `null`/absent ⇒ no allowlist. Missing identity ⇒ deny. |
| `deniedModels` | Evaluated before `allowedModels`, so a denied model is refused even if it also appears in the allowlist. |
| `allowedUseCases` | The caller's `useCase` must be in this list. If an allowlist exists and the caller declares **no** use case, that's a hard deny (`missing-use-case-with-allowlist`). |
| `deniedUseCases` | Evaluated before `allowedUseCases`; denial wins. |
| `maxTokensPerDay` | Rolling 24-hour token budget. Tokens ≈ response-payload length / 4. |
| `maxTokensPerRequest` | Per-response cap, checked after execution against the serialised payload. |
| `canStore: false` | **Advisory.** Surfaced as a `do-not-store` hint in `describe` and a loud startup notice — the gateway cannot prevent a model from storing data once it crosses the wire. Use cloud-IAM ephemeral credentials for a real guarantee. |
| `auditRequired: true` | The gateway always writes a local audit copy; this surfaces the audit location at startup and reminds operators to point `FLUID_AUDIT_ROOT` at a SIEM-forwarded path. |
| `retentionPolicy.requireDeletion` | **Advisory.** The gateway is not the data owner — pair with a Snowflake `TASK` / BigQuery scheduled query to enforce retention at the source. |

CLI overrides (`--allow-models`, `--deny-models`, `--allow-use-cases`, `--deny-use-cases`) **replace** the contract values entirely (not merged) so the override is intentional and grep-able in the audit trail as `policySource: cli`.

::: tip Validation catches the silent-gate footgun
`fluid validate` warns when an expose that carries an `mcp` block **and** a non-empty `policy.agentPolicy` block declares neither `allowedModels` nor `deniedModels` — without one, the runtime gate is open and the contract's intent to govern downstream LLM access is silently lost.

Note the scope. The check runs only for exposes that declare an `agentPolicy` with at least one field set. An `mcp` block with no `agentPolicy` at all, or an empty `agentPolicy: {}`, is not reported today — even under `--strict` — so do not read a clean validate as proof that a gateway expose is gated.
:::

### Decision precedence and reason codes (since 0.15.0)

Since `0.15.0` every `agentPolicy` decision comes from one function (`fluid_build/policy/decision.py::decide`) over a closed vocabulary of reason codes, and precedence is **data** rather than an accident of statement order. `CHECK_ORDER`, in full:

1. `tool-not-allowed` — denied outright, or absent from a declared tool allowlist.
2. `missing-caller-jurisdiction`
3. `in-denied-jurisdiction`
4. `not-in-allowed-jurisdictions`
5. `missing-model-identity`
6. `in-deniedModels`
7. `in-deniedUseCases`
8. `not-in-allowedModels`
9. `missing-use-case-with-allowlist`
10. `not-in-allowedUseCases`

plus `allowed` when nothing fires. Two principles set that order: bounded surfaces are checked first, and an **explicit denial beats absence from an allowlist**. Jurisdiction sits above the identity gates on a third — a legal constraint outranks a usage constraint as the *reported* reason, because "your model is not on the allowlist" describes the least important thing wrong with a request from a caller who may not receive the data at all.

The wire values are the existing kebab-case strings, so a caller comparing against `"tool-not-allowed"` keeps working. What is new is that an unenumerated reason now raises instead of quietly becoming a reason nobody defined.

::: warning Behavior change in 0.15.0
**No verdict changes, but a reported reason does.** `check_tool_call` documented its precedence as tool denylist → tool allowlist → model denylist → use-case denylist → model allowlist → use-case allowlist, then evaluated the whole model stage before the use-case stage. So a caller whose model was merely *absent from* `allowedModels` and whose use case was *explicitly denied* reported `not-in-allowedModels`; it now reports `in-deniedUseCases`, as the documented precedence always promised. The allow or deny verdict is the same as on `0.14.1`; the reported reason is what changed. **Operators routing alerts, dashboards or audit queries on those two strings should re-check their rules**, since the reason is what you route on and what an auditor reads.
:::

A decision record (`Decision.to_record()`) carries `allow`, `reasonCode`, the request identity, and *(since 0.15.0)* three new fields:

| Field | Meaning |
| --- | --- |
| `policyDigest` | `"<scheme>:<sha256>"` over the RFC 8785 (JCS) canonical form of the **effective** rule lists, sorted and de-duplicated so authoring order cannot change it. `None` and `()` digest differently, because "no allowlist" and "allow nothing" are different policies. The scheme is part of the value so the algorithm can be migrated without invalidating stored records. |
| `callerJurisdiction` | The caller's jurisdiction as the gate saw it, or `null`. |
| `callerJurisdictionSource` | Structured provenance — `"jwt:<claim>"` — rather than a bare `verified: true` boolean. |

Portable conformance vectors ship inside the wheel at `policy/data/vectors/agent-policy-vectors.json`, so a consumer can check their own gate without cloning the repo. The digest is reachable from `OutputPortPolicy.policy_digest()` and `Decision.to_record()`, and since 0.15.0 every `data_access` audit record carries it as `policyDigest`, alongside `policySource` and `callerJurisdiction`.

### Caller-jurisdiction enforcement (since 0.15.0)

Before `0.15.0`, `sovereignty` bound provisioning and nothing else: a contract declaring `jurisdiction: EU` refused to provision into `us-east-1`, then answered a tool call from a caller sitting there. Since `0.15.0` the gateway derives a **query-time** caller-jurisdiction rule from the contract's own `sovereignty` block.

**Enforced, not advisory, and on by default.** There is no flag to switch it on and none to switch it off — the escape hatches are all in the contract:

| Contract state | Gate |
| --- | --- |
| `jurisdiction` pinned, `crossBorderTransfer` unset or `false` (the schema's own default) | **Enforced.** Every `tools/call` needs a verified caller jurisdiction that matches. |
| `crossBorderTransfer: true` | Not enforced — the contract permits the transfer this gate exists to prevent. |
| `jurisdiction: Global` or `Multi-Region` | Not enforced — the contract is explicitly not pinned to one jurisdiction. |
| No `jurisdiction` at all | Not enforced. Every contract that has never pinned one is entirely unaffected, policy digest included. |

**Verified claims only, and fail-closed.** The claim is admissible only from `request.scope["fluid_auth_attrs"]`, which the HTTP transport writes only *after* a credential validates, and never from the caller's self-attested `clientInfo`. In practice that means the `jurisdiction` claim of a verified JWT: a shared token and a proxy-forwarded client certificate carry no jurisdiction. A client typing `jurisdiction: "EU"` into its own handshake satisfies nothing and collapses to the same `missing-caller-jurisdiction` denial as no claim at all. There is no no-auth fallback, on purpose. Matching is **exact and case-sensitive**: a verified `"eu"` against a contract pinning `"EU"` is refused.

::: warning Startup refusal, new in `0.15.0`
A jurisdiction-pinned contract **refuses to serve and exits 2** on the two deployments that could never satisfy the rule, rather than denying every call one at a time:

- `--transport stdio` — the **default**, and a pipe carries no headers, so the middleware never runs.
- `--transport http` with `FLUID_MCP_AUTH_MODE` unset or `none` — the middleware short-circuits before stamping anything.

Both messages name the contract's jurisdiction and give the command that fixes it: serve over HTTP with `FLUID_MCP_AUTH_MODE=jwt` (plus `FLUID_MCP_JWT_ISSUER` / `_AUDIENCE` / `_JWKS_URL`), or set `sovereignty.crossBorderTransfer: true` if the data may leave. The most common desktop-client setup — stdio — is therefore the one configuration such a contract cannot serve.

The startup check looks only at whether an auth mode is configured. `FLUID_MCP_AUTH_MODE=shared-token` passes it, and a shared token carries no jurisdiction, so such a contract then denies every call as `missing-caller-jurisdiction`. Only `jwt` can supply the claim.

*(since 0.31.0, [forge-cli #891](https://github.com/Agenticstiger/forge-cli/pull/891))* The startup check asks the auth validator instead. Over HTTP such a contract starts only with `FLUID_MCP_AUTH_MODE=jwt`, its issuer, audience and JWKS URL set, and a claim mapped to `jurisdiction` (the default mapping has one). Every other setup exits 2 before it listens: `shared-token` with or without a token, behind a trusted proxy or not; `jwt` without its issuer, audience or JWKS URL; and a `FLUID_MCP_JWT_CLAIM_MAPPING` that maps the claim away. Each message names the jurisdiction, says why no claim can be verified, and says how to supply one (JWT auth, or mapping the IdP's claim to `jurisdiction`) or to set `sovereignty.crossBorderTransfer: true`.
:::

`jurisdiction` is also one of the [default JWT claim mappings](#authentication-modes), and it is the one default whose absence **closes** the gate rather than widening it: an operator whose IdP calls the claim something else locks themselves out of a jurisdiction-pinned contract until they map it.

### Authentication modes

Identity is resolved once at gateway start from `FLUID_MCP_AUTH_MODE`. There are three modes plus an explicit opt-out:

| Mode (`FLUID_MCP_AUTH_MODE`) | How it works | Config |
| --- | --- | --- |
| `shared-token` *(default)* | Symmetric bearer token compared with `hmac.compare_digest` (constant-time). One secret, every client uses the same value. | `FLUID_MCP_AUTH_TOKEN` |
| `jwt` | RFC 7519 bearer. Validates the signature against an issuer's **JWKS** endpoint (`RS256` / `ES256` / `EdDSA`), checks `iss` / `aud` / `exp` / `nbf`, and maps configured claims into `caller_attributes`. Works with Auth0, Okta, Keycloak, AWS Cognito, Google IAP, Azure AD. JWKS keys are cached in-process with a TTL. | `FLUID_MCP_JWT_ISSUER`, `FLUID_MCP_JWT_AUDIENCE`, `FLUID_MCP_JWT_JWKS_URL`, optional `FLUID_MCP_JWT_ALGORITHMS`, `FLUID_MCP_JWT_CLAIM_MAPPING` |
| `none` | Operator explicitly opts out. Every request is allowed and the gateway logs a startup warning that it is unauthenticated. The `data_access` audit record has no field that says how the caller authenticated, so unauthenticated traffic cannot be told apart in it. *(since 0.15.0)* A contract that pins `sovereignty.jurisdiction` refuses to start in this mode — see below. | — |
| *(unconfigured)* | If `shared-token` has no token, or JWT is missing issuer/audience/JWKS, the gateway runs **unauthenticated** and emits a loud startup warning. *(since 0.15.0)* Same exception: a jurisdiction-pinned contract refuses to start instead. | — |

*(since 0.31.0, [forge-cli #879](https://github.com/Agenticstiger/forge-cli/pull/879))* `fluid mcp serve --transport http` reads the same variables. Over HTTP, `none` and an unconfigured mode serve only on a loopback `--host`: anywhere else the server refuses to start and exits 2, and off loopback a shared token must be at least 32 characters. "Every request is allowed" then means that no credential is checked. A cross-origin browser request still gets 403, and a request whose `Host` is not loopback gets 421, so behind a proxy that forwards its public name every request gets 421. See [The HTTP transport](../cli/mcp.md#the-http-transport).

::: warning Startup refusal for a jurisdiction-pinned contract, new in `0.15.0`
The two rows above no longer hold for a contract that pins `sovereignty.jurisdiction` without `crossBorderTransfer: true`. Because the caller-jurisdiction gate admits only claims the auth middleware verified, an unauthenticated gateway would deny **every** call — so `fluid mcp output-port serve` writes a refusal to stderr and **returns exit code 2** before binding, for `--transport stdio` (any auth mode: a pipe carries no headers) and for `--transport http` with `FLUID_MCP_AUTH_MODE` unset or `none`. See [Caller-jurisdiction enforcement](#caller-jurisdiction-enforcement-since-0-15-0).

*(since 0.31.0, [forge-cli #891](https://github.com/Agenticstiger/forge-cli/pull/891))* The `shared-token` row does not hold for such a contract either: it refuses to start with a token too, because a shared token carries no jurisdiction. So does `jwt` when no claim maps to `jurisdiction`.
:::

Only a verified JWT binds identity. With `shared-token`, the gateway knows that the caller held the shared secret and nothing else: once the token is enforced, any `model`, `useCase` or tenant attribute the client declares for itself is dropped. A contract with an `allowedModels` or `deniedModels` gate then denies every call as `missing-model-identity`, and one with `allowedUseCases` as `missing-use-case-with-allowlist`. Use `jwt` when the gates must see who is calling.

::: warning mTLS authenticates the connection; it does not bind identity
`FLUID_MCP_AUTH_MODE` accepts only `shared-token`, `jwt` and `none`. With `FLUID_MCP_AUTH_MODE=mtls`, `fluid mcp output-port serve --transport http` exits 2 with `ERR_INVALID_AUTH_MODE`, naming the bad value, the accepted ones (`shared-token, jwt, none`) and a hint to terminate mTLS at a reverse proxy. `off` and `disabled` are refused the same way.

A proxy in front of the gateway can require client certificates, which keeps hosts without one off the network path. The gateway never sees the certificate. It sees two request headers the proxy sets, `X-Client-CN` and `X-Client-Fingerprint`, and what it does with them is narrow:

- It reads them only when an auth mode is enforced: `jwt` with its three settings, or `shared-token` with `FLUID_MCP_AUTH_TOKEN` set. With `none`, or with neither configured, the middleware passes the request on without looking.
- It copies them, unverified, into the request's caller attributes as `client_cn` and `client_fingerprint`, so the gateway must be reachable only through the proxy, and the proxy must overwrite any copy of those headers the client sends.
- *On forge-cli `main`, not yet in a release ([forge-cli #1107](https://github.com/Agenticstiger/forge-cli/pull/1107)).* Neither attribute selects rows. A row filter reads the caller's `principal` and no other attribute, and the gateway no longer resolves the old `${caller.client_cn}` and `${caller.client_fingerprint}` placeholders of `policy.rowFilters`: a certificate is not a principal, so a certificate checked by a proxy does not decide which rows a caller reads. A client that names its own `client_cn` or `client_fingerprint` is ignored, in every auth mode.
- They never supply `model`, `use_case`, `tenant_id` or `jurisdiction`. Those come from the mapped claims of a verified JWT, or from the client's own declaration when no auth mode is enforced.
- In 0.18.1 neither header is written to a `data_access` audit record.

Without an auth mode, the gateway is unauthenticated whatever the proxy does: a caller picks its own model, use case and `tenant_id`. *On forge-cli `main`, not yet in a release ([forge-cli #1107](https://github.com/Agenticstiger/forge-cli/pull/1107)).* The principal that a row filter reads does not bind from what a client says about itself, so an expose that declares `policy.authz.rowFilters` refuses every call there, and `serve` refuses to start it (see [Row-level security](#row-level-security-—-policy-authz-rowfilters)). *(since 0.31.0, [forge-cli #879](https://github.com/Agenticstiger/forge-cli/pull/879))* Such a gateway also answers 421 to every request a proxy forwards under its public name, so it serves only callers on its own machine.
:::

`FLUID_MCP_JWT_CLAIM_MAPPING` is a comma-separated `claim=attr` list, e.g. `sub=principal,https://fluid/model=model,https://fluid/tenant=tenant_id`. Mapped claims land in `caller_attributes`. *On forge-cli `main`, not yet in a release ([forge-cli #1107](https://github.com/Agenticstiger/forge-cli/pull/1107)).* The claim mapped to `principal` is what `policy.authz.rowFilters` and `policy.authz.readers` match, so on the JWT path the rows a caller reads follow a verified credential, never self-attested `clientInfo`.

*(since 0.15.0)* The value **merges over** the default mappings instead of replacing them. Those defaults are:

| Claim | `caller_attributes` key | Why it is load-bearing |
| --- | --- | --- |
| `sub` | `sub` | *On forge-cli `main`, not yet in a release ([forge-cli #1107](https://github.com/Agenticstiger/forge-cli/pull/1107)).* Kept as a caller attribute. The gateway reads nothing from it, and a row filter does not read it: map a claim to `principal` for that. |
| `model` | `model` | Input to the `agentPolicy` model gate. |
| `use_case` | `use_case` | Input to the `agentPolicy` use-case gate. |
| `tenant_id` | `tenant_id` | *On forge-cli `main`, not yet in a release ([forge-cli #1107](https://github.com/Agenticstiger/forge-cli/pull/1107)).* Kept as a caller attribute. The gateway reads nothing from it, and a row filter does not read it: map a claim to `principal` for that. |
| `jurisdiction` | `jurisdiction` | *(since 0.15.0)* The verified claim the [caller-jurisdiction gate](#caller-jurisdiction-enforcement-since-0-15-0) reads. |

*On forge-cli `main`, not yet in a release ([forge-cli #1107](https://github.com/Agenticstiger/forge-cli/pull/1107)).* No claim maps to `principal` by default. Add one, for example `FLUID_MCP_JWT_CLAIM_MAPPING=groups=principal`, on a gateway that serves an expose with `policy.authz.rowFilters`. A claim that holds a list gives the caller every principal in it.

::: warning Behavior change in 0.15.0
On `0.14.1` and earlier the parsed value was assigned **wholesale**, so mapping one extra claim silently dropped all four defaults — turning off the `agentPolicy` model and use-case gates and emptying every `${caller.*}` row filter, with no error and a server still reporting healthy. Mapping a default away explicitly still works; what no longer happens is losing one by accident while adding something unrelated.

Note the asymmetry for the newest default: losing `sub` / `model` / `use_case` / `tenant_id` **widens** access, while losing `jurisdiction` **closes** the gate completely — an operator who remaps their IdP's jurisdiction claim to some other attribute name locks themselves out of a jurisdiction-pinned contract rather than letting strangers in. That is the correct direction for a sovereignty control, and this mapping is where to look when it happens.

*(since 0.31.0, [forge-cli #891](https://github.com/Agenticstiger/forge-cli/pull/891))* When no claim is left mapped to `jurisdiction`, `fluid mcp output-port serve` refuses to start such a contract and names `FLUID_MCP_JWT_CLAIM_MAPPING`, instead of denying every call.
:::

::: warning
There is no `--auth-token` CLI flag. Auth is configured entirely through `FLUID_MCP_*` environment variables, so the same contract can be served at different trust levels without editing it.
:::

### PII / PHI value redaction

Columns marked `sensitivity: pii`, `sensitivity: phi` or `sensitivity: sensitive` in `expose.contract.schema` keep their **key** visible (the agent still sees the field exists and can write `COUNT(DISTINCT …)` aggregates) but their **values** are replaced with the constant `[REDACTED-PII]` before the row leaves the gateway.

This happens at the **driver boundary** — `EngineDriver.project()` masks every row from `sample`, `query`, and `query_sql` alike. It is distinct from `columnRestrictions`, which drops a column *wholesale*:

| Layer | Source | Effect |
| --- | --- | --- |
| **PII redaction** | `contract.schema[].sensitivity` ∈ `{pii, phi, sensitive}` | Column stays in the schema; values become `[REDACTED-PII]`. |
| **Column restriction** | `policy.authz.columnRestrictions` (`access: deny`) or `policy.privacy.masking` | Column is removed entirely from the projection. |

Both are **alias-proof on the free-form path.** Masking matches by output column *name*, so `SELECT email AS x` would otherwise sneak a PII value past it. The `query_sql` compiler closes that hole by rejecting any reference to a restricted *or* PII column at compile time (string literals are stripped first, so `WHERE label = 'email'` doesn't false-positive). The agent cannot alias the column away.

### Restricted columns on the query tools

*On forge-cli `main`, not yet in a release ([forge-cli #1105](https://github.com/Agenticstiger/forge-cli/pull/1105)).*

A column is restricted when `policy.authz.columnRestrictions` denies it (`access: deny`), whichever principal the entry names, or `policy.privacy.masking` names it. On an expose with restricted columns, `query` and `query_sql` read through a projection of the columns the contract allows, not through the table. A restricted column is not part of what an expression or a statement can see, however it is written. The name check described above stays as the early, readable refusal.

The examples below run against this expose, served over a CSV file on DuckDB with `ssn` denied:

```yaml
exposes:
  - exposeId: customers
    contract:
      schema:
        - { name: customer_id }
        - { name: email, sensitivity: pii }
        - { name: ssn }
        - { name: segment }
        - { name: amount }
        - { name: tenant_id }
    policy:
      authz:
        columnRestrictions:
          - { principal: analysts, columns: [ssn], access: deny }
```

#### `query`

Every dimension, measure, metric `filter` and filter key is evaluated over the allowed columns. The result's `compiled.sql` shows it:

```sql
SELECT segment AS segment, SUM(amount) AS total_amount
FROM (SELECT customer_id, email, segment, amount, tenant_id FROM customers) AS _fluid_allowed
GROUP BY segment
ORDER BY total_amount DESC, segment ASC
LIMIT 100
```

- **The allowed columns are the ones `contract.schema` declares, less the restricted ones.** A column the table has and the schema does not declare is not part of the projection, so an expression that uses it fails in the engine (`Referenced column "hidden_col" not found in FROM clause!` on DuckDB). An expose whose schema declares no readable column is refused: `This expose restricts columns, but contract.schema declares no readable column to project, so the governed query path cannot evaluate an expression without risking a restricted one. Declare the readable columns in contract.schema.` A column qualified with the table name (`customers.amount`) does not resolve either, on an expose with restricted columns; write the bare column name.
- **Row filters apply inside the projection.** *On forge-cli `main`, not yet in a release ([forge-cli #1107](https://github.com/Agenticstiger/forge-cli/pull/1107)).* A [row filter](#row-level-security-—-policy-authz-rowfilters) may therefore name a restricted column. With `tenant_id` denied and a filter on it, the statement reads `FROM (SELECT customer_id, email, ssn, segment, amount FROM customers AS _fluid_rows WHERE (<row filter>)) AS _fluid_allowed`, where `(<row filter>)` stands for the predicate, which the caller is not shown. A caller's own filter key on a restricted column is still refused by name.
- **A subquery in an expression is refused** on an expose that restricts or redacts columns, or declares row filters: `Dimension 'd' contains a subquery. On an expose with column restrictions or row filters, expressions may only use the exposed table's own columns.` An expression that spells `SELECT` is refused earlier, as an invalid SQL expression.
- **An expose with no restrictions** reads `FROM <table>` as before.

##### Redacted columns

On an expose with a column marked `sensitivity: pii`, `phi` or `sensitive`, redaction follows the columns an expression names. An expression that would read a column without naming it is therefore refused: a column selector such as `COLUMNS(...)`, `IDENTIFIER(...)`, a `*` that stands for columns, and the table (or `_fluid_allowed`) used as a whole-row value. It applies to a measure, a dimension, a metric filter and a filter key, and the message names which one:

```text
Measure 'm' selects columns without naming them (a column selector, IDENTIFIER(...), a star, or the whole row). This expose redacts columns (contract.schema[].sensitivity), and a redaction applies to the columns an expression names, so name the columns it reads.
```

`count(*)`, arithmetic such as `sum(amount * 2)` and `count(DISTINCT email)` are accepted and return their values. An expression that names the column is redacted as before: a dimension on `email` returns `[REDACTED-PII]` in every row.

#### `query_sql`

`query_sql` exists only with `--allow-sql`. On an expose that restricts or redacts columns, every reference to the exposed table in the statement (the `FROM` and each join, a self-join included) is replaced by a projection of the allowed columns. A redacted column is left out of that projection too, as a restricted one is. `SELECT *`, `alias.*` and the table or its alias used as a whole-row value return only the allowed columns:

```text
SELECT c.* FROM customers AS c JOIN customers AS d ON c.customer_id = d.customer_id
-> SELECT c.* FROM (SELECT customer_id, segment, amount, tenant_id FROM customers) AS c JOIN (SELECT customer_id, segment, amount, tenant_id FROM customers) AS d ON c.customer_id = d.customer_id
   columns: customer_id, segment, amount, tenant_id

SELECT to_json(c) AS row_json FROM customers AS c LIMIT 1
-> {"customer_id":1,"segment":"retail","amount":10,"tenant_id":"t1"}
```

A statement that names `ssn` or `email` is still refused by name. What the statement may read from is limited as well. *On forge-cli `main`, not yet in a release ([forge-cli #1107](https://github.com/Agenticstiger/forge-cli/pull/1107)).* The messages below say "columns or rows", since a filtered expose is limited the same way. Each of these is refused on such an expose, with the message shown:

| Statement | Refusal |
| --- | --- |
| A table function: `SELECT * FROM read_csv('customers.csv')` | `sql may only read from tables named in the usual way, subqueries, UNNEST and VALUES on an expose that restricts columns or rows; query the exposed table directly.` |
| A quoted file path as a table: `SELECT * FROM 'customers.csv'` | `sql may not read from a table function or a file path on an expose that restricts columns or rows; query the exposed table directly.` |
| The `TABLE` keyword: `SELECT * FROM (TABLE customers)` | `sql may not use the TABLE keyword on an expose that restricts columns or rows; select from the exposed table by name.` |
| Any other source that is not a plain table, `UNNEST` or `VALUES` | The first message in this table. |
| SQL the parser cannot read: `SELECT FROM FROM` | `sql could not be rewritten to read only the columns this expose allows; write one plain SELECT over the exposed table.` |

A subquery that spells `SELECT` is refused earlier, as an invalid SQL expression.

- On DuckDB the engine's own parser checks the rewritten statement as well. A statement it cannot parse, or one in which the exposed table is read in any form other than the allowed-column projection, is refused with `sql could not be checked against the columns this expose allows; write one plain SELECT over the exposed table.`
- A column written as `schema.table.column` no longer resolves once the table is rewritten. Give the table an alias, or write `table.column`.
- An expose with no restricted or redacted column runs the statement unchanged.

#### Postgres functions that read past the projection

`query_sql` and the `query` expressions refuse `table_to_xml`, `query_to_xml`, `cursor_to_xml`, every `schema_to_xml*` and `database_to_xml*` function, and their `*xmlschema` and `*_and_xmlschema` variants. The refusal holds on every engine, in any case, quoted or schema-qualified. In a `query` expression it is reported as `Invalid SQL expression`. A column or alias that only shares one of those names is not a call and is unaffected.

*On forge-cli `main`, not yet in a release ([forge-cli #1107](https://github.com/Agenticstiger/forge-cli/pull/1107)).* The refusal is wider than the XML functions. On every expose, `query_sql`, the `query` expressions and the drivers' statement guard also refuse the Postgres functions that run a query given as text, the catalog and statistics functions, the functions that read raw pages or other requests' statements, and `set_config`, which changes the session that later requests run in, and the `pg_prepared_statements` and `pg_cursors` views. They refuse a name or a string written with Unicode escapes too, which can spell any of those functions. On `query_sql` the message lists them:

```text
sql may not call a function that reads a relation or runs a query given as text, or that changes the session (table_to_xml, query_to_xml, cursor_to_xml, schema_to_xml, database_to_xml, ts_stat, ts_rewrite, connectby, crosstab, dblink, pgstattuple, pg_stat_*, pgrowlocks, get_raw_page and the other pageinspect functions, pg_cursor, pg_prepared_statement, set_config and their variants), name the pg_cursors or pg_prepared_statements views, or write a name or a string with Unicode escapes (U&"..."). Select the columns of the exposed table directly.
```

A string literal that contains `u&"` or `u&'` is refused as well. The rule sits in the shared expression check, so it also applies to the contract expressions that the Snowflake planner and the Databricks Genie and metrics emitters read. The same check runs on every row filter predicate; see [Row-level security](#row-level-security-—-policy-authz-rowfilters).

*On forge-cli `main`, not yet in a release ([forge-cli #1109](https://github.com/Agenticstiger/forge-cli/pull/1109)).* More Postgres functions are refused on every expose: those that read server files, the write-ahead log or logical-decoding changes, or touch the session, sequences, locks or other sessions. `query_sql`, the `query` expressions and the drivers' statement guard refuse `pg_read_*`, `pg_ls_*`, `pg_file_*`, the large-object functions, `pg_get_wal*`, `pg_logical*`, `pg_create_*`, `pg_advisory*`, `pg_try_advisory*`, `pg_sleep*`, `current_setting`, `nextval`, `setval`, `currval`, `lastval`, `pg_relation_filepath`, `pg_cancel_backend`, `pg_terminate_backend`, `pg_reload_conf`, `pg_switch_wal`, `pg_notify` and the replication-slot functions. A role allowed to call the file and write-ahead-log readers would read the rows a row filter withholds.

### Row-level security — `policy.authz.rowFilters`

*On forge-cli `main`, not yet in a release ([forge-cli #1107](https://github.com/Agenticstiger/forge-cli/pull/1107)).*

The gateway enforces `exposes[].policy.authz.rowFilters[]` on `sample`, `query` and `query_sql`. Each entry is `{principal, where, name?}`: the principal reads only the rows its `where` predicate selects. The key is in contract schema `0.7.6`, the stable default, and `0.7.7` (preview), not in `0.7.5`, so the contract needs `fluidVersion: "0.7.6"` or later. It is the key that `fluid apply` writes into a BigQuery row access policy, a Lake Formation data cells filter or a Unity Catalog row filter, and the gateway reads it with the same parser. See [Row filters](../providers/gcp.md#row-filters) on GCP.

```yaml
exposes:
  - exposeId: customers
    contract:
      schema:
        - { name: customer_id }
        - { name: tenant_id }
        - { name: amount }
    policy:
      authz:
        readers: ["group:ops"]
        rowFilters:
          - { principal: "tenant:acme",   where: "tenant_id = 'acme'" }
          - { principal: "tenant:globex", where: "tenant_id = 'globex'" }
```

`fluid validate` accepts that contract. The earlier key, `policy.rowFilters`, is not a contract field, and the same check refuses it:

```text
❌ Invalid FLUID contract (1 error(s)) (schema v0.7.6)
Validation completed in 0.003s

Validation Errors:
==================
 1. exposes[0].policy: Additional properties are not allowed ('rowFilters' was unexpected)
```

The gateway no longer reads `policy.rowFilters`. It refuses an expose that still carries the key, on every call and at `serve`, rather than serve it unfiltered:

```text
fluid mcp output-port: refusing to serve: this expose's row filters cannot be applied.
  exposes[customers].policy.rowFilters is not a contract field. Row filters are declared under exposes[customers].policy.authz.rowFilters, each naming a principal and a where predicate; an expose that still carries the old key is refused rather than served unfiltered.
```

To move a filter, write one `policy.authz.rowFilters` entry per principal, with the value in the predicate. A filter `{ column: tenant_id, equals: "${caller.tenant_id}" }` becomes `{ principal: "tenant:acme", where: "tenant_id = 'acme'" }` for each tenant. The `${caller.*}` placeholders are gone.

#### Which rows a caller reads

- **The principal comes from a verified JWT claim.** The caller attribute `principal`, one value or a list, is matched against the `principal` of each filter and against `policy.authz.readers`. It binds only from a JWT claim mapped to it, `FLUID_MCP_JWT_CLAIM_MAPPING=<claim>=principal` (see [Authentication modes](#authentication-modes)). A client that states its own `principal`, in `clientInfo` or in its `fluid` capability block, is dropped in every auth mode, so a client cannot pick its own filter or a reader's every row.
- **A caller reads the union of the filters that name its principals.** BigQuery combines row access policies the same way. A caller with two principals reads the rows of either predicate.
- **A reader no filter names reads every row.** A principal in `policy.authz.readers` that no filter names reads every row. A caller with any such principal reads every row, whatever its other principals are filtered to, and it reads the plain statement: undeclared columns and other relations are not fenced for it (see below).
- **A caller no filter or reader names is refused.** A request with no principal, or with principals that neither a filter nor `readers` names, gets `RowFilterIdentityMissing`. The gateway cannot tell an unfiltered reader from a filtered principal it does not know, so it serves neither.
- **`accessPolicy` grantees and `binding.principals` are not consulted.** To read every row through the gateway, a principal must be in `policy.authz.readers`.

#### What the gateway applies

- **Every read of the table is filtered, wherever it sits.** The gateway reads the table through `(SELECT <allowed columns> FROM <table> AS _fluid_rows WHERE <predicate>)`, the projection that [column restrictions](#restricted-columns-on-the-query-tools) already use. `sample` filters its scan, `query` reads the projection as `_fluid_allowed`, and `query_sql` has every reference to the exposed table replaced by it. The projection is applied at every place the table is read, so a second reference (a self-join) sees only the caller's rows. A subquery, a CTE or a set operation is refused earlier, as an invalid SQL expression. The predicate's columns are qualified with `_fluid_rows`, so none of them resolves to a column of the caller's own statement:

  ```text
  SELECT * FROM customers
  -> SELECT * FROM (SELECT customer_id, tenant_id, amount FROM customers AS _fluid_rows WHERE (<row filter>)) AS customers
     LIMIT 10
  ```

  The statement that the result shows the caller reads `(<row filter>)` in place of the predicate. `describe` does not return `policy.authz`, and the `expose.json` and `contract.yaml` resources omit it too.
- **The query tools read only the declared columns.** For a caller that a filter limits, `query` and `query_sql` read only the columns `contract.schema` declares, and `query_sql` reads only the exposed table, its own CTEs, `VALUES` and `UNNEST`. A reader that no filter names reads the plain statement: undeclared columns and other relations are not fenced for it, so keep `policy.authz.readers` to principals that may see the whole table. For a limited caller, they need plain-identifier column names. `sample` returns every column of the filtered scan, so it is not limited to the declared columns.
- **`query_sql` reads only the exposed table.** For a caller that a filter limits, and on an expose that restricts columns, a statement may read the exposed table, a CTE of its own where that CTE is in scope, `VALUES` and `UNNEST`. A join with another table, a catalog view and any other relation are refused, because a catalog view holds values from every row and column of the table, which the projection does not cover:

  ```text
  sql reads 'pg_stats'; on an expose that restricts columns or rows a statement reads only the exposed table, its own CTEs, VALUES and UNNEST.
  ```

  Read another table through its own expose.
- **The exposed table's name under another schema or catalog is refused.** Write the table unqualified, or as the expose binds it. On DuckDB, `main` counts as the schema of an unqualified binding, so `main.customers` still reads the exposed table. *On forge-cli `main`, not yet in a release ([forge-cli #1109](https://github.com/Agenticstiger/forge-cli/pull/1109)).* The catalog counts too: on DuckDB an unqualified binding's schema is `main` and its catalog is the database the binding opens, `memory` or the database file's name up to its first dot, so `memory.main.customers` reads the exposed table of an in-memory binding.

  ```text
  sql reads 'other.customers', a table of that name in another schema or catalog than the exposed table's; write the table unqualified or as the expose names it.
  ```
- **Functions that read past the projection are refused on every expose.** `query_sql`, the `query` expressions and the drivers' statement guard refuse the Postgres functions that run a query given as text, the statistics functions (`pg_stat*`, `pgstat*`), and the other functions listed under [Postgres functions that read past the projection](#postgres-functions-that-read-past-the-projection), beside the XML functions. A name or a string written with Unicode escapes is refused too.
- **The whole statement is checked.** The keyword and character checks and the drivers' statement guard read everything after the leading `SELECT`, including text written directly against the keyword.
- **On Postgres the filtered projection is a step of its own.** The statement ends the projection with `OFFSET 0`. Postgres can otherwise merge the projection into the caller's statement and evaluate the caller's conditions on rows the filter removes, where a failing cast or a division by zero would tell the caller that such a row exists.
- **Each Postgres request runs in its own read-only transaction, rolled back at the end.** The shared connection runs in autocommit, where its read-only flag applies to no statement and a session setting that one request changed would stay for the next. The per-request query timeout (`SET LOCAL statement_timeout`) takes effect in that transaction too.
- **`query` parenthesises every term of its `WHERE`**, so an `OR` inside a metric-filter or a dimension expression stays inside its own term and the row filter is still ANDed to the result.

#### What a caller a row filter narrows may write in `query_sql`

*On forge-cli `main`, not yet in a release ([forge-cli #1109](https://github.com/Agenticstiger/forge-cli/pull/1109)).*

An engine may evaluate a caller's condition on a row the filter removes. An error there, such as a failed cast or a division by zero, would tell the caller that the row exists. So for a caller that a filter narrows, `query_sql` limits which functions it may call and which conditions it may write, and checks the types of the values a condition relates. A reader that no filter narrows is not limited. The `query_sql` tool's description states the same limits.

**Functions.** A narrowed caller may call aggregates, window functions and each engine's common conditional, math, string, date, conversion, JSON and array functions, unqualified or under `pg_catalog`. These are refused:

- any function that is not listed;
- a function that another schema qualifies;
- a quoted function name that differs from the listed one in case;
- `OPERATOR(...)`;
- the generators `generate_series`, `range`, `repeat`, `lpad` and `rpad`. Not every engine stops a statement at the gateway's timeout, and the row cap does not bound a string built per row.

**Conditions.** Each WHERE, JOIN ON or USING, HAVING and QUALIFY condition is checked:

- Every condition, and each operand of AND, OR, NOT and IS TRUE / IS FALSE, is a comparison (`=`, `<>`, `<`, `<=`, `>`, `>=`, `IS DISTINCT FROM`), `IN`, `BETWEEN`, `LIKE`, `ILIKE`, `IS NULL`, `EXISTS`, a column declared as a boolean, or TRUE or FALSE. A non-boolean value as a condition is cast row by row, so it is refused. `IS UNKNOWN` is refused.
- The two values a comparison relates have one type, because a comparison between different types is cast row by row. Each `coalesce`, `IN` and `BETWEEN` operand is held to the same rules, and so are the members of a tuple.
- A `USING` column must have one type on both sides, and `NATURAL` joins are refused. An `IN` subquery must return one value of the left side's type. A value that a subquery computes is refused.
- A `VALUES` or `UNNEST` column, a computed value, and a JSON, array, map or struct value cannot be typed, so they are not compared.
- `LIKE` and `ILIKE` take a string and a string literal pattern, with no `ESCAPE` clause and no backslash, since both fail on a value that meets the escape character. A literal `%` or `_` cannot be matched.
- `lower` and `upper` take a string column or literal, and `coalesce` takes columns and constants of one type. Compute other values (casts, arithmetic, other functions) in the outer select list.

**Types.** The gateway types each column by the table's own type, read from the engine's catalog: `pg_catalog` on Postgres, so a view, a materialized view, an enum, `citext` and a domain are typed, and `information_schema.columns` on the other engines. The lookup uses the current schema when the binding names none, and it is read again after five minutes.

- A type that `contract.schema` declares must agree with the table's type, and a column the contract declares but the table lacks is refused. A column declared as a string but held as a number refuses the narrowed caller. Without a driver the declared type stands.
- The type follows a column through CTEs and derived tables that select it unchanged. A derived table's column list is read by position, and an alias column list on a table reference is refused. A name the catalog reports with two types, or with a type the gateway does not type, is not compared.
- A constant is a literal, a cast or an interval of one, or the current date or time. `DATE '2024-01-01'` and `CURRENT_DATE` are dates, a date plus or minus an integer is a date, `TIMESTAMP '...'` is a timestamp, and `now()` and `CURRENT_TIMESTAMP` are timestamps with a time zone. A date plus or minus an interval is not typed, because engines differ on whether the result is a date or a timestamp. Cast it: `CAST(CURRENT_DATE - INTERVAL '7' DAY AS DATE)`.
- A date meets only a date, a timestamp only a timestamp, and a timestamp with a time zone only a timestamp with a time zone. A date column compared with `'2024-01-01'` is refused, so write `DATE '2024-01-01'`.
- Exact numbers are compared as DECIMAL. An integer type is DECIMAL(d, 0), with d = 3, 5, 10, 19 and 39 for tinyint, smallint, int, bigint and hugeint, and a decimal literal is DECIMAL(its digits, its decimals). Two exact numbers meet only when the larger integer part plus the larger scale is at most 38 digits. A number of unknown precision, Postgres's unconstrained `numeric`, meets no other exact number until the table gives it a precision and scale. A float meets any number.

**HAVING and QUALIFY.** Aggregates and window values see only the rows the filter keeps, so they compare freely. The other values of such a comparison are still typed. A HAVING name that a select-list alias could take is typed only when the column and the alias have one type.

A refusal names the function or the condition as the caller wrote it, where the parser kept its position.

#### Refusals

- **A request that cannot be filtered is refused.** `RowFilterIdentityMissing` is the refusal for a caller without a principal that a filter or `readers` names. `RowFilterUnavailable` is the refusal on every call to an expose whose filter cannot be applied: a column that `contract.schema` does not declare, a malformed entry, a principal filtered twice, two filters whose derived names collide (set `name:` on one), a predicate that the engine would read differently, or the old `policy.rowFilters` key. A predicate that BigQuery or Spark would read differently is a double-quoted name, which is a string there, so write the name bare. `fluid generate iac` and `fluid apply` refuse a row filter with a double-quoted column name for BigQuery and Databricks as well, and check Lake Formation filters as Athena reads them.
- **The caller sees a generic message.** The wire message is `Tool '<tool>' failed; see server audit trail for the full annotated error.` for both. The detail, which names the predicate and the principals, goes to the operator log and the audit record.
- **A filter is checked as the engine reads it.** The same check refuses a predicate that holds the text `:p_`, because the gateway's bind markers are rewritten wherever they appear, and a predicate that holds the word `UNION`, `INTERSECT` or `EXCEPT`, because the statement guard reads string literals too.
- **Without sqlglot, every row filter is refused.** An unchecked predicate is never applied. sqlglot is a base dependency of forge-cli. *On forge-cli `main`, not yet in a release ([forge-cli #1109](https://github.com/Agenticstiger/forge-cli/pull/1109)).* The floor is 30.1: releases before 30.1 refuse some valid `query_sql` reads on an expose with row filters (a DuckDB `EXISTS (FROM ...)` subquery, for one), and 26.16 and older record no identifier positions and refuse every row filter. Upgrade with `pip install --upgrade "sqlglot>=30.1"` or upgrade `data-product-forge`.
- **An expose that holds an unresolved `$ref` is refused.** *On forge-cli `main`, not yet in a release ([forge-cli #1109](https://github.com/Agenticstiger/forge-cli/pull/1109)).* forge's loader resolves every reference, a pointer into the same document included, before `serve` reads a policy. A caller that hands the compiler an expose of its own (the Python functions `compile_semantic_query`, `compile_free_form_sql`, `row_filter_predicate` and `declares_row_filters`) could pass `policy: {$ref: ...}` unresolved, which read as no row filter. Every read path and the startup check now refuse an expose that is itself a `$ref`, or whose `policy`, `contract` or `contract.schema` entries hold one.

`fluid mcp output-port serve` refuses to start an expose whose row filters no request could satisfy, and exits 2: over stdio, over HTTP without auth or with a shared token, and over HTTP with JWT auth when no claim is mapped to `principal`. It refuses too when the old `policy.rowFilters` key is present or a filter cannot be applied, as the engine of the binding reads it. Serve such an expose over HTTP with JWT auth and map the claim that carries a caller's principal:

```text
fluid mcp output-port: refusing to serve: this expose declares policy.authz.rowFilters, which limit each caller to the rows its principal may read, and 'stdio' carries no verified identity, so every call would be refused.
  Serve it over HTTP with JWT auth and map the claim that carries a caller's principal:
    FLUID_MCP_AUTH_MODE=jwt FLUID_MCP_JWT_ISSUER=... FLUID_MCP_JWT_AUDIENCE=... FLUID_MCP_JWT_JWKS_URL=... \
    FLUID_MCP_JWT_CLAIM_MAPPING=<claim>=principal \
      fluid mcp output-port serve <contract> --transport http
```

Over HTTP with JWT auth and no claim mapped to `principal`, the message reads `... and no JWT claim is mapped to the principal, so every call would be refused.` in place of the stdio reason.

#### What a row filter does not cover

- **The gateway's account reads the table.** A row filter limits what a caller reads through the gateway. The gateway reads the table with its own database role or cloud account, so keep that role narrow: see [The gateway's database role](#the-database-role-of-the-gateway).
- **The error side channel is closed by two layers.** On Postgres the filtered projection is a step of its own, and on every engine a caller that a filter narrows writes only the typed conditions above. *On forge-cli `main`, not yet in a release ([forge-cli #1109](https://github.com/Agenticstiger/forge-cli/pull/1109)).* What is not checked is the outer select list, the arguments of aggregates in HAVING, and an aggregate's `FILTER (WHERE ...)`. An engine that evaluates them before the filter could still raise on a withheld row. This is unverified and engine-dependent, and Snowflake is the likely case. Trino and Athena's evaluation order is unverified too.
- **Timing remains.** How long a query runs can reflect rows that the filter withholds. The gateway does not hide it. The same holds for plan output, where an engine exposes it (an `EXPLAIN`-style channel).
- **On Postgres, table sizes stay visible**, through functions such as `pg_relation_size`.
- **The function list covers a narrowed caller only.** *On forge-cli `main`, not yet in a release ([forge-cli #1109](https://github.com/Agenticstiger/forge-cli/pull/1109)).* A caller that a filter narrows may call listed functions only. The deny-list of Postgres functions stays as a second layer on every expose, and a reader no filter narrows is limited by it alone. Some listed names have no built-in on every engine: `cardinality`, `strlen` and `age` have none on Snowflake or BigQuery, so an unqualified call there can resolve to a function the operator created where the gateway's role looks up names. A caller cannot create one.
- **The type rules refuse some comparisons an engine would run safely.** *On forge-cli `main`, not yet in a release ([forge-cli #1109](https://github.com/Agenticstiger/forge-cli/pull/1109)).* The 38-digit rule means a HUGEINT or a BIGNUMERIC meets no exact number, a Snowflake integer (`NUMBER(38,0)`) meets no fractional literal, and Postgres's unconstrained `numeric` meets no exact number. A float still meets all of them. On Postgres, an unconstrained `numeric` beyond a float's range (about 10^308) cannot be cast to one, and the `OFFSET 0` step keeps such a comparison off withheld rows.
- **A column's type can be up to five minutes old.** The table's types are kept for five minutes, so a column whose type changes is typed by its old type until the next read. On Athena, the catalog read uses `current_schema`, which has not been verified on a live engine; if it fails, narrowed callers are refused.
- **Direct warehouse access bypasses the gateway.** Anyone who connects to the warehouse with their own role is not filtered by it. `fluid apply` writes warehouse-side policy for that path; see [Cloud-IAM compilers](#cloud-iam-compilers-—-defending-the-bypass-path).

### The five engine drivers

Drivers are keyed on `(binding.platform, binding.format)` and built lazily, so `describe` works even when cloud credentials are missing. Out-of-tree drivers can register via `register_driver(("databricks", "delta_table"), DatabricksDriver)` from a private wheel — no core edits.

| Driver | Binds on | Notes |
| --- | --- | --- |
| **DuckDB** | `local` / `{csv, parquet, json, other}` | Reference driver — no credentials. Opens the file read-only (or `:memory:`), auto-creates a view over `read_csv_auto` / `read_parquet` / `read_json_auto`. The same engine the `local` provider uses, so a locally-developed contract serves over MCP unchanged. Since 0.18.0 the connection runs in the [DuckDB sandbox](./duckdb-sandbox.md#what-each-kind-of-sql-can-reach) and can read only the bound file; two DuckDB drivers bound to the same `.duckdb` file in one process conflict. |
| **BigQuery** | `gcp` / `bigquery_table` | `@p_<index>` parameters; honours `--query-timeout-seconds`. |
| **Snowflake** | `snowflake` / `snowflake_table` | `%(p_<index>)s` (DB-API `pyformat`) parameters; honours `--query-timeout-seconds`. |
| **PostgreSQL** | `postgres` / `{postgres_table, table}` | psycopg v3; *On forge-cli `main`, not yet in a release ([forge-cli #1107](https://github.com/Agenticstiger/forge-cli/pull/1107)).* each request runs in a read-only transaction of its own that is rolled back at the end; per-request timeout via `SET LOCAL statement_timeout`; `%(p_<index>)s` parameter rewrite. |
| **AWS Athena** | `aws` / `{athena_table, glue_table}` | boto3 default credential chain (env / `~/.aws/credentials` / IAM role / OIDC) — no long-lived keys baked in. `StartQueryExecution` → poll `GetQueryExecution` → page `GetQueryResults`; parameterised via `ExecutionParameters`; optional `workgroup` from the binding or `ATHENA_WORKGROUP`. |

The query compiler emits portable `:p_<index>` placeholders and each driver re-renders them to its dialect; every interpolated identifier passes through `_sql_safety.validate_ident`, and the rendered statement is swept for injection markers (`;`, `--`, `/*`, `*/`) and banned keywords (`UNION`, `DROP`, …) as defence-in-depth.

### The database role of the gateway

*On forge-cli `main`, not yet in a release ([forge-cli #1107](https://github.com/Agenticstiger/forge-cli/pull/1107)).*

The gateway reads the table as one database role or cloud account, whoever calls it. A row filter limits what a caller is shown; it does not limit what the gateway's own account can read. Give that account the least it needs, so that a statement a guard missed reaches no more than the exposed table.

**PostgreSQL.** The driver connects with `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_PASSWORD` and optionally `POSTGRES_SSLMODE`. *On forge-cli `main`, not yet in a release ([forge-cli #1109](https://github.com/Agenticstiger/forge-cli/pull/1109)).* At connect, the driver checks whether the role is privileged: a superuser, or a member, directly or through another role, of `pg_read_server_files`, `pg_write_server_files`, `pg_execute_server_program`, `pg_monitor`, `pg_read_all_data`, `pg_read_all_settings` or `pg_read_all_stats`. If it is, every read of an expose with row filters is refused with that reason, and any other expose logs a warning. A connection is kept only once its check has passed, so a check that failed runs again on the next request. Nothing else about the role is checked. Set it up as follows:

- It is not a superuser, and holds none of the predefined roles above, which read beyond the granted tables, run programs or read server files.
- Any extension that adds functions (`pageinspect`, `dblink` and others) is installed in a schema the role cannot use.
- It owns nothing and creates nothing: no `CREATE` on any schema, and no `pageinspect`, `dblink` or other extension function granted to it.
- It holds `SELECT` on the exposed tables and `USAGE` on their schema, and nothing else.
- Its `search_path` is fixed on the role, so a table name written without a schema always means the exposed table's schema, whatever a session sets. The schema holds no function that the operator created under the name of a listed function, because an unqualified call would resolve to it.
- `default_transaction_read_only` is on for the role. The gateway already runs each request in a read-only transaction; the setting is a second layer that does not depend on it.
- `EXECUTE` is revoked from `PUBLIC` on the dangerous built-in functions, such as those listed under [Postgres functions that read past the projection](#postgres-functions-that-read-past-the-projection).

```sql
CREATE ROLE fluid_gateway LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
ALTER ROLE fluid_gateway SET search_path = analytics;
ALTER ROLE fluid_gateway SET default_transaction_read_only = on;
GRANT USAGE ON SCHEMA analytics TO fluid_gateway;
GRANT SELECT ON analytics.customers TO fluid_gateway;
```

Set its password outside this script. The role name, schema and table are examples.

**BigQuery.** The gateway queries as its own account, the one the Google Cloud client library resolves from `GOOGLE_APPLICATION_CREDENTIALS` or the application default credentials. BigQuery shows an account that no row access policy names no row at all. `fluid apply` writes a policy per row filter for the principals the filters name, and one more, `fluid_all_rows` with the predicate `TRUE`, for every other member with an `accessPolicy` grant of any permission, write grants included, or listed in `policy.authz.readers`. The gateway's account must be one of those members, or its queries return no rows. Grant it a read permission in `accessPolicy`, so the service account resolves to a grant on the expose, and name it in no row filter, because a filter narrows every identity it names. Without the grant, BigQuery returns the gateway no rows once `fluid apply` writes the row access policies. The gateway's own per-caller filter then applies on top of the every-row policy. See [Row filters](../providers/gcp.md#row-filters) on GCP.

```yaml
# top level of the contract, beside exposes:
accessPolicy:
  grants:
    - principal: "serviceAccount:fluid-gateway@my-project-id.iam.gserviceaccount.com"
      permissions: [read, select, query]
```

### Cloud-IAM compilers — defending the bypass path

The gateway only governs traffic *through* it. An analyst querying the warehouse directly with their own role is a bypass, and the warehouse's own policy closes that gap. *On forge-cli `main`, not yet in a release ([forge-cli #1109](https://github.com/Agenticstiger/forge-cli/pull/1109)).* The Python module `fluid_build.output_ports.iam_compiler` is removed. Nothing called it, and it compiled row filters from the old `policy.rowFilters` key, which no contract schema allows and the gateway refuses. For a contract that declares `policy.authz.rowFilters`, `fluid apply` writes the filters into the warehouse:

| Target | What `fluid apply` writes from `policy.authz.rowFilters` |
| --- | --- |
| **BigQuery** | A row access policy per filter, and `fluid_all_rows` for the other members with a grant. See [Row filters](../providers/gcp.md#row-filters) on GCP. |
| **AWS Lake Formation** | A data cells filter. |
| **Databricks Unity Catalog** | A row filter. |
| **Snowflake, PostgreSQL** | Nothing. The Snowflake provider reads no row filters. |

`fluid generate iac` and `fluid apply` refuse a row filter that the platform's engine would read differently. See [Row-level security](#row-level-security-—-policy-authz-rowfilters).

### Resilience — rate limit, circuit breaker, backpressure

All three are in-process (single-replica) and tunable by environment variable. Set the limit to `0` to disable.

| Control | Env var(s) | Default | Behaviour |
| --- | --- | --- | --- |
| **Rate limit** | `FLUID_MCP_RATE_LIMIT`, `FLUID_MCP_RATE_WINDOW_SECONDS` | 60 calls / 60s | Sliding-window monotonic-clock deque (no background thread, no dependency). Over the cap ⇒ `RateLimitExceeded`. |
| **Backpressure** | `FLUID_MCP_MAX_CONCURRENCY` | 8 | `asyncio.Semaphore` bounds concurrent dispatches. The gateway tracks `_in_flight` (queued + running, for graceful drain) separately from `_actively_dispatching` (running, for connection-pool sizing). |
| **Circuit breaker** | `FLUID_MCP_CIRCUIT_THRESHOLD`, `FLUID_MCP_CIRCUIT_WINDOW_SECONDS`, `FLUID_MCP_CIRCUIT_COOLDOWN_SECONDS` | 5 failures / 60s window, 30s cooldown | Trips after `threshold` driver failures inside `window`; open for `cooldown` (implicit half-open — the first call after cooldown is allowed). Returns `CircuitOpen` fast instead of pinning event-loop slots on a downstream outage. A successful call partially heals the breaker. |

On graceful shutdown (SIGTERM / SIGINT) the gateway drains in-flight calls (up to 5s) before tearing down driver connections.

### Audit trail, rotation, and the webhook forwarder

Every gateway decision writes a `data_access` audit event to `~/.fluid/store/audit/` (override the root with `FLUID_AUDIT_ROOT`). Writes are atomic (stage-to-temp then rename) and use a microsecond + pid + process-tag + monotonic-counter suffix so concurrent decisions — even across a gateway fleet sharing a network volume — never overwrite each other. The local-disk copy is always the **source of truth**.

The record is written for every decision, whether or not `agentPolicy.auditRequired` is set; `auditRequired` only makes the gateway announce the audit location at startup. This is a real `allow` record (the file is `<timestamp>_<suffix>_data_access.json`):

```json
{
  "event": "data_access",
  "payload": {
    "argumentSummary": { "limit": 5 },
    "callerJurisdiction": null,
    "contractPath": "/work/customers/contract.fluid.yaml",
    "decision": "allow",
    "exposeId": "customer_segments",
    "modelId": "claude-haiku-4-5-20251001",
    "policyDigest": "jcs-sha256:1cbcc442095182120ff06255dcded1185fc5f824a8cfc195ddeef807b8b2c6e3",
    "policySource": "contract",
    "reason": null,
    "runId": "e230144051ba",
    "tool": "sample",
    "useCase": "analysis"
  },
  "timestamp_utc": "2026-10-05T01:08:05.577382+00:00"
}
```

A denial by the policy gate has the same keys, with `decision: "deny"` and a `reason`. A denial by the rate limit, the circuit breaker or the token budget carries a shorter set (`tool`, `exposeId`, `modelId`, `useCase`, `decision`, `reason`, `policySource`, `argumentSummary`, `runId`): no `contractPath`, `callerJurisdiction` or `policyDigest`, and a `policySource` of `rate-limit`, `circuit-breaker` or `token-budget`.

**Rotation** runs automatically at gateway startup, bounded by two independent knobs:

| Env var | Default | Effect |
| --- | --- | --- |
| `FLUID_AUDIT_MAX_AGE_DAYS` | 30 | Files older than this are removed. |
| `FLUID_AUDIT_MAX_TOTAL_MB` | 256 | If the directory still exceeds budget, the **oldest** files are dropped until it fits. |

**Webhook forwarding** mirrors every event to a central SIEM aggregator (Splunk HEC, Datadog, Elastic, Loki) for multi-replica HA. It is best-effort and fire-and-forget on a daemon thread — webhook failures **never** block the local write.

| Env var | Effect |
| --- | --- |
| `FLUID_MCP_AUDIT_WEBHOOK_URL` | POST each audit document here as JSON. |
| `FLUID_MCP_AUDIT_WEBHOOK_HEADER_AUTH` | Optional `Authorization` header value (shared bearer). |
| `FLUID_MCP_AUDIT_WEBHOOK_TIMEOUT_SECONDS` | Per-POST timeout (default 5.0). |

When `FLUID_STORE_BACKEND` points at a non-file backend (Postgres / Sqlite / Vector), each event is also written through the Store under the `audit` namespace — again without losing the on-disk fallback. *(since 0.31.0, [forge-cli #881](https://github.com/Agenticstiger/forge-cli/pull/881))* The Postgres and Vector backends are removed: `FLUID_STORE_BACKEND=postgres` or `vector` logs a warning and uses the file store. Sqlite stays.

Audit events are auto-correlated with the rest of the forge-cli pipeline: the gateway resolves the same cross-stage `run_id` (`FLUID_RUN_ID`) other CLI stages honour and stamps it onto both the audit payload and an OpenTelemetry span (`fluid.mcp.call_tool`) when an exporter is configured.

### HTTP transport and the reverse-proxy templates

*(since 0.31.0, [forge-cli #879](https://github.com/Agenticstiger/forge-cli/pull/879))* `--transport http` serves the gateway over MCP Streamable HTTP, and clients connect at `http://host:port/mcp`. It runs on the MCP SDK's `StreamableHTTPSessionManager`, with Starlette and uvicorn from the `mcp` extra, and `fluid mcp serve --transport http` uses the same transport. Up to 0.30.1 the gateway served MCP-SSE (`mcp.server.sse.SseServerTransport`), and clients connected at `http://host:port/sse`. The status codes a refused request gets, and the binds the server refuses, are in [The HTTP transport](../cli/mcp.md#the-http-transport).

With no auth mode enforced, identity binding is the same as over stdio: the client declares it. With one enforced, only verified attributes bind, as described under [Authentication modes](#authentication-modes).

The HTTP transport has **no built-in TLS or strong identity on its own.** Front it with a reverse proxy. The repo ships ready-to-edit templates at `examples/mcp-output-port-docker/proxy/`:

- **`Caddyfile`**: Caddy 2.x, with automatic TLS, `client_auth { mode require_and_verify }` mTLS, a proxy-layer bearer-token check, `flush_interval -1` so streamed MCP responses (SSE) are not buffered, and `header_up X-Client-CN {tls_client_subject}` / `X-Client-Fingerprint {tls_client_fingerprint}`, which forward the certificate's subject and fingerprint as the headers described under [Authentication modes](#authentication-modes).
- **`nginx.conf`**: the equivalent for nginx shops, with `ssl_verify_client on`, `proxy_buffering off` and long read/send timeouts for streamed responses, and the same `X-Client-CN` / `X-Client-Fingerprint` forwarding.

*(since 0.31.0, [forge-cli #879](https://github.com/Agenticstiger/forge-cli/pull/879))* Behind either template, keep `FLUID_MCP_AUTH_TOKEN` (or `jwt`) set on the gateway too. Without auth the gateway accepts only a loopback `Host` header, and both templates forward the public name, so every request would get `421 Invalid Host header`.

This is **defence-in-depth** — every layer stops a different failure:

| Layer | Stops | Where it lives |
| --- | --- | --- |
| mTLS client cert | Random network attackers (no valid cert) | Proxy |
| Bearer token (`FLUID_MCP_AUTH_TOKEN`) | A leaked client cert (attacker also needs the secret) | Proxy **and** gateway |
| `agentPolicy.allowedModels` / `allowedUseCases` | A legitimate client running an unapproved model / use case | Gateway (per-`tools/call`) |
| `policy.authz.rowFilters[]` | A legitimate client bound to a different tenant | *On forge-cli `main`, not yet in a release ([forge-cli #1107](https://github.com/Agenticstiger/forge-cli/pull/1107)).* Gateway (per-row `WHERE`, by the principal of a verified JWT claim) |
| Cloud row-access policy (`fluid apply`) | Bypass-the-gateway direct warehouse reads | Cloud (warehouse-side) |

The `agentPolicy` row and the row-filter row tell a legitimate client from another one only when the caller's identity is verified, which is `FLUID_MCP_AUTH_MODE=jwt`. Behind the shared token the gateway drops what the client declares about itself, and a client certificate supplies none of those attributes; see [Authentication modes](#authentication-modes).

### Environment variables (output port)

*(since 0.31.0, [forge-cli #879](https://github.com/Agenticstiger/forge-cli/pull/879))* `fluid mcp serve --transport http` reads the `FLUID_MCP_AUTH_*` and `FLUID_MCP_JWT_*` rows too.

| Env var | Purpose |
| --- | --- |
| `FLUID_QUIET=1` | Keep stdout for JSON-RPC frames (route notices to stderr). |
| `FLUID_MCP_AUTH_MODE` | `shared-token` (default) / `jwt` / `none`. |
| `FLUID_MCP_AUTH_TOKEN` | Shared bearer token (shared-token mode + HTTP 401 gate). |
| `FLUID_MCP_JWT_ISSUER` / `_AUDIENCE` / `_JWKS_URL` | JWT issuer, audience, and JWKS endpoint. |
| `FLUID_MCP_JWT_ALGORITHMS` | Override the accepted algorithms (default `RS256,ES256,EdDSA`). |
| `FLUID_MCP_JWT_CLAIM_MAPPING` | `claim=attr` comma list mapping JWT claims into `caller_attributes`. *(since 0.15.0)* Merges over the [default mappings](#authentication-modes) (`sub`, `model`, `use_case`, `tenant_id`, `jurisdiction`) rather than replacing them. *On forge-cli `main`, not yet in a release ([forge-cli #1107](https://github.com/Agenticstiger/forge-cli/pull/1107)).* No claim maps to `principal` by default; an expose with `policy.authz.rowFilters` needs `<claim>=principal`. |
| `FLUID_MCP_RATE_LIMIT` / `FLUID_MCP_RATE_WINDOW_SECONDS` | Sliding-window rate limit (default 60 / 60s; `0` disables). |
| `FLUID_MCP_MAX_CONCURRENCY` | Concurrent-dispatch cap (default 8; `0` disables). |
| `FLUID_MCP_CIRCUIT_THRESHOLD` / `_WINDOW_SECONDS` / `_COOLDOWN_SECONDS` | Circuit breaker (defaults 5 / 60 / 30). |
| `FLUID_AUDIT_ROOT` | Redirect the audit directory (e.g. a SIEM-forwarded path). |
| `FLUID_AUDIT_MAX_AGE_DAYS` / `FLUID_AUDIT_MAX_TOTAL_MB` | Audit rotation bounds (defaults 30 / 256). |
| `FLUID_MCP_AUDIT_WEBHOOK_URL` / `_HEADER_AUTH` / `_TIMEOUT_SECONDS` | Audit webhook forwarder. |
| `FLUID_STORE_BACKEND` | When non-file, mirror audit events through the Store `audit` namespace. *(since 0.31.0, [forge-cli #881](https://github.com/Agenticstiger/forge-cli/pull/881))* `postgres` and `vector` are removed and fall back to the file store. |
| `FLUID_RUN_ID` | Cross-stage correlation id stamped onto audit events + OTel spans. |
| `ATHENA_WORKGROUP` | Default Athena workgroup when the binding doesn't set one. |

---

## Related guides

- [`fluid mcp` CLI reference](../cli/mcp.md) — every flag, copy-paste examples, the four agent tools.
- [Walkthrough: MCP output port](../walkthrough/mcp-output-port.md) — serve the example DuckDB product end-to-end; watch PII masking and an agentPolicy deny.
- [Governance](./governance.md) — contract-level policy authoring, including sovereignty.
- [Environment variables](./environment-variables.md) — the full forge-cli env-var index.
