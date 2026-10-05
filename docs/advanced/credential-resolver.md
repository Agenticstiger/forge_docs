# Credential Resolver: Security Model

The `CredentialResolver` is the security boundary that keeps metadata-source credentials out of agent-driven MCP sessions. It serves the *source* side: where `fluid forge data-model from-source` reads metadata from (Snowflake, Unity, BigQuery, Dataplex, Glue, DataHub, Data Mesh Manager). It is separate from the credentials that publish targets use and from the `secretRef` values a contract hands to a build; see [`fluid secrets`](../cli/secrets.md) for those. This page documents the resolution chain, the storage rules and the fail-closed behaviour, so security teams can audit them and users know where their secrets live.

## The contract

> **The MCP server never receives catalog credentials from the client by default. Each tool call carries a `credential_id` string. The resolver maps the string to a concrete credential at call time.**

The CLI uses the same resolver, so `fluid forge data-model from-source --source snowflake --credential-id snowflake-prod` and a Claude Code `forge_from_source` call go through the same path.

## Resolution chain

The resolver tries these in order and returns the first that yields a credential:

```
1. Inline credentials   a per-call dict. CLI and tests only; see below for MCP
            |
            v  not provided?
2. credential_id        the entry named in ~/.fluid/sources.yaml (non-sensitive
                        fields) merged with the OS keyring entry of the same
                        name (secret fields)
            |
            v  not found, or no credential_id?
3. Environment          catalog-specific variables (SNOWFLAKE_ACCOUNT, ...)
            |
            v  not found?
4. Cloud metadata       workload identity or ADC, only when
                        --allow-metadata-service or FLUID_ALLOW_METADATA_SERVICE=1
            |
            v  still not found?
5. Fail closed          CredentialNotFoundError, with suggestions
```

When a `credential_id` is given and a saved source of that name is found, it wins over the environment: setting `SNOWFLAKE_PASSWORD` does not override it.

## What lands where

`fluid ai setup --source <catalog> --name <credential-id>` splits each source into two stores:

| Field type | Storage |
|---|---|
| Non-sensitive (account, host, region, role, warehouse, user, key file path) | `~/.fluid/sources.yaml` |
| Sensitive (password, token, passphrase, secret, API key) | The OS keyring, as one JSON entry under the service `fluid_source`, named by the credential id |

Example `~/.fluid/sources.yaml`:

```yaml
sources:
  snowflake-prod:
    source_type: snowflake
    config:
      account: myorg-abc12345
      user: ANALYST
      auth_method: private_key
      private_key_path: ~/.snowflake/rsa_key.p8
      role: ANALYST_RW
      warehouse: ANALYTICS_XS
```

The keyring entries are visible and revocable through your OS: Keychain Access on macOS (search for `fluid_source`), Credential Manager on Windows, `secret-tool` on Linux.

**Plaintext secrets in `sources.yaml` are refused by default.** If a source entry carries secret fields (a `secrets:` block, or a flat key whose name contains `password`, `passphrase`, `secret`, `token`, `private_key`, `api_key` or `credential`), resolution fails with `Refusing plaintext source secrets by default`. The legacy fallback needs both `FLUID_ALLOW_PLAINTEXT_SOURCE_SECRETS=1` and a `sources.yaml` that is mode 600; with the file at any other mode it fails with a `chmod 600` suggestion. Prefer moving the secrets to the keyring by re-running `fluid ai setup`.

## Per-catalog credential classes

Each catalog has a typed Pydantic model with `SecretStr` fields for sensitive values:

```python
class SnowflakeCredentials(BaseModel):
    account: str
    user: str
    auth_method: Literal["password", "private_key", "oauth", "sso"] = "private_key"
    password: Optional[SecretStr] = None
    private_key_path: Optional[Path] = None
    private_key_passphrase: Optional[SecretStr] = None
    oauth_token: Optional[SecretStr] = None
    role: Optional[str] = None
    warehouse: Optional[str] = None
```

`SecretStr` is a Pydantic type that prints as `**********` in `repr` and JSON dumps and needs an explicit `.get_secret_value()` to reach the string. `private_key` is the default and the recommended method; `sso` opens a browser, so it suits `fluid ai setup` and not headless CI.

The classes are `SnowflakeCredentials`, `UnityCredentials`, `BigQueryCredentials`, `DataplexCredentials`, `GlueCredentials`, `DataHubCredentials` and `DataMeshManagerCredentials`.

## Environment variables per catalog

Step 3 reads these variables. A catalog needs its minimum set; a partial set is not turned into a half-populated credential.

| Catalog | Variables |
|---|---|
| `snowflake` | `SNOWFLAKE_ACCOUNT` and `SNOWFLAKE_USER`, plus `SNOWFLAKE_PRIVATE_KEY_PATH` (and `SNOWFLAKE_PRIVATE_KEY_PASSPHRASE`) or `SNOWFLAKE_PASSWORD`; optional `SNOWFLAKE_ROLE`, `SNOWFLAKE_WAREHOUSE` |
| `unity` | `DATABRICKS_HOST` with `DATABRICKS_TOKEN`, or `DATABRICKS_CLIENT_ID` and `DATABRICKS_CLIENT_SECRET` |
| `bigquery` | `GOOGLE_CLOUD_PROJECT` or `GCLOUD_PROJECT`, `GOOGLE_APPLICATION_CREDENTIALS`, `GOOGLE_CLOUD_LOCATION` |
| `dataplex` | `GOOGLE_CLOUD_PROJECT` or `GCLOUD_PROJECT`, `DATAPLEX_LOCATION`, `GOOGLE_APPLICATION_CREDENTIALS` |
| `glue` | `AWS_REGION` or `AWS_DEFAULT_REGION`, with `AWS_PROFILE` or `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` (and `AWS_SESSION_TOKEN`) |
| `datahub` | `DATAHUB_GMS_HOST` or `DATAHUB_SERVER`, `DATAHUB_GMS_TOKEN` or `DATAHUB_TOKEN`, or `DATAHUB_OAUTH_CLIENT_ID` and `DATAHUB_OAUTH_CLIENT_SECRET` |
| `datamesh_manager` | `DMM_API_URL` or `DATAMESH_MANAGER_SERVER`, and `DMM_API_KEY` or `DATAMESH_MANAGER_API_KEY` |

## Inline credentials and MCP

The resolver accepts a per-call dict of inline credentials, and the CLI and tests can use it. An MCP server does not take inline secrets from its client unless it was started with `fluid mcp serve --allow-inline-credentials`, which permits clients to pass raw credentials in a `credentials.inline` argument. That flag is off by default because the MCP wire is normally model-facing; turn it on only for a trusted in-process harness. Without it the schema the server advertises asks for `credential_id`, and the server accepts only `credential_id` lookups:

```jsonc
{
  "credentials": {
    "credential_id": "snowflake-prod"
  }
}
```

## Cloud metadata service is opt-in

For workloads on AWS EC2, ECS or Lambda, or on Cloud Run or GKE, with an instance profile or workload identity attached, the resolver can fall back to the cloud metadata service. It is off by default, because metadata-service auth typically grants broad scopes and operators should choose between scoped credentials and broad IAM on purpose.

Opt in per call:

```bash
fluid forge data-model from-source \
  --source glue \
  --credential-id glue-prod \
  --allow-metadata-service \
  --database my_db -o my_db.fluid.yaml
```

Or for the whole process, with `FLUID_ALLOW_METADATA_SERVICE=1`. Via MCP, pass `"allow_metadata_service": true` in the tool arguments. Without the opt-in, when the metadata service is the only source available, the resolver raises `CredentialNotFoundError` rather than silently using broad IAM.

This switch belongs to the resolver. It does not relax the SSRF guard on outbound HTTP; see [network safety](./network-safety.md).

## Failure modes

`CredentialNotFoundError` carries a `suggestions` list with the exact next step:

```python
raise CredentialNotFoundError(
    message="No credentials configured for source 'snowflake-prod'.",
    suggestions=[
        "Run: fluid ai setup --source snowflake --name snowflake-prod",
        "Or set: SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, "
        "SNOWFLAKE_PRIVATE_KEY_PATH (private_key auth)",
    ],
)
```

The next action is in the message, not buried in the docs. Stored credentials that fail validation suggest `fluid ai setup --source <credential-id> --rotate`.

::: warning `SNOWFLAKE_ACCOUNT` on the IaC path *(since 0.15.0)*
`SNOWFLAKE_ACCOUNT` above is the **source-connection** credential and is still exactly right there. On the [`fluid apply`](../cli/apply.md) / OpenTofu path it is not: from Snowflake's OpenTofu provider 2.x the bare `account` field is gated behind the `PROVIDER_CONFIGURATION_ACCOUNT_FALLBACK` experiment, and the provider **errors the moment it sees the legacy variable** — whether or not the v2 `SNOWFLAKE_ORGANIZATION_NAME` + `SNOWFLAKE_ACCOUNT_NAME` pair is also present. Measured on provider 2.19.0 / OpenTofu 1.12.0: legacy only → rejected; legacy plus both v2 vars → rejected; v2 vars with the legacy variable blanked → `tofu plan` succeeds.

Since `0.15.0` the IaC credential overlay derives the v2 pair from the `<org>-<account>` form and **blanks** `SNOWFLAKE_ACCOUNT` in the environment handed to `tofu` once a complete v2 identity is available — blanked rather than removed, because callers apply the overlay with `env.update()`, which cannot delete, and an empty value reads as unset to the provider. **No contract or configuration change is needed:** an operator who keeps setting `SNOWFLAKE_ACCOUNT` in the standard `<org>-<account>` form goes from failing to working.

The one shape that still cannot plan is a bare account locator with no organisation (`xy12345`), which deliberately keeps its legacy value so the provider's actionable "enable the experiment" error survives instead of degrading to a vaguer "account is empty". That operator sets the two v2 variables directly, or opts into the experiment.
:::

## See also

- [`fluid secrets`](../cli/secrets.md): `secretRef` values that builds read
- [Catalogs index](../cli/catalogs/README.md): per-catalog auth options
- [V1.5 architecture](v1.5-architecture.md): the model around source catalogs
- [`fluid ai setup`](../cli/ai.md): the interactive wizard
