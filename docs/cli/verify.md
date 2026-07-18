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
| `--out` | Write the JSON verification report to this path. No default — omit it and no report file is written. |
| `--show-diffs` | Show field-by-field differences |
| `--reconcile-dbt` | *(since 0.11.0)* Cross-check the contract schema against the build's dbt project (`models/**/schema.yml`) and flag drift. Static, warehouse-free. |
| `--reconcile-lineage` | *(since 0.12.0)* Cross-check declared lineage against local run evidence and the catalog publish payload. Local-only, no network. |
| `--warn-only` | Downgrade `--reconcile-dbt` / `--reconcile-lineage` drift to a warning (exit 0) |
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

## Reconcile: contract ↔ dbt schema (`--reconcile-dbt`)

*(since `0.11.0`)* A **static, warehouse-free** cross-check that the contract's promised
columns (`exposes[].contract.schema`) agree with what the build's dbt project declares
(`models/**/schema.yml`). It never connects to a warehouse and never runs dbt. Drift it
surfaces:

- a column the contract promises that dbt doesn't model,
- a dbt column the contract never exposes,
- a declared type that disagrees (compared conservatively via coarse type families, so
  `NUMBER(38,0)` vs `integer` is *not* flagged across adapters).

Drift exits non-zero unless `--warn-only` is set — **independent of `--strict`** (you asked for
the check, so its drift gates on its own). The JSON report (`--out`) carries the detail under
`report["reconcile"]`.

## Reconcile: contract ↔ published lineage (`--reconcile-lineage`)

*(since `0.12.0`)* A **local-only** cross-check (no network) that the contract's *declared*
lineage — `consumes[]` upstream refs and `exposes[]` output ports — agrees with:

1. **Observed run evidence** — the run records and cursor state the build runners persist under
   `.fluid/` (which source streams were actually read), and
2. **The publish payload** — the exact lineage edges the catalog registrar *would* push,
   rebuilt locally from the contract.

Three drift classes:

| Drift class | Severity | Meaning |
| --- | --- | --- |
| `declared_but_never_read` | soft | A `consumes[]` entry with no run/cursor evidence. Never fails — the product may simply not have run yet; with no run evidence at all the check degrades to a note. |
| `read_but_undeclared` | **critical** | A stream a runner actually read that is neither a `consumes[]` ref nor a declared acquisition source stream. Data flowed in that the contract never admits to. |
| `publish_payload_mismatch` | **critical** | The lineage edges/assets the registrar would publish disagree with the contract. |

Critical drift fails the build under `--strict` unless `--warn-only` is set; soft drift never
fails. dbt run records are handled honestly: their streams are executed *nodes*, not upstream
reads, so they are excluded from the undeclared-read check (with a note) instead of producing
false positives. The JSON report carries the detail under `report["reconcile_lineage"]`.

## dbt test results (transformation checks)

*(since `0.12.0`)* When the product's build ran via dbt (`fluid apply --mode amend-and-build`),
the runner parses `target/run_results.json` into run records, and `fluid verify` gains
transformation-side checks next to the acquisition probes: **`dbt_tests_passed`** and
**`no_error_severity_failures`**. Both are critical, so a failing contract-derived dbt test
gates the exit code under `--strict`. See [`fluid runs status`](./runs.md) for the run-record
view of the same data.

## Examples

```bash
fluid verify contract.fluid.yaml
fluid verify contract.fluid.yaml --strict
fluid verify contract.fluid.yaml --expose bitcoin_prices
fluid verify contract.fluid.yaml --show-diffs
fluid verify contract.fluid.yaml --env prod --out runtime/verify-report.json --strict
fluid verify contract.fluid.yaml --reconcile-dbt --strict          # contract ↔ dbt schema drift
fluid verify contract.fluid.yaml --reconcile-lineage --strict      # contract ↔ observed/published lineage
fluid verify contract.fluid.yaml --reconcile-dbt --reconcile-lineage --warn-only   # report, never fail
```

## Notes

- Use `verify` after apply or in CI when you need contract-to-runtime confidence.
- Use [`fluid test`](./test.md) when you want broader live-resource validation.
- The JSON report contains per-expose severity + dimensional breakdown + remediation actions. CI dashboards can key off `result["severity"]["level"]` for red/amber/green status.
