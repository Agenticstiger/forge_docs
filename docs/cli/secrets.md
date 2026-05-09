# `fluid secrets`

Manage secrets used by acquisition pipelines — Postgres passwords, Snowflake key-pair paths, Airbyte API tokens, etc. Lives under its own umbrella so it doesn't collide with `fluid auth` (cloud-provider auth) or `fluid ai setup` (LLM credentials).

::: tip Where this fits
`fluid secrets` ships with the source-aligned acquisition stack in the upcoming `0.7.3` release. The pinned 0.8.0 docs baseline doesn't include it yet; this page documents the surface ahead of release.
:::

## Syntax

```bash
fluid secrets <subcommand> <secretRef> [options]
```

The `secretRef` is a dotted path that the contract refers to via `${SECRETREF}` placeholders — e.g. `postgres.prod.password`, `airbyte.token`, `snowflake.keypair_path`.

## Subcommands

### `fluid secrets login`

Store a secret. Reads the value from `--secret`, from stdin, or from an interactive prompt.

```bash
fluid secrets login postgres.prod.password
# (prompts for value; input is hidden)

fluid secrets login airbyte.token --secret abc123
fluid secrets login snowflake.keypair_path --secret /etc/keys/sf.p8 --expires-at 2027-01-01T00:00:00Z
```

| Option | Description |
|---|---|
| `<secretRef>` | Required. The reference name. |
| `--secret <value>` | The secret value. If omitted, reads from stdin / interactive prompt. |
| `--expires-at <iso8601>` | Optional. When the secret expires (informational; the rotator uses this hint). |
| `--json` | Emit `{ "stored": true, "ref": "..." }` on success. |

### `fluid secrets verify`

Probe the backend to confirm the secret exists and is reachable. Does not echo the value.

```bash
fluid secrets verify postgres.prod.password
fluid secrets verify postgres.prod.password --json
```

| Option | Description |
|---|---|
| `<secretRef>` | Required. The reference name. |
| `--json` | Emit `{ "exists": true\|false, "ref": "..." }`. |

### `fluid secrets rotate`

Update a stored secret. **Probes before rotating** — verifies the old secret exists in the backend before accepting the new value, so a typo in the ref doesn't create an orphan record.

```bash
fluid secrets rotate postgres.prod.password
# (prompts for new value)

fluid secrets rotate airbyte.token --new-secret newval --expires-at 2027-04-01T00:00:00Z
```

| Option | Description |
|---|---|
| `<secretRef>` | Required. The reference name. |
| `--new-secret <value>` | New value. If omitted, reads from stdin / prompt. |
| `--expires-at <iso8601>` | Optional new expiry. |
| `--json` | Emit `{ "rotated": true, "ref": "..." }`. |

## Backends

| Backend | When it's used |
|---|---|
| **OS keychain** *(default)* | macOS Keychain / Linux Secret Service / Windows Credential Manager. Same backend `fluid ai setup` uses for LLM keys. |
| **In-memory** | Tests and CI. Enable with `FLUID_SECRETS_INMEMORY=1`. Lost when the process exits. |

You don't pick the backend on the command line; it's process-global per the env var.

## How contracts reference secrets

Acquisition contract fields read `${env.VAR}` placeholders that are resolved at apply time:

```yaml
properties:
  source:
    connection:
      host: "{{ env.PGHOST }}"
      password: "{{ env.PGPASSWORD }}"
```

`fluid secrets login pg.password --secret <val>` doesn't change that — it stores into the backend so the next `fluid apply` can resolve `${SECRET:pg.password}` references when the contract uses that pattern. The two reference styles coexist:

- `{{ env.X }}` — read environment variable `X` at apply time
- `${SECRET:pg.password}` — read from the secrets backend at apply time

Use `${SECRET:...}` for credentials that shouldn't sit in environment variables (CI logs, parent processes); use `{{ env.X }}` for fixtures or local dev.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Operation succeeded |
| `1` | Backend unavailable, secret not found, or user declined the prompt |

## See also

- [Source-Aligned Acquisition](/forge_docs/advanced/source-aligned-acquisition.html) — why pipelines need secrets
- [Credential Resolver](/forge_docs/advanced/credential-resolver.html) — how Forge resolves `${SECRET:...}` placeholders at runtime
- [Typed CLI Errors](/forge_docs/advanced/typed-cli-errors.html) — `SecretResolutionError`
