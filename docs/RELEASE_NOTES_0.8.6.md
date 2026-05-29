# Fluid Forge Docs Baseline: CLI `0.8.6`

**Release Date:** May 29, 2026
**Status:** Current stable docs baseline (supersedes [`0.8.5`](./RELEASE_NOTES_0.8.5.md))

## Headline

`0.8.6` ships the **MCP output-port gateway** and, with it, **contract schema `fluidVersion` 0.7.4**. The headline is that `agentPolicy` stops being declarative metadata and becomes **runtime-enforced at the gateway**: when an expose carries an `expose.mcp` block, `fluid mcp output-port serve` enforces `allowedModels` / `deniedModels`, `allowedUseCases` / `deniedUseCases`, rate limits, token budgets, and per-tenant row filters on every `tools/call`. Gateway identity is now cryptographic — **JWT bearer + mTLS** — and the cloud-IAM compilers for **BigQuery row-access policies** and **AWS Lake Formation** are real implementations (no longer stubs), joined by **PostgreSQL** and **AWS Athena** drivers, **PII/PHI value redaction**, and an **audit webhook forwarder**. The release also fixes two important bugs: a monitoring daemon-thread leak that OOM-hung Python 3.13/3.14 CI, and a `ConfigManager` shared-defaults pollution bug.

Schema `0.7.4` is **backward-compatible with `0.7.3`** — existing contracts validate unchanged; the new `expose.mcp` block is additive and opt-in.

---

## What changed in `v0.8.6`

### 1 — FLUID schema `0.7.4`: runtime `agentPolicy` enforcement at the MCP gateway

Schema `0.7.4` adds the **`expose.mcp` block**. Its presence does two things: it declares an expose **agent-consumable over MCP** (sampling caps + classification), and it **opts that expose into the gateway**.

When the gateway serves an expose that carries `expose.mcp`, it loads `policy.agentPolicy` and enforces it on every `tools/call`:

- **Model gating** — `allowedModels` / `deniedModels`. The caller's `model_id` comes from the MCP `clientInfo` handshake.
- **Use-case gating** — `allowedUseCases` / `deniedUseCases`, keyed off the caller's declared `useCase`.

The gateway is built on Anthropic's official [`mcp` Python SDK](https://github.com/modelcontextprotocol/python-sdk) (`>=1.20,<2.0`); the prior custom JSON-RPC dispatcher and stdio transport were removed. See [`fluid mcp`](./cli/mcp.md) and [MCP output-port gateway](./advanced/mcp.md) for the full surface.

**CLI overrides for incident response** — `--allow-models`, `--deny-models`, `--allow-use-cases`, `--deny-use-cases` on `fluid mcp output-port serve`. CLI values **replace** the contract values entirely (not merged); the audit event records `policySource: "cli"` vs `"contract"` so an audit reader can tell ops overrides from declared policy.

### 2 — Cryptographic gateway identity: JWT bearer + mTLS

Caller identity is no longer self-attested. A new `AuthValidator` strategy supports:

- **`shared-token`** — the existing v0.7.4 default (set `FLUID_MCP_AUTH_TOKEN`; the gateway returns `401` on any unauthenticated request **before** the SSE handshake).
- **`jwt`** — RS256 / ES256 / EdDSA validated against an issuer's JWKS endpoint (checks `iss` / `aud` / `exp` / signature). Configured JWT claims map into `caller_attributes`, so `policy.rowFilters` `${caller.<attr>}` placeholders resolve **cryptographically** rather than via self-attestation.
- **`none`** — operator opt-out; the gateway warns loudly at startup.

**mTLS** metadata forwarded by a reverse proxy (`X-Client-CN` + `X-Client-Fingerprint`) is mirrored into the identity for combined attribution. Reverse-proxy templates for production (Caddy + nginx, with mTLS + bearer token + SSE buffering) ship in `examples/mcp-output-port-docker/proxy/`.

### 3 — Real cloud-IAM compilers (defence-in-depth beyond the gateway)

So that "bypass the gateway and query the warehouse directly" is also gated, the cloud-IAM compiler now emits **runnable** policy for two more targets (previously `-- TODO` stubs):

- **BigQuery row-access policy** — `CREATE OR REPLACE ROW ACCESS POLICY ON <table> GRANT TO (<service_accounts>) FILTER USING (<predicate>)`, with `caller.user → SESSION_USER()` mapping and `agentPolicy.allowedModels → serviceAccount:fluid-mcp-<MODEL>@<project>` GRANT clauses.
- **AWS Lake Formation** — a runnable boto3 script (`lakeformation.create_data_cells_filter` + `grant_permissions`) bound to per-LLM IAM roles (`arn:aws:iam::<ACCOUNT>:role/fluid-mcp-<MODEL>`). Paste into CDK / Terraform or run directly.

These join the already-shipping Snowflake row-access-policy and Postgres `CREATE POLICY` emitters, which honour the same `agentPolicy` + `rowFilters` contract.

### 4 — New engine drivers: PostgreSQL + AWS Athena

- **PostgreSQL driver** — psycopg v3, **read-only sessions** enforced at connect time, per-statement timeout via `SET LOCAL statement_timeout`, and `:p_<idx>` → `%(p_<idx>)s` parameter rewrite (SQL-injection-safe). Exercised end-to-end against the dockerized Postgres in `examples/mcp-output-port-docker/`.
- **AWS Athena driver** — boto3 default credential chain (env / `~/.aws/credentials` / IAM role / OIDC), `StartQueryExecution` → poll → page-through with `ExecutionParameters`.

`EngineDriver.close()` is hoisted to the base class so every driver has a uniform, idempotent close path; out-of-tree driver registration via `register_driver()` is now pinned by tests so a refactor can't silently break private wheels.

### 5 — Row-level PII / PHI value redaction

Columns marked `sensitivity: pii`, `sensitivity: phi`, or `sensitivity: sensitive` in `expose.contract.schema` keep their **key** visible (so the agent knows the field exists and can write `COUNT(DISTINCT)` aggregates) but their **values** are replaced with `[REDACTED-PII]` before the row leaves the gateway. This is distinct from `columnRestrictions`, which drops the column wholesale.

### 6 — Audit webhook forwarder for multi-instance HA

Set `FLUID_MCP_AUDIT_WEBHOOK_URL` (and optionally `FLUID_MCP_AUDIT_WEBHOOK_HEADER_AUTH`) and every audit event is POST-ed on a daemon thread to a SIEM aggregator (Splunk HEC, Datadog, Elastic, Loki). It is **best-effort**: webhook failures never block the local-disk write — the local copy remains the source of truth. Pairs with the existing `FLUID_AUDIT_ROOT` redirect and audit-log rotation (`FLUID_AUDIT_MAX_AGE_DAYS`, `FLUID_AUDIT_MAX_TOTAL_MB`).

---

## Bug fixes

- **Daemon-thread leak that OOM-hung CI on Python 3.13 / 3.14.** `forge.core.monitoring.MonitoringSystem` started four background daemon workers per instance and only stopped them on an explicit `shutdown()`. Code that constructed instances and dropped them (notably the test suite) leaked threads without bound; across a long run the per-thread virtual stacks exhausted address space and the OS OOM-killed the process. Workers now stop promptly via a `threading.Event`, live instances are tracked in a `WeakSet`, `shutdown()` / context-manager support is added, and a per-test fixture drains them.
- **`ConfigManager` could corrupt process-wide defaults.** `_load_defaults` shallow-copied the module-level `DEFAULT_CONFIG`, sharing its nested dicts — so a later `set("logging.level", …)` or config-file merge mutated the shared defaults in place, affecting every other `ConfigManager` in the process. It now deep-copies the defaults.
- **MCP gateway rate limiter no longer leaks a background thread.** Replaced PyrateLimiter's `Limiter` (which spins a per-instance "leaker" thread) with an in-process monotonic-clock deque sliding window — functionally identical for the single-replica gateway, with no thread and no dependency. Drops the `pyrate-limiter` dependency.

---

## Notable for upgraders

- **Schema `0.7.4` is backward-compatible.** Existing `0.7.3` (and older) contracts validate unchanged. The `expose.mcp` block is additive and opt-in — nothing enforces `agentPolicy` at runtime until you add it and serve the expose over the gateway.
- **The gateway must not be exposed on an untrusted network in `shared-token` / `none` mode.** Use the `jwt` auth mode (with a JWKS issuer) or front the gateway with the mTLS reverse-proxy templates before exposing it beyond localhost. The CLI prints a loud startup warning when identity is self-attested.
- **`agentPolicy` is now load-bearing.** If you had `agentPolicy` blocks as documentation only, adding `expose.mcp` and serving via the gateway will start **enforcing** them — review `allowedModels` / `deniedUseCases` before you serve.
- **New env vars.** `FLUID_MCP_AUDIT_WEBHOOK_URL`, `FLUID_MCP_AUDIT_WEBHOOK_HEADER_AUTH`, plus the existing `FLUID_MCP_AUTH_TOKEN`, `FLUID_MCP_RATE_LIMIT` / `FLUID_MCP_RATE_WINDOW_SECONDS`, `FLUID_MCP_MAX_CONCURRENCY`, and the circuit-breaker / token-budget toggles. See [`fluid mcp`](./cli/mcp.md).
- **New drivers need their extras.** The PostgreSQL driver needs `psycopg` v3; the Athena driver uses boto3 — install the relevant extra for the engine you serve.
- **Python 3.13 / 3.14 users:** the monitoring thread-leak fix resolves the OOM hang — upgrade to `0.8.6` if you saw long test runs or long-lived processes balloon memory.

---

## What changed in the docs

- **[`fluid mcp`](./cli/mcp.md)** — the MCP output-port gateway command surface: `serve`, transports, auth modes, the CLI policy-override flags, rate-limit / concurrency / circuit-breaker env vars.
- **[MCP output-port gateway](./advanced/mcp.md)** — runtime `agentPolicy` enforcement, `expose.mcp` schema, JWT + mTLS identity, row filters, PII/PHI redaction, cloud-IAM compilers, and the audit forwarder.
- **`RELEASE_NOTES_0.8.6.md`** — this file.

---

## Installing

```bash
pip install --upgrade data-product-forge
pip install "data-product-forge==0.8.6"

# Verify
fluid version
# -> 0.8.6
```

---

## Archive note

Older release notes remain available: [`0.8.5`](./RELEASE_NOTES_0.8.5.md), [`0.8.4`](./RELEASE_NOTES_0.8.4.md), [`0.8.3`](./RELEASE_NOTES_0.8.3.md), [`0.8.0`](./RELEASE_NOTES_0.8.0.md), [`0.7.11`](./RELEASE_NOTES_0.7.11.md), [`0.7.9`](./RELEASE_NOTES_0.7.9.md), [`0.7.1`](./RELEASE_NOTES_0.7.1.md).
