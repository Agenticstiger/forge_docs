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

These are the rule shapes most production data products end up with. Copy them as a starting point.

### NOT NULL with conditional fallback

For columns that are required for "mature" rows but optional for early-stage ones (e.g., 30-day rolling metrics on customers younger than 30 days):

```yaml
dq:
  rules:
    - id: arpu_30d_not_null
      type: completeness
      selector: arpu_30d_eur
      where: customer_age_days >= 30      # ← conditional NOT NULL
      threshold: 0.99                     # 99% of qualifying rows
      operator: ">="
      severity: error
      fallback: zero                      # safe default for partial-window rows
```

This pattern is what saved the 3am incident in the [day2-ops demo](/forge_docs/see-it-run.html#skip-the-panic). A pure `NOT NULL` rule fails on every new EU signup; the conditional version respects the data lifecycle.

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
      window: P14D                    # 14-day rolling baseline
      threshold: 0.20                 # alert if >20% Wasserstein distance from baseline
      operator: "<="
      severity: warn
```

`drift_detection` requires the `verify` command running on a schedule against a baseline window. Set up via the `slas[].monitoring` block.

### Freshness with grace period

```yaml
dq:
  rules:
    - id: hourly_freshness
      type: freshness
      window: PT1H                    # max 1 hour stale
      grace: PT15M                    # warn at 1h, critical at 1h15m
      severity: warn
      escalate_after: PT15M
      escalate_severity: critical
```

### Valid values from a known set

```yaml
dq:
  rules:
    - id: country_valid_iso
      type: valid_values
      selector: country
      values_source: file:./refs/iso_3166_alpha2.csv     # external reference
      threshold: 1.0
      operator: ">="
      severity: error
```

## Multi-window monitoring

`slas[].monitoring` schedules `verify` runs at multiple cadences:

```yaml
slas:
  - name: production_freshness
    metric: freshness
    threshold: PT1H
    monitoring:
      schedule: "*/15 * * * *"        # every 15 min
      breach_action: alert
      breach_target: pagerduty:data-oncall
      
  - name: weekly_quality_audit
    metric: dq.completeness.overall
    threshold: 0.999
    monitoring:
      schedule: "0 8 * * MON"         # Monday 08:00
      breach_action: email
      breach_target: data-team@company.com
```

The fast schedule catches stale-data incidents; the slow schedule catches creeping quality issues that the fast one wouldn't notice (because each individual breach is below the per-rule threshold).

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
