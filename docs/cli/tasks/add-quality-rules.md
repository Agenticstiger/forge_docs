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

For columns that are *required for mature rows* but optional for young ones (e.g., 30-day rolling metrics), use the `where:` clause:

```yaml
dq:
  rules:
    - id: arpu_30d_not_null
      type: completeness
      selector: arpu_30d_eur
      where: customer_age_days >= 30      # ← conditional NOT NULL
      threshold: 0.99
      operator: ">="
      severity: error
      fallback: zero                      # safe default for partial-window rows
```

This pattern is what the [day2-ops demo](/forge_docs/see-it-run.html#skip-the-panic) uses to fix the 3am incident.

## Step 3 — add a freshness rule

```yaml
dq:
  rules:
    - id: hourly_freshness
      type: freshness
      window: PT1H                  # ISO-8601 duration: max 1h stale
      grace: PT15M                  # warn at 1h; critical at 1h15m
      severity: warn
      escalate_after: PT15M
      escalate_severity: critical
```

Freshness is evaluated against the deployed table's last write timestamp. Wire it to your `slas[].monitoring` schedule so `verify` runs every 15 minutes against the breach threshold.

## Step 4 — add a schema-stability rule

```yaml
dq:
  rules:
    - id: schema_stability
      type: schema
      severity: critical
```

This rule fails the deploy if a column was added, removed, or retyped without an explicit `exposes[].version` bump. The CLI requires a `--allow-schema-change` flag to override.

## Step 5 — add valid_values for enums

```yaml
dq:
  rules:
    - id: country_valid_iso
      type: valid_values
      selector: country
      values_source: file:./refs/iso_3166_alpha2.csv      # or values: [US, CA, GB, ...]
      threshold: 1.0
      operator: ">="
      severity: error
```

External `values_source` files are checked into git alongside the contract. The CLI tracks their hash so a values-file change triggers a `plan` diff.

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

For continuous monitoring, schedule `verify` via your orchestrator or via Forge's `slas[].monitoring`:

```yaml
slas:
  - name: production_freshness
    metric: freshness
    threshold: PT1H
    monitoring:
      schedule: "*/15 * * * *"             # every 15 min
      breach_action: alert
      breach_target: pagerduty:data-oncall
```

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

- [Quality, SLAs & Lineage](/forge_docs/concepts/quality-sla-lineage) — full conceptual treatment
- [Recipe: Add a quality rule](/forge_docs/recipes/add-a-quality-rule) — the 1-page copy-paste version
- [`fluid test`](/forge_docs/cli/test) — the pre-deploy gate command
- [`fluid verify`](/forge_docs/cli/verify) — runtime drift detection
