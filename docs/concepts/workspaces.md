---
title: Workspaces
description: fluid.workspace.yaml marks a workspace root. It lets chained products find each other's contracts, declares each product's environments, and bounds what contract SQL may read.
---

# Workspaces

A **workspace** is a directory tree of data products with a
`fluid.workspace.yaml` file at its root. The file holds team defaults, and it
is how one product's build finds the contracts of the products it consumes.

```text
acme-sales/
├── fluid.workspace.yaml       # the workspace root
├── .fluid/team-memory.yaml    # conventions for `fluid forge` (optional)
├── raw-orders/
│   ├── contract.fluid.yaml    # id: sales.raw_orders_v1
│   └── data/orders.csv
└── order-totals/
    └── contract.fluid.yaml    # consumes sales.raw_orders_v1 / orders
```

::: tip Not the `fluid workspace` command
[`fluid workspace`](../cli/workspace.md) is a separate team-collaboration tool
that keeps members, contract versions and change requests in a SQLite database
under `./.fluid-workspace/`. It does not read or write `fluid.workspace.yaml`,
and nothing on this page depends on it.
:::

## Example: a product that reads another product

```yaml
# order-totals/contract.fluid.yaml (excerpt)
consumes:
  - productId: sales.raw_orders_v1
    exposeId: orders
builds:
  - id: totals
    pattern: embedded-logic
    engine: sql
    properties:
      sql: SELECT customer_id, SUM(amount) AS total FROM orders GROUP BY customer_id
    outputs: [order_totals]
```

The SQL reads `orders`, the `exposeId` of the upstream. Build the upstream, then
the downstream:

```console
$ cd raw-orders && fluid apply contract.fluid.yaml --mode amend-and-build --yes
...
$ cd ../order-totals && fluid apply contract.fluid.yaml --mode amend-and-build --yes
...
🔷 Build 'totals' (embedded-SQL / local DuckDB)
   ⬅ consumes sales.raw_orders_v1/orders as view "orders":
/.../acme-sales/raw-orders/output/orders.parquet
...
   ✅ Completed in 0.06s — 1 action(s) executed
```

Without `fluid.workspace.yaml` above the contract, the same build fails before
any SQL runs:

```console
   ❌ consumes sales.raw_orders_v1/orders: no contract in the workspace declares id 'sales.raw_orders_v1'
      why: Looked in nowhere: no fluid.workspace.yaml in /.../acme-sales/order-totals or any directory above it, and FLUID_UPSTREAM_CONTRACTS is not set.
      fix: Check the productId, keep the upstream contract under the directory holding fluid.workspace.yaml, or add its repository to FLUID_UPSTREAM_CONTRACTS. Or bind it by hand: a builds[].properties.parameters.inputs entry named 'orders' (with the path to read) wins over the consumes entry and is used as is.
```

## Where the workspace root is

The workspace root is the nearest directory, walking up from the starting
directory, that holds a file named `fluid.workspace.yaml`. For a contract the
walk starts at the contract's directory; for commands that create or report on
a project (`fluid init`, `fluid forge`, `fluid status`, `fluid skills`) it
starts at the current directory. Without the file there is no workspace, and
each contract stands alone.

`fluid init` writes the file in the directory it runs in, so run it in a project
directory, never in your home directory or a directory that holds credentials
(see [the sandbox warning](#the-workspace-bounds-what-contract-sql-may-read)):

```yaml
# fluid.workspace.yaml, as written by `fluid init orders --quickstart`
schema_version: 1
kind: WorkspaceConfig
generated_at: '2026-10-05T00:02:51.391651Z'
generated_by:
  tool: fluid-cli
  version: 0.18.1
  command: fluid init
workspace:
  name: orders
  provider: local
```

A file you write yourself needs only the keys you use. The `workspace:` wrapper
is optional for the `workspace.*` keys below: written at the top level they are
read the same way. `expected-environments` is read only at the top level.

## Keys

| Key | Read by | What it does |
|---|---|---|
| `workspace.name` | `fluid status`, `fluid init`, `fluid forge` | The workspace's name, shown on `fluid status`'s Workspace line. |
| `workspace.domain`, `workspace.owner` (`{team, email}` or a team name), `workspace.provider` | `fluid init`, `fluid forge` | Defaults pre-filled into new products. |
| `workspace.products_dir` | `fluid init` | Where new products go below the root (default `.`). |
| `workspace.data_product_type_lock` | `fluid forge` | Locks new products to one productType; written by `fluid init --workspace-lock`. |
| `expected-environments` (top level, not under `workspace:`) | commands that load a contract with `--env` | Per product, the environments that must have an overlay. See below. |

## expected-environments

```yaml
expected-environments:
  customer-events: [aws, gcp]          # by the product's directory name
  sales.order_totals_v1: [dev, prod]   # or by its contract id
```

A product is looked up by the name of the directory its contract is in, then by
its contract `id`. When `--env <env>` names an environment listed for the
product and no overlay file exists for it, the command is refused instead of
running the base contract as if it were that environment
(`ERR_OVERLAY_DECLARED_BUT_MISSING`). `dev`, and an env equal to a platform the
base already binds to, are never refused. The full behaviour, with the error
text, is in
[Environments and overlays](./environments-and-overlays.md#when-no-overlay-matches).
Added in CLI 0.17.0. `fluid bundle` reports the refusal as `Compilation
failed: --env 'gcp' has no overlay, but fluid.workspace.yaml expected-environments ...`.

`fluid validate` with no contract argument, run inside a workspace, validates
the products it finds under the workspace's products directory.

## How a build finds the products it consumes

An embedded-SQL build on the DuckDB engine resolves each `consumes[]` entry
whose `exposeId` the SQL reads as a table name:

1. **Find the upstream contract.** It walks the workspace root and every
   directory in `FLUID_UPSTREAM_CONTRACTS` (colon-separated), four directories
   deep, in files named `contract.fluid.yaml` or `contract.fluid.json`, and
   matches the `id` each file declares. An id declared by two files is an error
   naming both.
2. **Load it with the same `--env`.** An `--env aws` build reads the upstream's
   aws binding, an `--env gcp` build its gcp binding.
3. **Read the expose.** A local file (anchored at the upstream contract's
   directory), the files under an S3 prefix, or a BigQuery table (read through
   the BigQuery API into a staged Parquet file; needs the `gcp` extra). Any
   other binding is refused with the platform named.

Each resolved entry becomes a DuckDB view named by its `exposeId`. An entry the
SQL does not read is lineage only and is not resolved. A
`builds[].properties.parameters.inputs` entry with the same name overrides the
`consumes[]` entry.

`FLUID_UPSTREAM_CONTRACTS` is for upstreams outside the workspace, for example
another repository checked out next to this one in CI:

```bash
FLUID_UPSTREAM_CONTRACTS=../platform-products fluid apply contract.fluid.yaml --mode amend-and-build --yes
```

## The workspace bounds what contract SQL may read

Since CLI 0.18.0, SQL from a contract runs in a DuckDB sandbox. The workspace
root is one of the directories it may read, next to the contract's own
directory, `./runtime` and the run's scratch directory. A product can therefore
read a sibling product's files by path. The sandbox page lists the other
readable directories, including declared inputs, resolved upstreams and the
roots in `FLUID_UPSTREAM_CONTRACTS`: [DuckDB sandbox](../advanced/duckdb-sandbox.md).

::: warning A workspace file in a parent directory widens what a contract's SQL can read
The nearest `fluid.workspace.yaml` above a contract is its workspace root, so a
workspace file in a broad directory makes everything below that directory
readable by the SQL of every contract under it.

- Do not run `fluid init` in `$HOME`, in `/tmp` or in a directory that holds
  credentials: it writes `fluid.workspace.yaml` in the directory it runs in.
- Before you run a contract you did not write, check which workspace root it
  resolves to. Run `fluid status` in the contract's directory and read the
  directory on the Workspace row. A root above the repository you cloned is not
  what you expect. A `—` in place of the workspace name means no
  `fluid.workspace.yaml` was found.
- Remove a `fluid.workspace.yaml` that you did not mean to create.
:::

## Team memory

`fluid init` also scaffolds `.fluid/team-memory.yaml` at the workspace root:
naming conventions, defaults and recorded decisions that `fluid forge` treats as
team guidance. It is meant to be committed. For the separate per-user memory
store, see [Forge copilot memory](../advanced/forge-copilot-memory.md).

## See also

- [Environments and overlays](./environments-and-overlays.md)
- [Consume another contract](../recipes/consumes-contract-to-contract.md)
- [DuckDB sandbox](../advanced/duckdb-sandbox.md)
