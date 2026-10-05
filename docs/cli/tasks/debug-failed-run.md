---
title: Debug a failed pipeline run
description: 3am Slack ping, pipeline broke. Walk through fluid runs status, logs, diff, fix and ship.
---

# Task: Debug a failed pipeline run

It's 3am. PagerDuty fired. `gold.finance.customer_360_v1` missed its 1-hour freshness SLA. You need to find out **where** it broke, **why** it broke, **what** changed, fix it, and ship.

`fluid runs` reads the run records Forge wrote: three commands, one fix, one `ship`. The product, run ids and numbers on this page are a made-up scenario; the command output described is what 0.18.1 prints.

## The flow

```bash
fluid runs status gold.finance.customer_360_v1
fluid runs logs gold.finance.customer_360_v1 --component dlq --run-id <first-fail-run>
fluid runs diff gold.finance.customer_360_v1 --build customer_metrics --run-a <last-ok-run> --run-b <first-fail-run>
# ...edit one line in contract.fluid.yaml...
fluid ship contract.fluid.yaml --strict --env prod --yes
```

A frame-perfect cast of this exact flow is in the [day2-ops demo](/forge_docs/see-it-run.html#skip-the-panic) — bookmark it.

## Step 1 — `runs status` (where)

```bash
fluid runs status gold.finance.customer_360_v1
```

Shows the most recent run records of the product's build: for each run its id, state (`succeeded`, `failed`, `partial` or `running`), start and finish time, record count and error, plus the product's freshness (age of the newest succeeded run), its 24-hour error rate and the state of the newest run. The run records are the files under `.fluid/runs/<product-id>/<build-id>/runs/`. If there are none, the command says so and names the directory:

```text
no builds found for product silver.shop.customers_v1 under <project>/.fluid/runs/silver.shop.customers_v1/
```

In the scenario of this page, what you read from it:
- Several consecutive runs in state `failed`, so this is not a transient fluke
- The oldest of them is the first failure, which dates the change that broke the build

`runs status` shows the 5 most recent runs by default. Pass `--last 50` for more history, `--build <id>` to scope it to one build, or `--json` for the machine-readable report ([field list](../runs.md#output-shape-json)).

## Step 2 — `runs logs --component dlq` (why)

```bash
fluid runs logs gold.finance.customer_360_v1 --component dlq --run-id <first-fail-run>
```

The `dlq` component holds quarantined batches, the rows that failed a quality gate. `--run-id` pins the fetch to a specific run; omit it and `runs logs` reads the most recent run for the build. In this scenario the log names a failing `completeness` rule on `arpu_30d_eur` and a count of null rows, which tells you which rule fired and how many rows violate it.

Other components: `--component build`, `--component infra`, `--component server`, `--component worker`. The default is `build`. Add `--grep <pattern>` to filter log lines, or `--limit <n>` to cap how many are returned (default 1000).

## Step 3 — `runs diff` (what)

```bash
fluid runs diff gold.finance.customer_360_v1 --build customer_metrics --run-a <last-ok-run> --run-b <first-fail-run>
```

Compares the last successful run with the first failed one. The report lists columns added or removed between the two runs and the row-count delta (`added`, `removed` and `row_delta` with `--json`). It does not compare sources or metric definitions, so pair it with `git diff contract.fluid.yaml` to see what changed in the contract between the two runs.

In this scenario the contract diff shows that a new region was added before the first failure, which brought in customers younger than 30 days, and the completeness rule assumes 30 days of data. The fix is not removing the rule; it is making the data respect the customer lifecycle.

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

**4b. Relax the rule's threshold** so partial-window rows don't fail the gate (`threshold: 1.0` required every row to be non-null):

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
```

```text
✅ Valid FLUID contract (schema v0.7.5)
```

Then run `fluid test contract.fluid.yaml --no-cache` against the rebuilt data: it evaluates the `completeness` rule, and `--no-cache` makes it read the current schema ([the schema cache](../test.md#the-schema-cache)).

## Step 5 — `ship` (validate, bundle, plan, apply)

```bash
fluid ship contract.fluid.yaml --strict --env prod --yes
```

`ship` chains four stages and stops at the first failure (see [`fluid ship`](../ship.md)):
1. `validate` (`--strict` makes warnings errors)
2. `bundle` (skip it with `--skip-bundle` if you don't need a snapshot)
3. `plan`
4. `apply`

`ship` does not re-run quarantined batches. Rows in the DLQ stay there until you reprocess them with your own tooling, and `ship` does not run `verify`; run [`fluid verify`](../verify.md) afterwards.

For SOX-grade change tracking, commit the contract change behind a PR — the merged commit is the audit record. `git log contract.fluid.yaml` is the change history; `fluid runs status` is the runtime evidence.

## What about the rows still in the DLQ?

In this scenario the remaining rows are customers older than 30 days with no transactions at all, a data quality issue upstream rather than a lifecycle effect. List them with:

```bash
fluid runs logs gold.finance.customer_360_v1 --component dlq --run-id <ship-run-id>
```

then fix upstream or accept them as a known quality miss.

## What you DIDN'T have to do

- Open the cloud console and try to figure out what changed
- Diff Terraform state against actual deployed state
- Write a one-off SQL script to manually patch the rows

## Common patterns this enables

- **Pre-merge CI**: `fluid runs status <product-id> --last 1 --json` in CI catches a flaky build before it merges
- **Weekly health audit**: `fluid runs diff <product-id> --build <id> --run-a <last-week-run> --run-b <today-run>` for every product surfaces drift early
- **Post-incident review**: `fluid runs logs <product-id> --run-id <run-id> --component build > incident.log` is the audit artifact

## See also

- [Day-2 ops demo](/forge_docs/see-it-run.html#skip-the-panic) — frame-perfect cast of this exact flow
- [`fluid runs`](../runs.md) — the full command reference
- [`fluid ship`](../ship.md) — incident-response apply
- [Typed CLI Errors](/forge_docs/advanced/typed-cli-errors) — the error taxonomy you'll see in logs
