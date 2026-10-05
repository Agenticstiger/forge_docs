# `fluid rollback`

Restore a table from a snapshot recorded in `.fluid/rollback-state.json`. The intended use is the "how do I undo this?" step after a destructive `fluid apply --mode replace` or `replace-and-build`.

Added in `0.8.0`.

::: warning Check that a snapshot exists before you rely on this (as of 0.18.1)
`fluid rollback` restores from a state file. It does not create backups. `fluid apply` records a snapshot in that file only on its native apply engine, and in 0.18.1 contracts bound to the following providers do not use it:

- **`aws`, `gcp`, `snowflake` and `confluent` bindings** apply through OpenTofu, which has no snapshot step. The data-loss gate ([the mode gate](./apply.md#the-mode-gate) on the `apply` page) says so before it lets you proceed:

  ```text
  ❌ apply_mode_data_loss_blocked  [ERR_APPLY_MODE_DATA_LOSS_BLOCKED]
    mode: replace
    env: prod
    reason: --mode replace is destructive (env='prod'; target row count unknown (treating as populated)). Pass --allow-data-loss to confirm the drop. NO SNAPSHOT WILL BE TAKEN: this contract applies through the OpenTofu engine, which has no CTAS/CLONE step, so no <target>__backup_<ts> table is created and `fluid rollback` will have no restore point. Back the target up yourself before proceeding.
  ```

- **`local` bindings** apply natively, but `fluid apply --mode replace --allow-data-loss` on a `local` contract wrote no `.fluid/rollback-state.json` in a 0.18.1 test, although the gate's own message for `local` says the table "will be snapshotted".

Back up the target yourself before a destructive apply on any of these. [Evolve a live product](../recipes/evolve-a-live-product.md#breaking-changes-replace-and-rollback) walks through a `replace` and what to check first. The rest of this page describes what `fluid rollback` does when a state file is present.
:::

## Syntax

```bash
# Restore
fluid rollback --env ENV --product PRODUCT_ID [--snapshot NAME] [--dry-run] [--yes]

# Discovery (read-only)
fluid rollback --list [--env ENV] [--product PRODUCT_ID]
```

## Options

### Restore mode

| Option | Description |
| --- | --- |
| `--env` | Environment the product was applied to, matched against the `env` recorded in each snapshot. Required for restore. |
| `--product` | Product ID from the contract (its `id` field). Required for restore. |
| `--snapshot` | Name of the snapshot to restore, as shown in the `backup_name` column of `--list`. Default: the first snapshot in the state file that matches `--env` and `--product`; see [Which snapshot is "latest"](#which-snapshot-is-latest). |
| `--state-file` | Path to the rollback state file. Default `.fluid/rollback-state.json` relative to the current directory. |
| `--dry-run` | Print the chosen snapshot and the restore statement without running it. |
| `--yes` | Confirm the destructive restore. Required unless `--dry-run` is set. |

### Discovery mode

| Option | Description |
| --- | --- |
| `--list` | List the snapshots in the state file and restore nothing. Narrow with `--env` and `--product`. Read-only. |

## The state file

`.fluid/rollback-state.json` is a JSON object with a `version` and a list of `snapshots`. An entry that `fluid apply` records has this shape:

```json
{
  "version": "1",
  "snapshots": [
    {
      "backup_name": "BACKUP_SUBSCRIBER360_1790600000",
      "captured_at": "2026-09-28T12:53:20Z",
      "env": "prod",
      "product_id": "silver.telco.subscriber360_v1",
      "provider": "snowflake",
      "location": {
        "database": "TELCO_LAB",
        "schema": "BRONZE",
        "table": "SUBSCRIBER360",
        "backup_table": "BACKUP_SUBSCRIBER360_1790600000"
      },
      "ddl": [
        "CREATE OR REPLACE TABLE TELCO_LAB.BRONZE.SUBSCRIBER360 CLONE TELCO_LAB.BRONZE.BACKUP_SUBSCRIBER360_1790600000"
      ]
    }
  ]
}
```

When `fluid apply` appends a snapshot it keeps the 20 most recent per environment and product by default and drops the older entries. It also tries to delete the backup tables of the entries it drops, and logs a warning instead of failing the apply when that cleanup does not work. Set `FLUID_ROLLBACK_KEEP_LAST_N` to change the cap.

The `ddl` array is stored for the record and never executed. `fluid rollback` rebuilds the restore statement from `location` after checking that each part is a valid identifier. A state file is plain data that teams commit and review in pull requests, so a crafted `ddl` entry cannot make a restore run arbitrary SQL, and a `location` value with a space, quote or semicolon is rejected.

### Per-provider restore

The `provider` recorded in a snapshot picks the restore:

| `provider` | Restore statement | Notes |
| --- | --- | --- |
| `snowflake` | `CREATE OR REPLACE TABLE <db>.<schema>.<table> CLONE <db>.<schema>.<backup_table>` | A zero-copy table clone, one table per snapshot. Runs through the Snowflake provider, so the Snowflake driver must be installed. |
| `gcp`, `bigquery` | ``CREATE OR REPLACE TABLE `<project>.<dataset>.<table>` AS SELECT * FROM `<project>.<dataset>.<backup_table>` `` | BigQuery has no clone, so the restore copies the backup. Runs with the BigQuery client library under your default credentials. `location.database` holds the project and `location.schema` the dataset. |
| `redshift` | Not implemented | Fails with `rollback_redshift_not_implemented` and exit `2`. Restore by hand: `TRUNCATE` the live table and `INSERT INTO <live> SELECT * FROM <backup>` inside a transaction. |
| `aws` | Not accepted | A snapshot with `provider: aws` fails with `rollback_unknown_provider`. It is deliberately not routed to the Redshift restorer. |

Any other `provider` value fails the same way, and the error lists the supported ones.

## Which snapshot is "latest"

::: warning Known issue in 0.18.1: the default snapshot can be the oldest one
`fluid apply` writes the snapshot time as `captured_at`. `fluid rollback` reads `timestamp` (and `mode`) to order snapshots and to fill the `timestamp` and `mode` columns of `--list`. A state file written by `fluid apply` has neither key, so `--list` shows `—` in those columns, and a restore without `--snapshot` picks the **first** matching entry in the file, which is the oldest.
:::

With two snapshots recorded for the same product, `--dry-run` selects the older one:

```bash
fluid rollback --env prod --product silver.telco.subscriber360_v1 --dry-run
```

```text
[rollback] env=prod product=silver.telco.subscriber360_v1 provider=snowflake snapshot=BACKUP_SUBSCRIBER360_1790000000 timestamp=None dry-run=True
[rollback] snowflake CLONE plan:
    CREATE OR REPLACE TABLE TELCO_LAB.BRONZE.SUBSCRIBER360 CLONE TELCO_LAB.BRONZE.BACKUP_SUBSCRIBER360_1790000000;
[rollback] ✔ dry-run complete; no state mutated.
```

`BACKUP_SUBSCRIBER360_1790000000` is the earlier of the two. Until this is fixed, name the snapshot you want with `--snapshot`. `--list` prints newest first (the file is appended in time order and the list reverses it), so the first row is the most recent. The number at the end of a backup name is a Unix timestamp, which gives a second check.

## Examples

### Discovery before a restore

`--list` reads the state file and never touches a provider:

```bash
fluid rollback --list
```

```text
  #  timestamp                   env       mode                  product_id                                  backup_name
------------------------------------------------------------------------------------------------------------------------
  1  —                           prod      —                     silver.telco.subscriber360_v1               BACKUP_SUBSCRIBER360_1790600000
  2  —                           prod      —                     silver.telco.subscriber360_v1               BACKUP_SUBSCRIBER360_1790000000

[rollback] 2 snapshot(s). Restore with: fluid rollback --env <ENV> --product <ID> --snapshot <BACKUP_NAME> --yes
```

Narrow it:

```bash
fluid rollback --list --env prod
fluid rollback --list --product silver.telco.subscriber360_v1
```

`--list` exits `0` when the state file does not exist. A workspace with no snapshots is not a failure.

### Preview a restore

`--dry-run` prints the statement without running it, and needs no database credentials:

```bash
fluid rollback --env prod --product silver.sales.orders_v1 --state-file multi.json --dry-run
```

```text
[rollback] env=prod product=silver.sales.orders_v1 provider=gcp snapshot=BACKUP_orders_1790000000 timestamp=None dry-run=True
[rollback] bigquery CTAS restore plan:
    CREATE OR REPLACE TABLE `demo-proj.sales.orders` AS SELECT * FROM `demo-proj.sales.BACKUP_orders_1790000000`;
[rollback] ✔ dry-run complete; no state mutated.
```

Run a dry run before every restore on a production environment, and read the statement it prints.

### Restore a named snapshot

```bash
fluid rollback \
  --env prod \
  --product silver.telco.subscriber360_v1 \
  --snapshot BACKUP_SUBSCRIBER360_1790600000 \
  --yes
```

Copy the `backup_name` from `fluid rollback --list`. Without `--yes` and without `--dry-run`, the command refuses and exits `2`:

```text
CLI command error
❌ rollback_confirmation_required  [ERR_ROLLBACK_CONFIRMATION_REQUIRED]
  hint: rollback is destructive (overwrites the current product state). Re-run with --yes to confirm, or --dry-run to preview the plan.
```

### When the snapshot does not exist

A `--snapshot` that matches nothing for that `--env` and `--product` lists the names that do:

```text
❌ rollback_snapshot_name_not_found  [ERR_ROLLBACK_SNAPSHOT_NAME_NOT_FOUND]
  name: nope
  env: prod
  product_id: silver.telco.subscriber360_v1
  available: ['BACKUP_SUBSCRIBER360_1790000000', 'BACKUP_SUBSCRIBER360_1790600000']
```

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | A restore, a dry run or a listing finished. |
| `2` | The command refused or failed: missing `--env` or `--product`, no `--yes`, no state file, no matching snapshot, an unsupported or unimplemented provider, an identifier that fails validation, or the restore statement failed. |

## Safety properties

- **A confirmation gate.** A restore without `--yes` and without `--dry-run` exits `2` and changes nothing.
- **Restore statements are rebuilt, not replayed.** The statement comes from `location` after identifier validation, never from the stored `ddl`.
- **One statement.** The restore runs the single statement `--dry-run` shows. It does not touch grants, policies or other resources.
- **Read-only discovery.** `--list` returns before any provider call.

## Notes

- `.fluid/rollback-state.json` is a record of destructive operations. Commit it to the product repository for an audit trail, or keep it local and rely on warehouse-level retention.
- The snapshots themselves are tables in your warehouse (`BACKUP_<table>_<unix timestamp>`, in the table's own schema or dataset). The state file only records where they are, so deleting a backup table makes the matching entry unusable.
- For how destructive modes and the data-loss gate work, see [`fluid apply`](./apply.md) and [Production troubleshooting](../advanced/production-troubleshooting.md#apply-data-loss-gate).
