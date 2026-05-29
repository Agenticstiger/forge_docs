# MCP Server

Fluid Forge ships **two** Model Context Protocol servers under `fluid mcp`:

- **`fluid mcp serve`** — the **producer / authoring** server. Exposes the staged forge pipeline as stdio MCP tools so an editor's AI can inspect, validate, and edit contracts.
- **`fluid mcp output-port serve`** — the **consumer / data-access** server (the flagship 0.8.6 capability). Binds one expose of a published contract and serves a small, governed, read-only surface to AI agents.

The first half of this page covers the authoring server. The second half is a deep dive on the output port's runtime governance — the part that takes reading several files to learn.

---

## Authoring server — `fluid mcp serve`

`fluid mcp serve` exposes the staged forge pipeline as a stdio MCP server for clients such as Claude Code, Cursor, Continue, and VS Code MCP integrations. It is a foreground process: no daemon, no HTTP port, and no background service. The server is built on the official MCP Python SDK (`FastMCP`) and speaks MCP protocol version `2025-06-18`.

### Start the server

```bash
fluid mcp serve                 # full surface
fluid mcp serve --read-only     # read-only inspection
```

For scoped write access:

```bash
fluid mcp serve \
  --readable-paths ./forge-output \
  --writable-paths ./forge-output \
  --writable-namespaces history,audit
```

### Access controls

Every `tools/call` is checked by policy before it executes.

| Control | Flag | What it does |
| --- | --- | --- |
| Read-only mode | `--read-only` | Rejects every mutating tool |
| Read scope | `--readable-paths PATH[,PATH...]` | Path-based read tools may only inspect files below these roots |
| Tool allowlist | `--allow-tools TOOL[,TOOL...]` | Hides and blocks tools outside the allowlist |
| Tool blocklist | `--deny-tools TOOL[,TOOL...]` | Blocks named tools; denial wins over allow |
| Filesystem scope | `--writable-paths PATH[,PATH...]` | Mutating tools may only write below these roots |
| Store scope | `--writable-namespaces NS[,NS...]` | Mutating tools may only write listed store namespaces |
| Inline credentials | `--allow-inline-credentials` | Permit raw catalog credentials via `credentials.inline` (OFF by default) |

The default readable and writable path is the current working directory. The default writable namespaces are `history,audit`.

### Authoring tools

The authoring server advertises **16 typed tools**:

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
      rowFilters:                    # per-tenant row-level security
        - { column: tenant_id, equals: "${caller.tenant_id}" }
```

### Per-`tools/call` enforcement order

Every `tools/call` runs through a fixed gauntlet. The order is deliberate: cheap, abuse-resistant gates fire first so a runaway agent can't burn audit storage hammering denied tools.

1. **Identity binding.** The caller's `model_id`, `useCase`, and any extra `clientInfo` fields are read from the MCP `initialize` handshake and bound to the session on the first call. Missing identity is treated as `missing-model-identity` (fail-closed at the model gate).
2. **Rate limit.** A sliding-window deque caps calls per window (default 60 calls / 60s). Over the cap returns a `RateLimitExceeded` envelope.
3. **agentPolicy gate.** `OutputPortPolicy.check_tool_call` evaluates, first-deny-wins: tool denylist → tool allowlist → model denylist → use-case denylist → model allowlist → use-case allowlist. A deny returns an `AgentPolicyDenied` envelope.
4. **Circuit breaker.** If recent driver failures tripped the breaker, the call fast-fails with a `CircuitOpen` envelope instead of queueing behind another doomed connection.
5. **Token budget (pre-check).** `agentPolicy.maxTokensPerDay` is checked against a rolling 24-hour counter. Over budget returns `TokenBudgetExceeded`.
6. **Backpressure.** An `asyncio.Semaphore` bounds concurrent dispatches (default 8) so a runaway agent can't saturate the engine connection pool.
7. **Dispatch + post-checks.** The tool runs in an executor (driver SDKs are blocking). After it returns, `agentPolicy.maxTokensPerRequest` is checked against the actual response size, the daily counter is topped up, and the circuit breaker records success/failure.

**Every decision — allow and deny — is written to the audit trail**, tagged with the `policySource` that produced it (`rate-limit`, `circuit-breaker`, `token-budget`, `contract`, `cli`, …).

::: tip Self-attested vs. cryptographic identity
Over **stdio**, the caller's `model_id` / `useCase` come from `clientInfo` — self-attested, and a buggy or malicious client can lie. The gateway prints a loud startup warning whenever a model/use-case gate is active so operators don't mistake it for cryptographic identity. Over **HTTP**, configure JWT or mTLS (below) so identity is cryptographically bound; JWT claims and the mTLS cert subject then *override* self-attestation for downstream `rowFilter` resolution.
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
`fluid validate` warns when an expose opts into the gateway (carries an `mcp` block) but declares neither `allowedModels` nor `deniedModels` — without one, the runtime gate is open and the contract's intent to govern downstream LLM access is silently lost.
:::

### Authentication modes

Identity is resolved once at gateway start from `FLUID_MCP_AUTH_MODE`. There are three modes plus an explicit opt-out:

| Mode (`FLUID_MCP_AUTH_MODE`) | How it works | Config |
| --- | --- | --- |
| `shared-token` *(default)* | Symmetric bearer token compared with `hmac.compare_digest` (constant-time). One secret, every client uses the same value. | `FLUID_MCP_AUTH_TOKEN` |
| `jwt` | RFC 7519 bearer. Validates the signature against an issuer's **JWKS** endpoint (`RS256` / `ES256` / `EdDSA`), checks `iss` / `aud` / `exp` / `nbf`, and maps configured claims into `caller_attributes`. Works with Auth0, Okta, Keycloak, AWS Cognito, Google IAP, Azure AD. JWKS keys are cached in-process with a TTL. | `FLUID_MCP_JWT_ISSUER`, `FLUID_MCP_JWT_AUDIENCE`, `FLUID_MCP_JWT_JWKS_URL`, optional `FLUID_MCP_JWT_ALGORITHMS`, `FLUID_MCP_JWT_CLAIM_MAPPING` |
| `none` | Operator explicitly opts out. Every request is allowed; the audit trail records `identity_kind=none` so un-authed traffic is greppable. | — |
| *(unconfigured)* | If `shared-token` has no token, or JWT is missing issuer/audience/JWKS, the gateway runs **unauthenticated** and emits a loud startup warning. | — |

**mTLS** is handled by the reverse proxy in front of the gateway, not inside it. The proxy terminates the client cert and forwards `X-Client-CN` + `X-Client-Fingerprint`; the gateway reads those headers (`extract_mtls_identity`) and stamps the cert identity onto the audit event **alongside** the JWT claims, so a call carries both "which token" and "which cert."

`FLUID_MCP_JWT_CLAIM_MAPPING` is a comma-separated `claim=attr` list, e.g. `sub=principal,https://fluid/model=model,https://fluid/tenant=tenant_id`. Mapped claims land in `caller_attributes`, which is exactly what `rowFilters` `${caller.<attr>}` placeholders resolve against — so on the JWT path, per-tenant filters resolve **cryptographically** rather than from self-attested `clientInfo`.

::: warning
There is no `--auth-token` CLI flag. Auth is configured entirely through `FLUID_MCP_*` environment variables, so the same contract can be served at different trust levels without editing it.
:::

### PII / PHI value redaction

Columns marked `sensitivity: pii`, `sensitivity: phi`, or `sensitivity: sensitive` in `expose.contract.schema` keep their **key** visible (the agent still sees the field exists and can write `COUNT(DISTINCT …)` aggregates) but their **values** are replaced with the constant `[REDACTED-PII]` before the row leaves the gateway.

This happens at the **driver boundary** — `EngineDriver.project()` masks every row from `sample`, `query`, and `query_sql` alike. It is distinct from `columnRestrictions`, which drops a column *wholesale*:

| Layer | Source | Effect |
| --- | --- | --- |
| **PII redaction** | `contract.schema[].sensitivity` ∈ `{pii, phi, sensitive}` | Column stays in the schema; values become `[REDACTED-PII]`. |
| **Column restriction** | `policy.authz.columnRestrictions` (`access: deny`) or `policy.privacy.masking` | Column is removed entirely from the projection. |

Both are **alias-proof on the free-form path.** Masking matches by output column *name*, so `SELECT email AS x` would otherwise sneak a PII value past it. The `query_sql` compiler closes that hole by rejecting any reference to a restricted *or* PII column at compile time (string literals are stripped first, so `WHERE label = 'email'` doesn't false-positive). The agent cannot alias the column away.

### Row-level security — `policy.rowFilters`

For per-tenant isolation, declare `policy.rowFilters[]` on the expose. Each filter compiles to a parameterised `WHERE` clause appended to `sample` / `query` reads, bound to the caller's identity:

```yaml
policy:
  rowFilters:
    - { column: tenant_id, equals: "${caller.tenant_id}" }
    - { column: region,    in:     "${caller.regions}" }
```

`${caller.<attr>}` placeholders resolve from `caller_attributes` — populated from the MCP `clientInfo` extras over stdio, or from JWT claims / the mTLS cert over HTTP. The supported operators are `equals` (scalar) and `in` (non-empty list); values are always **bound as parameters**, never interpolated.

**Missing identity fails closed.** If a filter references `${caller.tenant_id}` and the caller never supplied it, the read raises `RowFilterIdentityMissing` and serves **no rows** — the gateway prefers no rows to wrong rows.

### The five engine drivers

Drivers are keyed on `(binding.platform, binding.format)` and built lazily, so `describe` works even when cloud credentials are missing. Out-of-tree drivers can register via `register_driver(("databricks", "delta_table"), DatabricksDriver)` from a private wheel — no core edits.

| Driver | Binds on | Notes |
| --- | --- | --- |
| **DuckDB** | `local` / `{csv, parquet, json, other}` | Reference driver — no credentials. Opens the file read-only (or `:memory:`), auto-creates a view over `read_csv_auto` / `read_parquet` / `read_json_auto`. The same engine the `local` provider uses, so a locally-developed contract serves over MCP unchanged. |
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

`--transport http` serves the gateway over MCP-SSE (`mcp.server.sse.SseServerTransport` + Starlette + uvicorn, transitive deps of the `mcp` extra). Clients connect at `http://host:port/sse`. Identity binding is identical to stdio — only the wire differs.

The HTTP transport has **no built-in TLS or strong identity on its own.** Front it with a reverse proxy. The repo ships ready-to-edit templates at `examples/mcp-output-port-docker/proxy/`:

- **`Caddyfile`** — Caddy 2.x: automatic TLS, `client_auth { mode require_and_verify }` mTLS, a proxy-layer bearer-token check, `flush_interval -1` for SSE, and `header_up X-Client-CN {tls_client_subject}` / `X-Client-Fingerprint {tls_client_fingerprint}` so the gateway records cert identity.
- **`nginx.conf`** — equivalent for nginx shops: `ssl_verify_client on`, `proxy_buffering off` + long read/send timeouts for SSE, and the same `X-Client-CN` / `X-Client-Fingerprint` forwarding.

This is **defence-in-depth** — every layer stops a different failure:

| Layer | Stops | Where it lives |
| --- | --- | --- |
| mTLS client cert | Random network attackers (no valid cert) | Proxy |
| Bearer token (`FLUID_MCP_AUTH_TOKEN`) | A leaked client cert (attacker also needs the secret) | Proxy **and** gateway |
| `agentPolicy.allowedModels` / `allowedUseCases` | A legitimate client running an unapproved model / use case | Gateway (per-`tools/call`) |
| `policy.rowFilters[]` | A legitimate client bound to a different tenant | Gateway (per-row `WHERE`) |
| Cloud row-access policy (IAM compiler) | Bypass-the-gateway direct warehouse reads | Cloud (warehouse-side) |

### Environment variables (output port)

| Env var | Purpose |
| --- | --- |
| `FLUID_QUIET=1` | Keep stdout for JSON-RPC frames (route notices to stderr). |
| `FLUID_MCP_AUTH_MODE` | `shared-token` (default) / `jwt` / `none`. |
| `FLUID_MCP_AUTH_TOKEN` | Shared bearer token (shared-token mode + HTTP 401 gate). |
| `FLUID_MCP_JWT_ISSUER` / `_AUDIENCE` / `_JWKS_URL` | JWT issuer, audience, and JWKS endpoint. |
| `FLUID_MCP_JWT_ALGORITHMS` | Override the accepted algorithms (default `RS256,ES256,EdDSA`). |
| `FLUID_MCP_JWT_CLAIM_MAPPING` | `claim=attr` comma list mapping JWT claims into `caller_attributes`. |
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
- [Governance](./governance.md) — contract-level policy authoring.
- [Environment variables](./environment-variables.md) — the full forge-cli env-var index.
