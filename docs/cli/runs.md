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

::: tip Where this fits
`fluid runs` ships with the source-aligned acquisition stack in the upcoming `0.7.3` release (schema 0.7.3). The pinned 0.8.0 docs baseline doesn't include it yet; this page documents the surface ahead of release.
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
| `--json` | Emit each log line as a JSON record (timestamp, severity, message, component). |

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

`fluid runs status --json` returns:

```json
{
  "product": "bronze.crm_orders",
  "build": "ingest_orders",
  "runs": [
    {
      "runId": "2026-04-30T12-34-56",
      "startedAt": "2026-04-30T12:34:56Z",
      "completedAt": "2026-04-30T12:34:58Z",
      "state": "success",
      "exitCode": 0,
      "rowsRead": 8,
      "rowsWritten": 8,
      "rowsToDlq": 0,
      "durationSeconds": 2.3,
      "engine": "duckdb"
    }
  ],
  "summary": {
    "errorRate24h": 0.0,
    "freshnessSeconds": 145,
    "lastState": "success"
  }
}
```

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
