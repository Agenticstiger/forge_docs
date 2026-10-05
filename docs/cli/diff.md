# `fluid diff`

Stage 5 of the 11-stage pipeline. Detect drift between the contract and what is deployed — or, with `--baseline`, run a semantic [version diff](#contract-version-diff) between two revisions of a contract.

## Syntax

```bash
fluid diff CONTRACT [--env ENV] [--exit-on-drift] [--last-applied PLAN] [--out PATH]
fluid diff CONTRACT --baseline OLD_CONTRACT [--fail-on-breaking] [--format FORMAT]
```

`CONTRACT` is a contract file or a bundle (`.tgz`) written by [`fluid bundle`](./bundle.md). The generated Jenkins pipeline's stage 5 diffs the bundle stage 1 wrote.

## Examples

### Drift gate: does the target still match the contract?

```bash
fluid diff contract.fluid.yaml --exit-on-drift
```

With no `--state`, `diff` reads each expose's live target and compares its columns with the contract. This is real output for a contract with one expose bound to a local Parquet file (the lines the provider prints while it plans are left out):

```text
Live drift check: 1 expose(s)
  orders [local] match  .../output/orders.parquet
State drift check: not run (the contract runs on the local engine, which keeps no OpenTofu state). Drift comes from the live checks alone.
```

The exit code is 0. If someone changes the file outside the contract (here the `amount` column was retyped and `status` dropped), the same command reports it and exits 1:

```text
Live drift check: 1 expose(s)
  orders [local] drift  .../output/orders.parquet
      - amount: type changed, contract=DECIMAL(10,2) target=VARCHAR
      - status: declared (VARCHAR) but not in the target (allowed by schemaPolicy: removed -> warn)
...
{"time": "...", "level": "WARNING", "name": "fluid.cli", "message": "diff_live_drift_detected", "exposes": ["orders"], "columns": 1, "out": ".../runtime/diff.json"}
```

Only `amount` counts as drift. A dropped column is a difference the expose's `schemaPolicy` lets a build make, so it is listed and not counted.

A target that does not exist yet is not drift, because `apply` will create it:

```text
Live drift check: 1 expose(s)
  orders [local] absent (to be created)  .../output/orders.parquet
```

A target `diff` could not read is an error, not a pass. Under `--exit-on-drift` it exits 2:

```text
Live drift check: 1 expose(s)
  orders [aws] error  glue:web_analytics.pageviews (eu-west-1)
      Exception: Error retrieving AWS Glue table: An error occurred (UnrecognizedClientException) when calling the GetTable operation: The security token included in the request is invalid.
State drift check: not run (no apply state for this contract at .fluid/iac/aws/analytics_web_pageviews: run from the directory `fluid apply` ran in (or pass --workspace-dir), or name the remote state with --state-backend / FLUID_STATE_BACKEND). Drift comes from the live checks alone.
❌ diff_live_inspection_failed  [ERR_DIFF_LIVE_INSPECTION_FAILED]
  exposes: ['pageviews']
  detail: --exit-on-drift could not read every live target, so it cannot say there is no drift; see the report's live.exposes
```

### Tell a pending change from drift

If you changed the contract and have not applied yet, the target no longer matches it, and that is not drift. Pass the plan the last successful apply ran as `--last-applied`:

```bash
fluid diff contract.fluid.yaml --last-applied runtime/plan.json --exit-on-drift
```

```text
Live drift check: 1 expose(s)
  orders [local] pending (apply will change it)  .../output/orders.parquet
      - currency: declared (VARCHAR) but not in the target (pending: the contract changed it since the last apply)
```

The comparison becomes three-way, the way `kubectl apply` uses its last-applied configuration: a column where the contract moved away from the last apply and the target did not is `pending`, and only a target that moved away from the last apply is `drift`. A `--last-applied` path that does not exist is ignored, so the first run needs no special case. A file that exists but holds no contract is an error (`diff_last_applied_invalid`, exit 2).

`fluid generate ci --system jenkins --diff-last-applied` writes a stage 5 that passes the last applied plan for the env as `--last-applied`.

### Compare two contract versions

```bash
fluid diff v2/contract.fluid.yaml --baseline v1/contract.fluid.yaml
fluid diff v2/contract.fluid.yaml --baseline v1/contract.fluid.yaml --fail-on-breaking
fluid diff v2/contract.fluid.yaml --baseline v1/contract.fluid.yaml --format markdown
```

See [Contract version diff](#contract-version-diff).

## Where drift is measured from

Drift mode compares the contract with one of three baselines.

| Baseline | Chosen when | What is compared |
| --- | --- | --- |
| Live targets, plus the apply's OpenTofu state | The default: no `--state`, or a `--state` file that does not exist. | Each expose's target as it exists now, and, for a cloud contract whose apply state is reachable, what changed outside the apply. |
| A saved report | `--state <file>` names a file that exists. | The plan's resource ids against that file's `results` list. The live targets are not read. |
| None | `--no-live` and no `--state`. | Nothing. `--exit-on-drift` is downgraded to a warning (`diff_exit_on_drift_skipped`) and the run exits 0. |

### Live targets

For each expose, `diff` reads the target the way `apply` writes it and compares the columns with the contract:

- local files and DuckDB tables;
- AWS Glue tables;
- BigQuery tables.

An expose bound to anything else, such as Snowflake, is reported `not_checked`, and so is an expose whose contract declares no schema. Each expose ends in exactly one status:

| Status | Meaning | Counts as drift |
| --- | --- | --- |
| `match` | The target exists with the declared columns and types. | No |
| `evolved` | It differs only in ways the expose's `schemaPolicy` lets a build make. | No |
| `pending` | The contract changed a column since the last apply, and the target is still as that apply left it. Needs `--last-applied`. | No |
| `drift` | The target exists and differs: a column added, removed or retyped outside the contract. | Yes |
| `absent` | The target does not exist yet. | No |
| `not_checked` | forge has no live reader for this binding, or the contract declares no schema. | No, and not a pass either |
| `error` | The reader ran and could not answer: credentials, network or a missing SDK. | Exit 2 under `--exit-on-drift` |

What counts as drift depends on who owns the columns:

- **Local files and DuckDB tables** are written by the build, with the columns the source had, as far as `schemaPolicy` allows. The default policy, `evolve_safe`, lets a new source column in and a removed one out. A difference is classified by the same decision the build makes, so only what the policy would refuse is drift. Files that carry no column types (`.csv`, `.tsv`, `.json`, `.jsonl`, `.ndjson`) are compared by column name only.
- **Glue and BigQuery tables** have their columns declared by the infrastructure code from the contract, and a build loads rows into them without changing them. Any column difference is drift, whatever the policy says.

Relative local paths are anchored at the directory of the source contract, which for a bundle is the contract the bundle's manifest records, not the bundle's own directory. A `{{ env.NAME }}` placeholder in a binding is resolved from the environment before the target is read, the way `fluid apply` and `fluid verify` resolve it.

::: warning Since 0.18.1; a variable that is not set
On 0.18.0 the live check read the placeholder text itself. A BigQuery binding whose project is `{{ env.FLUID_GCP_PROJECT }}` was refused as an invalid id, so `--exit-on-drift` failed the drift stage of that product's pipeline, while `fluid apply` and `fluid verify` read the real table. 0.18.1 resolves the contract first. A variable that is not set resolves to an empty string: with `ORDERS_DIR` unset, a path `{{ env.ORDERS_DIR }}/orders.parquet` is read as `/orders.parquet`, measured as `absent (to be created)`, which is not drift. Export the variables the contract names before the drift step.
:::

### The apply's OpenTofu state

For a cloud contract applied through OpenTofu, `diff` also refreshes the state `fluid apply` keeps and reports what changed outside the apply (`drift`) apart from what the next apply will change (`pending`). It runs `tofu plan -detailed-exitcode` against the apply's own workdir and backend, so a resource changed by hand fails `--exit-on-drift`. It writes no state: the apply's `main.tf.json` is put back, the saved plan is deleted, and nothing is imported.

A change counts as drift when the refresh saw an attribute change outside OpenTofu and the plan would put that attribute back. A planned change with no such change behind it is `pending`: the contract moved. A change the module does not declare is listed as outside the contract and is not drift.

It needs the state the apply used:

- Run `diff` from the directory `fluid apply` ran in, or pass `--workspace-dir` for local state. The workdir is `.fluid/iac/<provider>/<safe-id>/` under it.
- For remote state, pass `--state-backend`, or export `FLUID_STATE_BACKEND`, exactly as for `apply`. `--state-backend ""` forces local state. See [Remote state](./apply.md#remote-state).
- `tofu` must be installed. `--ensure-opentofu` provisions the pinned, SHA-256-verified build `fluid apply --ensure-opentofu` uses.

While the one-time move to the per-provider state key is pending after an upgrade, `diff` reads the old key and leaves it where it is. When there is no state to read, the pass reports `not_checked` with the reason, as in the output above, and the live checks are the only answer. `--no-state-drift` skips the pass. A pass that ran ends with a line about what a state read cannot see, such as what the build writes into the containers and the shared containers the contract only references; the live readers cover those where forge has one.

### A saved report (`--state`)

`--state <file>` compares the plan's resource ids with the `results` list of that JSON file and, with `--exit-on-drift`, exits 1 when they differ.

::: warning As of 0.18.1, an apply report does not work as `--state`
`fluid apply --report runtime/apply-report.json` writes HTML unless you also pass `--report-format json`, because the format flag, not the file extension, decides. `diff --state` on that file fails with `diff_failed` (`Expecting value: line 1 column 1`) and exit 1. A JSON report from `--report-format json` has no `results` list, so every planned resource reads as `added` and `--exit-on-drift` exits 1 on a target that has not drifted. Use the live comparison, with `--last-applied runtime/plan.json` to tell pending changes from drift.
:::

## Exit codes with `--exit-on-drift`

Without `--exit-on-drift`, `diff` reports and exits 0.

| Exit | When |
| --- | --- |
| `0` | No drift: every target is `match`, `evolved`, `pending`, `absent` or `not_checked`, and the state check found nothing outside the apply. |
| `1` | Drift against the baseline: a `drift` target, or a resource changed outside the apply. |
| `2` | A live target could not be inspected (`diff_live_inspection_failed`), the apply's state could not be refreshed (`diff_state_inspection_failed`), or `--last-applied` named a file that holds no contract. |

The codes follow `diff(1)`: 0 means no differences, 1 means some, 2 means trouble. A failure to inspect wins over drift, because a comparison that could not finish might have found drift too. Exit 2 is also what an argument error returns, so a gate script that treats 1 as "drifted" and anything else non-zero as "broken" reads all three correctly.

If no expose has a target `diff` answered for (each one is `not_checked`) and the state check did not run, nothing was compared and the gate is downgraded to a warning (`diff_exit_on_drift_skipped`).

## Provider resolution

In drift mode `fluid diff` needs a provider to enumerate the desired resources. It resolves the provider in order:

1. The global `--provider` flag, given before the command (`fluid --provider snowflake diff ...`), or the `FLUID_PROVIDER` environment variable.
2. `contract.binding.platform` — the auto-detected fallback, logged as `diff_provider_inferred platform=<name> source=contract.binding.platform`.

To diff against a non-default provider, export `FLUID_PROVIDER` before the run:

```bash
FLUID_PROVIDER=snowflake fluid diff contract.fluid.yaml
```

The binding's project and region are used as `fluid plan` uses them. `--region` overrides the region for the provider plan and for where the live check reads each target; without it the order is the binding's, then the global `--region` or `FLUID_REGION`.

Version-diff mode (`--baseline`) needs no provider at all — it is a pure structural comparison between two contract files.

## Options

| Option | Default | Description |
| --- | --- | --- |
| `--state` | none | A previous report to compare the plan's resources with. A path that does not exist falls back to the live comparison (`diff_state_not_found`). See [the warning above](#a-saved-report-state). |
| `--env` | none | Apply an environment overlay (drift mode only; with `--baseline` it is refused). A bundle built for another env is refused with `bundle_env_mismatch`. See [Environments and overlays](../concepts/environments-and-overlays.md). |
| `--out` | `runtime/diff.json` | Output file for the diff report. |
| `--exit-on-drift` | off | Exit 1 on drift against `--state` when given, else against the live targets; exit 2 when a live target could not be inspected. |
| `--region REGION` | the binding's | Override the region or location for the provider plan; the live check reads each target where `apply` puts it. |
| `--last-applied PLAN` | none | The `plan.json` the last successful apply ran, or that contract. A change the contract made since then, where the target still matches the last apply, is `pending`, not drift. A path that does not exist is ignored. |
| `--no-live` | live on | Do not read the live targets or the apply's state. Without `--state` there is then no baseline and `--exit-on-drift` is downgraded to a warning. |
| `--state-backend` | `$FLUID_STATE_BACKEND`, else local | The remote state `fluid apply` used (`s3://<bucket>/<key>` or `gcs://<bucket>/<prefix>`). `""` forces local. |
| `--workspace-dir DIR` | `.` | The directory `fluid apply` ran in, for its local state. |
| `--no-state-drift` | state check on | Compare the live targets only, not the apply's state. |
| `--ensure-opentofu` | off | If the apply's state is reachable and `tofu` is missing, provision the pinned, SHA-256-verified build. |
| `--baseline` | none | Compare against an older revision of the contract: switches `diff` into version-diff mode. |
| `--fail-on-breaking` | off | In version-diff mode, exit `1` when a breaking change is found. |
| `--format` | `text` | Version-diff output format: `text`, `json` or `markdown`. |

Every path argument (`CONTRACT`, `--baseline`, `--state`, `--last-applied`, `--out`) is checked before it is read or written: a relative path containing `..` is refused with `ERR_PATH_TRAVERSAL_DETECTED`.

## The report

`--out` receives the report in drift mode. This is the report for the drifted target above, trimmed to its first column:

```json
{
  "timestamp": 1791160791.078934,
  "contract": ".../contract.fluid.yaml",
  "env": null,
  "drift_source": "live",
  "summary": { "added": 1, "removed": 0, "unchanged": 0, "has_drift": true },
  "changes": { "added": ["file:orders"], "removed": [], "unchanged": [] },
  "desired_actions": [ "..." ],
  "live": {
    "has_drift": true,
    "compared": 1,
    "counts": { "match": 0, "evolved": 0, "pending": 0, "drift": 1, "absent": 0, "not_checked": 0, "error": 0 },
    "exposes": [
      {
        "expose_id": "orders",
        "platform": "local",
        "target": ".../output/orders.parquet",
        "status": "drift",
        "baseline": "contract",
        "schema_policy": "evolve_safe",
        "columns": [
          {
            "column": "amount",
            "reason": "type_mismatch",
            "contract_type": "DECIMAL(10,2)",
            "target_type": "VARCHAR",
            "classification": "drift",
            "event": "type_changed",
            "action": "fail",
            "in_last_applied": null,
            "last_applied_type": null
          }
        ],
        "detail": null
      }
    ]
  },
  "state_drift": {
    "status": "not_checked",
    "state": null,
    "detail": "the contract runs on the local engine, which keeps no OpenTofu state",
    "has_drift": false,
    "counts": { "drift": 0, "pending": 0, "match": 0 },
    "plan_exit_code": null,
    "resources": [],
    "referenced": []
  }
}
```

- `drift_source` is `live`, `state` (a `--state` file) or `none`.
- `summary.has_drift` is the verdict for whichever comparison ran. `summary.added`, `removed` and `unchanged` compare the plan's resource ids with the `--state` file, so in live mode they list every planned resource as added. Read `live` for the verdict.
- A column's `reason` is `missing_in_target`, `missing_in_contract` or `type_mismatch`, and its `classification` is `drift`, `allowed` (the policy permits it) or `pending`.
- `state_drift.status` is `checked`, `not_checked` or `error`. A checked pass lists each resource as `drift`, `pending` or `match`.

## Contract version diff

Passing `--baseline` switches `fluid diff` from drift detection to a **semantic version diff** between two revisions of the same contract. Each change is classified as breaking, non-breaking or info:

```bash
fluid diff v2/contract.fluid.yaml --baseline v1/contract.fluid.yaml
```

```text
BREAKING (1)
------------
  sovereignty_regions_narrowed     sovereignty.allowedRegions: sovereignty.allowedRegions narrowed (removed: ['europe-west4'])

NON-BREAKING (2)
----------------
  consume_added                    consumes: upstream product 'bronze.sales.raw_orders_v1' added to consumes[]
  expose_added                     exposes[1]: expose 'order_items' added

INFO (1)
--------
  metadata_description_changed     description: description updated

Summary: 1 breaking, 2 non-breaking, 1 info
```

This is contract-aware comparison, not generic schema differencing. The diff understands:

- **Expose changes** — an expose added (non-breaking) or removed (breaking).
- **Upstreams** — `consumes[]` entries added or removed.
- **Policy narrowing** — `agentPolicy` and `sovereignty.allowedRegions` changes.
- **Columns** — a column removed (breaking) or added, a type widened (safe) or narrowed (breaking), `DECIMAL(p,s)` and `VARCHAR(n)` precision, nested `fields[]`, and PII annotation drift.
- **Quality severity escalation** — a rule promoted to a stricter severity.

::: warning As of 0.18.1, the column rules read `exposes[].schema`
`fluid diff --baseline` finds an expose's columns at `exposes[].schema`. A contract that `fluid validate` accepts declares them at `exposes[].contract.schema`, and rejects `schema` directly under the expose. On such a contract, removing a column or narrowing `DECIMAL(10,2)` to `DECIMAL(6,2)` reports `No changes detected.` and `--fail-on-breaking` exits 0 (measured). Expose, `consumes[]`, sovereignty and metadata changes are reported as shown above. Do not use `--fail-on-breaking` as the only guard against a column change. [`fluid contract-tests`](./contract-tests.md) is the column gate, and [Evolve a live product](../recipes/evolve-a-live-product.md#_2-check-the-change-against-the-baseline) shows it in a pipeline.
:::

`--fail-on-breaking` makes the command exit `1` on any breaking change, so it can serve as a contract-compatibility gate. `--format json` or `markdown` print a structured report to stdout for PR comments or release notes, and the JSON envelope is also written to `--out`. `--baseline` cannot be combined with `--env` or `--state` (`diff_modes_mutually_exclusive`, exit 2): an overlay and a prior report belong to drift mode.

### Contracts split with `$ref`

Version diff resolves `$ref` on both files before it compares, so it compares resolved documents: moving content into fragments, or back out, is never reported as a change. A baseline needs its fragments next to it, which a copy of the root file alone does not have:

```bash
# Fails: the fragments are not next to the copy
git show main:contract.fluid.yaml > /tmp/old-root.yaml
fluid diff contract.fluid.yaml --baseline /tmp/old-root.yaml
```

```text
❌ diff_failed  [ERR_DIFF_FAILED]
  error: $ref target not found: parts/orders-contract.yaml (resolved to /tmp/parts/orders-contract.yaml)
```

Take the baseline from a checkout of the old tree instead, and pass its absolute path (a relative path containing `..` is refused):

```bash
git worktree add /tmp/base origin/main
fluid diff contract.fluid.yaml --baseline /tmp/base/contract.fluid.yaml --fail-on-breaking
```

`fluid bundle <contract> --out base.yaml`, run in the old checkout, gives a flat baseline file the same way. Each side's `$ref` targets must stay inside that side's own directory tree; see [Composing a contract with `$ref`](../concepts/contract-refs.md).

## Notes

- `changes` and `desired_actions` in the report are the plan's resources and actions, compared with a `--state` file when there is one. Read `live` and `state_drift` for what the targets and the apply's state say.
- `--exit-on-drift` composes with Jenkins and GitHub Actions: exit 1 blocks the deploy, and exit 2 tells you the check itself failed rather than the target.
- The live reader for local files and DuckDB opens only the file it is checking, inside the [DuckDB sandbox](../advanced/duckdb-sandbox.md). A contract that points at an absolute path outside its own directory is still read.
