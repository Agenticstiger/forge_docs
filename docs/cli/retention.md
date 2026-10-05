# `fluid retention`

Sweep state-root directories of run records, logs, lineage events and DLQ entries that are older than a fixed horizon.

::: warning The sweeper does not read your contract
As of 0.18.1, `fluid retention sweep` reads no contract and no per-product setting. It applies the same four horizons to every product under the state root: run state 30 days, run logs 90 days, lineage 365 days, DLQ 180 days. A top-level `retention:` block in a contract, such as `runState: P365D`, does not change what the sweep deletes. A product that declares a longer run-state horizon than 30 days still has its run records deleted after 30 days. If you must keep records longer than the defaults, do not run `fluid retention sweep` against that state root.
:::

::: tip Where this fits
`fluid retention` ships with the source-aligned acquisition stack in `0.8.3` (schema `0.7.3`). Earlier releases don't include it.
:::

## Syntax

```bash
fluid retention sweep [--state-root PATH] [--json]
```

## Example

A state root with one run record 65 days old and one fresh, a log file 126 days old, and a contract whose `retention.runState` is `P365D`:

```bash
fluid retention sweep --json
```

```json
{
  "by_category": {
    "dlq": 0,
    "lineage": 0,
    "run_logs": 1,
    "run_state": 1
  },
  "bytes_freed": 5,
  "deleted_paths": [
    "/.../.fluid/runs/gold.orders_v1/build/runs/old.json",
    "/.../.fluid/logs/gold.orders_v1/old.log"
  ]
}
```

The 65-day-old run record is deleted although the contract declares `P365D`: the sweep never read the contract.

## Subcommands

### `fluid retention sweep`

Walk the state root and delete files older than the horizons below. Emits a structured summary at the end.

| Option | Description |
|---|---|
| `--state-root <path>` | State directory to sweep. Default `./.fluid`. |
| `--json` | Emit a JSON summary instead of the human-readable one. |

## What gets swept

The sweep deletes, by file modification time, every file older than the horizon in four directories of the state root, across all products:

| Directory | Category in the summary | Horizon |
|---|---|---|
| `<state-root>/runs/` | `run_state` | 30 days |
| `<state-root>/logs/` | `run_logs` | 90 days |
| `<state-root>/lineage/` | `lineage` | 365 days |
| `<state-root>/dlq/` | `dlq` | 180 days |

Nothing else in the state root is touched. A directory that does not exist is skipped. A file the sweep cannot delete is logged as a warning and skipped.

## Output shape

`fluid retention sweep --json` returns the `RetentionSummary` shape. The keys are `snake_case` and sorted alphabetically.

- `deleted_paths`: every file the sweep removed, as an absolute path.
- `bytes_freed`: total bytes reclaimed across all categories.
- `by_category`: per-category count of deleted files.

Each deletion is also logged as `retention.delete path=<path>`.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | The sweep ran to the end, with or without deletions. |

The command returns `0` whenever it completes, so a CI step cannot use its exit code to learn whether anything was deleted: read `by_category` from the JSON.

## The `retention:` block and the data-retention fields

Three things carry the word retention, and the sweeper reads none of them:

- **Top-level `retention:`** (schema 0.7.3): `runState`, `runLogs`, `lineage` and `dlq`, each an ISO-8601 duration. The values must be ISO-8601 (`P90D`, not `90d`) to pass `fluid validate`. The block describes the horizons you intend for run artifacts, but `fluid retention sweep` does not consult it, and nothing in the CLI reads the `.fluid/policies/<id>/retention.json` that the acquisition stage writes from it.
- **`exposes[].lifecycle.retention`**: how long the data itself is kept. It is a declaration unless the expose also sets `lifecycle.expire: true` (contract schema 0.7.6, a preview schema selected with `fluidVersion: "0.7.6"`), which turns it into deletion of data in the bucket or table. That is unrelated to the state-root sweep.
- **`exposes[].lifecycle.state` and `deprecationPolicy`**: the lifecycle state of a product (`preview`, `active`, `deprecated`, `retired`) and how it is retired.

## Scheduling the sweeper

`fluid retention sweep` is a one-shot command. Schedule it with your own cron, CI scheduler or Kubernetes `CronJob`, running in the directory that holds the `.fluid/` state root or with `--state-root`.

## See also

- [Source-Aligned Acquisition → Top-level retention](/forge_docs/advanced/source-aligned-acquisition.html#top-level-retention): the `retention:` block
- [`fluid runs`](/forge_docs/cli/runs.html): what the run records look like before they get swept
- [Typed CLI Errors](/forge_docs/advanced/typed-cli-errors.html): `LockHeldError`, `StaleReplayError`
