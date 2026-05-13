---
title: Quality, SLAs & Lineage
description: Block bad deploys before they happen. dq.rules, qos, and auto-derived lineage.
---

# Quality, SLAs & Lineage

Three pillars of "is this data product trustworthy?" — all declarative, all enforced by `fluid validate` + `fluid test` + `fluid verify`.

## Data quality rules — `dq.rules`

Live at `exposes[].contract.dq.rules`. Each rule has an `id`, a `type`, a `severity`, and (usually) a `selector` + `threshold` + `operator`.

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
            type: completeness          # ← one of the 8 allowed types
            selector: price_usd
            threshold: 1.0
            operator: ">="
            severity: error             # error | warn | info

          - id: data_freshness
            type: freshness
            window: PT1H                # ISO 8601 duration
            severity: warn
```

Allowed `type` values (v0.7.2 schema):
`freshness` · `completeness` · `uniqueness` · `valid_values` · `accuracy` · `schema` · `anomaly_detection` · `drift_detection`

Severity enum (verified against `fluid-schema-0.7.2.json`): `info` · `warn` · `error` · `critical`.

Conventional behavior (confirm specifics with `fluid apply -h` / `fluid test -h` for your CLI version):
- **`error` / `critical`** — block the deploy. Used for hard guarantees.
- **`warn`** — deploy proceeds; warning emitted to stdout + the test report.
- **`info`** — recorded only.

## SLAs — `qos`

Service-level targets at `exposes[].qos`:

```yaml
exposes:
  - exposeId: bitcoin_prices
    qos:
      availability: "99.5%"
      maxLatency: PT5S
```

Currently used for catalog publish (ODCS) + Data Mesh Manager. Active monitoring against these thresholds is on the roadmap.

## Lineage — auto-derived

You don't write lineage yourself. The schema captures upstream relationships through:

1. **`consumes[]`** — explicit upstream-product references at the contract root.
2. **`builds[].properties.sql`** — column-level lineage parsed from SQL.
3. **`builds[].repository`** — for `hybrid-reference` builds, the dbt manifest is read for graph data.

The exact output paths and viewer formats depend on the CLI version + provider. Run `fluid plan --html` and check the generated artifact directory; document what you see in your team's runbook rather than relying on this page.

## Common rule patterns

These are the rule shapes most production data products end up with. Copy them as a starting point. **Each example uses only fields defined in `fluid-schema-0.7.2.json`.**

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

### Drift detection on schema or distribution

```yaml
dq:
  rules:
    - id: schema_stability
      type: schema
      severity: critical              # block deploy on schema change without explicit version bump

    - id: revenue_distribution_drift
      type: drift_detection
      selector: weekly_revenue
      window: P14D                    # 14-day rolling baseline (ISO 8601 duration)
      threshold: 0.20                 # alert if drift score exceeds threshold
      operator: "<="
      severity: warn
```

`drift_detection` requires the `verify` command running on a schedule against a baseline window. Schedule `fluid verify` via your CI / orchestrator (Airflow, Dagster, GitHub Actions cron) — the `qos` block on the expose declares the *target*, but scheduling lives in the runtime layer.

### Freshness with two-tier severity

The schema has no `grace` / `escalate_after` field — declare two separate rules with different windows + severities to express the same intent:

```yaml
dq:
  rules:
    - id: freshness_hourly_warn
      type: freshness
      window: PT1H
      severity: warn

    - id: freshness_75min_critical
      type: freshness
      window: PT75M
      severity: critical
```

CI runs `fluid verify`; both rules evaluate against the same deployed-table last-write timestamp; whichever crosses first fires.

### Valid values

The schema's `valid_values` rule type takes a `selector` plus a `threshold` + `operator` — the actual allowed set is enforced by the build's filtering (or the schema field's `description`). Common pattern:

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

For richer enum enforcement, gate it in the build's `WHERE` clause (rejecting non-conforming rows to a quarantine table) or use the schema field's `description` to document the allowed set.

## Multi-window monitoring

The schema doesn't provide a built-in scheduling block — `qos` declares targets, runtime declares schedules. Pattern:

1. **Targets** live on `exposes[].qos`:
   ```yaml
   exposes:
     - exposeId: customer_360_table
       qos:
         availability: 99.5
         freshnessSLO: PT1H              # ISO 8601 duration
         latencyP95: PT500MS
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
     verify:
       runs-on: ubuntu-latest
       steps:
         - run: fluid verify contract.fluid.yaml --strict --env prod

   # .github/workflows/verify-weekly-audit.yml
   on:
     schedule:
       - cron: "0 8 * * MON"           # Monday 08:00
   jobs:
     audit:
       runs-on: ubuntu-latest
       steps:
         - run: fluid verify contract.fluid.yaml --strict --env prod --json | tee audit.log
```

The fast schedule catches stale-data incidents (against `freshnessSLO`); the slow audit catches creeping quality drift (against `completenessTarget`). Both invoke `fluid verify` against the same contract; the contract is the source of truth.

## Lineage emission formats

`fluid generate artifacts` emits lineage in three industry-standard formats:

| Format | File | Used by |
|---|---|---|
| **OPDS** (Open Product Data Schema) | `artifacts/standards/product.opds.json` | Generic catalog ingest |
| **ODCS** (Open Data Contract Standard) | `artifacts/standards/product.odcs.yaml` | Data Mesh Manager, Atlan, Collibra (when configured) |
| **OpenLineage** | `artifacts/lineage/openlineage.json` | Marquez, DataHub, OpenLineage-compliant tools |

Pick whichever your existing catalog speaks. The contract is the source of truth; these are derived artifacts that re-emit on every `apply`.

## Where to look next

- [Governance & Policy](./governance-policy.md) — `accessPolicy` and `agentPolicy` complementing `dq.rules`
- [Builds, Exposes, Bindings](./builds-exposes-bindings.md) — where `dq.rules` lives in the schema
- [`fluid verify`](/forge_docs/cli/verify) — runtime drift detection
- [`fluid test`](/forge_docs/cli/test) — pre-deploy quality gates
