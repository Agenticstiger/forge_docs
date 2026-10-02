---
title: Upgrading to CLI 0.18.0
description: Breaking changes and migration steps for data-product-forge 0.18.0 — $ref confinement, the DuckDB sandbox, and the public contract-loading API.
---

# Upgrading to CLI `0.18.0`

**Status:** Upgrade notes for `data-product-forge` `0.18.0`. The site's
[pinned docs baseline](./RELEASE_NOTES_0.8.3.md) is unchanged by this page.

## Headline

A contract can no longer make the engine read the machine it runs on.

- **`$ref` composes only files inside the contract's own directory tree.**
  ([forge-cli #687](https://github.com/Agenticstiger/forge-cli/pull/687))
- **Contract SQL runs inside DuckDB's own sandbox.**
  ([forge-cli #689](https://github.com/Agenticstiger/forge-cli/pull/689))
- **A new public API loads a contract exactly as `fluid plan` sees it.**
  ([forge-cli #688](https://github.com/Agenticstiger/forge-cli/pull/688))

These changes come from a security review of the FLUID Command Center, which
runs the engine on user-supplied contracts. The same holes apply to any
service, CI job or shared host that runs contracts its operator did not write.

## Do I need to change anything?

| If your contracts… | Then |
|---|---|
| use `$ref` only to files under the contract's own directory | nothing |
| use `$ref: ../…` to reach another product's or a shared directory | [widen the ref root](#ref-to-files-outside-the-contract-directory) |
| use a `$ref` with a URL (`file://`, `https://`) or an absolute path | [copy the fragment in](#ref-to-files-outside-the-contract-directory) |
| run SQL only on files under the contract's directory or workspace | nothing |
| declare inputs, outputs or acquisition sources at absolute paths elsewhere (`/data/landing/*.csv`) | [allow the directory](#sql-or-declarations-that-read-outside-the-contract-directory) |
| call `read_xlsx`, `sqlite_scan`, `ST_Read`, `delta_scan` or `iceberg_scan` in contract SQL | [convert or land the data](#functions-duckdb-used-to-autoload) |
| install DuckDB yourself at a version below 1.5.0 | [upgrade DuckDB](#upgrade-duckdb) |

## Breaking changes and migration

### `$ref` to files outside the contract directory

Every `$ref` must name a file inside the **ref root**, by default the
directory that holds the root contract. URL refs (`file://` included) and
absolute paths are refused; `..` and symlink escapes are refused after
resolution. The check applies to `fluid validate`, `plan`, `apply` and
`bundle`.

```console
$ fluid validate contract.fluid.yaml
❌ Validation error: contract_load_failed
   error: $ref '../shared/policy.yaml#/gold' at JSON pointer '/exposes/0/policy' in
   /work/orders/contract.fluid.yaml escapes the ref root /work/orders (after resolving
   '..' and symlinks); refs may only name files inside it. ...
```

**Migrate a monorepo** that shares fragments across products: set
`FLUID_REF_ROOT` to the narrowest directory that holds the products and their
shared fragments, per command:

```bash
FLUID_REF_ROOT="$(git rev-parse --show-toplevel)" \
  fluid validate products/orders/contract.fluid.yaml
```

From Python, pass `ref_root=` to `load_contract`, `load_with_overlay` or
`compile_contract` in `fluid_build.loader`.

- A `FLUID_REF_ROOT` that does not contain the contract is ignored for that
  contract, with a `ref_root_env_ignored` warning.
- Do not `export` it: every contract under it is widened without a warning.
- URL and absolute-path refs cannot be allowed by any setting. Copy the
  fragment under the ref root and refer to it by a relative path.

`RefConfinementError` subclasses `RefResolutionError`, so existing
`except RefResolutionError` handlers still catch it.

Full reference: [Composing a contract with `$ref`](./concepts/contract-refs.md).

### SQL or declarations that read outside the contract directory

SQL in a contract can read and write only:

- the contract's directory and its FLUID workspace;
- `./runtime` and the run's scratch directory;
- the locations the contract declares, and only those inside the same roots;
- any directory the operator lists in `FLUID_DUCKDB_ALLOWED_DIRS`.

A declared input, output or acquisition source outside those roots is refused
before any SQL runs:

```console
$ fluid apply contract.fluid.yaml --mode amend-and-build --yes
🔷 Build 'summarise' (embedded-SQL / local DuckDB)
   ❌ Failed: 1 action(s) failed
      The contract declares '/work/reference/rates.csv' (/work/reference/rates.csv),
      outside the directories it may read and write (/work/orders,
      /work/orders/runtime, $TMPDIR/fluid_jl4bqbtc). The operator can allow a directory
      with FLUID_DUCKDB_ALLOWED_DIRS.
```

**Migrate** either by moving the data under the contract's directory or
workspace, or by allowing its directory in the environment that runs `fluid`
(absolute paths, `:`-separated), and declaring the file in the contract:

```bash
FLUID_DUCKDB_ALLOWED_DIRS=/work/reference \
  fluid apply contract.fluid.yaml --mode amend-and-build --yes
```

SQL that reads a path the contract does not declare (`read_csv('/etc/passwd')`,
`../`, an undeclared URL) is refused by DuckDB itself. Declare the location as
an input.

A declared glob grants the directory above its first wildcard, because DuckDB
expands the glob again when the SQL runs; that directory must itself be
inside the allowed roots.

Full reference: [DuckDB sandbox for contract SQL](./advanced/duckdb-sandbox.md).

### Functions DuckDB used to autoload

`sqlite_scan`, `read_xlsx`, `ST_Read`, `delta_scan` and `iceberg_scan` no
longer work in contract SQL. Extension autoloading is off, and contract SQL
cannot `INSTALL` or `LOAD` an extension. **Migrate** by reading CSV, Parquet
or JSON instead, or by landing the data with an acquisition build first.

### Upgrade DuckDB

The `local` extra now requires `duckdb>=1.5.0`, and the engine refuses to open
DuckDB on anything older (`DuckDB 1.4.4 is too old to sandbox contract SQL`).
Older versions let `<dir>/./../` and symlinks escape the allowlist.

```bash
pip install -U 'data-product-forge[local]'
```

### A DuckDB database file can be open once per process

A file DuckDB database already open in the same process can no longer be
opened a second time. It raises a clear `DuckDBSandboxError` instead of
sharing the instance. Two MCP DuckDB drivers bound to the same `.duckdb` file
in one process, or two concurrent `persist=True` local runs, hit this.

Persistent DuckDB secrets (`~/.duckdb/stored_secrets`) are no longer loaded;
object-store builds use the credential-chain secret the engine creates.

## Security

- `$ref` resolution refuses remote, absolute and escaping targets, before it
  tests whether the target exists (#687).
- `fluid validate` on a bundle no longer hands an OpenAPI fragment with an
  external `$ref` to openapi-spec-validator, which followed `file://` refs. It
  reports `OAS-REF-EXTERNAL` instead (#687).
- Every DuckDB connection in the engine goes through one helper,
  `secure_duckdb_connect` (#689). It applies DuckDB's built-in sandbox:
  `allowed_directories` / `allowed_paths`, `enable_external_access = false`,
  autoload and autoinstall off, no persistent secrets, no community
  extensions, and `lock_configuration = true`. Contract SQL can no longer
  read host files, URLs or other databases, or change those settings. A guard
  test fails if a new `duckdb.connect` bypasses the helper.

## Added

- `fluid_build.api.load_contract`, `load_contract_from_text` and
  `load_contract_from_dict` (#688). They return a `LoadedContract` whose
  `contract` is the dict `fluid plan` plans, after parsing, `$ref`
  composition, the env overlay and the engine's alias and legacy-`build:`
  rewrites, plus its plan-digest canonicalisation (`.digest`). Failures raise
  a typed `ContractLoadError`. The `fluid_build.api` version is now `1.1`.
  See [Contract loading API](./advanced/contract-loading-api.md).

## Fixed

- One failed SQL action no longer makes every later action of the same local
  apply fail with "configuration has been locked" (#689).

## See also

- [Composing a contract with `$ref`](./concepts/contract-refs.md)
- [DuckDB sandbox for contract SQL](./advanced/duckdb-sandbox.md)
- [Contract loading API](./advanced/contract-loading-api.md)
- [API Stability](./advanced/api-stability.md)
