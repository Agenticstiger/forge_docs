# `fluid policy check`

Static lint of the contract's governance and compliance declarations. No cloud calls, no state mutation — safe to run from any branch, any environment. Pair with [`fluid validate`](./validate.md) in a pre-commit hook or stage-2 CI gate.

`0.8.0` added the unified `fluid policy {check,compile,apply}` subcommand group. The older `fluid policy-check` form is still registered in 0.18.1, prints no deprecation notice, and takes the same arguments.

## Syntax

```bash
# New idiomatic form
fluid policy check CONTRACT

# Older form (same behaviour)
fluid policy-check CONTRACT
```

## Key options

| Option | Description |
| --- | --- |
| `--env` | Apply an environment overlay |
| `--strict` | Treat warnings as errors: a contract whose only finding is a warning exits `1` instead of `0`. |
| `--category` | Report only violations in one category. See the note below: it does not skip the other checks. |
| `--output`, `-o` | Write the policy report to this path as JSON |
| `--format` | `rich` (default), `text`, or `json` |
| `--show-passed` | Show successful checks too |

Available categories include:

- `sensitivity`
- `access_control`
- `data_quality`
- `lifecycle`
- `schema_evolution`

## Example output

A contract with a PII column that has a masking rule and no `lifecycle.retention`, checked with `--format text`:

```bash
fluid policy check contract.fluid.yaml --format text
```

```text
📋 Schema-Based Policy Validation
Contract: gold.finance.customer_360_v1
Score: 95/100

============================================================

✅ Sensitivity

✅ Access Control

✅ Data Quality

❌ Lifecycle (1 issues)
  WARNING: Sensitive data should have explicit retention policy
    💡 Add lifecycle.retention (e.g., 'P90D' for 90 days)

✅ Schema Evolution

============================================================
Checks Passed: 5
Checks Failed: 0
Advisory Issues: 1
Total Violations: 1
Blocking Issues: 0
Policy Score: 95/100
```

The exit code is `0` here, because the only finding is a warning. With `--strict` it is `1`. A `CRITICAL` violation, for example a `sensitivity: pii` column with no `policy.privacy.masking`, exits `1` without `--strict`.

`--format json` (and `--output`) write `is_compliant`, `score`, `checks_passed`, `checks_failed`, `violations[]` (each with `category`, `severity`, `message`, `field`, `expose_id`, `rule_id`, `remediation`) and `blocking_violations`.

::: warning Measured behaviour of `--category` and the counters in 0.18.1
- `--category lifecycle` and `--category sensitivity` ran the same checks on the contract above. Only the reported violations differ: with `sensitivity` the lifecycle warning is dropped and the score reads `100/100`, while the log line printed first still says `5 passed, 1 failed, score: 95/100`.
- The counters do not agree across formats. For the same contract, `--format json` printed `checks_failed: 1` next to `is_compliant: true`, and the rich report printed `Checks Failed: 0`.
- Judge a run by the exit code and the violations list, not by the counters.
:::

## Examples

### New idiomatic form

```bash
fluid policy check contract.fluid.yaml
fluid policy check contract.fluid.yaml --strict
fluid policy check contract.fluid.yaml --category access_control
fluid policy check contract.fluid.yaml --format json --output runtime/policy.json
```

### Hyphenated form (still registered)

```bash
fluid policy-check contract.fluid.yaml
fluid policy-check contract.fluid.yaml --strict
```

## Related

- [`fluid policy compile`](./policy-compile.md) — after the lint passes, compile to `bindings.json`.
- [`fluid policy apply`](./policy-apply.md) — hand the compiled bindings to the provider (stage 8 of the pipeline; it changes no permissions in 0.18.1).
