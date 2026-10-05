---
title: Quality, SLAs & Lineage
description: Declare data quality rules, SLA targets and lineage in the contract, and run the rules with fluid test.
---

# Quality, SLAs & Lineage

Three pillars of "is this data product trustworthy?", all declared in the contract. `fluid validate` checks their shape, `fluid test` runs the quality rules against the data, and `fluid verify` compares the deployed product with the contract. The SLA targets are declarations: they are published, not monitored.

> **Why it matters**
> Consumers — and agents — can tell whether to trust a product *before* they use it: freshness, quality, and provenance are declared, not assumed.
> `exposes[].contract.dq.rules`, `exposes[].qos`, and `consumes[]` / `lineage` ship inside the contract.

## Data quality rules — `dq.rules`

Rules live at `exposes[].contract.dq.rules`. `fluid test` runs them against the deployed table and exits 1 when a rule at `error` or `critical` fails (`--strict` also fails on warnings).

```yaml
exposes:
  - exposeId: bitcoin_prices
    contract:
      schema:
        - name: price_usd
          type: NUMERIC
          required: true
        - name: updated_at
          type: TIMESTAMP
      dq:
        rules:
          - id: price_not_null
            type: completeness
            selector: price_usd          # the column the rule checks
            threshold: 1.0
            operator: ">="
            severity: error              # info | warn | error | critical

          - id: data_freshness
            type: freshness
            selector: updated_at         # the timestamp column to age
            window: PT1H                 # ISO-8601 duration
            severity: warn
```

Each rule needs `id`, `type` and `severity` to validate, and a `selector` to run: a rule with no `selector` fails with "missing 'selector' (column name)". A rule that fails at `error` or `critical` fails the test; `warn` is reported; `info` is recorded.

| `type` | What `fluid test` checks |
|---|---|
| `completeness` | Share of non-null values in `selector`, against `threshold` and `operator` |
| `uniqueness` | Share of distinct values in `selector`, against `threshold` and `operator` |
| `accuracy` | Values of `selector` against `threshold` and `operator` |
| `valid_values` | Values of `selector` are in an allowed list, written in the description as `"<column> valid values: A, B, C."` (the schema has no list field) |
| `freshness` | The newest value of the `selector` timestamp is no older than `window` |
| `anomaly_detection` | Row count (`selector: "*"`) against `threshold` and `operator` |
| `schema`, `drift_detection` | Not implemented. The schema accepts them, and `fluid test` reports each as a failed rule at its declared severity, saying the gate is not enforced |

`fluid apply` does not evaluate `dq.rules`, so a failing rule does not stop a deploy; `fluid test` is the gate. A step-by-step example, including the exit codes, is in [Add a quality rule](../recipes/add-a-quality-rule.md).

## SLAs — `qos`

Service-level targets at `exposes[].qos`:

```yaml
exposes:
  - exposeId: bitcoin_prices
    qos:
      availability: "99.5%"
      freshnessSLO: PT1H
      latencyP95: PT1S
      dataLossSLO: "0 rows"
      completenessTarget: 0.99
      errorBudget: 0.01
```

| Field | Type | Example |
|---|---|---|
| `availability` | String ending in `%` | `"99.5%"` (a bare `99.5` fails validation) |
| `freshnessSLO`, `latencyP95` | ISO-8601 duration: years, months, weeks, days, hours, minutes, whole seconds | `PT1H`, `PT1S`. `PT500MS` and fractional seconds fail validation |
| `dataLossSLO` | Free-form string | `"0 rows"` |
| `completenessTarget`, `errorBudget` | Number from 0 to 1 | `0.99`, `0.01` |

The standards exporters (ODCS, ODPS, OPDS) and Data Mesh Manager publishing read these targets. As of 0.18.1 no forge-cli command measures the product against them; schedule your own checks (see [Multi-window monitoring](#multi-window-monitoring)).

`exposes[].observability` sits next to `qos`: `metrics`, `onBreach` targets, `defaultSLIs` and `alert.channels`. Of these, the acquisition runner reads `observability.alert.channels` (`log`, `file` or `webhook`) to send DLQ-overflow, schema-change and anomaly alerts. As of 0.18.1 nothing reads `metrics`, `onBreach` or `defaultSLIs`.

## Lineage — declared, then checked

Lineage comes from what the contract declares:

1. **`consumes[]`** — upstream data products this one reads, at the contract root. This is what composes products into higher-value products.
2. **`lineage`** — an optional top-level block for cross-system lineage: `granularity` (`table_level` or `field_level`), `upstream[]` (each with `productId`, `exposeId`, optional `relationship` and `fieldMappings` from source to target field) and `downstream`.

```yaml
lineage:
  granularity: field_level
  upstream:
    - productId: silver.crm.customers_v1
      exposeId: customers
      relationship: direct_consumption
      fieldMappings:
        - sourceField: email
          targetField: email_hash
          transformation: {type: calculation, expression: "sha256(email)"}
```

`fluid verify --reconcile-lineage` cross-checks the declared lineage (`consumes[]` and `exposes[]`) against local run evidence and the catalog publish payload; an undeclared read fails under `--strict`. `fluid plan --html` writes an HTML view of the plan.

## Common rule patterns

These are the rule shapes most production data products end up with. Copy them as a starting point. **Each example uses only fields defined in `fluid-schema-0.7.3.json`.**

### Conditional completeness via the build, not the rule

The schema's `dqRule` shape (`id`, `type`, `selector`, `threshold`, `operator`, `window`, `severity`, `description`, `tags`, `labels`) intentionally doesn't carry a `where:` clause. The recommended pattern when a column is *required for some rows but not others* is to handle it in the SQL build, then check completeness on the fully-populated column:

```yaml
builds:
  - id: customer_metrics
    pattern: embedded-logic
    engine: sql
    properties:
      sql: |
        SELECT
          customer_id,
          customer_age_days,
          -- arpu is non-null only when 30 days of history exists
          CASE
            WHEN customer_age_days >= 30 THEN COALESCE(arpu_30d_eur_raw, 0)
            ELSE NULL
          END AS arpu_30d_eur
        FROM raw.customers c
        LEFT JOIN raw.transactions t USING (customer_id)
```

Then the rule is plain completeness, scoped to the rows you care about via the `selector`'s downstream filter (or simply tolerated at threshold < 1.0):

```yaml
dq:
  rules:
    - id: arpu_30d_completeness
      type: completeness
      selector: arpu_30d_eur
      threshold: 0.85         # 85% of all rows have non-null arpu (the 15% are < 30 days)
      operator: ">="
      severity: error
```

This pattern keeps the rule schema clean and pushes the lifecycle logic into SQL where it belongs.

### Schema and distribution drift

`schema` and `drift_detection` rules are not implemented by any engine as of 0.18.1: `fluid test` reports them as failed (an `error` rule fails the run), the dbt export emits a test name dbt reports as not found, and `--engine soda` lists them as unmapped. Use what is implemented instead:

- Schema drift: `fluid verify` compares the deployed table's schema with the contract; `--strict` fails on critical drift.
- Volume drift: an `anomaly_detection` rule on the row count.

```yaml
dq:
  rules:
    - id: row_count_floor
      type: anomaly_detection
      selector: "*"                   # row count
      threshold: 1000
      operator: ">="
      severity: warn
```

### Freshness with two-tier severity

The schema has no `grace` / `escalate_after` field — declare two separate rules with different windows + severities to express the same intent:

```yaml
dq:
  rules:
    - id: freshness_hourly_warn
      type: freshness
      selector: updated_at
      window: PT1H
      severity: warn

    - id: freshness_75min_critical
      type: freshness
      selector: updated_at
      window: PT75M
      severity: critical
```

A scheduled `fluid test` evaluates both against the newest `updated_at`; past one hour the first warns, past 75 minutes the second fails the run.

### Valid values

The allowed set goes in the rule's `description`, in the form `<column> valid values: A, B, C.`; the schema has no list field for it. A `valid_values` rule whose description names no values fails with "declares no allowed values, so nothing was checked".

```yaml
dq:
  rules:
    - id: country_valid_iso
      type: valid_values
      selector: country
      severity: error
      description: "country valid values: US, CA, GB, DE, FR."
```

The list ends at the first full stop, so values cannot contain one.

## Multi-window monitoring

The schema has no scheduling block for checks: `qos` declares targets, and your CI or orchestrator runs the checks. Pattern:

1. **Targets** live on `exposes[].qos`:
   ```yaml
   exposes:
     - exposeId: customer_360_table
       qos:
         availability: "99.5%"
         freshnessSLO: PT1H              # ISO 8601 duration
         latencyP95: PT1S                # whole seconds; no millisecond unit
         completenessTarget: 0.99
         errorBudget: 0.01
   ```

2. **Schedules** live in your CI / orchestrator (Airflow / Dagster / GitHub Actions cron). For example:
   ```yaml
   # .github/workflows/verify-fast.yml
   on:
     schedule:
       - cron: "*/15 * * * *"          # every 15 min
   jobs:
     test:
       runs-on: ubuntu-latest
       steps:
         - run: fluid test contract.fluid.yaml --env prod

   # .github/workflows/verify-weekly-audit.yml
   on:
     schedule:
       - cron: "0 8 * * MON"           # Monday 08:00
   jobs:
     audit:
       runs-on: ubuntu-latest
       steps:
         - run: fluid verify contract.fluid.yaml --strict --env prod --out verify-report.json | tee audit.log
```

The fast schedule runs the `dq.rules`, so a `freshness` rule whose `window` matches `freshnessSLO` catches stale data; the weekly run compares the deployed product with the contract and keeps the JSON report. Neither command reads the `qos` values themselves: express each target you want checked as a rule.

## Lineage and catalog formats

`fluid generate artifacts` writes the contract in catalog standards, plus the compiled policy bindings, under `dist/artifacts/` with a `MANIFEST.json` that hashes every file. On the quickstart contract:

```text
dist/artifacts/MANIFEST.json
dist/artifacts/odcs/product.odcs.customer_360_master.yaml
dist/artifacts/odcs/product.odcs.high_value_customers.yaml
dist/artifacts/odps-bitol/gold.customer.analytics_360_v1.customer_360_master.odcs.yaml
dist/artifacts/odps-bitol/gold.customer.analytics_360_v1.high_value_customers.odcs.yaml
dist/artifacts/odps-bitol/gold.customer.analytics_360_v1.odps.yaml
dist/artifacts/opds/gold.customer.analytics_360_v1.opds.json
dist/artifacts/policy/bindings.json
```

| Format | Directory | Used by |
|---|---|---|
| **ODCS** (Open Data Contract Standard), one per expose | `odcs/` | Data Mesh Manager and other ODCS-aware catalogs |
| **ODPS-Bitol** (Bitol Open Data Product Standard) | `odps-bitol/` | Bitol-aware catalogs |
| **OPDS** (Open Data Product Specification v4.1, LF/ODPI) | `opds/` | Generic catalog ingest |

OpenLineage is not written to a file. Runs send OpenLineage run events over HTTP when `OPENLINEAGE_URL` (or `FLUID_OPENLINEAGE_URL`) is set: acquisition builds, and `fluid apply` through OpenTofu. Marquez and DataHub accept them. With no URL set, nothing is sent.

## Where to look next

- [Governance & Policy](./governance-policy.md) — `accessPolicy` and `agentPolicy` complementing `dq.rules`
- [Builds, Exposes, Bindings](./builds-exposes-bindings.md) — where `dq.rules` lives in the schema
- [`fluid verify`](/forge_docs/cli/verify) — runtime drift detection
- [`fluid test`](/forge_docs/cli/test) — pre-deploy quality gates
