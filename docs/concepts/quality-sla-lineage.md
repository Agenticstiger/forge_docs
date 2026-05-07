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

---

::: warning This page is a stub
Full coverage of monitoring windows, anomaly detection thresholds, and the OPDS lineage export format is tracked in [docs-content #concepts-quality](https://github.com/Agentics-Rising/forge_docs/issues?q=is%3Aopen+label%3Adocs-content).
:::
