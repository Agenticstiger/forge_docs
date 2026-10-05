---
title: Add quality rules
description: Add dq.rules to your data product contract — completeness, freshness, drift, valid_values, and how they block bad deploys before they ship.
---

# Task: Add quality rules to your data product

Forge's `dq.rules` block declares what *correct* means for your data product. `fluid validate` checks that the rules are well-formed, and [`fluid test`](../test.md) evaluates them against the data. Severity decides whether a failed rule fails the run or only warns.

Time: ~10 minutes for the basic shape, longer if you're fitting rules to existing production data.

## Where rules live

Rules live at `exposes[].contract.dq.rules`:

```yaml
exposes:
  - exposeId: bitcoin_prices
    contract:
      schema:
        - name: price_usd
          type: NUMERIC
          required: true
      dq:
        rules:
          - id: price_not_null
            type: completeness
            selector: price_usd
            threshold: 1.0
            operator: ">="
            severity: error
```

Each rule has `id` (unique, used in error messages), `type` (see the table below), `selector` (which column/table), `threshold` + `operator` (the gate), and `severity` (`info` / `warn` / `error` / `critical`).

## Step 1 — pick a rule type

The contract schema accepts these types. The native engine of `fluid test` runs six of them:

| Type | What it checks | Typical use |
|---|---|---|
| `completeness` | Non-null ratio of the `selector` column | Required IDs, mandatory metrics |
| `uniqueness` | Share of distinct values in a column | Primary keys, business keys |
| `freshness` | Age of the newest timestamp in the `selector` column, against `window` | SLA-bound products |
| `valid_values` | Every value is in an allowed list written in the rule's `description` | ISO codes, status enums |
| `accuracy` | Column values compared with `threshold` using `operator` | Amounts that must not be negative |
| `schema` | Accepted by the schema, **not implemented**: reported as failing | Not enforced by any engine |
| `anomaly_detection` | Row count: `selector: '*'` means `COUNT(*)`, compared with `threshold` | Empty or truncated loads |
| `drift_detection` | Accepted by the schema, **not implemented**: reported as failing | Not enforced by any engine |

A reasonable starting set is completeness on key fields, uniqueness on the primary key, and freshness on the SLA window. For column-set changes, use [`fluid contract-tests`](../contract-tests.md), which compares each expose's schema with a saved baseline.

## Step 2 — add a completeness rule

The simplest rule. "This column must not be null."

```yaml
dq:
  rules:
    - id: customer_id_required
      type: completeness
      selector: customer_id
      threshold: 1.0                # 100% of rows
      operator: ">="
      severity: error               # blocks deploy if violated
```

For columns that are *required for mature rows* but optional for young ones (e.g., 30-day rolling metrics), the schema doesn't carry a `where:` clause on the rule itself — handle the lifecycle in the SQL build, then check completeness on the populated column. See [Concepts → Quality, SLAs & Lineage → Common rule patterns](/forge_docs/concepts/quality-sla-lineage#common-rule-patterns) for the full pattern, including the production code that fixed the 3am incident in the [day2-ops demo](/forge_docs/see-it-run.html#skip-the-panic).

The shorter version: emit `NULL` from the SQL when the row isn't ready, set the rule's `threshold` below 1.0, and the rule passes for partial-window data without a fake `where:` field.

## Step 3 — add a freshness rule

```yaml
dq:
  rules:
    - id: hourly_freshness
      type: freshness
      selector: updated_at          # timestamp column to age
      window: PT1H                  # ISO-8601 duration: max 1h stale
      severity: warn
```

Freshness needs a `selector` naming a timestamp column: without one the rule fails with `missing 'selector' (column name)`. It compares the newest value in that column with `window`, so a table whose timestamp column is not updated on write looks stale. The schema doesn't carry a `grace:` field — for a two-tier severity (warn at 1h, critical at 1h15m), declare two rules:

```yaml
dq:
  rules:
    - id: freshness_warn_1h
      type: freshness
      selector: updated_at
      window: PT1H
      severity: warn

    - id: freshness_critical_75min
      type: freshness
      selector: updated_at
      window: PT75M
      severity: critical
```

Run `fluid test` on a schedule from your CI or orchestrator so both rules evaluate against the data as it is.

## Step 4 — do not rely on `schema` or `drift_detection`

```yaml
dq:
  rules:
    - id: schema_stability
      type: schema
      selector: '*'
      severity: critical
```

The contract schema accepts this rule and `fluid validate` passes. `fluid test` then fails it at its own severity, because no engine implements the type. Measured against 0.18.1:

```text
Rule 'schema_stability' has type 'schema', which the native quality engine does not implement — this gate is NOT being enforced. No fluid engine implements it (`--engine soda` reports it as unmapped too); ...
```

`drift_detection` behaves the same way. To catch a changed column set, save a baseline with `fluid contract-tests --write-baseline` and compare against it in CI (see [`fluid contract-tests`](../contract-tests.md)).

## Step 5 — add valid_values for enums

```yaml
dq:
  rules:
    - id: country_valid_iso
      type: valid_values
      selector: country
      threshold: 1.0
      operator: ">="
      severity: error
      description: "country valid values: US, CA, GB"
```

The allowed list is read from the rule's `description` (for example `country valid values: US, CA, GB.`); the schema has no field for it, and a rule with no list checks nothing and says so. For stricter enforcement, gate it in the SQL build's `WHERE` clause (rejecting non-conforming rows to a quarantine table).

## Step 6 — validate that the rules are well-formed

```bash
fluid validate contract.fluid.yaml --strict
```

```text
✅ Valid FLUID contract (schema v0.7.5)
```

`validate` checks the rule shape against the schema, for example an unknown `type` or `severity`. It does not read your data.

## Step 7 — test against actual data

`fluid test` reads the data the expose is bound to and evaluates the rules. With a `completeness` rule on `customer_id` (severity `error`) and one on `country` (severity `warn`) over a three-row Parquet file in which one country is null:

```bash
fluid test contract.fluid.yaml
```

```text
│ 7    │ ⚠️     │ Quality tests          │ country_complete — completeness for │
│      │        │                        │ 'country' is 66.67%                 │
...
✅ 5 passed  |  3 warned  |  0 error(s)  |  2 warning(s)  |  0.45s
Data-quality rules: 1/2 passed
```

The exit code is `0` because the failing rule has severity `warn`. `--strict` turns any warning into exit `1`. A failing `error` or `critical` rule fails the run with exit `1`. Pass `--no-cache` after you change the data's schema; see [the schema cache](../test.md#the-schema-cache).

## Step 8 — run `test` after deploy, and `verify` for deployed state

```bash
fluid verify contract.fluid.yaml --strict
```

`verify` compares the deployed resource with the contract. Against the local provider it checks that the declared columns exist; it did not evaluate `dq.rules` in a measured run, so keep `fluid test` as the command that runs them. Declare SLA targets on the expose's `qos` block if you want them recorded with the contract:

```yaml
exposes:
  - exposeId: customer_360_table
    qos:
      availability: 99.5
      freshnessSLO: PT1H              # ISO 8601 duration
      completenessTarget: 0.99
      latencyP95: PT500MS
      errorBudget: 0.01
```

Schedule the commands from your CI or orchestrator; the contract declares the targets and scheduling lives in the runtime layer:

```yaml
# .github/workflows/test-fast.yml
on:
  schedule:
    - cron: "*/15 * * * *"            # every 15 min
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: fluid test contract.fluid.yaml --env prod --no-cache
```

Wire alerting to whatever your CI or orchestrator emits on a non-zero exit (PagerDuty webhook, Slack notification, and so on).

## Severity and exit codes in `fluid test`

| Severity | Result in `fluid test` | Exit code |
|---|---|---|
| `info` | Recorded, counts as passed | 0 |
| `warn` | Shown as a warning | 0 (`1` with `--strict`) |
| `error` | Fails the run | 1 |
| `critical` | Fails the run | 1 |

## What you DIDN'T have to do

- Hand-roll dbt tests (`assertions: not_null`) for each column — `dq.rules` is per-product, not per-warehouse-syntax
- Wire a separate Great Expectations / Soda Core layer
- Maintain a separate "data quality monitoring" repo
- Write rules per warehouse: `fluid test` runs the same `dq.rules` on whichever provider the expose is bound to, and `--engine soda` runs them through Soda

## See also

- [Quality, SLAs & Lineage](/forge_docs/concepts/quality-sla-lineage) — full conceptual treatment
- [Recipe: Add a quality rule](/forge_docs/recipes/add-a-quality-rule) — the 1-page copy-paste version
- [`fluid test`](../test.md) — the pre-deploy gate command
- [`fluid verify`](../verify.md) — runtime drift detection
