# `fluid runs`

Day-2 introspection for acquisition (and other) runs. `fluid runs` is the umbrella for inspecting the state files Forge writes under `.fluid/runs/<product>/<build>/runs/`. Distinct from `fluid status` (workspace overview), `fluid doctor` (system diagnostic), and `fluid auth` (cloud credentials) — those serve different purposes.

<iframe
  src="/forge_docs/reels/day2-ops.html"
  width="100%"
  height="500"
  style="border: 1px solid #232a3d; border-radius: 12px; max-width: 1100px;"
  loading="lazy"
  title="Skip the panic — Fluid Forge day-2 ops">
</iframe>

3am Slack ping: pipeline broke. Ninety seconds later, you've shipped the fix. The reel above walks `runs status` → `runs logs --component dlq` → `runs diff` → policy fix → `fluid ship`. Pairs with [`fluid retention`](./retention.html), [`fluid secrets`](./secrets.html), and [`fluid stats`](./stats.html).

::: tip Available in 0.8.3
`fluid runs` ships with the source-aligned acquisition stack in `0.8.3` (schema `0.7.3`). Earlier releases don't include it.
:::

## Syntax

```bash
fluid runs <subcommand> <product-id> [options]
```

## Subcommands

### `fluid runs status`

Show the last N run records for a product, with freshness, error rate over the last 24h, last state, and per-stream record counts.

```bash
fluid runs status bronze.crm_orders
fluid runs status bronze.crm_orders --build ingest_orders --last 10
fluid runs status bronze.crm_orders --json
```

| Option | Description |
|---|---|
| `<product-id>` | Required. The data product ID. |
| `--build <id>` | Specific build to inspect. Auto-discovered if omitted. |
| `--last <n>` | How many recent runs to show. Default `5`. |
| `--state-root <path>` | Override the state directory. Default `./.fluid`. |
| `--json` | Emit JSON instead of the human table. |

### `fluid runs logs`

Component-scoped log fetch with optional regex filtering.

```bash
fluid runs logs bronze.crm_orders --component build
fluid runs logs bronze.crm_orders --component dlq --grep "schema_drift"
fluid runs logs bronze.crm_orders --run-id 2026-04-30T12-34-56 --json
```

| Option | Description |
|---|---|
| `<product-id>` | Required. The data product ID. |
| `--component {build\|infra\|server\|worker\|dlq}` | Which component's logs. Default `build`. |
| `--run-id <id>` | Specific run. Otherwise the most recent run for the build. |
| `--grep <pattern>` | Regex filter applied to log lines. |
| `--limit <n>` | Maximum lines returned. Default `1000`. |
| `--json` | Emit each log line as a JSON record (`timestamp`, `level`, `component`, `message`). |

### `fluid runs diff`

Compare two runs of the same build — added/removed columns and row-count delta.

```bash
fluid runs diff bronze.crm_orders \
  --build ingest_orders \
  --run-a 2026-04-29T12-00-00 \
  --run-b 2026-04-30T12-00-00
```

| Option | Description |
|---|---|
| `<product-id>` | Required. The data product ID. |
| `--build <id>` | Required. The build to diff within. |
| `--run-a <id>` | Required. Baseline run. |
| `--run-b <id>` | Required. Comparison run. |
| `--json` | Structured diff output (`added`, `removed`, `row_delta`). |

## Output shape (JSON)

`fluid runs status --json` returns the `StatusReport` shape (keys are `snake_case`; the emitter sorts keys alphabetically):

```json
{
  "product_id": "bronze.crm_orders",
  "build_id": "ingest_orders",
  "runs": [
    {
      "run_id": "2026-04-30T12-34-56",
      "state": "succeeded",
      "started_at": "2026-04-30T12:34:56Z",
      "finished_at": "2026-04-30T12:34:58Z",
      "records_total": 8,
      "duration_seconds": 2.3,
      "error": null,
      "streams": []
    }
  ],
  "freshness_seconds": 145.0,
  "error_rate_24h": 0.0,
  "last_state": "succeeded",
  "facets": { "total_runs_seen": 1 }
}
```

Field notes:

- `runs[]` — each entry has `run_id`, `state`, `started_at`, `finished_at`, `records_total`, `duration_seconds`, `error` (`null` on success), and `streams` (per-stream record counts on that run).
- `state` — one of `succeeded`, `failed`, `partial`, or `running`.
- `freshness_seconds` — age of the most recent succeeded run; `null` if none succeeded.
- `error_rate_24h` — fraction (`0`–`1`) of runs in the last 24h that failed or were partial.
- `last_state` — `state` of the newest run record.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Subcommand succeeded |
| `1` | User error (missing args, invalid product ID) |
| `2` | Partial result (some runs unreadable; the rest are reported) |
| `3` | Transient — state directory unavailable; retry later |
| `4` | Internal — log this with state-root path and traceback |

## See also

- [Source-Aligned Acquisition](/forge_docs/advanced/source-aligned-acquisition.html) — what produces these run records
- [`fluid retention`](/forge_docs/cli/retention.html) — sweep run records past their horizon
- [`fluid stats`](/forge_docs/cli/stats.html) — aggregate cost across runs
- [Typed CLI Errors](/forge_docs/advanced/typed-cli-errors.html) — error catalog (PartialFailureError, StaleReplayError, etc.)
