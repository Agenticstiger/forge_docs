# `fluid secrets`

Manage secrets used by acquisition pipelines — Postgres passwords, Snowflake key-pair paths, Airbyte API tokens, etc. Lives under its own umbrella so it doesn't collide with `fluid auth` (cloud-provider auth) or `fluid ai setup` (LLM credentials).

::: tip Available in 0.8.3
`fluid secrets` ships with the source-aligned acquisition stack in `0.8.3` (schema `0.7.3`). Earlier releases don't include it.
:::

::: warning Contracts do not read this keychain
`fluid secrets` stores a value under the service name `fluid-forge` in the OS keychain. As of 0.18.1, no other command reads that entry: not `fluid apply`, and not the acquisition runners. A secret stored with `fluid secrets login` is not what a contract's `secretRef` resolves. See [How contracts consume secrets](#how-contracts-consume-secrets).
:::

::: tip Got `copilot_missing_llm_api_key`?
That error links to this page, but LLM credentials are not managed here. Run `fluid ai setup` to store a provider key. See [`fluid ai`](./ai.md).
:::

## Syntax

```bash
fluid secrets <subcommand> <secretRef> [options]
```

The `secretRef` here is a name you choose for the keychain entry, for example `postgres.prod.password`, `airbyte.token` or `snowflake.keypair_path`. It is not the `secretRef` URI a contract uses (`env://PGPASSWORD`, `vault://...`).

## Subcommands

### `fluid secrets login`

Store a secret. The value is read from stdin (when piped) or an interactive hidden prompt — never from a command-line flag, so it can't leak via `ps` or shell history.

```bash
fluid secrets login postgres.prod.password
# (prompts for value; input is hidden)

# Pipe the value from stdin (CI / scripted)
printf '%s' "$AIRBYTE_TOKEN" | fluid secrets login airbyte.token

cat /etc/keys/sf.p8 | fluid secrets login snowflake.keypair_path --expires-at 2027-01-01T00:00:00Z
```

| Option | Description |
|---|---|
| `<secretRef>` | Required. The reference name. |
| `--expires-at <iso8601>` | Optional. Echoed in the result as `expires_at`. The keychain backend does not store it. |
| `--json` | Emit a JSON result object instead of the human line. |

### `fluid secrets verify`

Probe the backend to confirm the secret exists and is reachable. Does not echo the value.

```bash
fluid secrets verify postgres.prod.password
fluid secrets verify postgres.prod.password --json
```

| Option | Description |
|---|---|
| `<secretRef>` | Required. The reference name. |
| `--json` | Emit a JSON result object instead of the human line. |

### `fluid secrets rotate`

Replace a stored secret with a new value. The new value is read from stdin or an interactive hidden prompt — never from a flag. The result object's `detail` field reports `rotated` when a prior secret existed, or `stored (no prior secret)` when there wasn't one.

```bash
fluid secrets rotate postgres.prod.password
# (prompts for new value)

# Pipe the new value from stdin
printf '%s' "$NEW_TOKEN" | fluid secrets rotate airbyte.token --expires-at 2027-04-01T00:00:00Z
```

| Option | Description |
|---|---|
| `<secretRef>` | Required. The reference name. |
| `--expires-at <iso8601>` | Optional new expiry. |
| `--json` | Emit a JSON result object instead of the human line. |

## `--json` output

All three subcommands share one result shape under `--json`:

```json
{
  "success": true,
  "ref": "postgres.prod.password",
  "backend": "keychain",
  "detail": "present",
  "expires_at": null
}
```

That is the shape `verify` returns for a stored secret.

- `success`: `true` when the operation completed; the process exit code mirrors this.
- `backend`: `keychain` (default) or `memory` (when `FLUID_SECRETS_INMEMORY=1`).
- `detail`: a short note. `login` leaves it `null`; `verify` says `present` or `not found in backend`; `rotate` says `rotated` or `stored (no prior secret)`.
- `expires_at`: echoes `--expires-at` when one was passed; otherwise `null`.

## Backends

| Backend | When it's used |
|---|---|
| **OS keychain** *(default)* | macOS Keychain / Linux Secret Service / Windows Credential Manager, through the `keyring` package. Entries use the service name `fluid-forge` and the secret reference as the account. |
| **In-memory** | Tests and CI. Enable with `FLUID_SECRETS_INMEMORY=1`. Lost when the process exits. |

You don't pick the backend on the command line; it's process-global per the env var.

## How contracts consume secrets

A contract names a secret with a `secretRef` URI, `<scheme>://<identifier>`, on the field that needs it. For an acquisition source it sits in `connection`:

```yaml
builds:
- id: ingest_orders
  pattern: acquisition
  properties:
    source:
      kind: postgres
      connection:
        host: "{{ env.PGHOST }}"
        database: orders
        user: ingest
        secretRef: env://PGPASSWORD
      mode: full_refresh
      streams: [public.orders]
```

The runner resolves the URI when the build runs. The schemes are:

| Scheme | Reads from |
|---|---|
| `env://VAR` | The environment variable `VAR`. An unset variable is an error. |
| `vault://path` | HashiCorp Vault |
| `aws://name` | AWS Secrets Manager |
| `gcp://name` | GCP Secret Manager |
| `azure://name` | Azure Key Vault |
| `file://path` | A local file |

Any other scheme fails with the list of supported ones. `{{ env.VAR }}` is a different mechanism: it substitutes an environment variable into a string field of the contract. When `fluid apply` or `fluid publish` resolves a contract, a placeholder whose name looks like a credential (`..._PASSWORD`, `..._TOKEN`, `..._SECRET`, `..._API_KEY`) is left unresolved, so use `secretRef` for credentials. No `${SECRET:...}` placeholder exists.

Use `env://` in CI, where the variable comes from your CI system's secret store, and `vault://`, `aws://`, `gcp://` or `azure://` where a secrets manager holds the value. The keychain is not among the schemes, so `fluid secrets login` does not feed a build. Its entries are for the CLI's own `fluid secrets verify` and `rotate`.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Operation succeeded |
| `1` | Backend unavailable, secret not found, or user declined the prompt |

## See also

- [Source-Aligned Acquisition](/forge_docs/advanced/source-aligned-acquisition.html) — why pipelines need secrets
- [Credential Resolver](/forge_docs/advanced/credential-resolver.html): how the CLI stores and reads catalog credentials
- [Typed CLI Errors](/forge_docs/advanced/typed-cli-errors.html): `SecretResolutionError`
