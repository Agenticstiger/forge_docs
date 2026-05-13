---
title: Debug a failed pipeline run
description: 3am Slack ping, pipeline broke. Walk through fluid runs status → logs → diff → fix → ship in under 90 seconds.
---

# Task: Debug a failed pipeline run

It's 3am. PagerDuty fired. `gold.finance.customer_360_v1` missed its 1-hour freshness SLA. You have 90 seconds to figure out **where** it broke, **why** it broke, **what** changed, fix it, and ship.

This is what `fluid runs` is built for. Three commands, one fix, one `ship`.

## The 90-second flow

```bash
fluid runs status --product gold.finance.customer_360_v1
fluid runs logs <run-id> --component dlq --tail
fluid runs diff <last-ok-run> <first-fail-run>
# ...edit one line in contract.fluid.yaml...
fluid ship contract.fluid.yaml --strict --env prod --yes
```

A frame-perfect cast of this exact flow is in the [day2-ops demo](/see-it-run.html#skip-the-panic) — bookmark it.

## Step 1 — `runs status` (where)

```bash
fluid runs status --product gold.finance.customer_360_v1
```

Shows the last 10 runs of this product:

```
run-id      ts          duration  status   stage
─────────  ──────────  ────────  ───────  ──────
r-2a4f8c3  03:01 AM    38 s      FAIL     apply
r-2a4f8c2  02:01 AM    41 s      FAIL     apply
r-2a4f8c1  01:01 AM    37 s      FAIL     apply
r-2a4f8c0  12:01 AM    4.2 m     OK
─────────────────────────────────────────────────
3 consecutive failures. First failure: r-2a4f8c1 (01:01 AM)
⚠ Stage: apply — DDL succeeded, build failed
```

What you learned in 5 seconds:
- 3 consecutive failures (not a transient fluke)
- First failure was at 01:01 AM (so the change came in around then)
- Stage is `apply` — the build inside apply is what's failing, not the IAM or schema layer

Add `--limit 50` if you need more history. Add `--since "2 days ago"` to time-bound.

## Step 2 — `runs logs --component dlq` (why)

```bash
fluid runs logs r-2a4f8c1 --component dlq --tail
```

The `dlq` component holds quarantined batches — rows that failed quality gates. `--tail` shows the most recent log lines:

```
01:01:23  build  ERROR  CHECK constraint failed:
01:01:23           arpu_30d_eur expected NOT NULL,
01:01:23           got 47 nulls in 12,408 rows
01:01:23  build  ERROR  Quarantined to dlq:
01:01:23           s3://forge-runtime/dlq/r-2a4f8c1/...
01:01:23  apply  FAIL   Hard gate: dq.rules NOT_NULL violated
```

Now you know:
- The failing rule is `arpu_30d_eur NOT_NULL`
- 47 of 12,408 rows are violating
- The data is preserved in S3 DLQ for re-processing

Other components you can ask about: `--component build`, `--component apply`, `--component verify`, `--component policy`. Default is all components, which is noisier.

## Step 3 — `runs diff` (what)

```bash
fluid runs diff r-2a4f8c0 r-2a4f8c1
```

Compares the last successful run to the first failed one — what *changed* between the two:

```
sources:
  + eu_signups_q4     (new region added 12h before first fail)
metrics:
    ~ arpu_30d_eur    now sees < 30 day customers
─────────────────────────────────────────────────
✓ Drift surface: 1 source added · 1 metric scope changed
ℹ dq.rules unchanged — they're correct, but assume 30 days of data
```

Now you have the full picture:
- A new EU region was added 12h before the first failure
- The metric's scope expanded to include customers younger than 30 days
- The `NOT_NULL` rule is correct, but the data lifecycle changed

The fix is *not* removing the rule — it's making the rule respect the lifecycle.

## Step 4 — fix (build SQL + rule threshold)

The schema's `dq.rule` shape doesn't carry a `where:` clause — instead, push the lifecycle logic into the SQL build (where it belongs) and relax the rule's threshold to acknowledge that some partial-window rows will be NULL by design.

**4a. Update the build's SQL** to emit `NULL` for customers younger than 30 days:

```yaml
# contract.fluid.yaml
builds:
  - id: customer_metrics
    pattern: embedded-logic
    engine: sql
    properties:
      sql: |
        SELECT
          customer_id,
          customer_age_days,
          -- Only emit arpu_30d_eur once the customer has 30 days of history
          CASE
            WHEN customer_age_days >= 30 THEN COALESCE(arpu_30d_eur_raw, 0)
            ELSE NULL
          END AS arpu_30d_eur
        FROM raw.customers c
        LEFT JOIN raw.transactions t USING (customer_id)
```

**4b. Relax the rule's threshold** so partial-window rows don't fail the gate:

```yaml
exposes:
  - exposeId: customer_360_table
    contract:
      dq:
        rules:
          - id: arpu_30d_eur_completeness
            type: completeness
            selector: arpu_30d_eur
            # threshold: 1.0  ← the bad version (failed on every <30-day customer)
            threshold: 0.85    # ← new: 85% of all rows have non-null arpu
            operator: ">="
            severity: error
            description: "arpu_30d_eur is intentionally NULL for customers younger than 30 days; 85% threshold accommodates the partial-window cohort"
```

`fluid validate` confirms the rule still parses:

```bash
fluid validate contract.fluid.yaml --strict
# ✓ Schema 0.7.2 — passed
# ✓ dq.rules — 8 rules, 1 changed, no breaking moves
# ✓ Contract validation passed (strict)
```

## Step 5 — `ship` (apply + verify + drain DLQ + restore SLA)

```bash
fluid ship contract.fluid.yaml --strict --env prod --yes
```

`ship` is the canonical "I'm fixing an incident, do all the right things" command:

```
⏳ Validating contract... ✓
⏳ Rendering plan... ✓ (plan checksum: a4f8c4...)
⏳ Applying...
✓ BigQuery DDL applied (no destructive changes)
⏳ Re-running quarantined batch from r-2a4f8c1 dlq...
✓ Recovered 12,361 rows (47 still in dlq, fallback applied)
✓ Freshness SLA restored: last successful run = 12 s ago
✓ Ship complete in 87 seconds — incident closed
```

What `ship` did, in order (per the canonical 4-stage chain — see [`fluid ship`](/forge_docs/cli/ship)):
1. `validate` (schema check)
2. `bundle` (skipped here via `--skip-bundle` if you don't need a snapshot)
3. `plan` (deterministic, plan-bound)
4. `apply` (idempotent re-application of the contract)

After apply, the runtime drains the DLQ from the failed run and re-runs `verify` against the deployed state. Audit records ship to the platform's native audit channel (BigQuery audit log / Snowflake `ACCESS_HISTORY` / CloudTrail) with the run ID, the contract checksum, and the deployed bindings.

For SOX-grade change tracking, commit the contract change behind a PR — the merged commit is the audit record. `git log contract.fluid.yaml` is the change history; `fluid runs status` is the runtime evidence.

## What about the 47 still in DLQ?

Those rows had `customer_age_days >= 30` AND null `arpu_30d_eur_raw` — a real data quality issue (mature customer, missing transactions). The new build emits `0` only via `COALESCE(arpu_30d_eur_raw, 0)`, but only when there's no `transactions` row at all; if the row exists with `NULL` already, the COALESCE returns 0 and the rule passes. The 47 are likely transactions-missing-for-the-customer cases — fix upstream or accept as a known quality miss.

Run:

```bash
fluid runs logs r-<ship-run-id> --component dlq
```

…to see them, then either fix upstream or accept them as a known quality miss.

## What you DIDN'T have to do

- Open the BigQuery web console and try to figure out what changed
- Diff Terraform state against actual deployed state
- Translate the schema-validator error into operator language
- Write a one-off SQL script to manually patch the 12,361 row
- Update three different tools with the same fix
- Wake up your platform engineer

## Common patterns this enables

- **Pre-merge CI**: `fluid runs status --product X --since "1 hour ago"` in CI catches a flaky build before it merges
- **Weekly health audit**: `fluid runs diff <last-week> <today>` for every product surfaces drift early
- **Post-incident review**: `fluid runs logs <run-id> --component all > incident.log` is the audit artifact

## See also

- [Day-2 ops demo](/see-it-run.html#skip-the-panic) — frame-perfect cast of this exact flow
- [`fluid runs`](/forge_docs/cli/runs) — the full command reference
- [`fluid ship`](/forge_docs/cli/ship) — incident-response apply
- [Typed CLI Errors](/forge_docs/advanced/typed-cli-errors) — the error taxonomy you'll see in logs
