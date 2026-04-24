# `fluid verify`

Stage 9 of the 11-stage pipeline. Multi-dimensional validation that deployed infrastructure still matches the FLUID contract — schema, data types, constraints, and region all checked independently with severity-based drift assessment.

## Syntax

```bash
fluid verify CONTRACT
```

## Key options

| Option | Description |
| --- | --- |
| `--expose`, `--expose-id` | Verify only a specific expose |
| `--strict` | Exit non-zero when mismatches are found |
| `--out` | Write a JSON verification report (default: `runtime/verify-report.json`) |
| `--show-diffs` | Show field-by-field differences |
| `--env` | Apply an environment overlay |

## Dimensional analysis

Each expose is checked across four dimensions:

| Dimension | What it compares |
| --- | --- |
| **Schema structure** | Column names and count vs. the contract |
| **Data types** | Each column's warehouse type vs. the FLUID type |
| **Constraints** | `nullable` vs. `required` |
| **Location** | Region / location matches `binding.location.region` |

Each mismatch is scored for severity:

| Severity | When it fires | Remediation |
| --- | --- | --- |
| 🔴 **CRITICAL** | Missing fields, type mismatches, or region mismatch | Manual intervention (table recreation / migration). |
| 🟡 **WARNING** | Constraint mismatches (nullable / required) | Manual recommended; non-breaking but worth addressing. |
| 🔵 **INFO** | Extra fields in the table not in the contract | Auto-fixable; update the contract if intentional. |
| 🟢 **SUCCESS** | Everything matches | No action. |

## Reference-only contracts

For contracts where `builds[].pattern` is `hybrid-reference`, `reference`, or `external-reference`, the target tables are materialised by an externally-owned dbt or Airflow project — NOT by `fluid apply`. On the first pipeline run the external DAG hasn't run yet, so a "table not found" result is expected state, not a verification failure.

`fluid verify` detects this mode via `builds[].pattern` and downgrades missing-table errors to `INFO` under `--strict`:

```
(contract is reference-only — missing tables will be reported as INFO,
not treated as verification failures)

📋 Verifying: subscriber360_core
   Format: snowflake_table
   Target: TELCO_LAB.TELCO_FLUID_DEMO.SUBSCRIBER360_CORE_V1
   🔵 INFO: Table not found: ... (reference-only — external pipeline owns creation)
```

The downgrade is narrowly scoped:

- Only missing-table shapes (`result["exists"] is False`) are downgraded.
- Auth / config / connection errors still hard-fail under `--strict`.
- Non-reference contracts (imperative / declarative) keep the original hard-fail behaviour.

## Examples

```bash
fluid verify contract.fluid.yaml
fluid verify contract.fluid.yaml --strict
fluid verify contract.fluid.yaml --expose bitcoin_prices
fluid verify contract.fluid.yaml --show-diffs
fluid verify contract.fluid.yaml --env prod --out runtime/verify-report.json --strict
```

## Notes

- Use `verify` after apply or in CI when you need contract-to-runtime confidence.
- Use [`fluid test`](./test.md) when you want broader live-resource validation.
- The JSON report contains per-expose severity + dimensional breakdown + remediation actions. CI dashboards can key off `result["severity"]["level"]` for red/amber/green status.
