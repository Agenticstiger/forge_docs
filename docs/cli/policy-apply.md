# `fluid policy apply`

Stage 8 of the 11-stage pipeline. Reads the compiled bindings file from [`fluid policy compile`](./policy-compile.md) and hands it to the contract's provider.

::: warning As of 0.18.1 this stage changes no cloud permissions
In 0.18.1 `fluid policy apply` does not create IAM bindings, GRANTs or policies on the providers this page lists. The GCP provider reports the compiled bindings and applies none. Every other provider has no policy applier, so the command prints a warning and exits `0`. Access resources reach the cloud through [`fluid apply`](./apply.md), which provisions them with OpenTofu. See [What each provider does](#what-each-provider-does).
:::

*(since 0.33.0, [forge-cli #993](https://github.com/Agenticstiger/forge-cli/pull/993))* A table that Lakekeeper catalogs is the exception: stage 8 reads its grants in Lakekeeper and, with `--mode enforce`, changes them. See [Lakekeeper tables](#lakekeeper-tables).

The unified `fluid policy {check,compile,apply}` group was added in `0.8.0`. The older `fluid policy-apply` form is still registered in 0.18.1 and behaves the same; it prints no deprecation notice.

## Syntax

```bash
fluid policy apply BINDINGS [--mode {check,enforce}]

# Older form, same behaviour
fluid policy-apply BINDINGS [--mode {check,enforce}]
```

## Key options

| Option | Description |
| --- | --- |
| `BINDINGS` | Path to compiled bindings file, typically `runtime/policy/bindings.json` (positional, required). |
| `--mode` | `check` (default) or `enforce`. In 0.18.1 neither mode mutates a provider (see below), so the value only changes the `mode` the provider reports. *(since 0.33.0, [forge-cli #993](https://github.com/Agenticstiger/forge-cli/pull/993))* On a Lakekeeper table, `check` reads the table's grants and plans the difference and changes nothing, and `enforce` applies the plan. |

The provider is not a flag of this command. Set it before the subcommand (`fluid --provider gcp policy apply ...`) or with `FLUID_PROVIDER`.

## What each provider does

| Provider named in the bindings | What `fluid policy apply` does |
| --- | --- |
| `gcp` | Reports the compiled bindings and returns `status: ok` with `applied: 0`, in both modes. The provider's own message says GCP IAM is provisioned declaratively by `fluid apply` from the contract, and that this stage does not mutate IAM through the Google SDK. |
| `aws`, `snowflake`, `local`, and any other provider without an applier | Prints `No policy bindings were enforced` and says the provider has no standalone policy applier. Exit `0`. |
| `lakekeeper`, a binding that [`fluid policy compile`](./policy-compile.md#lakekeeper-tables) writes for an Iceberg table that Lakekeeper catalogs | *(since 0.33.0, [forge-cli #993](https://github.com/Agenticstiger/forge-cli/pull/993))* Reads the table's grants in Lakekeeper itself and, with `--mode enforce`, applies the difference, whatever cloud the expose is on. See [Lakekeeper tables](#lakekeeper-tables). |
| any provider, `bindings` empty | Succeeds without resolving a provider. A contract with no `accessPolicy` grants compiles to zero bindings. |

For the cloud providers the grants, masking and row-access policies come from `fluid apply` (stage 7). For GCP that includes the column-level policy tags that `policy.authz.columnRestrictions` produces; `fluid policy compile` does not model them, so they never appear in `bindings.json`.

The AWS case, measured against 0.18.1 with the bindings file from [`fluid policy compile`](./policy-compile.md):

```text
⚠️  No policy bindings were enforced — the 'aws' provider has no standalone
policy applier. For cloud providers, IAM/GRANT, masking and row-access policies
are emitted and applied during `fluid apply` (stage 7), so `fluid policy-apply`
is a no-op for this provider.
```

::: tip Constructing a cloud provider can call the cloud
`fluid policy apply` builds the provider named in the bindings before it knows the provider has nothing to apply. With an AWS bindings file on a machine that had AWS credentials, the log line `provider_initialized` carried the caller's account id, so the AWS SDK had made an identity call. Run it where that is acceptable, or leave this stage out of a pipeline whose providers have no applier.
:::

## Lakekeeper tables

*(since 0.33.0, [forge-cli #993](https://github.com/Agenticstiger/forge-cli/pull/993))*

A binding with `provider: lakekeeper` goes to Lakekeeper itself, through its management API, and never to a cloud. [`fluid policy compile`](./policy-compile.md#lakekeeper-tables) writes one for each principal that has access to an Iceberg table that Lakekeeper catalogs. A bindings file can hold both kinds: the bindings of a cloud go to its provider first, as before, and the Lakekeeper ones after them. A file with Lakekeeper bindings alone builds no provider, so it needs no cloud credentials.

### What a run does

For each table the bindings name, in both modes, the command:

1. finds the warehouse by its name, and the table in its namespace;
2. reads the table's direct grants;
3. plans the grants to add and the grants to remove, so that the table's `describe`, `select` and `modify` grants are the ones the contract declares.

`--mode enforce` then sends the plan in one request per table, which holds the grants and the revokes together. A plan of more than 100 changes goes in requests of 100, with the grants first. `--mode check` stops after the plan and changes nothing. Both modes read the table, so both sign in to Lakekeeper with [the operator's settings](#the-operator-s-settings).

Only the three data relations are managed, and only on a table the bindings name. The contract's grants are added, and any other direct `describe`, `select` or `modify` grant on that table is removed, one a person added by hand in Lakekeeper included. Ownership, `pass_grants`, `manage_grants` and `manage_tags` are never compared and never changed. A table that no binding names is left alone.

The output below is from forge-cli's own test double of Lakekeeper's API, not from a Lakekeeper server. It holds the table `curated.events_daily` in the warehouse `sales-wh`, two users, a role, and a `select` grant to a user that the contract does not declare. The bindings are the ones [`fluid policy compile`](./policy-compile.md#lakekeeper-tables) writes from the contract excerpt on that page: `select` for a service account and for a role.

```bash
fluid policy apply runtime/policy/bindings.json --mode check
```

```text
Lakekeeper https://lakekeeper.test: signed in as lab-admin (oidc~admin)
  + sales-wh/curated.events_daily: would grant select to group:sales-analysts@corp.com (role 0190c5b4-0000-7000-8000-0000000000e1)
  + sales-wh/curated.events_daily: would grant select to serviceAccount:trino (user oidc~trino)
  - sales-wh/curated.events_daily: would revoke select from user oidc~probe (service-account-lab-probe)
Lakekeeper: 1 table(s): 2 grant(s) and 1 revoke(s) to apply, 0 unchanged; check mode changed nothing (--mode enforce applies them).
```

The same command with `--mode enforce` prints `grant` and `revoke` where `check` prints `would grant` and `would revoke`, and ends with `Lakekeeper: 1 table(s): 2 grant(s) and 1 revoke(s) applied, 0 unchanged.` Run again, it finds nothing to do:

```text
Lakekeeper https://lakekeeper.test: signed in as lab-admin (oidc~admin)
  = sales-wh/curated.events_daily: 2 grant(s) already in place
Lakekeeper: 1 table(s): 0 grant(s) and 0 revoke(s) to apply, 2 unchanged; check mode changed nothing (--mode enforce applies them).
```

Each line about a table starts with one mark:

| Mark | Meaning |
| --- | --- |
| `+` | A grant, or a grant that `check` would make. |
| `-` | A revoke, or one that `check` would make. |
| `=` | The table's grants are already the ones the contract declares. |
| `?` | The table does not exist yet. |
| `x` | The table failed, and the line says why. |

The command exits `0` when every table was checked or applied, and `1` when any table failed. A failure on one table does not stop the others. Without a credential, `--mode check` prints `Lakekeeper: 1 table(s) not checked, no Lakekeeper credential is configured: ...` and exits `0`, and `--mode enforce` fails with the same reason and `no grant was applied`.

### A table that does not exist yet

A Lakekeeper table is created by whatever writes it, the build or a sink at its first commit, and not by `fluid apply`. A first deploy therefore reaches stage 8 before the table exists. That is not a failure in either mode: the table is marked `?`, no grant is applied on it, the exit code stays `0`, and the summary counts it as `not created yet`:

```text
Lakekeeper https://lakekeeper.test: signed in as lab-admin (oidc~admin)
  ? sales-wh/curated.events_daily does not exist in Lakekeeper yet (or the identity forge signed in as cannot see it): its 2 grant(s) were not applied. Its writer creates it (the build, or the sink at its first commit); run policy-apply again then.
Lakekeeper: 1 table(s): 0 grant(s) and 0 revoke(s) applied, 0 unchanged, 1 table(s) not created yet.
```

Run the stage again once the writer has created the table. The same line appears when the identity forge signed in as cannot see the table.

### When a table is left as it is

The plan revokes what the contract does not declare, so a plan made from part of the contract would remove access that someone should have. Whenever the command cannot be sure of the plan, it stops on that table, says why, and carries on with the other tables. It changes nothing on the table, except after a later request of a large plan fails (the last item):

- **A principal cannot be found in Lakekeeper.** No user has the name, the e-mail or the id, or more than one does, or no role has the name or the id. The line reads `nothing was changed on this table, because a principal could not be resolved`, and names the principal and, in most cases, the mapping to write in `binding.principals`. A user exists in Lakekeeper once they have signed in.
- **Lakekeeper refuses a read or a change.** On a `403` the line says what the identity needs. See [The identity forge signs in as](#the-identity-forge-signs-in-as). A refused token (`401`) points at `FLUID_LAKEKEEPER_SCOPE`: on the first request it is the sign-in failure of the next item, and on a later one it is a line for that table.
- **forge cannot sign in.** The token endpoint refuses the client, the reference is not allowed for the catalog's host, a URL is not `https://`, or Lakekeeper refuses the token (`401`) or answers the first request with a redirect. Every table of that Lakekeeper fails with one line that says why, and not one line for each table.
- **The warehouse is unknown to the identity.** Lakekeeper hides a warehouse that a caller may not see.
- **The table is outside the operator's list of namespaces.** See [The operator's settings](#the-operator-s-settings).
- **A binding does not describe the table's grants.** It names no warehouse, namespace or table, holds an unrendered `{{ }}` or `${ }` template, or names no identity or no relation. The line names the problem and says to compile the bindings again.
- **Lakekeeper keeps answering `409`**, a concurrent change. The command tries up to three times in all, reading and planning the table again before each retry, and then stops with `Run policy-apply again.`
- **A later request of a large plan fails.** A plan of more than 100 changes goes in several requests. The line then lists the changes that landed before the failure.

```text
Lakekeeper https://lakekeeper.test: signed in as lab-admin (oidc~admin)
  x sales-wh/curated.events_daily: nothing was changed on this table, because a principal could not be resolved: serviceAccount:trino: no Lakekeeper user has the name 'service-account-trino'. A user appears in Lakekeeper once it has signed in; a Keycloak client's service account is named service-account-<client-id>. Map the principal in binding.principals to the user's id (user:oidc~<subject>), the one spelling no user can choose.
Lakekeeper: 1 table(s): 0 grant(s) and 0 revoke(s) applied, 0 unchanged, 1 table(s) failed.
```

### The operator's settings

The contract names the tables, so the operator, and not the contract, decides which Lakekeeper forge signs in to, with what, and which namespaces it may change. Each variable is read only from the real environment of the job that runs `fluid policy apply`: a project `.env` cannot set any of them.

| Variable | What it holds |
| --- | --- |
| `FLUID_LAKEKEEPER_CREDENTIAL_REF` | A [secret reference](./secrets.md) to `client_id:client_secret`, the shape of Iceberg's `credential` catalog property. forge asks the token endpoint for a client-credentials token. Needs the next two variables. |
| `FLUID_LAKEKEEPER_OAUTH2_SERVER_URI` | The token endpoint. |
| `FLUID_LAKEKEEPER_SCOPE` | The scope to ask for. Behind Keycloak, the scope whose audience mapper names Lakekeeper. |
| `FLUID_LAKEKEEPER_TOKEN_REF` | A secret reference to a bearer token, used as it is. Set this or `FLUID_LAKEKEEPER_CREDENTIAL_REF`, not both. |
| `FLUID_LAKEKEEPER_NAMESPACE_ALLOWLIST` | The namespaces whose tables stage 8 may change: comma-separated `<warehouse>/<namespace prefix>` entries, matched on whole dotted levels. `sales-wh/curated` allows `curated` and `curated.eu` in `sales-wh`, and not `curated_old`. A `*` is an ordinary character, not a wildcard. **Unset allows none.** |

- **The references.** A reference is `env://`, `file://`, `vault://` or `aws-sm://`, as in [Secret references](./secrets.md). It has to be allowed for the catalog's host in [`FLUID_ACQUISITION_SECRET_REF_ALLOWLIST`](./secrets.md#fluid-acquisition-secret-ref-allowlist) before it is read: `NAME@host` for an `env://NAME` reference, or the full reference followed by `@host`. That entry pins the host only, and the contract still chooses the port and the path of `binding.location.uri`, so give Lakekeeper a host of its own and allow the reference for that host, not for any host. A loopback host needs no entry.
- **TLS.** `binding.location.uri`, and the token endpoint when `FLUID_LAKEKEEPER_CREDENTIAL_REF` is used, have to be `https://` URLs, a loopback address too. forge sends the client secret to the token endpoint and a bearer token to Lakekeeper, and follows no redirect from either. For a private CA, set `REQUESTS_CA_BUNDLE` or `SSL_CERT_FILE` to its bundle.
- **The allowlist.** A table outside it fails the run, with exit `1`. In `enforce` mode it is refused before any request for it: nothing is read and no token is requested. In `check` mode forge still reads the table and shows the plan, then reports the refusal that `enforce` would make. Take the list from configuration that the product cannot edit, and never from the contract the run applies: a list built from the contract lets any contract allow itself.

The refusal names the entry to export. In `enforce` mode the line reads:

```text
  x sales-wh/curated.events_daily: its namespace is not in FLUID_LAKEKEEPER_NAMESPACE_ALLOWLIST (unset allows none), so policy-apply changes no grant on it. If this product may manage that namespace, allow it in the operator environment: export FLUID_LAKEKEEPER_NAMESPACE_ALLOWLIST="sales-wh/curated"
```

In `check` mode the same text follows `enforce mode would refuse it:`.

### The identity forge signs in as

The identity needs the right to manage grants on the tables: `manage_grants` on the table, its namespace or its warehouse (an owner has it unless managed access is on), or `security_admin` on the project. It also reads the warehouses, the tables of each namespace, and the users and roles it has to find.

The contract names the tables, so a contract can claim any table in an allowed namespace that the identity may manage. Give stage 8 an identity that manages only the product's own namespaces, and list only those in the allowlist. On Lakekeeper with OpenFGA, the identity that creates a namespace owns it, which is enough. forge-cli's checks of the API were against Lakekeeper v0.14.0, through its OpenFGA assignments API.

### What it does not do

- **It grants whole tables.** A principal with `select` reads every column and row, with any engine. `policy.authz.columnRestrictions`, masking and row filters are not enforced by Lakekeeper, and [`fluid policy compile`](./policy-compile.md#what-the-command-warns-about-instead-of-dropping) warns about each.
- **It never grants ownership or the right to grant.** `manage` and `admin` become `modify`.
- **It does not create a table or a user.** A principal that Lakekeeper has not seen fails its table.

## Pipeline ordering

Stage 8 runs **after** stage 7 apply and **before** stage 9 verify. The Jenkins and 7-system CI templates from `fluid generate ci` wire it in. The stage is self-gated on `dist/artifacts/policy/bindings.json` existing, so contracts that do not emit policy bindings skip it.

## Examples

### Report the compiled bindings

```bash
fluid policy apply runtime/policy/bindings.json
# exit 0 when the provider returns ok or noop; exit 1 for any other status
```

### Pass the provider explicitly

```bash
fluid --provider gcp policy apply runtime/policy/bindings.json --mode enforce
```

### Older hyphenated form

```bash
fluid policy-apply runtime/policy/bindings.json --mode enforce
# same as: fluid policy apply runtime/policy/bindings.json --mode enforce
```

## Errors

| Code | When | Exit |
| --- | --- | --- |
| [`ERR_PROVIDER_NOT_SPECIFIED`](./providers.md#err-provider-not-specified) | The bindings carry a binding with no `provider`, and neither `--provider` nor `FLUID_PROVIDER` is set. | 2 |
| [`ERR_PROVIDER_UNKNOWN`](./providers.md#err-provider-unknown) | The bindings name a provider that is not registered. | 2 |
| `ERR_POLICY_APPLY_FAILED` | The file is not valid JSON, or the provider raised. Passing a contract instead of a bindings file ends here. | 1 |

## Notes

- Provider and project are read from the first binding that sets them. `fluid policy compile` writes both from the contract's `binding.platform` and `binding.location`. A provider given by flag or environment overrides the file's.
- Returns `0` for `ok` or `noop` results, `1` otherwise.
- *([forge-cli #710](https://github.com/Agenticstiger/forge-cli/pull/710), since 0.20.0)* Before it hands the bindings to the provider, the command prints each warning in the file's `warnings` array other than `No grants found in accessPolicy` to stderr, as a `policy_bindings_warning` log line at WARNING level, so a grant that [compiled to no binding](./policy-compile.md#warnings) shows in a job that runs apply apart from compile. The warnings do not change the exit code.
- Compile bindings first with [`fluid policy compile`](./policy-compile.md); see [`fluid policy check`](./policy-check.md) for static linting of the access policy.
- Both spellings share one argument set. Prefer `fluid policy apply` in new code; the hyphenated form is still registered in 0.18.1.
