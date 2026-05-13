---
title: Add quality rules
description: Add dq.rules to your data product contract — completeness, freshness, drift, valid_values, and how they block bad deploys before they ship.
---

# Task: Add quality rules to your data product

Forge's `dq.rules` block declares what *correct* means for your data product. Rules are evaluated at three points: at `validate` (schema-level), at `test` (pre-deploy quality gate), and at `verify` (post-deploy drift detection). Severity decides whether a violation blocks the deploy or just warns.

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

Each rule has `id` (unique, used in error messages), `type` (one of 8 allowed types), `selector` (which column/table), `threshold` + `operator` (the gate), and `severity` (`info` / `warn` / `error` / `critical`).

## Step 1 — pick a rule type

The 8 supported types in v0.7.2:

| Type | What it checks | Typical use |
|---|---|---|
| `completeness` | Non-null ratio of a column | Required IDs, mandatory metrics |
| `uniqueness` | No duplicates within a column or column-set | Primary keys, business keys |
| `freshness` | Time since last successful update | SLA-bound products |
| `valid_values` | All values in column appear in an allowed set | ISO codes, status enums |
| `accuracy` | Column compared against a reference | Daily totals matching upstream system |
| `schema` | No silent schema changes (added/removed/retyped columns) | Stability gate |
| `anomaly_detection` | Statistical outliers in a column | Revenue spikes, click anomalies |
| `drift_detection` | Distribution shift vs a baseline window | Model input drift, customer behaviour |

Most production contracts use 3-5 rules: usually **schema + completeness on key fields + freshness on the SLA window** as the minimum.

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

For columns that are *required for mature rows* but optional for young ones (e.g., 30-day rolling metrics), the schema doesn't carry a `where:` clause on the rule itself — handle the lifecycle in the SQL build, then check completeness on the populated column. See [Concepts → Quality, SLAs & Lineage → Common rule patterns](/concepts/quality-sla-lineage#common-rule-patterns) for the full pattern, including the production code that fixed the 3am incident in the [day2-ops demo](/see-it-run.html#skip-the-panic).

The shorter version: emit `NULL` from the SQL when the row isn't ready, set the rule's `threshold` below 1.0, and the rule passes for partial-window data without a fake `where:` field.

## Step 3 — add a freshness rule

```yaml
dq:
  rules:
    - id: hourly_freshness
      type: freshness
      window: PT1H                  # ISO-8601 duration: max 1h stale
      severity: warn
```

Freshness is evaluated against the deployed table's last write timestamp. The schema doesn't carry a `grace:` field — for a two-tier severity (warn at 1h, critical at 1h15m), declare two rules:

```yaml
dq:
  rules:
    - id: freshness_warn_1h
      type: freshness
      window: PT1H
      severity: warn

    - id: freshness_critical_75min
      type: freshness
      window: PT75M
      severity: critical
```

Wire scheduled `fluid verify` runs (every 15 minutes via your CI / orchestrator) so both rules evaluate against the actual deployed-table state.

## Step 4 — add a schema-stability rule

```yaml
dq:
  rules:
    - id: schema_stability
      type: schema
      severity: critical
```

This rule fails the deploy if a column was added, removed, or retyped without an explicit `exposes[].version` bump.

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
      description: "country must be in ISO 3166 alpha-2 (US, CA, GB, ...)"
```

For richer enum enforcement, gate it in the SQL build's `WHERE` clause (rejecting non-conforming rows to a quarantine table). The contract's `dq.rule` then verifies that `valid_values` holds against the cleaned product.

## Step 6 — validate that the rules are well-formed

```bash
fluid validate contract.fluid.yaml --strict
# ✓ Schema 0.7.2 — passed
# ✓ dq.rules — 4 rules, all reference real schema fields
# ✓ Severity enum values valid
# ✓ Contract validation passed (strict)
```

`validate --strict` catches malformed rules (typos in selector, unsupported operator, conflicting thresholds) before they reach a real deploy.

## Step 7 — test against actual data

`fluid test` runs the rules against the current state of the deployed product (or a sample if you pass `--sample`):

```bash
fluid test contract.fluid.yaml --sample
# ⏳ Loading 10,000-row sample from runtime/out/bitcoin_prices.parquet...
# ✓ price_not_null: 10,000 / 10,000 (100.0%) — pass
# ✓ schema_stability: no changes detected — pass
# ⚠ hourly_freshness: 1h 4m since last update — warn
# ✓ country_valid_iso: 9,847 / 9,847 (100.0%) — pass (153 rows null)
```

`test` is the pre-deploy gate. Severity controls behaviour: `error`/`critical` exit non-zero (blocks CI); `warn`/`info` exit zero (logged but doesn't block).

## Step 8 — wire `verify` for runtime drift detection

```bash
fluid verify contract.fluid.yaml --strict
```

`verify` runs against the **deployed state** (not a sample). It's the post-deploy gate: confirm that the live table actually has the schema, freshness, and quality the contract promised.

For continuous monitoring, declare your SLA targets on the expose's `qos` block:

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

Then schedule `fluid verify` via your CI / orchestrator (the contract declares the *target*; scheduling lives in the runtime layer):

```yaml
# .github/workflows/verify-fast.yml
on:
  schedule:
    - cron: "*/15 * * * *"            # every 15 min
jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - run: fluid verify contract.fluid.yaml --strict --env prod
```

Wire alerting to whatever your CI / orchestrator emits on a non-zero exit (PagerDuty webhook, Slack notification, etc.) — `fluid verify` exits non-zero on breach.

## Severity → CI behaviour

| Severity | `validate` | `test` | `verify --strict` |
|---|---|---|---|
| `info` | recorded | exit 0 | exit 0 |
| `warn` | recorded | exit 0 | exit 0 (warning only) |
| `error` | exit 0 (it's about runtime) | exit non-zero (blocks CI) | exit non-zero |
| `critical` | exit 0 | exit non-zero + emit incident | exit non-zero + emit incident |

## What you DIDN'T have to do

- Hand-roll dbt tests (`assertions: not_null`) for each column — `dq.rules` is per-product, not per-warehouse-syntax
- Wire a separate Great Expectations / Soda Core layer
- Maintain a separate "data quality monitoring" repo
- Translate rules between cloud-specific systems (BigQuery's column-level constraints, Snowflake's quality rules) — Forge translates them for you at `policy-apply`

## See also

- [Quality, SLAs & Lineage](/concepts/quality-sla-lineage) — full conceptual treatment
- [Recipe: Add a quality rule](/recipes/add-a-quality-rule) — the 1-page copy-paste version
- [`fluid test`](/forge_docs/cli/test) — the pre-deploy gate command
- [`fluid verify`](/forge_docs/cli/verify) — runtime drift detection
