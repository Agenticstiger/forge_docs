# `fluid rollback`

Restore a data product from the auto-snapshot taken before a destructive `fluid apply --mode replace` / `replace-and-build`. This is the "how do I undo this?" answer after a bad destructive deploy.

Added in `0.8.0`.

## Syntax

```bash
# Restore
fluid rollback --env ENV --product PRODUCT_ID [--snapshot NAME] [--dry-run] [--yes]

# Discovery (read-only)
fluid rollback --list [--env ENV] [--product PRODUCT_ID]
```

## Key options

### Restore mode

| Option | Description |
| --- | --- |
| `--env` | Environment the product was applied to (`dev` / `staging` / `prod` / …). Required for restore. |
| `--product` | Product ID from the contract (matches the `id` field). Required for restore. |
| `--snapshot` | Specific snapshot name to restore. Default: the most recent snapshot matching `--env` + `--product`. |
| `--state-file` | Path to the rollback state file. Default `.fluid/rollback-state.json` relative to CWD. |
| `--dry-run` | Print the target snapshot + restore DDL without executing. Use before every production rollback. |
| `--yes` | Confirm the destructive restore. Required when not `--dry-run`. |

### Discovery mode

| Option | Description |
| --- | --- |
| `--list` | List available snapshots from `.fluid/rollback-state.json` without performing any restore. Optionally narrow with `--env` and/or `--product`. Read-only; safe in any env. |

## How snapshots are created

Every time `fluid apply --mode replace*` runs, the pipeline auto-snapshots the target **before** the destructive DDL. The snapshot is recorded in `.fluid/rollback-state.json` (git-ignored by default):

```json
{
  "version": "1",
  "snapshots": [
    {
      "timestamp": "2026-04-23T10:00:00Z",
      "env": "prod",
      "product_id": "silver.telco.subscriber360_v1",
      "backup_name": "backup_silver_telco_subscriber360_v1_1714000000",
      "provider": "snowflake",
      "mode": "replace",
      "location": {"database": "TELCO_LAB", "schema": "TELCO_FLUID_DEMO"}
    }
  ]
}
```

Per-provider snapshot technique. Snowflake clones are **table-level**, not database-level — the snapshot's `ddl[]` array is the source of truth, and limiting clones to the tables actually being changed avoids overwriting unrelated tables in the same database during restore.

| Provider | Snapshot | Restore |
| --- | --- | --- |
| **Snowflake** | `CREATE OR REPLACE TABLE <db>.<sch>.<tbl>__backup CLONE <db>.<sch>.<tbl>` (per-table, zero-copy) | `CREATE OR REPLACE TABLE <db>.<sch>.<tbl> CLONE <db>.<sch>.<tbl>__backup` |
| **BigQuery** | `bq cp --force <src> <backup>` per table | `bq cp --force <backup> <src>` per table |
| **Redshift** | `CREATE TABLE <backup> AS SELECT * FROM <src>` (slow but correct) | `TRUNCATE <src>; INSERT INTO <src> SELECT * FROM <backup>` in a transaction |

## Examples

### Discovery before a restore

Always check what's available first — `--list` is read-only:

```bash
# All recorded snapshots, newest first
fluid rollback --list

# Narrow by environment
fluid rollback --list --env prod

# Narrow by product
fluid rollback --list --product silver.telco.subscriber360_v1

# Both filters
fluid rollback --list --env prod --product silver.telco.subscriber360_v1
```

Sample output:

```
  #  timestamp                   env       mode                  product_id                                  backup_name
-----------------------------------------------------------------------------------------------------
  1  2026-04-23T10:00:00Z        prod      replace-and-build     silver.telco.subscriber360_v1              backup_silver_telco_subscriber360_v1_1714001000
  2  2026-04-20T10:00:00Z        dev       replace               silver.telco.subscriber360_v1              backup_silver_telco_subscriber360_v1_1713000000

[rollback] 2 snapshot(s). Restore with:
fluid rollback --env <ENV> --product <ID> --snapshot <BACKUP_NAME> --yes
```

### Dry-run preview (SAFE — no state mutation)

```bash
fluid rollback \
  --env prod \
  --product silver.telco.subscriber360_v1 \
  --dry-run
```

Prints the exact DDL that would run, the chosen snapshot, and the timestamp. Use this before every production rollback.

### Restore the latest snapshot

```bash
fluid rollback \
  --env prod \
  --product silver.telco.subscriber360_v1 \
  --yes
```

`--yes` is **required** unless `--dry-run` is also set. Rollback is destructive (it overwrites the current state with the snapshot).

### Restore a specific named snapshot

Useful when the "latest snapshot" isn't what you want (e.g. you want to roll back two deploys, not one):

```bash
fluid rollback \
  --env prod \
  --product silver.telco.subscriber360_v1 \
  --snapshot backup_silver_telco_subscriber360_v1_1713000000 \
  --yes
```

Copy the `backup_name` from `fluid rollback --list` output.

## Safety properties

- **Two-factor destructive gate**: `--yes` required unless `--dry-run`. Refuses to run otherwise with a clear error.
- **SQL-injection hardened**: every identifier (database, backup name) flows through `validate_ident` + `quote_string_literal` from `providers/_sql_safety.py` before the CLONE / `bq cp` / CTAS DDL is composed. A malicious `--snapshot` value is rejected by the whitelist, not interpolated.
- **Read-only discovery**: `--list` is guaranteed to not touch the provider. Regression-tested — a future change that accidentally dispatches to the provider restore path under `--list` breaks the CI.
- **Idempotent**: restoring the same snapshot twice produces the same final state.

## Notes

- `.fluid/rollback-state.json` is part of the product's operational history. Commit it to the product repo for an audit trail, or treat it as ephemeral and rely on warehouse-level snapshot retention instead.
- `--list` exits 0 even when the state file doesn't exist (a fresh workspace has no snapshots — that's not a failure).
- For providers that don't yet have a restore implementation (BigQuery and Redshift are limited), the CLI raises `rollback_not_implemented` with an actionable hint for the equivalent manual workflow.
- Rollback is stage-8-agnostic: IAM bindings are not re-applied by rollback. If you need both the data AND the policy rolled back, chain `fluid rollback` with a re-run of `fluid policy apply` against the historical `bindings.json`.
