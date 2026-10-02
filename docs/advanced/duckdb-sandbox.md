---
title: DuckDB sandbox for contract SQL
description: What SQL inside a contract can read and write on the local DuckDB engine, how to grant more, and the limits of the sandbox.
---

# DuckDB sandbox for contract SQL

From CLI 0.18.0, every DuckDB connection the engine opens runs inside
DuckDB's own sandbox. SQL in a contract can read and write the contract's
directory and the locations the contract declares. It cannot read the rest of
the host, fetch a URL the contract does not declare, attach another database,
install an extension, or change those settings.

::: warning Breaking in 0.18.0
- A declared input, output or acquisition source **outside the allowed
  directories is refused before any SQL runs**, including absolute landing
  paths such as `/data/landing/*.csv`. The operator allows a directory with
  [`FLUID_DUCKDB_ALLOWED_DIRS`](#reading-a-file-from-another-directory).
- **Functions DuckDB used to autoload no longer work in contract SQL**:
  `sqlite_scan`, `read_xlsx`, `ST_Read`, `delta_scan`, `iceberg_scan`.
- The `local` extra requires **`duckdb>=1.5.0`**, and the engine refuses to
  open DuckDB on anything older.

Migration steps are in the [0.18.0 upgrade notes](../RELEASE_NOTES_0.18.0.md).
:::

## Example

The build below reads the contract's own CSV. It works as before:

```yaml
# orders/parts/build.yaml
id: summarise
pattern: embedded-logic
engine: sql
properties:
  sql: SELECT id, amount * 2 AS doubled FROM read_csv('data/orders.csv')
```

```console
$ fluid apply contract.fluid.yaml --mode amend-and-build --yes
🔷 Build 'summarise' (embedded-SQL / local DuckDB)
   ✅ Completed in 0.02s — 1 action(s) executed
   📁 /work/orders/out/summary.csv
```

The same build pointed at a host file is refused by DuckDB:

```yaml
  sql: SELECT * FROM read_csv('/etc/passwd')
```

```console
$ fluid apply contract.fluid.yaml --mode amend-and-build --yes
🔷 Build 'summarise' (embedded-SQL / local DuckDB)
   ❌ Failed: 1 action(s) failed
      Permission Error: Cannot access file "/etc/passwd" - file system operations are
      disabled by configuration DuckDB refused it: contract SQL may only read and write
      the locations the contract declares and its own directory (/work/orders,
      /work/orders/runtime, $TMPDIR/fluid_gxyqoqe4, /work/orders/out/summary.csv).
      Declare the file as an input under the contract's directory or workspace, or move
      it there (the operator can allow another directory with FLUID_DUCKDB_ALLOWED_DIRS).
```

The list in parentheses is exactly what that build's SQL may touch: the
contract's directory, `./runtime`, the run's scratch directory, and the
declared output.

## What SQL is refused

The same message (`DuckDB refused it: …`) follows each of these:

| SQL in the contract | DuckDB's error |
|---|---|
| `read_csv('/etc/passwd')`, `read_text(...)`, `read_blob(...)`, `read_parquet(...)`, `read_json(...)`, `glob('/etc/*')` on a path outside the list | `Permission Error: Cannot access file …` |
| `read_csv('../shared/x.csv')`, `<dir>/./../`, a symlink that points outside | `Permission Error: Cannot access file …` |
| `read_csv('https://example.com/x.csv')`, or any URL the contract does not declare | `File https://… requires the extension httpfs to be loaded` |
| `INSTALL httpfs`, `LOAD …` | `Permission Error: Cannot access directory "~/.duckdb/extensions/…"` |
| `SET enable_external_access = true`, or any other `SET` | `Cannot change configuration option … - the configuration has been locked` |
| `read_xlsx(...)`, `sqlite_scan(...)`, `ST_Read(...)`, `delta_scan(...)`, `iceberg_scan(...)` | `Catalog Error: Table Function with name "read_xlsx" is not in the catalog` |

`ATTACH` of another database file and `COPY … TO` / `COPY … FROM` a location
outside the list are refused the same way. `~/…` is refused unless the
matching file under `$HOME` is itself in the list.

### Functions that used to autoload

DuckDB used to install and load an extension the first time a query called
one of its functions. With autoloading off, functions from extensions the
engine does not load for that build are not in the catalog, even for a file
inside the contract's directory:

```console
   ❌ Failed: 1 action(s) failed
      Catalog Error: Table Function with name "read_xlsx" is not in the catalog, but it
      exists in the excel extension. ... DuckDB refused it: contract SQL runs with
      extension autoloading off and cannot INSTALL or LOAD one, so functions from
      extensions the engine does not load (sqlite_scan, read_xlsx, ST_Read, delta_scan,
      iceberg_scan) are not available. Read the data as CSV, Parquet or JSON, or land it
      with an acquisition build first.
```

DuckDB's own hint in that message (`INSTALL excel; LOAD excel;` or
`SET autoload_known_extensions=1`) does not apply: contract SQL cannot run
either. Convert the file to CSV, Parquet or JSON, or land the data with an
acquisition build first.

## What each kind of SQL can reach

| Where the SQL runs | It can read and write |
|---|---|
| Embedded-SQL build on the local DuckDB engine (`builds[].properties.sql`) | the contract's directory, the FLUID workspace it sits in (`fluid.workspace.yaml`), `./runtime`, the run's scratch directory, each declared `parameters.inputs[].path`, each resolved `consumes[]` upstream, the expose's landing path, and the `s3://` prefixes those name. A declared local path counts only [inside the allowed directories](#declared-locations-stay-inside-the-allowed-directories). |
| DuckDB acquisition build (`pattern: acquisition`, `engine: duckdb`) | the contract's directory, the declared `source.connection.uri` (or stream paths), and each stream's landing file, each inside the allowed directories. A `mysql` source is attached before the sandbox closes; so is a `sqlite` source, and its file must also be inside the allowed directories. |
| `fluid validate` quality rules, `fluid verify`, `fluid diff` | the one file being checked |
| `fluid contract-tests` local actions | each declared input file and each output file |
| Discovery (`fluid forge data-model from-source`, `discover`) | the one file or URL being introspected; a JDBC source is attached first |
| MCP output port (DuckDB driver) | the bound file |

## Declared locations stay inside the allowed directories

Each declared input and output is granted to the build's SQL, and whoever
writes the contract writes the declarations. So a declaration grants a local
path only inside these directories:

- the contract's directory and the FLUID workspace it sits in;
- `./runtime` and the run's scratch directory;
- the upstream roots in `FLUID_UPSTREAM_CONTRACTS`;
- the directories the operator lists in `FLUID_DUCKDB_ALLOWED_DIRS`.

Anything else is refused before any SQL runs. Declaring an innocuous glob in
`$HOME` does not make `~/.aws/credentials` readable:

```yaml
properties:
  sql: SELECT content FROM read_text('~/.aws/credentials')
  parameters:
    inputs:
      - name: d
        path: /home/me/*.csv
```

```console
$ fluid apply contract.fluid.yaml --mode amend-and-build --yes
🔷 Build 'summarise' (embedded-SQL / local DuckDB)
   ❌ Failed: 1 action(s) failed
      The contract declares '/home/me/*.csv' (/home/me), outside the directories it may
      read and write (/work/orders, /work/orders/runtime, $TMPDIR/fluid_tb4ky08e). The
      operator can allow a directory with FLUID_DUCKDB_ALLOWED_DIRS.
```

Both sides are compared after resolving symlinks, as DuckDB resolves them: a
symlink inside the contract's directory that points at `/` grants nothing. A
relative declared path is resolved where DuckDB opens it, the working
directory, and is confined the same way.

What a declaration grants, once allowed:

| Declared | Granted |
|---|---|
| a file (`/shared/reference/rates.csv`) | that file |
| a glob (`data/*.csv`, `landing/**/*.parquet`) | the directory above its first wildcard (`data/`, `landing/`), which must itself be inside the allowed directories |
| a directory (`data/`) | everything under it |
| an `s3://` URL | its prefix (see [the limits](#limits)) |

A glob grants its directory, not the files it matches when the run starts,
because DuckDB expands the glob again when the SQL runs. DuckDB checks each
expanded file after resolving symlinks, so a matched symlink that points
outside the directory is refused.

A `[`, `?` or `*` in the name of a directory that exists (for example a
project checked out under `Proj [old]/`) is part of that name, not a wildcard.

### `./runtime` that is a symlink

`./runtime` is granted by convention, not by a declaration. It is granted only
when it is a real directory, or a symlink into the contract's directory or
workspace. A repository that ships `runtime` as a symlink out of itself does
not get that directory granted: the symlink is ignored with a
`local_runtime_not_granted` warning, and SQL that reads or writes under it is
refused.

### SQLite sources

A SQLite acquisition source (`source.kind: sqlite`) is confined the same way,
and refused with the same `FLUID_DUCKDB_ALLOWED_DIRS` message outside the
allowed directories. This check is the only one on it: the sqlite scanner
opens the file through its own library, which DuckDB's allowlist does not
bound.

## Reading a file from another directory

The operator allows the directory; the contract then declares the file. In
the build below the declared input is available to the SQL as the view
`rates`:

```yaml
id: summarise
pattern: embedded-logic
engine: sql
properties:
  sql: >-
    SELECT o.id, o.amount * r.rate AS doubled
    FROM read_csv('data/orders.csv') o JOIN rates r USING (id)
  parameters:
    inputs:
      - name: rates
        path: /work/reference/rates.csv
```

Without the variable, the declaration is refused before any SQL runs:

```console
$ fluid apply contract.fluid.yaml --mode amend-and-build --yes
🔷 Build 'summarise' (embedded-SQL / local DuckDB)
   ❌ Failed: 1 action(s) failed
      The contract declares '/work/reference/rates.csv' (/work/reference/rates.csv),
      outside the directories it may read and write (/work/orders,
      /work/orders/runtime, $TMPDIR/fluid_jl4bqbtc). The operator can allow a directory
      with FLUID_DUCKDB_ALLOWED_DIRS.
```

With it, the build runs:

```console
$ FLUID_DUCKDB_ALLOWED_DIRS=/work/reference \
    fluid apply contract.fluid.yaml --mode amend-and-build --yes
🔷 Build 'summarise' (embedded-SQL / local DuckDB)
   ✅ Completed in 0.02s — 1 action(s) executed
   📁 /work/orders/out/summary.csv
```

The declared file becomes readable. Its neighbours in `/work/reference` do
not, unless the contract declares them too (or declares a glob or the
directory). Reading an undeclared neighbour is refused, and the list in the
message now includes the declared file:

```console
      Permission Error: Cannot access file "/work/reference/neighbour.csv" - file system
      operations are disabled by configuration DuckDB refused it: contract SQL may only
      read and write the locations the contract declares and its own directory
      (/work/orders, /work/orders/runtime, $TMPDIR/fluid_ft7ya_8s,
      /work/reference/rates.csv, /work/orders/out/summary.csv). ...
```

### `FLUID_DUCKDB_ALLOWED_DIRS`

- Absolute directories, separated by `:` (`;` on Windows). `~` is expanded.
- Read from the environment of the process that runs the engine. No contract
  field can set it.
- A relative entry, or `/`, fails the run:

  ```console
  $ FLUID_DUCKDB_ALLOWED_DIRS=relative/dir fluid apply contract.fluid.yaml --mode amend-and-build --yes
     ❌ Failed: 1 action(s) failed
        FLUID_DUCKDB_ALLOWED_DIRS entry 'relative/dir' is not an absolute path

  $ FLUID_DUCKDB_ALLOWED_DIRS=/ fluid apply contract.fluid.yaml --mode amend-and-build --yes
     ❌ Failed: 1 action(s) failed
        FLUID_DUCKDB_ALLOWED_DIRS entry '/' is the filesystem root
  ```

- It lets a contract *declare* a location in that directory. It does not make
  the directory readable to SQL that has not declared it.

A product inside a FLUID workspace can also read its sibling products' files
by path, because the workspace is an allowed directory, and a `consumes[]`
entry resolves to the upstream's landed file.

## How it works

`fluid_build/providers/_duckdb_sandbox.py` (`secure_duckdb_connect`) is the one
place the engine calls `duckdb.connect`; a test fails if any other module
opens DuckDB without it. For each connection it:

1. connects (a file-backed database is opened here and needs no grant);
2. turns off persistent secrets and community extensions, loads the
   extensions the call site needs, and runs its set-up (an `ATTACH` of a
   declared source, an object-store secret);
3. turns off extension autoinstall and autoload;
4. pins `home_directory` to `$HOME`, then sets `allowed_directories` and
   `allowed_paths`;
5. sets `enable_external_access = false`;
6. sets `lock_configuration = true`.

These are DuckDB's own settings, in the order the
[Securing DuckDB](https://duckdb.org/docs/current/operations_manual/securing_duckdb/overview.html)
guide gives.

## Limits

- **DuckDB 1.5.0 or newer.** Up to 1.4.3, `<dir>/./../` escaped
  `allowed_directories`, and through 1.4.x a symlink inside an allowed
  directory reached its target. On an older DuckDB every build fails:

  ```console
  🔷 Build 'summarise' (embedded-SQL / local DuckDB)
     ❌ Failed: 1 action(s) failed
        DuckDB 1.4.4 is too old to sandbox contract SQL
  ```

  Upgrade with `pip install 'duckdb>=1.5.0'`, or reinstall
  `data-product-forge[local]`.
- **A remote prefix bounds the bucket, not the path.** DuckDB 1.5 does not
  resolve `..` inside a URL, so a declared `s3://bucket/landing/` also lets the
  SQL reach other keys in that bucket with the same credentials.
- **A loaded database scanner is not bounded by the allowlist.** The `sqlite`,
  `postgres` and `mysql` extensions open files and sockets through their own
  client libraries. The engine loads them only for an acquisition build's
  declared source, discovery, and the copilot's sample-rows tool, whose SQL the
  engine builds from validated identifiers. Contract SQL never runs on such a
  connection.
- **One open connection per database file.** DuckDB shares one instance per
  database file within a process, and the sandbox locks that instance. A second
  connection to a file that is already open raises `DuckDBSandboxError`
  (`DuckDB database … is already open in this process`). Two MCP DuckDB
  drivers bound to the same `.duckdb` file in one process, or two concurrent
  `persist=True` local runs, hit this.
- **Persistent DuckDB secrets are off.** Secrets saved in
  `~/.duckdb/stored_secrets` are no longer loaded; object-store builds use the
  credential-chain secret the engine creates.
- **Defense in depth, not isolation.** DuckDB describes these settings as not a
  substitute for proper sandboxing. A service that runs other people's
  contracts (the Command Center, a shared CI runner) should still run each one
  in its own container.

## Related

- [Composing a contract with `$ref`](../concepts/contract-refs.md): the matching confinement for contract fragments
- [Local provider](../providers/local.md)
- [Upgrading to 0.18.0](../RELEASE_NOTES_0.18.0.md)

::: tip About the examples
Output on this page was produced with the 0.18.0 code (forge-cli
[#689](https://github.com/Agenticstiger/forge-cli/pull/689)) and DuckDB 1.5.6.
Only the build block of each run is shown. Long temporary paths are shortened
to `/work` and `$TMPDIR`, `$HOME` is shown as `/home/me`, and long lines are
re-wrapped.
:::
