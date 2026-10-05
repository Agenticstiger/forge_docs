# `fluid contract-tests`

Compare a contract's column schema with a saved baseline and fail when they differ. Write the baseline at a release, then run the comparison in CI.

## Syntax

```bash
fluid contract-tests CONTRACT [--env ENV] [--baseline PATH | --write-baseline PATH]
```

## Examples

Write a baseline when you release, commit it, and compare against it on every change:

```bash
fluid contract-tests contract.fluid.yaml --write-baseline baseline.schema.json
fluid contract-tests contract.fluid.yaml --baseline baseline.schema.json
```

```text
✅ Baseline written to baseline.schema.json
✅ Contract tests passed
```

Change a column type, and the comparison names the difference and exits `2`:

```text
❌ Contract tests failed — 1 incompatibility(ies) found
   • customer_360_master.customer_id: type changed INTEGER -> BIGINT
```

With no `--baseline`, nothing is compared:

```bash
fluid contract-tests contract.fluid.yaml
```

```text
⚠️  Contract tests skipped: no --baseline to compare against. Create one with: 
fluid contract-tests contract.fluid.yaml --write-baseline baseline.schema.json
```

That run exits `0`. A CI step that omits `--baseline` passes without testing anything.

## Key options

| Option | Description |
| --- | --- |
| `CONTRACT` | Path to `contract.fluid.yaml` (positional, required). |
| `--env` | Overlay environment to apply before reading the schema. |
| `--baseline PATH` | Baseline file to compare against. |
| `--write-baseline PATH` | Write the contract's schema signature to `PATH` and exit. Mutually exclusive with `--baseline`. |

## What is compared

The signature is, per expose, the `exposeId` and the ordered list of `(name, type, nullable)` for each column in `exposes[].contract.schema`. A column is non-nullable when it has `required: true` (or the older `nullable: false`). The comparison is strict equality, so each of these fails and is named:

| Change | Message |
| --- | --- |
| Column removed | `<expose>.<column>: column removed` |
| Column added | `<expose>.<column>: column added` |
| Type changed | `<expose>.<column>: type changed INTEGER -> BIGINT` |
| Nullability changed | `<expose>.<column>: nullable -> required` |
| Columns reordered | `<expose>: column order changed` |
| Expose removed or added | `expose '<id>' is in the baseline but not in the contract`, or `is not in the baseline` |

The command does not classify a change as breaking or safe. A widening such as `INTEGER` to `BIGINT`, and an added nullable column, both fail. If you want that judgement, use [`fluid diff --baseline --fail-on-breaking`](./diff.md#contract-version-diff), subject to the limit below, or update the baseline when you accept the change:

```bash
fluid contract-tests contract.fluid.yaml --write-baseline baseline.schema.json
```

`--write-baseline` overwrites an existing file without asking.

The contract is loaded the way `fluid plan` loads it, with `$ref` fragments and the `--env` overlay applied. A column moved into a fragment is still compared. The baseline file is JSON with one key, `signature`, whose value is a string. Treat it as an artifact the CLI writes; edit nothing by hand.

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | The signatures match, or no `--baseline` was given (skipped), or `--write-baseline` wrote a file. |
| `1` | The baseline is missing (`contract_tests_baseline_missing`) or unreadable (`contract_tests_bad_baseline`), or the contract failed to load. |
| `2` | The signatures differ, or the arguments conflict (`--baseline` with `--write-baseline`). |

## Run it in CI

```yaml
- name: Schema gate
  run: |
    pip install data-product-forge==0.18.1
    fluid contract-tests contract.fluid.yaml --baseline baseline.schema.json
```

Commit `baseline.schema.json` next to the contract. Regenerate it in the same pull request that intentionally changes a schema, so the diff of the baseline is the review of the change.

## Notes

- Before 0.16.5 this command always reported that a contract was compatible, because the comparison it called did not exist. A green result from an earlier version proves nothing; write a baseline and run it again.
- Pair with [`fluid contract-validation`](./contract-validation.md) when you also need to validate the contract against deployed resources.
- `fluid diff --baseline` is the contract-aware comparison that separates breaking from non-breaking changes. As of 0.18.1 it reads columns from `exposes[].schema`, so for a contract that declares columns under `exposes[].contract.schema`, as the `fluid init` directory templates do, it printed `No changes detected` after a column was removed from the `customer-360` contract, while `fluid contract-tests` reported `column removed`. For the schema gate, use `contract-tests`.
- [`fluid diff`](./diff.md) also covers drift against the last apply (`--state`, `--exit-on-drift`); `contract-tests` does not.
