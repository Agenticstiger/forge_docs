# MCP Server

Fluid Forge ships **two** Model Context Protocol servers under `fluid mcp`:

- **`fluid mcp serve`** — the **producer / authoring** server. Exposes the staged forge pipeline as stdio MCP tools so an editor's AI can inspect, validate, and edit contracts.
- **`fluid mcp output-port serve`** — the **consumer / data-access** server (the flagship output-port capability). Binds one expose of a published contract and serves a small, governed, read-only surface to AI agents.

The first half of this page covers the authoring server. The second half is a deep dive on the output port's runtime governance — the part that takes reading several files to learn.

---

## Authoring server — `fluid mcp serve`

`fluid mcp serve` exposes the staged forge pipeline as a stdio MCP server for clients such as Claude Code, Cursor, Continue, and VS Code MCP integrations. It is a foreground process: no daemon, no HTTP port, and no background service. The server is built on the official MCP Python SDK (`FastMCP`) and speaks MCP protocol version `2025-06-18`.

### Start the server

```bash
fluid mcp serve --read-only     # inspection only
fluid mcp serve                 # full surface, scoped to the working directory
```

Every `tools/call` is checked by policy before it runs. The flags that scope it (`--read-only`, `--allow-tools`, `--deny-tools`, `--readable-paths`, `--writable-paths`, `--writable-namespaces`, `--allow-inline-credentials`) are documented once, in the [`fluid mcp` CLI reference](../cli/mcp.md#access-controls). This page covers what the tools do and how the output port enforces governance.

### Authoring tools

The authoring server advertises these tools. With `--read-only`, the tools marked *write* are not advertised:

| Tool | Mode | What it does |
| --- | --- | --- |
| `read_logical_model` | read | Load a `.model.json` sidecar and return the typed logical model |
| `validate_contract` | read | Validate a Fluid contract or forged model sidecar |
| `diff_models` | read | Compare two logical model sidecars |
| `search_semantic_memory` | read | Search the semantic memory namespace for similar prior models |
| `score_contract_quality` | read | Score a contract against the forge quality rubric |
| `enrich_contract_suggestions` | read | Suggest contract enrichments (descriptions, semantics, policy) |
| `update_entity` | write | Rename or update one logical model entity |
| `add_relationship` | write | Add a relationship to a logical sidecar |
| `regenerate_physical` | write | Regenerate the contract and physical fanout from a logical sidecar |
| `list_source_adapters` | read | List available source-catalog adapters |
| `list_source_tables` | read | Enumerate tables from a configured source catalog |
| `inspect_source_table` | read | Inspect a source table profile and metadata |
| `list_source_lineage` | read | Read lineage from a configured source catalog |
| `list_source_glossary` | read | Read glossary terms from a configured source catalog |
| `forge_from_source` | write | Forge a contract and `.model.json` sidecar from a configured source catalog |
| `forge_run` | write | Run a full `fluid forge` in-process — `mode` is `blank`, `diag`, or `ai` |

Every advertised tool includes an MCP `inputSchema`, so clients can provide typed autocomplete and validate arguments before dispatch.

#### Fragment-first contracts

A contract split into fragments keeps `$ref` stubs in its root file (see [Composing a contract with `$ref`](../concepts/contract-refs.md)). `fluid validate`, `fluid plan` and `fluid mcp output-port serve` resolve those references. As of 0.18.1, the authoring tools that take a `contract_path` read the file as written and do not resolve `$ref` stubs. `validate_contract` takes `contract_path` (or `logical_path`) and no inline contract; `score_contract_quality` and `enrich_contract_suggestions` accept either `contract_path` or an inline `contract` object.

On a root that holds `$ref` stubs, `validate_contract` reports errors that `fluid validate` does not:

```text
{"score": 0, "passes_schema": false, "issues": [
  {"message": "builds[0]: Additional properties are not allowed ('$ref' was unexpected)", ...},
  {"message": "exposes[0]: 'exposeId' is a required property", ...}, ...]}
```

`fluid validate` on the same file prints `✅ Valid FLUID contract (schema v0.7.5)`. Resolve the references first and point the tool at the result:

```bash
fluid bundle contract.fluid.yaml --out runtime/contract.bundled.yaml
```

With `contract_path: runtime/contract.bundled.yaml`, the same call returns `passes_schema: false` only for the findings the contract really has. An editor agent driving `fluid mcp serve` on a project that [`fluid forge`](../cli/forge.md) split into fragments needs this step, or it scores `$ref` stubs and not the contract.

### LLM sampling

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

Nothing about the gateway's governance is configured on the command line by default — it is read from the bound expose. The CLI flags (`--allow-models`, `--max-sample-rows`, …) are *operational overrides* for incident response; the contract is the source of truth, and the audit trail records which one won via a `policySource` field (`contract`, `cli`, or `default`).

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

Per-tenant row filters are also read from `policy.rowFilters`, with a caveat about schema validation: see [Row-level security](#row-level-security-—-policy-rowfilters).

### Per-`tools/call` enforcement order

Every `tools/call` runs through a fixed gauntlet. The order is deliberate: cheap, abuse-resistant gates fire first so a runaway agent can't burn audit storage hammering denied tools.

1. **Identity binding.** The caller's `model`, `useCase` and any extra attributes are read from the MCP `initialize` handshake, from the `fluid` block of the client's `capabilities.experimental` (and, on MCP SDK 1.x, from extra `clientInfo` fields), and resolved again on every tool call from that request's own context, never cached on the shared session (on HTTP/SSE one process serves many clients, so a cached identity would carry one client's `agentPolicy` principal and tenant row filter onto the next). Missing identity is treated as `missing-model-identity` (fail-closed at the model gate).
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

Any other key in that block becomes a caller attribute, which is what `${caller.<attr>}` row filters resolve against. Whenever a model or use-case gate is active, the gateway prints this notice at startup:

```text
⚠️  fluid mcp output-port: caller model_id is self-attested via MCP clientInfo. Do not expose this gateway over an untrusted network until P3 (OAuth/mTLS identity) ships. See https://agenticstiger.github.io/forge_docs/concepts/agent-policy.html
```

The notice is printed whatever the transport and auth mode. Its "until P3 ships" wording predates the JWT mode: over **HTTP** with `FLUID_MCP_AUTH_MODE=jwt`, identity is cryptographically bound, because the verified JWT claims then *replace* self-attestation for the model and use-case gates, `rowFilters` resolution and the [caller-jurisdiction gate](#caller-jurisdiction-enforcement-since-0-15-0). A client certificate checked by a proxy does not bind identity; see [mTLS authenticates the connection](#authentication-modes) under Authentication modes.
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

**Verified claims only, and fail-closed.** The claim is admissible only from `request.scope["fluid_auth_attrs"]`, which the HTTP `_AuthMiddleware` writes *after* a credential validates — never from the caller's self-attested `clientInfo`. In practice that means the `jurisdiction` claim of a verified JWT: a shared token and a proxy-forwarded client certificate carry no jurisdiction. A client typing `jurisdiction: "EU"` into its own handshake satisfies nothing and collapses to the same `missing-caller-jurisdiction` denial as no claim at all. There is no no-auth fallback, on purpose. Matching is **exact and case-sensitive**: a verified `"eu"` against a contract pinning `"EU"` is refused.

::: warning Startup refusal, new in `0.15.0`
A jurisdiction-pinned contract **refuses to serve and exits 2** on the two deployments that could never satisfy the rule, rather than denying every call one at a time:

- `--transport stdio` — the **default**, and a pipe carries no headers, so the middleware never runs.
- `--transport http` with `FLUID_MCP_AUTH_MODE` unset, `none`, `off` or `disabled` — the middleware short-circuits before stamping anything.

Both messages name the contract's jurisdiction and give the command that fixes it: serve over HTTP with `FLUID_MCP_AUTH_MODE=jwt` (plus `FLUID_MCP_JWT_ISSUER` / `_AUDIENCE` / `_JWKS_URL`), or set `sovereignty.crossBorderTransfer: true` if the data may leave. The most common desktop-client setup — stdio — is therefore the one configuration such a contract cannot serve.

The startup check looks only at whether an auth mode is configured. `FLUID_MCP_AUTH_MODE=shared-token` passes it, and a shared token carries no jurisdiction, so such a contract then denies every call as `missing-caller-jurisdiction`. Only `jwt` can supply the claim.
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

::: warning Startup refusal for a jurisdiction-pinned contract, new in `0.15.0`
The two rows above no longer hold for a contract that pins `sovereignty.jurisdiction` without `crossBorderTransfer: true`. Because the caller-jurisdiction gate admits only claims the auth middleware verified, an unauthenticated gateway would deny **every** call — so `fluid mcp output-port serve` writes a refusal to stderr and **returns exit code 2** before binding, for `--transport stdio` (any auth mode: a pipe carries no headers) and for `--transport http` with `FLUID_MCP_AUTH_MODE` unset, `none`, `off` or `disabled`. See [Caller-jurisdiction enforcement](#caller-jurisdiction-enforcement-since-0-15-0).
:::

Only a verified JWT binds identity. With `shared-token`, the gateway knows that the caller held the shared secret and nothing else: once the token is enforced, any `model`, `useCase` or tenant attribute the client declares for itself is dropped. A contract with an `allowedModels` or `deniedModels` gate then denies every call as `missing-model-identity`, and one with `allowedUseCases` as `missing-use-case-with-allowlist`. Use `jwt` when the gates must see who is calling.

::: warning mTLS authenticates the connection; it does not bind identity
`FLUID_MCP_AUTH_MODE` accepts only `shared-token`, `jwt` and `none`. With `FLUID_MCP_AUTH_MODE=mtls`, `fluid mcp output-port serve --transport http` exits 1 with a traceback that ends `ValueError: unknown FLUID_MCP_AUTH_MODE='mtls'; expected one of shared-token / jwt / none`.

A proxy in front of the gateway can require client certificates, which keeps hosts without one off the network path. The gateway never sees the certificate. It sees two request headers the proxy sets, `X-Client-CN` and `X-Client-Fingerprint`, and what it does with them is narrow:

- It reads them only when an auth mode is enforced: `jwt` with its three settings, or `shared-token` with `FLUID_MCP_AUTH_TOKEN` set. With `none`, or with neither configured, the middleware passes the request on without looking.
- It copies them, unverified, into the request's caller attributes as `client_cn` and `client_fingerprint`. A `${caller.client_cn}` placeholder resolves from the header, so the gateway must be reachable only through the proxy, and the proxy must overwrite any copy of those headers the client sends.
- They never supply `model`, `use_case`, `tenant_id` or `jurisdiction`. Those come from the mapped claims of a verified JWT, or from the client's own declaration when no auth mode is enforced.
- In 0.18.1 neither header is written to a `data_access` audit record.

Without an auth mode, the gateway is unauthenticated whatever the proxy does: a caller picks its own model, use case and `tenant_id`, so a `${caller.tenant_id}` row filter filters on a value the caller chose.
:::

`FLUID_MCP_JWT_CLAIM_MAPPING` is a comma-separated `claim=attr` list, e.g. `sub=principal,https://fluid/model=model,https://fluid/tenant=tenant_id`. Mapped claims land in `caller_attributes`, which is exactly what `rowFilters` `${caller.<attr>}` placeholders resolve against — so on the JWT path, per-tenant filters resolve **cryptographically** rather than from self-attested `clientInfo`.

*(since 0.15.0)* The value **merges over** the default mappings instead of replacing them. Those defaults are:

| Claim | `caller_attributes` key | Why it is load-bearing |
| --- | --- | --- |
| `sub` | `sub` | Interpolated by `${caller.sub}` row filters. |
| `model` | `model` | Input to the `agentPolicy` model gate. |
| `use_case` | `use_case` | Input to the `agentPolicy` use-case gate. |
| `tenant_id` | `tenant_id` | Interpolated by `${caller.tenant_id}` row filters. |
| `jurisdiction` | `jurisdiction` | *(since 0.15.0)* The verified claim the [caller-jurisdiction gate](#caller-jurisdiction-enforcement-since-0-15-0) reads. |

::: warning Behavior change in 0.15.0
On `0.14.1` and earlier the parsed value was assigned **wholesale**, so mapping one extra claim silently dropped all four defaults — turning off the `agentPolicy` model and use-case gates and emptying every `${caller.*}` row filter, with no error and a server still reporting healthy. Mapping a default away explicitly still works; what no longer happens is losing one by accident while adding something unrelated.

Note the asymmetry for the newest default: losing `sub` / `model` / `use_case` / `tenant_id` **widens** access, while losing `jurisdiction` **closes** the gate completely — an operator who remaps their IdP's jurisdiction claim to some other attribute name locks themselves out of a jurisdiction-pinned contract rather than letting strangers in. That is the correct direction for a sovereignty control, and this mapping is where to look when it happens.
:::

::: warning
There is no `--auth-token` CLI flag. Auth is configured entirely through `FLUID_MCP_*` environment variables, so the same contract can be served at different trust levels without editing it.
:::

### PII / PHI value redaction

Columns marked `sensitivity: pii` or `sensitivity: phi` in `expose.contract.schema` keep their **key** visible (the agent still sees the field exists and can write `COUNT(DISTINCT …)` aggregates) but their **values** are replaced with the constant `[REDACTED-PII]` before the row leaves the gateway.

This happens at the **driver boundary** — `EngineDriver.project()` masks every row from `sample`, `query`, and `query_sql` alike. It is distinct from `columnRestrictions`, which drops a column *wholesale*:

| Layer | Source | Effect |
| --- | --- | --- |
| **PII redaction** | `contract.schema[].sensitivity` ∈ `{pii, phi}` | Column stays in the schema; values become `[REDACTED-PII]`. |
| **Column restriction** | `policy.authz.columnRestrictions` (`access: deny`) or `policy.privacy.masking` | Column is removed entirely from the projection. |

Both are **alias-proof on the free-form path.** Masking matches by output column *name*, so `SELECT email AS x` would otherwise sneak a PII value past it. The `query_sql` compiler closes that hole by rejecting any reference to a restricted *or* PII column at compile time (string literals are stripped first, so `WHERE label = 'email'` doesn't false-positive). The agent cannot alias the column away.

### Row-level security — `policy.rowFilters`

For per-tenant isolation, the gateway reads `policy.rowFilters[]` from the expose. Each filter compiles to a parameterised `WHERE` clause appended to `sample` / `query` reads, bound to the caller's identity:

```yaml
policy:
  rowFilters:
    - { column: tenant_id, equals: "${caller.tenant_id}" }
    - { column: region,    in:     "${caller.regions}" }
```

::: warning `rowFilters` is not in any schema version
As of 0.18.1, no bundled contract schema (`0.7.1` through `0.7.6`) declares `rowFilters`: `exposePolicy` accepts `authn`, `authz`, `privacy`, `classification`, `agentPolicy`, `tags` and `labels` and nothing else. A contract that declares it fails `fluid validate`, and so `fluid plan` and `fluid apply`, at every `fluidVersion`:

```text
 1. exposes[0].policy: Additional properties are not allowed ('rowFilters' was
unexpected)
```

The output-port gateway loads the contract without schema validation, so the filter works there. Serving the contract above with a caller that declares `tenant_id: t1` returns only that tenant's rows, with the PII column redacted:

```json
{"rows": [{"customer_id": 1, "email": "[REDACTED-PII]", "segment": "gold", "tenant_id": "t1"}], "rowCount": 1}
```

So a contract that uses `rowFilters` can be served but cannot go through the validate, plan and apply path. Until the schema accepts it, use the cloud-native row policies from the [IAM compilers](#cloud-iam-compilers-—-defending-the-bypass-path) for warehouse-side enforcement on a contract you apply. The [MCP output port walkthrough](../walkthrough/mcp-output-port.md#policy-rowfilters-is-read-by-the-gateway-and-rejected-by-fluid-validate) shows the same refusal from a worked example.
:::

`${caller.<attr>}` placeholders resolve from `caller_attributes`: the `fluid` block of the client's declared capabilities over stdio or over HTTP with no auth mode enforced, or the mapped claims of a verified JWT over HTTP with `FLUID_MCP_AUTH_MODE=jwt`. A client certificate checked by a proxy does not supply `tenant_id`; see [Authentication modes](#authentication-modes). The supported operators are `equals` (scalar) and `in` (non-empty list); values are always **bound as parameters**, never interpolated.

**Missing identity fails closed.** If a filter references `${caller.tenant_id}` and the caller never supplied it, the read raises `RowFilterIdentityMissing` and serves **no rows**. The gateway prefers no rows to wrong rows.

### The five engine drivers

Drivers are keyed on `(binding.platform, binding.format)` and built lazily, so `describe` works even when cloud credentials are missing. Out-of-tree drivers can register via `register_driver(("databricks", "delta_table"), DatabricksDriver)` from a private wheel — no core edits.

| Driver | Binds on | Notes |
| --- | --- | --- |
| **DuckDB** | `local` / `{csv, parquet, json, other}` | Reference driver — no credentials. Opens the file read-only (or `:memory:`), auto-creates a view over `read_csv_auto` / `read_parquet` / `read_json_auto`. The same engine the `local` provider uses, so a locally-developed contract serves over MCP unchanged. Since 0.18.0 the connection runs in the [DuckDB sandbox](./duckdb-sandbox.md#what-each-kind-of-sql-can-reach) and can read only the bound file; two DuckDB drivers bound to the same `.duckdb` file in one process conflict. |
| **BigQuery** | `gcp` / `bigquery_table` | `@p_<index>` parameters; honours `--query-timeout-seconds`. |
| **Snowflake** | `snowflake` / `snowflake_table` | `%(p_<index>)s` (DB-API `pyformat`) parameters; honours `--query-timeout-seconds`. |
| **PostgreSQL** | `postgres` / `{postgres_table, table}` | psycopg v3; **read-only session enforced at connect**; per-statement timeout via `SET LOCAL statement_timeout`; `%(p_<index>)s` parameter rewrite. |
| **AWS Athena** | `aws` / `{athena_table, glue_table}` | boto3 default credential chain (env / `~/.aws/credentials` / IAM role / OIDC) — no long-lived keys baked in. `StartQueryExecution` → poll `GetQueryExecution` → page `GetQueryResults`; parameterised via `ExecutionParameters`; optional `workgroup` from the binding or `ATHENA_WORKGROUP`. |

The query compiler emits portable `:p_<index>` placeholders and each driver re-renders them to its dialect; every interpolated identifier passes through `_sql_safety.validate_ident`, and the rendered statement is swept for injection markers (`;`, `--`, `/*`, `*/`) and banned keywords (`UNION`, `DROP`, …) as defence-in-depth.

### Cloud-IAM compilers — defending the bypass path

The gateway only governs traffic *through* it. An analyst querying the warehouse directly with their own role is a bypass. `fluid_build.output_ports.iam_compiler` closes that gap by compiling the same `agentPolicy` + `rowFilters` contract into **cloud-native** policy you apply warehouse-side:

| Target | Emits |
| --- | --- |
| **Snowflake** | `CREATE OR REPLACE ROW ACCESS POLICY … RETURNS BOOLEAN` + `ALTER TABLE … ADD ROW ACCESS POLICY`. `${caller.role}` → `CURRENT_ROLE()`, `${caller.user}` → `CURRENT_USER()`; `allowedModels` → `CURRENT_ROLE() IN ('FLUID_MODEL_<MODEL>', …)`. |
| **PostgreSQL** | `ALTER TABLE … ENABLE ROW LEVEL SECURITY` + `CREATE POLICY … FOR SELECT USING (…)`, mapping `${caller.user}` → `current_user`, `${caller.role}` → `current_role`. |
| **BigQuery** | `CREATE OR REPLACE ROW ACCESS POLICY … GRANT TO (…) FILTER USING (…)`, with `${caller.user}` → `SESSION_USER()` and `allowedModels` → `serviceAccount:fluid-mcp-<model>@<project>.iam.gserviceaccount.com` grantees. |
| **AWS Lake Formation** | A runnable **boto3 script** (Lake Formation has no SQL surface): `create_data_cells_filter` (row-level rule) + `grant_permissions` to per-LLM IAM roles `arn:aws:iam::<ACCOUNT>:role/fluid-mcp-<model>`. Paste into CDK/Terraform or run directly. |

Each `CompiledPolicy` carries a `warnings` list naming the `agentPolicy` fields the target can't enforce natively (e.g. a `${caller.tenant_id}` with no warehouse primitive), so operators know exactly which gap to plug with another control.

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

When `FLUID_STORE_BACKEND` points at a non-file backend (Postgres / Sqlite / Vector), each event is also written through the Store under the `audit` namespace — again without losing the on-disk fallback.

Audit events are auto-correlated with the rest of the forge-cli pipeline: the gateway resolves the same cross-stage `run_id` (`FLUID_RUN_ID`) other CLI stages honour and stamps it onto both the audit payload and an OpenTelemetry span (`fluid.mcp.call_tool`) when an exporter is configured.

### HTTP and SSE transport, and the reverse-proxy templates

`--transport http` serves the gateway over MCP-SSE (`mcp.server.sse.SseServerTransport` + Starlette + uvicorn, transitive deps of the `mcp` extra). Clients connect at `http://host:port/sse`. With no auth mode enforced, identity binding is the same as over stdio: the client declares it. With one enforced, only verified attributes bind, as described under [Authentication modes](#authentication-modes).

The HTTP transport has **no built-in TLS or strong identity on its own.** Front it with a reverse proxy. The repo ships ready-to-edit templates at `examples/mcp-output-port-docker/proxy/`:

- **`Caddyfile`** — Caddy 2.x: automatic TLS, `client_auth { mode require_and_verify }` mTLS, a proxy-layer bearer-token check, `flush_interval -1` for SSE, and `header_up X-Client-CN {tls_client_subject}` / `X-Client-Fingerprint {tls_client_fingerprint}`, which forward the certificate's subject and fingerprint as the headers described under [Authentication modes](#authentication-modes).
- **`nginx.conf`** — equivalent for nginx shops: `ssl_verify_client on`, `proxy_buffering off` + long read/send timeouts for SSE, and the same `X-Client-CN` / `X-Client-Fingerprint` forwarding.

This is **defence-in-depth** — every layer stops a different failure:

| Layer | Stops | Where it lives |
| --- | --- | --- |
| mTLS client cert | Random network attackers (no valid cert) | Proxy |
| Bearer token (`FLUID_MCP_AUTH_TOKEN`) | A leaked client cert (attacker also needs the secret) | Proxy **and** gateway |
| `agentPolicy.allowedModels` / `allowedUseCases` | A legitimate client running an unapproved model / use case | Gateway (per-`tools/call`) |
| `policy.rowFilters[]` | A legitimate client bound to a different tenant | Gateway (per-row `WHERE`) |
| Cloud row-access policy (IAM compiler) | Bypass-the-gateway direct warehouse reads | Cloud (warehouse-side) |

The model, use-case and tenant rows tell a legitimate client from another one only when the caller's identity is verified, which is `FLUID_MCP_AUTH_MODE=jwt`. Behind the shared token the gateway drops what the client declares about itself, and a client certificate supplies none of those attributes; see [Authentication modes](#authentication-modes).

### Environment variables (output port)

| Env var | Purpose |
| --- | --- |
| `FLUID_QUIET=1` | Keep stdout for JSON-RPC frames (route notices to stderr). |
| `FLUID_MCP_AUTH_MODE` | `shared-token` (default) / `jwt` / `none`. |
| `FLUID_MCP_AUTH_TOKEN` | Shared bearer token (shared-token mode + HTTP 401 gate). |
| `FLUID_MCP_JWT_ISSUER` / `_AUDIENCE` / `_JWKS_URL` | JWT issuer, audience, and JWKS endpoint. |
| `FLUID_MCP_JWT_ALGORITHMS` | Override the accepted algorithms (default `RS256,ES256,EdDSA`). |
| `FLUID_MCP_JWT_CLAIM_MAPPING` | `claim=attr` comma list mapping JWT claims into `caller_attributes`. *(since 0.15.0)* Merges over the [default mappings](#authentication-modes) (`sub`, `model`, `use_case`, `tenant_id`, `jurisdiction`) rather than replacing them. |
| `FLUID_MCP_RATE_LIMIT` / `FLUID_MCP_RATE_WINDOW_SECONDS` | Sliding-window rate limit (default 60 / 60s; `0` disables). |
| `FLUID_MCP_MAX_CONCURRENCY` | Concurrent-dispatch cap (default 8; `0` disables). |
| `FLUID_MCP_CIRCUIT_THRESHOLD` / `_WINDOW_SECONDS` / `_COOLDOWN_SECONDS` | Circuit breaker (defaults 5 / 60 / 30). |
| `FLUID_AUDIT_ROOT` | Redirect the audit directory (e.g. a SIEM-forwarded path). |
| `FLUID_AUDIT_MAX_AGE_DAYS` / `FLUID_AUDIT_MAX_TOTAL_MB` | Audit rotation bounds (defaults 30 / 256). |
| `FLUID_MCP_AUDIT_WEBHOOK_URL` / `_HEADER_AUTH` / `_TIMEOUT_SECONDS` | Audit webhook forwarder. |
| `FLUID_STORE_BACKEND` | When non-file, mirror audit events through the Store `audit` namespace. |
| `FLUID_RUN_ID` | Cross-stage correlation id stamped onto audit events + OTel spans. |
| `ATHENA_WORKGROUP` | Default Athena workgroup when the binding doesn't set one. |

---

## Related guides

- [`fluid mcp` CLI reference](../cli/mcp.md) — every flag, copy-paste examples, the four agent tools.
- [Walkthrough: MCP output port](../walkthrough/mcp-output-port.md) — serve the example DuckDB product end-to-end; watch PII masking and an agentPolicy deny.
- [Governance](./governance.md) — contract-level policy authoring, including sovereignty.
- [Environment variables](./environment-variables.md) — the full forge-cli env-var index.
