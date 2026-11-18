# `fluid secrets`

Manage secrets used by acquisition pipelines — Postgres passwords, Snowflake key-pair paths, Airbyte API tokens, etc. Lives under its own umbrella so it doesn't collide with `fluid auth` (cloud-provider auth) or `fluid ai setup` (LLM credentials).

::: tip Available in 0.8.3
`fluid secrets` ships with the source-aligned acquisition stack in `0.8.3` (schema `0.7.3`). Earlier releases don't include it.
:::

::: warning Contracts do not read this keychain
`fluid secrets login`, `verify` and `rotate` store a value under the service name `fluid-forge` in the OS keychain. No other command reads that entry: not `fluid apply`, not the acquisition runners, and no `secretRef` scheme. A secret stored with `fluid secrets login` is not what a contract's `secretRef` resolves. See [How contracts consume secrets](#how-contracts-consume-secrets).
:::

::: tip Got `copilot_missing_llm_api_key`?
That error links to this page, but LLM credentials are not managed here. Run `fluid ai setup` to store a provider key. See [`fluid ai`](./ai.md).
:::

## Syntax

```bash
fluid secrets check <contract> [--env ENV] [--resolve] [--json]
fluid secrets <login|verify|rotate> <secretRef> [options]
```

*(since 0.31.0, [forge-cli #893](https://github.com/Agenticstiger/forge-cli/pull/893))* `check` reads a contract and tests the secret references in it. `login`, `verify` and `rotate` manage the OS keychain.

For those three, the `secretRef` is a name you choose for the keychain entry, for example `postgres.prod.password`, `airbyte.token` or `snowflake.keypair_path`. It is not the `secretRef` URI a contract uses (`env://PGPASSWORD`, `vault://kv/orders/pg#db_pass`).

## Subcommands

### `fluid secrets check`

*(since 0.31.0, [forge-cli #893](https://github.com/Agenticstiger/forge-cli/pull/893))* Test every `secretRef` in a contract against the grammar and [the operator's policy](#the-operator-s-policy): the scheme is enabled, the locator is under an allowed prefix, and every host the value would be sent to is allowed. It reads no value, so it is safe in a lint job, and `fluid validate` runs the same test.

```bash
fluid secrets check contract.fluid.yaml
fluid secrets check contract.fluid.yaml --resolve
fluid secrets check contract.fluid.yaml --json
```

| Option | Description |
|---|---|
| `<contract>` | Required. Path to the contract (`contract.fluid.yaml`). |
| `--env ENV` | Overlay environment to apply first. |
| `--resolve` | Also prove that each reference exists in its store, without reading its value: KV v2 metadata for `vault://`, `DescribeSecret` for `aws-sm://`, the variable or the file for `env://` and `file://`. It uses this shell's own store login. |
| `--json` | Emit JSON. |

With the default policy, a contract whose references pass prints one line per reference:

```text
$ fluid secrets check contract.fluid.yaml
✅ builds[0].properties.source.connection.secretRef: env://PGPASSWORD
✅ builds[1].properties.source.connection.secretRef: vault://kv/orders/pg#db_pass
All 2 secret references pass.
```

A refused reference prints what is wrong, why, and the setting that allows it. This run has `FLUID_SECRET_SCHEMES=env,file`, which leaves `vault://` off:

```text
$ FLUID_SECRET_SCHEMES=env,file fluid secrets check contract.fluid.yaml
✅ builds[0].properties.source.connection.secretRef: env://PGPASSWORD
❌ builds[1].properties.source.connection.secretRef: vault://kv/orders/pg#db_pass
   vault://kv/orders/pg#db_pass: the vault:// scheme is not enabled
   why: The operator decides which secret stores a contract may read from.
   fix: Set it in the operator environment (a shell or CI variable, not a project .env): FLUID_SECRET_SCHEMES="env,file,vault".
1 of 2 secret references need attention.
```

With `--resolve`, each reference that passed the policy also says whether it exists. This run has `PGPASSWORD` set, `PG_MISSING` unset, one file present and one absent:

```text
$ fluid secrets check contract.fluid.yaml --resolve
✅ builds[0].properties.source.connection.secretRef: env://PGPASSWORD
   exists: PGPASSWORD is set
❌ builds[1].properties.source.connection.secretRef: env://PG_MISSING
   missing: PG_MISSING is not set
✅ builds[2].properties.source.connection.secretRef: file:///run/secrets/db_pw
   exists: the file exists and is readable
❌ builds[3].properties.source.connection.secretRef: file:///run/secrets/absent
   missing: no regular file at that path
2 of 4 secret references need attention.
```

A store that cannot answer is reported as `cannot tell`, and counts as a failure. For example, with `BAO_ADDR` set to an address nothing listens on:

```text
❌ builds[0].properties.source.connection.secretRef: vault://kv/orders/pg#db_pass
   cannot tell: the store at https://127.0.0.1:9 could not be reached (ConnectError). Check BAO_ADDR / VAULT_ADDR and the network path to it.
```

A reference that is not in the grammar is shown as written, unless it may be a secret pasted in its place; see [What is refused](#what-is-refused). A contract with no `secretRef` prints `No secret references in <contract>.` and exits 0.

`--json` prints one object. `ok` is `false` when any reference failed, and each reference carries its `pointer`, the canonical `reference`, its `scheme` and `ok`. A refused reference adds `code`, `what`, `why` and `fix`. With `--resolve`, a reference adds `exists` (`true`, `false` or `null`) and `detail`.

```json
{
  "contract": "contract.fluid.yaml",
  "ok": true,
  "references": [
    {
      "pointer": "builds[0].properties.source.connection.secretRef",
      "reference": "env://PGPASSWORD",
      "scheme": "env",
      "ok": true
    }
  ]
}
```

Exit codes are in [Exit codes](#exit-codes).

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

`login`, `verify` and `rotate` share one result shape under `--json` (`check` has its own, shown above):

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

A contract names a secret. It never carries one. The name is a `secretRef`, one string in one grammar for every store:

```text
<scheme>://<locator>[#<field>][?version=<n>]
```

*(since 0.31.0, [forge-cli #893](https://github.com/Agenticstiger/forge-cli/pull/893))* The parts:

| Part | Meaning | Default |
|---|---|---|
| `<scheme>` | The store. Case-insensitive as written, and an alias is read as its canonical scheme (see the table below). Output shows the canonical, lower-case form. | None. A reference without `://` is refused. |
| `<locator>` | Where the secret lives in that store. | None. It may not be empty. |
| `#<field>` | One key of a secret that holds several: a KV v2 secret, a JSON Secrets Manager secret. A field is letters, digits, `_`, `.`, `@` or `-`. | No field. `vault://` requires one. |
| `?version=<n>` | Pins a version where the store keeps them. It is the only query a reference takes, and it comes after the field: `...#<field>?version=<n>`. | The store's current version. |

For an acquisition source the reference sits in `connection`:

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

A literal `password` in the same `connection` block wins over `secretRef`, and then the reference is never read. A contract that [`fluid init --discover`](./init.md) wrote, which carries the URI's password in `connection.password`, needs that line deleted when you add the `secretRef`. A password typed into a command-line URI also lands in shell history and in `ps` output; keep it out of the URI where you can.

### Schemes

| Scheme | Form | Store | Aliases | Extra needed | Notes |
|---|---|---|---|---|---|
| `env` | `env://<VARIABLE>` | An environment variable of the `fluid` process | None | None | The name is letters, digits and `_`, not starting with a digit. It takes no field or version. An unset variable is an error. |
| `file` | `file:///<absolute/path>` | A mounted secret file | None | None | An absolute path, so three slashes. Only under an allowed prefix, `/run/secrets/` by default (where [Docker](https://docs.docker.com/compose/how-tos/use-secrets/) and [Kubernetes](https://kubernetes.io/docs/concepts/configuration/secret/) mount secrets). A regular file of at most 64 KiB, read as UTF-8, with one trailing line break dropped. A symlink is followed and the real path is checked against the prefixes again. No field or version. |
| `vault` | `vault://<mount>/<path>#<field>[?version=<n>]` | KV v2 on [OpenBao](https://openbao.org/docs/secrets/kv/kv-v2/) or Vault | `openbao://` | None | `#<field>` is required. The first path segment is the KV v2 mount. See [Vault and OpenBao](#vault-and-openbao). |
| `aws-sm` | `aws-sm://<name-or-arn>[#<json-key>][?version=<version-id>]` | AWS Secrets Manager | `aws://` | `pip install 'data-product-forge[aws]'` | Uses boto3's credential chain. The region comes from an ARN, else from boto3. `#<json-key>` reads one key of a JSON secret. `?version=` takes a `VersionId`. |
| `gcp-sm` | `gcp-sm://projects/<project>/secrets/<secret>[/versions/<n>]` | GCP Secret Manager | `gcp://` | A resolver pack | The version goes in the path. No field. |
| `azure-kv` | `azure-kv://<vault-name>/<secret>[?version=<id>]` | Azure Key Vault | `azure://` | A resolver pack | No field. `?version=` takes a 32-digit hexadecimal version id. |

A pack is a Python package that registers a resolver in the `fluid_build.secret_resolvers` entry-point group, named after its scheme. A pack's scheme can be any lower-case name, for example `op://`; core checks only the generic grammar for it and leaves the locator to the pack. Packs are found, allowed and blocked like every other plugin (`FLUID_PLUGINS_ALLOWLIST`, `FLUID_PLUGINS_BLOCKLIST`), and [`fluid plugins`](./plugins.md) lists them. A pack cannot replace `env`, `file`, `vault` or `aws-sm`. Installing a pack does not turn its scheme on: the operator lists it in [`FLUID_SECRET_SCHEMES`](#fluid-secret-schemes).

A contract that names `gcp-sm://` or `azure-kv://` where no pack is installed gets a warning from `fluid validate` and `fluid secrets check`, not an error, because the machine that lints may not be the machine that applies. The machine that applies needs the pack.

`{{ env.VAR }}` is a different mechanism: it substitutes an environment variable into a string field of the contract. When `fluid apply` or `fluid publish` resolves a contract, a placeholder whose name looks like a credential (`..._PASSWORD`, `..._TOKEN`, `..._SECRET`, `..._API_KEY`) is left unresolved, so use `secretRef` for credentials. No `${SECRET:...}` placeholder exists.

Use `env://` in CI, where the variable comes from your CI system's secret store, `file://` where an orchestrator mounts the secret, and `vault://` or `aws-sm://` where a secrets manager holds the value. The keychain is not among the schemes, so `fluid secrets login` does not feed a build. Its entries are for the CLI's own `fluid secrets verify` and `rotate`.

### Which fields take a `secretRef`

*(since 0.31.0, [forge-cli #893](https://github.com/Agenticstiger/forge-cli/pull/893))* Two fields name a secret that a run reads and sends somewhere, and the policy judges where:

- **`builds[].properties.source.connection.secretRef`**: the credential of an acquisition source. Every host the connection block names has to be allowed.
- **`builds[].properties.airbyte.deployment.auth.secretRef`**: the token of an Airbyte server you run (`bring-your-own`). The host is `deployment.server_url`. An inline `auth.token` wins, and then the reference is never read.

Every other `secretRef` string in a contract, such as a schema registry's `auth.secretRef`, is checked for the grammar, the scheme and the prefix. The contract reference lists each field: [stable schema](../reference/contract-0.7.6.md) and [0.7.7 preview](../reference/contract-0.7.7-preview.md). In the 0.7.7 preview every `secretRef` field takes a pattern per scheme, and `connection.password` and `deployment.auth.token` are write-only: `fluid validate` refuses a literal there and never prints it.

### What is refused

*(since 0.31.0, [forge-cli #893](https://github.com/Agenticstiger/forge-cli/pull/893))* `fluid validate` and `fluid secrets check` refuse a reference without reading anything. A message names the reference and never a value.

- **A pasted secret.** A `secretRef` with no `://`, or a URL with `user:password@`, is most likely a credential typed where its reference belongs. It is refused, and the message does not repeat it.
- **A malformed reference.** Each scheme has its own grammar, and the message says which part is wrong and how to write it.

```text
$ fluid secrets check contract.fluid.yaml
❌ builds[0].properties.source.connection.secretRef: (value not shown)
   the secretRef is not a valid secret reference
   why: It carries user:password@, like a connection URL: a reference names a secret and never holds one, so it is not shown.
   fix: Write it as <scheme>://<locator>[#<field>][?version=<n>].
❌ builds[1].properties.source.connection.secretRef: (value not shown)
   the secretRef is not a valid secret reference
   why: A reference starts with the store's scheme and '://'; this one does not, so it may be a secret pasted in its place, and is not shown.
   fix: Write it as <scheme>://<locator>[#<field>][?version=<n>].
❌ builds[2].properties.source.connection.secretRef: vault://kv/orders/pg
   'vault://kv/orders/pg' is not a valid secret reference
   why: A KV v2 secret holds several keys, so name one with #<field>.
   fix: Write it as vault://<mount>/<path>#<field>[?version=<n>].
❌ builds[3].properties.source.connection.secretRef: file://run/secrets/pg
   'file://run/secrets/pg' is not a valid secret reference
   why: A file reference takes an absolute path, so file:// is followed by a third '/' (file:///run/secrets/name).
   fix: Write it as file:///<absolute/path>.
❌ builds[4].properties.source.connection.secretRef: env://PG-PASS
   'env://PG-PASS' is not a valid secret reference
   why: An environment variable name is letters, digits and '_', not starting with a digit, and it takes no field or version.
   fix: Write it as env://<VARIABLE>.
5 of 5 secret references need attention.
```

`fluid validate` prints the same text as errors, and exits 1. A reference that is well formed but not allowed by the operator's policy is refused too: see [The operator's policy](#the-operator-s-policy).

### When a value is fetched

*(since 0.31.0, [forge-cli #893](https://github.com/Agenticstiger/forge-cli/pull/893))* A value is fetched late, by the stage that sends it, and by no other. By default that stage is `apply`. `validate`, `plan`, `bundle` and `diff` never fetch a value, whatever the operator sets: they only lint references.

When a stage asks for a reference, forge checks, in this order, before any store is asked:

1. The reference is well formed.
2. Its scheme is enabled ([`FLUID_SECRET_SCHEMES`](#fluid-secret-schemes)).
3. Its locator is under an allowed prefix ([`FLUID_SECRET_PREFIXES`](#fluid-secret-prefixes)).
4. The running stage may fetch values ([`FLUID_SECRET_STAGES`](#fluid-secret-stages)).
5. Every host the value would be sent to is allowed ([`FLUID_ACQUISITION_SECRET_REF_ALLOWLIST`](#fluid-acquisition-secret-ref-allowlist)).

Then the value comes from the run's cache (one fetch per reference per run), else from [the run-secrets file](#the-run-secrets-file) when one is set, else from the scheme's store. A refusal at any step reads nothing.

A fetched value is held for the run and no longer. It is registered with the log redactor, so a client library that echoes it in an error is masked, and each lookup is recorded as a `fluid.secret.resolve` span event that carries the reference, the scheme, the stage and the outcome, never the value. A token that forge itself obtained from a store is revoked when the run ends.

## The operator's policy

*(since 0.31.0, [forge-cli #893](https://github.com/Agenticstiger/forge-cli/pull/893))* A contract names a secret, and beside it the host the value is sent to. Both are the contract's to choose, so without a limit a contract run with your identity could read any secret you can read and send it to a host it picked. The operator sets the limit, in four variables. The contract only names.

| Variable | Decides | Default |
|---|---|---|
| [`FLUID_SECRET_SCHEMES`](#fluid-secret-schemes) | Which stores a contract may read from | `env`, `file`, `vault`, `aws-sm` |
| [`FLUID_SECRET_PREFIXES`](#fluid-secret-prefixes) | Which locators a contract may name, per scheme | `file` under `/run/secrets/`; no limit for the others |
| [`FLUID_SECRET_STAGES`](#fluid-secret-stages) | Which stages may fetch a value | `apply` |
| [`FLUID_ACQUISITION_SECRET_REF_ALLOWLIST`](#fluid-acquisition-secret-ref-allowlist) | Which hosts a value may be sent to | None: only a loopback host |

All four are read only from the real environment: your shell, your CI job, or a `FLUID_SECRETS_FILE` you export yourself. A project's `.env` cannot set them, because `fluid apply` loads the `.env` files committed beside a contract, and a repository must not grant itself the policy that constrains it. A value set there is ignored, and `fluid` says so. See [What a project's `.env` may set](../advanced/project-dotenv-trust.md).

Each refusal below is printed by `fluid validate`, `fluid secrets check` and the stage itself, and its last sentence is the fix.

### `FLUID_SECRET_SCHEMES`

- **Default:** `env,file,vault,aws-sm`, the four schemes forge resolves itself.
- **Syntax:** comma-separated scheme names. An alias is read as its canonical scheme (`aws` is `aws-sm`, `openbao` is `vault`). Setting it replaces the default, so list every scheme you want, the core ones included. A pack's scheme resolves only when it is listed here.
- **Example:** `export FLUID_SECRET_SCHEMES=env,vault,azure-kv`
- **Refusal:** a reference whose scheme is not listed.

```text
vault://kv/orders/pg#db_pass: the vault:// scheme is not enabled
why: The operator decides which secret stores a contract may read from.
fix: Set it in the operator environment (a shell or CI variable, not a project .env): FLUID_SECRET_SCHEMES="env,file,vault".
```

The fix is the current list plus the scheme: add it to the variable.

### `FLUID_SECRET_PREFIXES`

- **Default:** `file` is limited to `/run/secrets/`. Every other scheme is unrestricted, because the store's own access policy is the first lock.
- **Syntax:** comma-separated `<scheme>://<locator-prefix>` entries. For a scheme you list, your entries replace its default, so `file:///etc/fluid/` alone drops `/run/secrets/`. An entry with no `://` or no prefix is dropped and grants nothing. A prefix ending in `*` matches every locator that starts with it. A prefix ending in `/` matches the locators under it. Any other prefix matches itself and the locators under it, so `kv/orders` covers `kv/orders/pg` and never `kv/orders-old`.
- **Example:** `export FLUID_SECRET_PREFIXES="vault://kv/orders/,file:///run/secrets/,file:///etc/fluid/"`
- **Refusal:** a locator outside every prefix of its scheme. The locator of a `file` reference is its absolute path, and of a `vault` reference `<mount>/<path>`.

```text
vault://kv/orders/pg#db_pass: the locator is outside the prefixes allowed for vault://
why: The operator allows vault:// references under: vault://kv/other/.
fix: If this is intended, add a prefix in the operator environment: FLUID_SECRET_PREFIXES="vault://<prefix>/" (comma-separated, one per entry).
```

The default for `file` follows the model of Kafka Connect's `FileConfigProvider` `allowed.paths`, with one difference: Kafka allows every path when it is unset, and forge allows only `/run/secrets/`.

### `FLUID_SECRET_STAGES`

- **Default:** `apply`.
- **Syntax:** comma-separated stage names, as the pipeline spells them: `apply`, `policy-apply`, `verify`, `publish`, `schedule-sync`, `generate-artifacts`, `validate-artifacts`. `policy_apply` and `policy-apply` are one stage. Setting it replaces the default, so keep `apply` in it. `validate`, `plan`, `bundle` and `diff` are ignored when listed: they never fetch.
- **Example:** `export FLUID_SECRET_STAGES=apply,verify`
- **Refusal:** a stage that is not listed asks for a value.

```text
env://PGPASSWORD: the verify stage may not fetch secret values
why: The operator lets these stages fetch values: apply.
fix: If verify must send this value, set it in the operator environment: FLUID_SECRET_STAGES="apply,verify".
```

A stage that never fetches gives a different refusal, which has nothing to change: `` `fluid plan` never fetches a secret value ``, with the note that the value is read when `fluid apply` runs. A lookup made outside every stage is refused too, and the message says to run the stage that uses the secret.

### `FLUID_ACQUISITION_SECRET_REF_ALLOWLIST`

*(since 0.31.0, [forge-cli #893](https://github.com/Agenticstiger/forge-cli/pull/893))* This variable existed for `env://` references alone, and now covers every scheme. A value from `vault://`, `aws-sm://`, `file://` or a pack is sent to a host that leaves this machine only when this variable allows it. For what it decides for a streaming catalog credential, see [Operator allowlists](../advanced/source-aligned-acquisition.md#operator-allowlists).

- **Default:** empty. A loopback host needs no entry, because sending to your own machine discloses nothing. Every other host needs one.
- **Syntax:** comma-separated entries, in three forms:

  | Entry | Allows |
  |---|---|
  | `NAME` or `NAME@host` | `env://NAME` to any host, or to that host |
  | `<reference>@<host>` or `<reference>@*` | that reference, in any scheme, to that host, or to any host |
  | `<prefix>*@<host>` | every reference that starts with the prefix, to that host |

  The `@<host>` part is required in the reference forms, because a Secrets Manager name may itself contain `@`. A reference is compared in its canonical form, so `aws://x` and `aws-sm://x` are one. A host written with a port never matches: leave the port off. A malformed entry grants nothing.
- **Example:** `export FLUID_ACQUISITION_SECRET_REF_ALLOWLIST="PGPASSWORD@db.example.com,vault://kv/orders/pg#db_pass@*,aws-sm://fluid/orders/*@db.example.com"`
- **Refusal:** a destination that leaves this machine and has no entry. Every host of a connection counts, a host list included, and a port that is not a number counts as a host that cannot be read.

```text
the contract would send environment variable 'PGPASSWORD' to host 'db.example.com' as a credential
why: A contract names both the secret to read and the host it is sent to, so without an operator allowlist any secret this run can read could be sent to a host the contract chose. A loopback host needs no entry; every destination that leaves this machine does.
fix: If this is intended, set it in the OPERATOR environment (a shell or CI variable, not a project .env, which is ignored for this setting): FLUID_ACQUISITION_SECRET_REF_ALLOWLIST="PGPASSWORD@db.example.com" for that host only, or FLUID_ACQUISITION_SECRET_REF_ALLOWLIST="PGPASSWORD" for any host. A host written with a port never matches, so leave the port off.
```

For a reference of another scheme the message names the secret (`secret vault://kv/orders/pg#db_pass`) and suggests `<reference>@<host>` for that host or `<reference>@*` for any host. Prefer the entry for one host.

A Debezium `extra_config` may not set a host or credential key (`database.hostname`, `mongodb.connection.string` and the like) when the connection has a `secretRef`. Such a key would send the resolved value past this check, so it is refused with the key named.

## Vault and OpenBao

*(since 0.31.0, [forge-cli #893](https://github.com/Agenticstiger/forge-cli/pull/893))* `vault://` reads KV v2 through the Vault HTTP API, which OpenBao and HashiCorp Vault both speak. forge does not need the `hvac` package. For OpenBao's own settings see its [client variables](https://openbao.org/docs/commands/), [KV v2](https://openbao.org/docs/secrets/kv/kv-v2/) and [JWT auth](https://openbao.org/docs/auth/jwt/); this section says only what forge reads.

The address, namespace and CA bundle each have a `BAO_` and a `VAULT_` name. forge reads the `BAO_` name first and falls back to the `VAULT_` name only when the `BAO_` one is unset or empty, so when both are set the `BAO_` value wins.

| Setting | Variables, first set wins | Notes |
|---|---|---|
| Address | `BAO_ADDR`, `VAULT_ADDR` | Required. `scheme://host[:port]` only: no path, query or credentials. |
| Namespace | `BAO_NAMESPACE`, `VAULT_NAMESPACE` | Sent as `X-Vault-Namespace`. |
| CA bundle | `BAO_CACERT`, `VAULT_CACERT` | A PEM file that signed the store's certificate. |
| Token | `BAO_TOKEN`, `VAULT_TOKEN` | See the order below. |

The address, the namespace, the CA bundle and every `FLUID_VAULT_` variable are operator-only: a project `.env` cannot set them.

### Which token is used

forge uses the first of these that applies:

1. `FLUID_VAULT_WRAPPED_TOKEN`: a response-wrapped token that a runner hands to one run.
2. `FLUID_VAULT_JWT_ROLE`: a JWT login, for CI.
3. `BAO_TOKEN`, else `VAULT_TOKEN`.
4. The token helper file, `~/.vault-token`, which `bao login` and `vault login` write. It has to be a regular file (not a link) that you own. forge reads that default helper only, and does not read `BAO_TOKEN_PATH`.

So `FLUID_VAULT_JWT_ROLE` beats a `BAO_TOKEN` that is also set. A run with none of them stops with `no store token was found`, and says to sign in, set `BAO_TOKEN` or `VAULT_TOKEN`, set `FLUID_VAULT_JWT_ROLE` in CI, or have a runner hand over `FLUID_VAULT_WRAPPED_TOKEN`.

### JWT login for CI

`FLUID_VAULT_JWT_ROLE` names the role. forge posts the role and the CI job's OIDC token to the JWT auth mount and uses the token it gets back. The [OpenBao JWT auth](https://openbao.org/docs/auth/jwt/) page explains the role and its bound claims.

| Variable | Meaning |
|---|---|
| `FLUID_VAULT_JWT_ROLE` | The role to log in as. Setting it turns the JWT login on. |
| `FLUID_VAULT_JWT` | The JWT itself. It wins over the file when both are set. |
| `FLUID_VAULT_JWT_FILE` | A file that holds the JWT: a regular file of at most 64 KiB, not empty. Prefer it to `FLUID_VAULT_JWT`, so the token stays out of the process environment. |
| `FLUID_VAULT_JWT_MOUNT` | The auth mount. Default `jwt`. |

With a role set and neither `FLUID_VAULT_JWT` nor `FLUID_VAULT_JWT_FILE`, the run stops and says to set `FLUID_VAULT_JWT_FILE`. A refused login names the role and the mount, and says to check the role's bound claims and audience against the job's token. The CI page shows [an OpenBao login in a generated pipeline](../advanced/operating-in-ci.md#what-each-system-gets).

### A response-wrapped token

`FLUID_VAULT_WRAPPED_TOKEN` carries a [response-wrapped](https://openbao.org/docs/concepts/response-wrapping/) token, the per-run handoff of a runner such as Command Center. forge unwraps it once and uses the token inside. A wrapping token works once, so a refused unwrap means it expired or something else used it, and forge says to treat the run's credentials as exposed and to check the store's audit log. A second run in the same process is refused as well: start a new process per run.

### Transport

- **https.** The address is `https`, or `http` to a loopback address only. Plain `http` to any other host is refused, because the token would cross the network in clear text.
- **No redirects.** A redirect from the store is an error and is not followed, because it could carry the token to another host. Point the address at the active node.
- **TLS verification is always on.** `*_SKIP_VERIFY` is not read. A private CA goes in `BAO_CACERT` or `VAULT_CACERT`.
- **One resolved address.** The address is resolved once and the connection is pinned to it. A host that resolves to a cloud metadata address is refused. A request waits 10 seconds.
- **Revocation.** A token that forge obtained, by unwrapping or by a JWT login, is revoked when the run ends (`auth/token/revoke-self`). If the revoke fails it logs a warning, and the token lasts until its TTL. A token you supplied (`BAO_TOKEN`, `VAULT_TOKEN`, the helper file) is yours, and is left alone.

The token's policy needs `read` on `<mount>/data/<path>` to read a secret, and `read` on `<mount>/metadata/<path>` for `fluid secrets check --resolve`. Without the metadata policy, `--resolve` reports `cannot tell`. Only KV v2 is read, and the first path segment is the mount: nested mounts are not supported.

## The run-secrets file

*(since 0.31.0, [forge-cli #893](https://github.com/Agenticstiger/forge-cli/pull/893))* A runner that starts `fluid` can hand it exactly the secrets one run may use, in a file, instead of giving the process an identity in a store. Command Center's `runner-env` does this. The runner sets `FLUID_RUN_SECRETS_FILE` to the file's path. forge never writes the file or deletes it: the runner owns its lifetime.

While the variable is set:

- a reference resolves from the file, and no store is asked, so the process needs no identity of its own;
- a reference the file does not list does not resolve at all, so a contract that names more than its runner granted fails closed.

The scheme, prefix, stage and destination policies still apply to a reference before the file is read.

The file is a JSON object of reference to value:

```json
{
  "env://PGPASSWORD": "a-value-the-runner-chose",
  "vault://kv/orders/pg#db_pass": "another-value"
}
```

Keys are canonical references, and a key is read like any reference: `aws://x` and `aws-sm://x` are one key, and two spellings with different values are refused. A value is a non-empty string. forge checks the file before it reads it, and refuses a file that is:

- not a regular file (a link is refused);
- owned by another user;
- readable by group or others: the mode has to be `0600` or stricter;
- larger than 1 MiB;
- not UTF-8 JSON, or not a JSON object, or holding a key that is not a reference or a value that is not a non-empty string.

A refusal names the path, says why, and says to unset the variable to resolve from the stores instead. It never falls back to the stores by itself. With a file at mode `0644`:

```text
$ FLUID_RUN_SECRETS_FILE=/run/fluid/run-secrets.json fluid secrets check contract.fluid.yaml --resolve
❌ builds[0].properties.source.connection.secretRef: env://PGPASSWORD
   cannot tell: its mode is 0644; group and others must have no access (0600). The runner that sets FLUID_RUN_SECRETS_FILE writes it: a JSON object of {"<reference>": "<value>"}, mode 0600, owned by this user. Unset the variable to resolve from the stores instead.
```

With the same file at mode `0600`, `--resolve` answers from the file:

```text
$ FLUID_RUN_SECRETS_FILE=/run/fluid/run-secrets.json fluid secrets check contract.fluid.yaml --resolve
✅ builds[0].properties.source.connection.secretRef: env://PGPASSWORD
   exists: listed in the run-secrets file
✅ builds[1].properties.source.connection.secretRef: vault://kv/orders/pg#db_pass
   exists: listed in the run-secrets file
All 2 secret references pass.
```

A reference the file does not list is reported as `missing: not listed in the run-secrets file`. At `apply` it is refused with `was not handed to this run`, and the fix is to add the reference to the run's secrets where the runner is configured, or to correct the contract.

`FLUID_RUN_SECRETS_FILE` is operator-only. A project `.env` cannot set it.

## Provider credentials from a store

*(since 0.31.0, [forge-cli #893](https://github.com/Agenticstiger/forge-cli/pull/893))* The credentials forge uses to reach a provider (Snowflake, GCP, AWS) come from a chain: the CLI argument, the environment, the project's `.env`, the OS keyring, then a secret store, then the provider's own default, then a prompt. The secret store is a step only when you name one in `FLUID_CREDENTIAL_STORE`. Setting `GCP_PROJECT` or `AWS_REGION` no longer sends a lookup to a cloud secret manager.

- **Default:** unset, and then no store is asked.
- **Accepted values:** `vault://<mount>/<prefix>` (or `openbao://`), or `aws-sm://<prefix>` (or `aws://`). A store whose secrets hold fields is required, so any other value stops the run with `FLUID_CREDENTIAL_STORE must name a store whose secrets hold fields, such as vault://<mount>/<prefix> or aws-sm://<prefix>`.
- **Where the value is read:** one secret per provider and one field per key, at `<prefix>/<provider>#<key>`. With `FLUID_CREDENTIAL_STORE=vault://kv/fluid/credentials`, the Snowflake `password` is `vault://kv/fluid/credentials/snowflake#password`.
- **A missing secret** falls through to the next source. Any other failure (an unreachable store, a denied read, a reference the policy refuses) stops the run with the reason, because falling through would hide a broken store behind a default or a prompt.
- **Policy:** the scheme and prefix rules apply, so the scheme has to be in `FLUID_SECRET_SCHEMES`.
- **Not stage-gated.** forge names this key, not the contract, and you named the store. So the stage rule and the destination allowlist do not apply, and a `plan` or `diff` against the warehouse connects with the credential it reads here. The rule that `validate`, `plan`, `bundle` and `diff` never fetch is about the references a contract names.

`FLUID_CREDENTIAL_STORE` is operator-only. A project `.env` cannot set it. The [Credential Resolver](../advanced/credential-resolver.md) page describes a different chain, the one for metadata sources.

## `fluid doctor`

`fluid doctor` prints a Secrets table, and `fluid doctor --json` carries the same facts under `secrets`: the enabled schemes, the prefixes, the stages that fetch and the stages that never do, the number of destination entries, the run-secrets file, the credential store, the Vault or OpenBao store (address, auth method, reachability, token TTL) and the installed packs. See [`fluid doctor`](./doctor.md). It never prints a value, never unwraps a wrapped token and never makes a JWT login.

```json
{
  "schemes_enabled": ["aws-sm", "env", "file", "vault"],
  "prefixes": {"file": ["/run/secrets/"]},
  "stages_that_resolve": ["apply"],
  "stages_that_never_resolve": ["bundle", "diff", "plan", "validate"],
  "destination_entries": 0,
  "run_secrets_file": {"set": false},
  "credential_store": null,
  "vault": {"configured": false},
  "aws_sm": {"boto3_installed": false},
  "packs": {}
}
```

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Operation succeeded. For `check`: every reference passed, or the contract has none. |
| `1` | Backend unavailable, secret not found, or user declined the prompt. For `check`: a reference was refused, or with `--resolve` is missing or could not be checked. |
| `2` | `check` could not load the contract, for example because the file does not exist. |

## See also

- [Source-Aligned Acquisition](/forge_docs/advanced/source-aligned-acquisition.html): why pipelines need secrets, and its [Operator allowlists](../advanced/source-aligned-acquisition.md#operator-allowlists)
- [What a project's `.env` may set](../advanced/project-dotenv-trust.md): why the operator's policy comes only from the real environment
- [Environment variables](../advanced/environment-variables.md#secret-references): every variable on this page, in one table
- [Operating in CI](../advanced/operating-in-ci.md): the OpenBao login in a generated pipeline
- [`fluid doctor`](./doctor.md): the Secrets report
- [Credential Resolver](/forge_docs/advanced/credential-resolver.html): how the CLI stores and reads catalog credentials
- [Typed CLI Errors](/forge_docs/advanced/typed-cli-errors.html): `SecretResolutionError`
