# `fluid policy compile`

Compile a contract's `accessPolicy` into provider-specific IAM / GRANT bindings. Pure-function shape: contract in, JSON out. No cloud calls.

`0.8.0` added the unified `fluid policy {check,compile,apply}` subcommand group. The older `fluid policy-compile` form is still registered in 0.18.1, prints no deprecation notice, and takes the same arguments.

This command runs as part of stage 3 (`fluid generate artifacts`) but is also available standalone.

## Syntax

```bash
# New idiomatic form
fluid policy compile CONTRACT [--env ENV] [--out PATH]

# Older form (same behaviour)
fluid policy-compile CONTRACT [--env ENV] [--out PATH]
```

## Key options

| Option | Description |
| --- | --- |
| `CONTRACT` | Path to `contract.fluid.yaml` (positional, required). |
| `--env` | Overlay env to apply before compiling. |
| `--out` | Output bindings path (default `runtime/policy/bindings.json`). |

## Examples

```bash
# New idiomatic form
fluid policy compile contract.fluid.yaml
fluid policy compile contract.fluid.yaml --env prod
fluid policy compile contract.fluid.yaml --out build/bindings.json

# Hyphenated form (still registered)
fluid policy-compile contract.fluid.yaml --env prod
```

## Warnings

*([forge-cli #710](https://github.com/Agenticstiger/forge-cli/pull/710), since 0.20.0)* Each compiler warning goes into the `warnings` array of the output file, and each one other than `No grants found in accessPolicy` is also printed to stderr, as a `policy_compile_warning` log line at WARNING level. Warnings leave the exit code at `0`. A warning can be the only sign that a grant compiled to no binding. Through 0.32.0, a `read` grant on an AWS Iceberg expose that Lakekeeper catalogs compiled to the S3 bucket binding only, and printed:

```bash
fluid policy compile contract.fluid.yaml
```

```text
{"time": "...", "level": "WARNING", "name": "fluid.cli", "message": "policy_compile_warning", "warning": "Iceberg expose 'orders' is cataloged in 'lakekeeper', not AWS Glue, so no table grant was compiled for group:analysts@acme.com ['read']. Enforce it in the 'lakekeeper' catalog's own access control.", "out": "runtime/policy/bindings.json"}
```

*On forge-cli `main`, not yet in a release ([forge-cli #993](https://github.com/Agenticstiger/forge-cli/pull/993)).* That grant now also compiles to a binding for the table in Lakekeeper, and the warning above is no longer printed for a Lakekeeper table. A table whose binding lacks its catalog `uri`, its `warehouse`, its namespace or its `table` gets a different warning, which names the missing keys. See [Lakekeeper tables](#lakekeeper-tables).

A contract with no `accessPolicy` grants gets `No grants found in accessPolicy` in the file only: no grant is left unenforced. [`fluid policy apply`](./policy-apply.md#notes) prints the file's warnings again. Before #710 the warnings were written only to the file.

## Lakekeeper tables

*On forge-cli `main`, not yet in a release ([forge-cli #993](https://github.com/Agenticstiger/forge-cli/pull/993)).*

An Iceberg expose whose `binding.location.catalog` is `lakekeeper` lives in Lakekeeper, so Lakekeeper's own authorization decides who may read or write its table, not a cloud's IAM. For each such table the command writes one binding with `provider: lakekeeper` for each principal the contract gives access to it. They sit in the same file as the bindings of the cloud the expose is on: an AWS expose keeps its S3 bucket bindings. [`fluid policy apply`](./policy-apply.md#lakekeeper-tables) sends them to Lakekeeper.

The command reads the access a contract declares in three places:

- `accessPolicy.grants`, for the exposes a grant's `resources` names. A grant with no `resources` covers every expose, and so do `$.exposes[*]` and `$.exposes`. `$.exposes[?(@.exposeId=='<id>')]` names one. Any other `resources` value cannot be evaluated: it could cover any table, so no Lakekeeper binding is written at all and the command warns, naming the grant.
- The deprecated `metadata.policies`.
- The expose's own `policy.authz.readers` and `policy.authz.writers`. A contract that declares access only there, with no `accessPolicy` grants, still compiles these.

Each permission becomes one of Lakekeeper's table relations:

| Permission | Relation in Lakekeeper |
| --- | --- |
| `read`, `select`, `query` (and an expose's `readers`) | `select` |
| `write`, `insert`, `update`, `delete`, `manage`, `admin` (and an expose's `writers`) | `modify` |
| `create` | None: Lakekeeper grants it on a namespace or a warehouse, never on a table. The command warns that it was not granted. |

In Lakekeeper `modify` includes `select`, which includes `describe`. `manage` and `admin` stop at `modify`: no permission here grants ownership or the right to grant access.

The binding finds the table by its location: `binding.location.uri` (Lakekeeper's catalog URL, `https://<host>/catalog`), `warehouse` (the warehouse's name), `database` (the namespace, where a dot separates levels) and `table`. An excerpt of a contract that grants `read` on one Lakekeeper table to a service account and to a group:

```yaml
accessPolicy:
  grants:
    - principal: serviceAccount:trino
      permissions: [read]
    - principal: group:sales-analysts@corp.com
      permissions: [read]
exposes:
  - exposeId: events_daily
    binding:
      platform: aws
      format: iceberg
      location:
        catalog: lakekeeper
        uri: https://lakekeeper.test/catalog
        warehouse: sales-wh
        database: curated
        table: events_daily
        bucket: sales-lake
        region: eu-west-1
      principals:
        serviceAccount:trino: user:service-account-trino
        group:sales-analysts@corp.com: role:sales-analysts
```

The file `fluid policy compile` writes for it holds two S3 bucket bindings, as before, and one Lakekeeper binding for each principal. The one for the service account:

```json
{
  "provider": "lakekeeper",
  "resource_type": "lakekeeper.table",
  "resource_id": "sales-wh/curated.events_daily",
  "exposeId": "events_daily",
  "catalog_uri": "https://lakekeeper.test/catalog",
  "warehouse": "sales-wh",
  "namespace": ["curated"],
  "table": "events_daily",
  "principal": "serviceAccount:trino",
  "identities": ["user:service-account-trino"],
  "relations": ["select"]
}
```

A table that no grant and no `policy.authz` names gets no binding, so `fluid policy apply` leaves it alone.

### Principals

`binding.principals` maps a principal of a grant to the Lakekeeper identity it stands for, as it maps one to an IAM identity on a cloud. A binding with no `binding.principals` reads each principal as it is written. Once a binding has the key, every principal that is granted access to the table has to be in it, or the table gets no binding (see [below](#what-the-command-warns-about-instead-of-dropping)). `fluid policy apply` finds each identity in Lakekeeper:

| Identity | Found in Lakekeeper as |
| --- | --- |
| `user:oidc~<subject>`, or any `user:` or `serviceAccount:` value with a `~` | The user with that id. It has to exist. |
| `user:<name>`, `serviceAccount:<name>` | The user with exactly that name. A Keycloak client's service account is named `service-account-<client-id>`. |
| `user:<e-mail>`, `serviceAccount:<e-mail>` (a value with `@`) | The user with that e-mail, matched without regard to case, and never by name. |
| `role:<name>`, `role:<id>` | The role with that name, or that id. |
| `group:<name>` | The role with that name. Lakekeeper with OpenFGA reads no group from the identity provider, so create a role of that name in Lakekeeper and add the group's members to it. |
| `[]` | Nothing: the principal is granted nothing. If every principal of a table maps to `[]`, the table gets no binding, and `fluid policy apply` leaves its grants as they are. |

A `domain:` principal has no counterpart in Lakekeeper, and an e-mail under a reserved top-level domain (`.example`, `.test`, `.invalid` or `.localhost`) is a placeholder that no user has. Each is refused with a warning that names the principal and the mapping to write, and the table gets no binding.

A name is matched exactly and an e-mail without regard to case, but an identity provider may let a user choose their own, so only a user's id cannot be claimed by someone else. When a binding names a user by name or e-mail, the command warns, and the best mapping for a person is `user:oidc~<subject>`:

```text
{"time": "...", "level": "WARNING", "name": "fluid.cli", "message": "policy_compile_warning", "warning": "Lakekeeper: ['user:service-account-trino'] are found at apply time by e-mail (a value with @) or else by exact name, among the users Lakekeeper holds. Only user:oidc~<subject> is spoof-proof: an identity provider may let a user set their own name or e-mail, so map people by id in binding.principals.", "out": "runtime/policy/bindings.json"}
```

### What the command warns about instead of dropping

Lakekeeper grants whole tables. Each of these is a warning that says what was not done and how to fix it, and none changes the exit code:

- **A rule Lakekeeper cannot enforce.** An expose that declares `policy.authz.columnRestrictions`, `policy.privacy.masking` or `policy.privacy.rowLevelPolicy` still gets its bindings (`select` for a reader, `modify` for a writer), and a principal that has one reads every column and row with any engine. Grant the table to the identity of a query engine that enforces the rules, and not to the readers they restrict.
- **A table whose binding lacks `uri`, `warehouse`, `database` or `table`.** No grant is compiled for it. The warning names the missing keys.
- **A principal that cannot be mapped.** `fluid policy apply` revokes the grants a contract does not declare on a table it manages, so the table gets no binding at all: with the other principals alone it would revoke the one that is missing. The same holds when another expose names the same table and could not be compiled. Stage 8 then leaves that table's grants as they are, until every principal maps.

## Errors

| Code | When | Exit |
| --- | --- | --- |
| `ERR_POLICY_COMPILER_CRASHED` | *([forge-cli #710](https://github.com/Agenticstiger/forge-cli/pull/710), since 0.20.0)* The policy compiler raised an exception. No bindings file is written; one from an earlier run is left as it was. | 1 |
| `ERR_POLICY_COMPILE_FAILED` | The command failed outside the compiler, for example because the contract or overlay is missing or does not parse, or the bindings file cannot be written. | 1 |

`policy compile` does not validate the contract against its schema, so a value of the wrong type where the compiler reads (`accessPolicy`, its `grants`, a grant's `permissions`, an expose's `binding` and `binding.location`) reaches the compiler. When it crashes there, the error names each such value by path and expected type, never by its content. A grant written as a bare string:

```yaml
accessPolicy:
  grants:
    - group:analysts@acme.com
```

```text
❌ policy_compiler_crashed  [ERR_POLICY_COMPILER_CRASHED]
  error: policy compile failed on contract values of the wrong type: accessPolicy.grants[0] is not of type 'object'

💡 Suggestions:
  • Run 'fluid validate <contract>': policy compile reads accessPolicy and exposes without validating them against the contract schema
  • If the contract validates, re-run with 'fluid --log-level DEBUG policy compile <contract>' to see the compiler's traceback

📖 Documentation: https://agenticstiger.github.io/forge_docs/cli/policy-compile.html#errors
```

When the schema finds no such error, the message is the compiler's own exception: `policy compiler failed: <exception type>: <message>`. The policy step of [`fluid generate artifacts`](./generate-artifacts.md) fails with the same error. Before #710 a crash wrote a bindings file with no bindings and the crash as a warning, and exited `0`, so the next stage read it as no grants to enforce.

## Notes

- Loads the contract with the requested env overlay and emits a JSON document with `bindings` and `warnings` arrays at the `--out` path.
- The compiler embeds `provider` and `project` on each binding so [`fluid policy apply`](./policy-apply.md) can target the right account without extra flags.
- Pair with [`fluid policy check`](./policy-check.md) for static linting and [`fluid policy apply`](./policy-apply.md) for the stage-8 hand-off to the provider (it changes no permissions in 0.18.1, and on forge-cli `main`, not yet in a release ([forge-cli #993](https://github.com/Agenticstiger/forge-cli/pull/993)), it changes only the grants of Lakekeeper tables).
