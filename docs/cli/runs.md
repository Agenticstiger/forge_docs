# `fluid runs`

Day-2 introspection for acquisition runs. `fluid runs` reads the run records and logs that source-aligned builds leave in the state directory (`.fluid/` by default) and answers three questions: what ran lately and how did it end, what did a component log, and what changed between two runs.

It is separate from [`fluid status`](./status.md) (a summary of one product's files), [`fluid doctor`](./doctor.md) (health of the CLI and its machine) and [`fluid auth`](./auth.md) (cloud credentials).

<iframe
  src="/forge_docs/reels/day2-ops.html"
  width="100%"
  height="500"
  style="border: 1px solid #232a3d; border-radius: 12px; max-width: 1100px;"
  loading="lazy"
  title="Skip the panic — Fluid Forge day-2 ops">
</iframe>

The reel above walks `runs status`, `runs logs --component dlq`, `runs diff`, a policy fix and `fluid ship`. It pairs with [`fluid retention`](./retention.md), [`fluid secrets`](./secrets.md) and [`fluid stats`](./stats.md).

::: tip Available in 0.8.3
`fluid runs` ships with the source-aligned acquisition stack in `0.8.3` (schema `0.7.3`). Earlier releases do not include it.
:::

## Syntax

```bash
fluid runs status <product-id> [--build BUILD] [--last N] [--state-root PATH] [--json]
fluid runs logs   <product-id> [--component C] [--run-id ID] [--grep TEXT] [--limit N] [--state-root PATH] [--json]
fluid runs diff   <product-id> --build BUILD --run-a ID --run-b ID [--state-root PATH] [--json]
```

All three read the state directory, `./.fluid` unless you pass `--state-root`. Run them from the directory that holds the product's `.fluid/`, which for acquisition builds is the directory of the contract.

Without `--json`, the output is an indented `key: value` listing, not a table. With `--json`, it is a JSON document with sorted keys.

## Where the data comes from

```text
.fluid/
├── runs/<product-id>/<build-id>/runs/<run-id>.json    # one record per run
├── logs/<product-id>/<build-id>/<component>.log        # component logs
└── dlq/<run-id>/<stream>.ndjson                        # records routed to the dead-letter queue
```

Acquisition builds write the run records and the dead-letter files. A run record is a JSON file. These are the keys the `runs` commands read:

```json
{
  "run_id": "0101M3W8N4EGS716V5",
  "state": "partial",
  "started_at": "2026-10-01T17:37:06Z",
  "finished_at": "2026-10-01T17:37:09Z",
  "records_total": 11,
  "facets": { "duration_seconds": 3.1 },
  "error": "stream refunds: 1 record routed to the DLQ",
  "streams": [
    { "name": "orders", "records": 10, "state": "succeeded" },
    { "name": "refunds", "records": 1, "state": "failed" }
  ]
}
```

`state` is one of `queued`, `running`, `succeeded`, `partial`, `failed`, `cancelled` or `archived`. The examples below read two records of this shape. The run IDs are the file names, and `runs status` orders runs by them, newest first.

## `fluid runs status`

Show the most recent runs of a product, with freshness, the error rate over the last 24 hours, and per-stream record counts.

```bash
fluid runs status bronze.crm_orders
fluid runs status bronze.crm_orders --build ingest_orders --last 10
fluid runs status bronze.crm_orders --json
```

| Option | Description |
| --- | --- |
| `<product-id>` | The data product ID. Required. |
| `--build ID` | The build to inspect. Without it, the command takes the first build directory it finds under `runs/<product-id>/`, in name order. Pass `--build` when a product has more than one. |
| `--last N` | How many recent runs to list. Default `5`. |
| `--state-root PATH` | The state directory. Default `./.fluid`. |
| `--json` | Emit JSON instead of the listing. |

```bash
fluid runs status bronze.crm_orders --json
```

```json
{
  "build_id": "ingest_orders",
  "error_rate_24h": 0.0,
  "facets": {
    "total_runs_seen": 2
  },
  "freshness_seconds": 304123.563919,
  "last_state": "partial",
  "product_id": "bronze.crm_orders",
  "runs": [
    {
      "duration_seconds": 3.1,
      "error": "stream refunds: 1 record routed to the DLQ",
      "finished_at": "2026-10-01T17:37:09Z",
      "records_total": 11,
      "run_id": "0101M3W8N4EGS716V5",
      "started_at": "2026-10-01T17:37:06Z",
      "state": "partial",
      "streams": [
        {
          "name": "orders",
          "records": 10,
          "state": "succeeded"
        },
        {
          "name": "refunds",
          "records": 1,
          "state": "failed"
        }
      ]
    },
    {
      "duration_seconds": 2.3,
      "error": null,
      "finished_at": "2026-10-01T11:41:08Z",
      "records_total": 8,
      "run_id": "0101M3VM992GJ62H1F",
      "started_at": "2026-10-01T11:41:06Z",
      "state": "succeeded",
      "streams": [
        {
          "name": "orders",
          "records": 8,
          "state": "succeeded"
        }
      ]
    }
  ]
}
```

What the top-level fields mean:

| Field | Meaning |
| --- | --- |
| `runs` | The most recent `--last` runs, newest first. `duration_seconds` comes from the record's `facets.duration_seconds`, or from `finished_at - started_at` when that is missing. |
| `freshness_seconds` | Seconds since the newest `succeeded` run finished. `null` when no run succeeded. |
| `error_rate_24h` | The fraction (`0` to `1`) of runs from the last 24 hours that ended `failed` or `partial`. `0.0` when no run falls in that window, as in the example, whose runs are days old. |
| `last_state` | The `state` of the newest run. |
| `facets.total_runs_seen` | How many records the command read: up to 100, or `--last` when that is larger. |

`freshness_seconds` depends on when you run the command.

With a product that has no runs, the command prints a one-line message and exits `1`:

```text
no builds found for product nothing.here under .../.fluid/runs/nothing.here/
```

## `fluid runs logs`

Read the logs a product left, filtered by component.

```bash
fluid runs logs bronze.crm_orders --component dlq --run-id 0101M3W8N4EGS716V5
fluid runs logs bronze.crm_orders --grep schema_drift
fluid runs logs bronze.crm_orders --component dlq --run-id 0101M3W8N4EGS716V5 --json
```

| Option | Description |
| --- | --- |
| `<product-id>` | The data product ID. Required. |
| `--component {build\|infra\|server\|worker\|dlq}` | Which component's logs to read. Default `build`. |
| `--run-id ID` | The run whose dead-letter files to read. **Required for `dlq`**: without it the result is empty. Ignored for the other components. |
| `--grep TEXT` | Keep only lines that contain `TEXT`. A case-sensitive substring match, not a regular expression. |
| `--limit N` | Keep the last `N` lines of each log file. Default `1000`. |
| `--state-root PATH` | The state directory. Default `./.fluid`. |
| `--json` | Emit a JSON array of `{timestamp, level, component, message}` objects. |

Where each component reads from:

| Component | Reads |
| --- | --- |
| `build`, `infra`, `server`, `worker` | `logs/<product-id>/<build>/<component>.log` for each build under the product. JSON lines with `timestamp`, `level` and `message` keys are parsed; any other line is returned as plain text. |
| `dlq` | Every `dlq/<run-id>/*.ndjson` file for the `--run-id` you give. Each line is returned as the message, unparsed. |

```text
2026-10-01T17:37:06Z  INFO   stream orders: 10 records
2026-10-01T17:37:08Z  WARN   stream refunds: schema_drift on amount
-  -      plain text line
```

That is `fluid runs logs bronze.crm_orders` over a `build.log` holding two JSON lines and one plain line. A line with no timestamp or level prints `-` in both columns.

As of 0.18.1, the CLI itself does not write the `.log` files; the `build`, `infra`, `server` and `worker` components show what is already in `.fluid/logs/`. The `dlq` component reads files the acquisition runners do write. When nothing matches, the output is `(no <component> logs for <product-id>)` and the exit code is `0`.

`--limit` and `--grep` act per file. `--grep 'schema_.*drift'` matches the literal text `schema_.*drift`, so it finds nothing here.

## `fluid runs diff`

Compare two runs of the same build: record counts, duration and state, overall and per stream.

```bash
fluid runs diff bronze.crm_orders \
  --build ingest_orders \
  --run-a 0101M3VM992GJ62H1F \
  --run-b 0101M3W8N4EGS716V5
```

```text
run_a: 0101M3VM992GJ62H1F
run_b: 0101M3W8N4EGS716V5
state_a: succeeded
state_b: partial
records_total_a: 8
records_total_b: 11
records_delta: 3
duration_a: 2.3
duration_b: 3.1
duration_delta: 0.8000000000000003
streams:
  -
    name: orders
    records_a: 8
    records_b: 10
    delta: 2
  -
    name: refunds
    records_a: 0
    records_b: 1
    delta: 1
error_a: None
error_b: stream refunds: 1 record routed to the DLQ
```

| Option | Description |
| --- | --- |
| `<product-id>` | The data product ID. Required. |
| `--build ID` | The build to diff within. Required. |
| `--run-a ID` | The baseline run. Required. |
| `--run-b ID` | The run to compare against it. Required. |
| `--state-root PATH` | The state directory. Default `./.fluid`. |
| `--json` | Emit the diff as JSON. |

With `--json`, the document has `run_a`, `run_b`, `state_a`, `state_b`, `records_total_a`, `records_total_b`, `records_delta`, `duration_a`, `duration_b`, `duration_delta`, `error_a`, `error_b` and `streams`, a list of `{name, records_a, records_b, delta}`. Every delta is `b` minus `a`, and a stream present in only one run counts as `0` in the other.

`runs diff` compares counts. It does not compare columns or schemas, so it cannot tell you that a column was added or removed.

Run IDs that do not exist are not an error. The diff comes back with zero counts, `null` states and an empty `streams` list, and the exit code is `0`. Check `state_a` and `state_b` before you read the deltas in a script.

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | The command ran, including a diff of run IDs that do not exist and logs with no matches. |
| `1` | `runs status` found no builds for the product. |
| `2` | A usage error: a missing required argument, an unknown subcommand, an invalid `--component`. |

## See also

- [Source-aligned acquisition](../advanced/source-aligned-acquisition.md): what produces these run records
- [`fluid retention`](./retention.md): sweep run records past their horizon
- [`fluid stats`](./stats.md): aggregate cost across forge runs
- [Typed CLI errors](../advanced/typed-cli-errors.md): the error catalog
