# `fluid retention`

Sweep state-root directories of run records, logs, lineage events, and DLQ entries past their retention horizons. Horizons are declared by the contract's top-level `retention:` block (schema 0.7.3); the sweeper honors them per-product.

::: tip Where this fits
`fluid retention` ships with the source-aligned acquisition stack on the `feat/source-aligned-acquisition` branch (schema 0.7.3). The pinned 0.8.0 docs baseline doesn't include it yet; this page documents the surface ahead of release.
:::

## Syntax

```bash
fluid retention <subcommand> [options]
```

## Subcommands

### `fluid retention sweep`

Walk all products under the state root and delete entries older than their declared horizons. Emits a structured summary at the end.

```bash
fluid retention sweep
fluid retention sweep --dry-run
fluid retention sweep --state-root /var/fluid --json
```

| Option | Description |
|---|---|
| `--state-root <path>` | State directory to sweep. Default `./.fluid`. |
| `--dry-run` | Show what would be deleted without deleting. |
| `--json` | Emit JSON summary instead of human table. |

## What gets swept

The sweeper reads each contract's top-level `retention:` block:

```yaml
retention:
  runState: P30D     # ISO-8601 duration — 30 days
  runLogs: P90D      # 90 days
  lineage: P365D     # 365 days
  dlq: P180D         # 180 days
```

Anything older than its respective horizon is removed. Horizons may be omitted; missing keys default to never-sweep for that category.

## Output shape

```json
{
  "swept": {
    "runState": { "deletedCount": 12, "freedBytes": 48230 },
    "runLogs":  { "deletedCount": 47, "freedBytes": 211893 },
    "lineage":  { "deletedCount": 0,  "freedBytes": 0 },
    "dlq":      { "deletedCount": 3,  "freedBytes": 9120 }
  },
  "totalDeleted": 62,
  "totalFreedBytes": 269243,
  "products": ["bronze.crm_orders", "silver.customer_360"]
}
```

In dry-run mode the same shape is returned, but the entries report `wouldDelete*` and `wouldFreeBytes` instead of `deleted*`/`freedBytes`.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Sweep complete (or dry-run complete) |
| `1` | Permission error or state directory corruption |
| `3` | Transient — state directory locked by an in-flight run |

## Scheduling the sweeper

A Forge-emitted CI job typically schedules `fluid retention sweep` on a daily or weekly cron. For Kubernetes deployments, the `managed` infra layer can emit a `CronJob` running the same command on the cluster. See [Source-Aligned Acquisition → Three deployment modes](/forge_docs/advanced/source-aligned-acquisition.html#three-deployment-modes).

## See also

- [Source-Aligned Acquisition → Top-level retention](/forge_docs/advanced/source-aligned-acquisition.html#top-level-retention) — declaring the horizons
- [`fluid runs`](/forge_docs/cli/runs.html) — what the run records look like before they get swept
- [Typed CLI Errors](/forge_docs/advanced/typed-cli-errors.html) — `LockHeldError`, `StaleReplayError`
