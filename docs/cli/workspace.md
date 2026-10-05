# `fluid workspace`

Team workspace and collaboration features — manage members, contract versions, change requests, and an activity log backed by a local SQLite database.

::: tip Looking for `fluid.workspace.yaml`?
That file is a different thing from the `fluid workspace` command. `fluid workspace` manages the SQLite store in `./.fluid-workspace/`, described on this page. `fluid.workspace.yaml` is an optional config file that `fluid init` writes at the root of a workspace; the CLI reads it for shared defaults and environment expectations. It has [its own section below](#the-workspace-config-file-fluid-workspace-yaml), and the concept page is [Workspaces](../concepts/workspaces.md).
:::

## Syntax

```bash
fluid workspace ACTION [SUBACTION] [...]
```

## Key options

| Option | Description |
| --- | --- |
| `init NAME [--description TEXT] [--owner NAME]` | Initialize a new workspace under `./.fluid-workspace/`. |
| `info` | Show workspace information (name, description, owner, member/version/change counts). |
| `team list` | List team members. |
| `team add NAME EMAIL [--role {owner,admin,developer,viewer}]` | Add a team member (default role: `developer`). |
| `version create CONTRACT --message MSG [--author NAME]` | Create a new contract version. |
| `version list [--contract PATH]` | List contract versions, optionally filtered by contract. |
| `changes create TITLE CONTRACT [--description TEXT] [--author NAME]` | Create a change request against a contract. |
| `changes list [--status {open,in_review,approved,rejected,merged}]` | List change requests, optionally filtered by status. |
| `changes approve REQUEST_ID [--approver NAME]` | Approve a change request that is currently `in_review`. |
| `activity [--limit N]` | Show the most recent activity log entries (default `--limit 20`). |

## Examples

```bash
fluid workspace init "Data Platform" --owner alice
fluid workspace team add bob bob@example.com --role developer
fluid workspace version create contracts/orders.fluid.yaml --message "Bump schema"
fluid workspace changes list --status open
```

## Notes

- The workspace lives in `./.fluid-workspace/` and stores everything in `workspace.db` (SQLite). A git repo is auto-initialised in that folder when `gitpython` is available.
- All output requires the `rich` library — without it, subcommands print a one-line "requires rich library" message and exit with code 1.
- Version numbers are auto-generated as `v1.<n>.0` based on the count of existing versions for that contract path.
- `changes approve` only succeeds if the request's current status is `in_review`.
- For human-driven development workflows tied to git directly, see [`fluid forge`](./forge.md).

## The workspace config file: `fluid.workspace.yaml`

`fluid init` writes this file in the current directory when no workspace root exists above it. Reproduced with `fluid init my-project --quickstart --yes` in an empty directory, which wrote `fluid.workspace.yaml` beside the new `my-project/`:

```yaml
schema_version: 1
kind: WorkspaceConfig
generated_at: '2026-10-05T00:49:39.471211Z'
generated_by:
  tool: fluid-cli
  version: 0.18.1
  command: fluid init
workspace:
  name: my-project
  provider: local
```

The **workspace root** is the nearest directory, walking up from where a command starts, that holds a file with this name. Nothing else marks a workspace. If a parent directory already has one, `fluid init` reuses it and writes none.

### What reads it

| Key | Read by | Effect |
| --- | --- | --- |
| `workspace.name` | `fluid status` | The `Workspace` line, with the root directory. |
| `workspace.provider`, `workspace.domain`, `workspace.owner` (`team`, `email`) | `fluid init`, `fluid forge` | Shared defaults pre-filled into new product metadata, so they are not asked again. |
| `workspace.products_dir` | `fluid init` | Where new products are created, relative to the root. Default `.`. A value that resolves outside the root falls back to the root. |
| `workspace.data_product_type_lock` | `fluid forge` | Set with `fluid init --workspace-lock SDP\|ADP\|CDP`. `fluid forge` then rejects a conflicting `--data-product-type`. |
| `expected-environments` | commands that load a contract with `--env` (shown below with `fluid validate`) | See below. |

The `workspace:` block is optional in the file: the loader also accepts these keys at the top level.

Three more behaviours depend on the root, not on a key:

- `fluid skills` keeps its industry-skills file under the workspace root and stops with `Not inside a FLUID workspace` when there is none.
- A product whose build runs embedded SQL and lists `consumes[]` finds those upstream contracts by `id`, searching the workspace root and any path in the colon-separated `FLUID_UPSTREAM_CONTRACTS`. An `id` declared by two files is an error that names both. This is what lets a Silver or Gold product read a Bronze product's output without hard-coding where it landed.
- The DuckDB sandbox that runs contract SQL allows reads under the workspace root as well as the contract's own directory. See [DuckDB sandbox](../advanced/duckdb-sandbox.md).

### `expected-environments`: a missing overlay becomes an error

Without it, `--env gcp` on a product that has no `overlays/gcp.yaml` falls back to the base contract, so a command for "gcp" runs against the local binding. List the environments a product is deployed to, and that fallback becomes a hard error ([Workspaces](../concepts/workspaces.md#expected-environments) and [Environments and overlays](../concepts/environments-and-overlays.md#when-no-overlay-matches) have the rest):

```yaml
# fluid.workspace.yaml
expected-environments:
  my-project: [dev, gcp]
```

The key under `expected-environments` is the product's directory name or its contract `id`. With no `overlays/gcp.yaml` in place:

```bash
fluid validate my-project/contract.fluid.yaml --env gcp
```

```text
❌ Validation error: contract_load_failed
   error: --env 'gcp' has no overlay, but fluid.workspace.yaml
expected-environments (my-project) declares 'gcp' an environment of this
product, so the base contract (bound to local) would be used as if it were
'gcp'. Add overlays/gcp.yaml, or remove 'gcp' from fluid.workspace.yaml
expected-environments (my-project)
   [ERR_CONTRACT_LOAD_FAILED]
```

The command exits `1`. `dev` is the base by convention, and an environment the base contract is already bound to (`local`, for a local base) is the base too; neither is refused. A contract's own `environments:` block does not trigger the error: a missing overlay for an environment that only that block names is a warning.

See [Per-environment overlays](../recipes/per-environment-overlays.md) for writing the overlay itself.
