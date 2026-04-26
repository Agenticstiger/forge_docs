# Credential Resolver — Security Model

The `CredentialResolver` is the V1.5 security boundary that keeps
catalog credentials out of agent-driven MCP sessions. This page
documents the resolution chain, the storage rules, and the
fail-closed behavior — so security teams can audit and so users
know exactly where their secrets live.

## The contract

> **The MCP server never holds catalog credentials. Each tool call
> receives a `credential_id` string. The resolver maps the string
> to a concrete credential at call time, from the highest-trust
> source available.**

The CLI surface uses the same resolver, so a `fluid forge
data-model from-source --source snowflake --credential-id snowflake-prod` and a Claude Code
`forge_from_source` MCP call exercise the identical credential
path.

## Resolution chain (highest trust first)

```
1. inline_credentials (CLI only — direct API call)
            │
            ▼  not provided?
2. OS keyring (macOS Keychain / Windows Credential Manager /
   Linux secret-service via `keyring` package)
            │
            ▼  not found?
3. ~/.fluid/sources.yaml  (non-sensitive fields only — never
   secrets in plain text)
            │
            ▼  not found?
4. Environment variables (catalog-specific names —
   SNOWFLAKE_PRIVATE_KEY_PATH, DATABRICKS_TOKEN, etc.)
            │
            ▼  not found?
5. Cloud metadata service (opt-in via allow_metadata_service=True
   — instance profiles, workload identity)
            │
            ▼  still not found?
6. Fail-closed → raise CredentialNotFoundError with a
   suggestions[] list pointing the operator at `fluid ai setup
   --source <catalog> --credential-id <name>`.
```

## What lands where

For `~/.fluid/sources.yaml`, secrets are **never** stored in plain
text. The wizard splits each source into two categories:

| Field type | Storage |
|---|---|
| Non-sensitive (host, account, region, role, default DB/schema, user) | `~/.fluid/sources.yaml` (plain YAML, world-readable mode 0644 OK) |
| Sensitive (token, password, private key passphrase, API key, secret) | OS keyring entry under `fluid:<source-name>:<field>` |

Example `~/.fluid/sources.yaml`:

```yaml
sources:
  snowflake-prod:
    catalog: snowflake
    account: myorg-abc12345
    user: analyst@example.com
    auth_method: key_pair
    private_key_path: /Users/me/.ssh/snowflake_key.p8
    # private_key_passphrase: <in OS keyring>
    warehouse: COMPUTE_WH
    role: ANALYST

  databricks-prod:
    catalog: databricks
    host: https://dbc-12345.cloud.databricks.com
    auth_method: pat
    # token: <in OS keyring>
    default_catalog: main
    default_schema: biz_lab
```

The keyring entries are visible (and revocable) via your OS:

- macOS: Keychain Access app, search for "fluid:".
- Windows: Credential Manager → Generic Credentials.
- Linux: `secret-tool search service fluid`.

## Per-catalog credential classes

Each catalog has a typed `*Credentials` Pydantic model with
`SecretStr` fields for sensitive values:

```python
class SnowflakeCredentials(BaseModel):
    account: str                                  # non-sensitive
    user: str                                     # non-sensitive
    auth_method: Literal["key_pair", "password", "externalbrowser", "oauth"]
    private_key_path: Path | None = None          # non-sensitive (path only)
    private_key_passphrase: SecretStr | None = None
    password: SecretStr | None = None
    role: str | None = None
    warehouse: str | None = None
    database: str | None = None
    schema_name: str | None = None
```

`SecretStr` is a Pydantic primitive that:
- prints as `**********` in any `__repr__` / `model_dump_json` call;
- requires explicit `.get_secret_value()` to access the underlying string;
- is excluded from `audit_context()` results so no secret ever
  lands in an audit event.

The seven classes — `SnowflakeCredentials`, `UnityCredentials`,
`BigQueryCredentials`, `DataplexCredentials`, `GlueCredentials`,
`DataHubCredentials`, `DataMeshManagerCredentials` — are all in
the public API (pinned by
`tests/test_public_api_stability.py`).

## Inline credentials are CLI-only

The MCP wire format has **no** `inline_credentials` field. The
schema in
`fluid_build/cli/mcp.py::_CREDENTIALS_PROP` only accepts
`credential_id`:

```jsonc
{
  "credentials": {
    "credential_id": "snowflake-prod"
    // no token, no password — server rejects extra secret keys
  }
}
```

This is enforced by:
1. The MCP `inputSchema` (advertised at `tools/list`) showing
   `credential_id` as the only required field on `credentials`.
2. Server-side validation that rejects credential blocks with
   inline secret keys.
3. Tests pinning that no MCP tool path ever accepts inline
   secrets.

CLI direct callers can still pass inline credentials when needed
(e.g. one-off scripts that don't want to set up sources.yaml) —
the resolver checks inline first.

## Cloud metadata service is opt-in

For workloads running on AWS EC2 / ECS / Lambda / Cloud Run / GKE
that have an instance profile or workload identity attached, the
resolver can fall back to the cloud metadata service. This is
**off by default** because:

- Metadata service auth typically grants broad scopes.
- Operators should explicitly choose between scoped credentials
  and broad-IAM auth.

Opt in per call:

```bash
fluid forge data-model from-source \
  --source glue \
  --credential-id glue-prod \
  --allow-metadata-service \
  --database my_db -o my_db.fluid.yaml
```

Or via MCP:

```jsonc
{ "tool": "forge_from_source", "arguments": {
  "source": "glue",
  "credentials": { "credential_id": "glue-prod" },
  "allow_metadata_service": true,
  ...
}}
```

When metadata service is the only credential source available
AND `allow_metadata_service=False`, the resolver raises
`CredentialNotFoundError` rather than silently using broad IAM.

## Audit trail per resolution

Every successful credential resolution writes an audit event:

```jsonc
{
  "event": "credential.resolved",
  "credential_id": "snowflake-prod",
  "catalog_name": "snowflake",
  "source": "keyring",        // or "sources.yaml" / "env" / "metadata_service" / "inline"
  "auth_method": "key_pair",
  "timestamp": "2026-04-25T14:33:21.123Z"
}
```

The actual secret values are NEVER in the audit event — only the
metadata about which source supplied them. Query with:

```bash
fluid memory show audit --filter credential.resolved
```

## Failure modes

`CredentialNotFoundError` is raised with a `suggestions: list[str]`
field that contains the exact command the operator should run:

```python
raise CredentialNotFoundError(
    f"No credentials configured for source 'snowflake-prod'.",
    suggestions=[
        "Run: fluid ai setup --source snowflake --name snowflake-prod",
        "Or set: SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, "
        "SNOWFLAKE_PRIVATE_KEY_PATH (key_pair auth)",
    ],
)
```

The next-action is in the message — not buried in the docs.

## See also

- [Catalogs index](../cli/catalogs/README.md) — per-catalog auth options
- [V1.5 architecture](v1.5-architecture.md) — full security model
- [`fluid ai setup`](../cli/ai.md) — interactive wizard
