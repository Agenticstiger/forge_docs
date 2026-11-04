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

An expose bound to anything else, such as Snowflake, is reported `not_checked`, and so is an expose whose contract declares no schema. *(forge-cli [#707](https://github.com/Agenticstiger/forge-cli/pull/707), since 0.20.0)* So is an AWS Iceberg expose whose `location.catalog` names a catalog other than Glue, with the detail `table lives in Iceberg catalog <kind>; Glue is not inspected`: `fluid apply` creates no Glue table for it, and a Glue table of the same name would belong to someone else. On 0.19.0 and earlier, `diff` looked such a table up in Glue. *([forge-cli #709](https://github.com/Agenticstiger/forge-cli/pull/709), since 0.20.0)* On AWS, a `location.catalog` value FLUID does not know is refused before anything is compared, because the AWS planner `diff` runs cannot tell whether the table is in Glue:

```text
❌ diff_failed  [ERR_DIFF_FAILED]
  error: exposes[orders] names Iceberg catalog 'lakekeper' (location.catalog), which FLUID does not know, so it cannot tell whether the table belongs in AWS Glue, and planning it would provision no Glue database or table. Use one of: bigquery, dynamodb, glue, hadoop, hive, jdbc, lakekeeper, nessie, polaris, rest, snowflake-managed, unity, iceberg-rest, snowflake. Or remove location.catalog to keep the table in the Glue catalog.
```

Each expose ends in exactly one status:

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
- **Columns** — a column removed or added, a column that becomes NOT NULL or nullable, a type change, nested `fields[]`, and the `pii` flag. [Which column changes are breaking](#which-column-changes-are-breaking) lists each rule. *(Not yet in a release, [forge-cli #805](https://github.com/Agenticstiger/forge-cli/pull/805).)* In a 0.7.x contract, a column whose `sensitivity` becomes or stops being `pii` or `phi` is `column_pii_added` or `column_pii_removed`, and any other change to it is `column_sensitivity_changed`, all info. A column that carries a key marker (a `primary-key` tag, a `semanticType` of `identifier` or `primary_key`, a `labels.constraint` of `primary_key` or `unique`, or a truthy `labels.unique`) and stops being `required` is `primary_key_nullable` (breaking).
- **Names declared twice** — an expose id, column or nested field that the new contract declares more than once. See [A name declared twice](#a-name-declared-twice).
- **Quality severity escalation** — a test in `exposes[].quality.tests[]` promoted to `error`. *(Not yet in a release, [forge-cli #805](https://github.com/Agenticstiger/forge-cli/pull/805).)* In a 0.7.x contract that is a rule in `contract.dq.rules`, `contract.quality` or a column's `quality` whose severity becomes `error` or `critical`. `critical` fails a run as `error` does, so `critical` to `error` is not an escalation.

The column rules for a 0.7.x contract, the stricter type rules and the repeated-name check are not in a release yet. Each section below says which forge-cli pull request carries it.

::: warning Through 0.26.0, the columns of a 0.7.x contract are not compared
Through 0.26.0, `fluid diff --baseline` finds an expose's columns at `exposes[].schema` only. A contract that `fluid validate` accepts declares them at `exposes[].contract.schema`, and rejects `schema` directly under the expose. On such a contract those releases report `No changes detected.` and `--fail-on-breaking` exits 0 after a column is removed, retyped, added as NOT NULL or declared twice (measured on 0.26.0). An expose added or removed is still reported. On those releases do not use `--fail-on-breaking` as the only guard against a column change: [`fluid contract-tests`](./contract-tests.md#choosing-between-contract-tests-and-diff) is the column gate, and [Evolve a live product](../recipes/evolve-a-live-product.md#_2-check-the-change-against-the-baseline) shows it in a pipeline.
:::

`--fail-on-breaking` makes the command exit `1` on any breaking change, so it can serve as a contract-compatibility gate. `--format json` or `markdown` print a structured report to stdout for PR comments or release notes, and the JSON envelope is also written to `--out`. `--baseline` cannot be combined with `--env` or `--state` (`diff_modes_mutually_exclusive`, exit 2): an overlay and a prior report belong to drift mode.

*(Not yet in a release, [forge-cli #805](https://github.com/Agenticstiger/forge-cli/pull/805).)* Names from the contract are printed as data. In text, a control, bidi or invisible character in a name is spelled out (`\x1b`, `\u202e`), so a name cannot drive the terminal or forge a line, and each entry is one line. In Markdown, the path and the description are each one code span, so a name adds no link, image, HTML comment or heading and mentions no one. Credential-shaped values (`password=...`, `api key: ...`) are masked in every format and in `--out`. An entry reads:

```markdown
- **column_removed** `exposes[0].contract.schema.email` — `column 'email' removed from expose 'orders'`
```

Through 0.26.0, the text and JSON on stdout were wrapped at the terminal width, 80 columns in CI. A long entry, such as a removed column's description, put a line break inside a JSON string, so `--format json | jq` failed. Read the envelope from `--out` on those versions.

::: warning A gate that passed can start failing
*(Not yet in a release, [forge-cli #789](https://github.com/Agenticstiger/forge-cli/pull/789), [#802](https://github.com/Agenticstiger/forge-cli/pull/802).)*

The release that carries these changes reads the columns of a 0.7.x contract, applies the type rules below and reports a name declared twice. A pipeline that runs `fluid diff --baseline --fail-on-breaking` and passes on 0.26.0 can exit `1` after the upgrade, on a contract nobody changed. A contract that declares a column twice exits `1` even when it is compared with an identical copy of itself (measured). [Findings that change for a contract already compared](#findings-that-change-for-a-contract-already-compared) lists findings that were `non_breaking`, `info` or not reported on 0.26.0, and [Both contracts must be valid](#both-contracts-must-be-valid) describes another way a gate can start failing. Run the gate once on the contract you release from, and read what it reports, before it blocks a merge.
:::

### Which column changes are breaking

*(On forge-cli `main`, not yet in a release, [forge-cli #789](https://github.com/Agenticstiger/forge-cli/pull/789).)*

The diff reads an expose's columns from `exposes[].contract.schema`, where a 0.7.x contract keeps them. When the expose also has a flat `exposes[].schema`, it reads that one and ignores `contract.schema` (measured). A column is NOT NULL when it has `required: true`, or the older `nullable: false`. A finding for a 0.7.x column is at `exposes[N].contract.schema.<column>`, and one for a flat column is at `exposes[N].schema.<column>`. A nullability finding ends in the key the contract uses, `.required` for a 0.7.x column.

| Change to a column | Severity | `kind` |
| --- | --- | --- |
| Removed | `breaking` | `column_removed` |
| Added, nullable | `non_breaking` | `column_added` |
| Added, NOT NULL | `breaking` | `column_added` |
| Becomes NOT NULL | `breaking` | `column_nullable_tightened` |
| Becomes nullable (not a `primaryKey` column) | `non_breaking` | `column_nullable_loosened` |
| A `primaryKey` column becomes nullable | `breaking` | `primary_key_nullable` |
| Type changes | see [Type changes](#type-changes) | `column_type_widened`, `column_type_changed`, `column_type_param_changed`, `column_type_normalized` |
| Description or `pii` flag changes | `info` | `column_description_changed`, `column_pii_added`, `column_pii_removed` |

Only a `breaking` finding makes `--fail-on-breaking` exit `1`. A `non_breaking` or `info` finding is listed and the run exits `0` (measured). Take the [`csv-basics` template](./init.md) as `v1`, and as `v2` the same contract without `days_since_last_purchase`, with `total_purchases` retyped from `INTEGER` to `VARCHAR`, and with a required `country` column added. This run exits `1` (measured):

```bash
fluid diff v2/contract.fluid.yaml --baseline v1/contract.fluid.yaml --fail-on-breaking
```

```text
BREAKING (3)
------------
  column_removed                   exposes[0].contract.schema.days_since_last_purchase: column 'days_since_last_purchase' removed from expose 'customers_clean'
  column_added                     exposes[0].contract.schema.country: NOT NULL column 'country' added to expose 'customers_clean' (breaks inserts that don't supply a value)
  column_type_changed              exposes[0].contract.schema.total_purchases.type: column 'total_purchases' type changed INTEGER -> VARCHAR (not a widening cast)

Summary: 3 breaking, 0 non-breaking, 0 info
```

### Type changes

*(Not yet in a release, [forge-cli #802](https://github.com/Agenticstiger/forge-cli/pull/802).)*

When a column has a type on both sides, a change is `non_breaking` only when it is on one of the lists below, and `breaking` otherwise, except a change in formatting alone, which is `info`. A type name that is plain ASCII is upper-cased before it is compared, and the findings print it upper-cased. The lists follow the widening and length-and-precision tables in forge-cli's `changelog_rules.py`, and the example rows were run as single changed columns (measured).

**A different base type** widens only along these lines, and only into a type that declares no parameters of its own:

| From | Widens to |
| --- | --- |
| `smallint` | `int`, `int32`, `int64`, `integer`, `bigint`, `long` |
| `int` | `integer`, `bigint`, `long`, `decimal`, `numeric`, `double` |
| `integer` | `bigint`, `long`, `decimal`, `double` |
| `int32` | `int64`, `bigint`, `long`, `decimal`, `double` |
| `float` | `double` |
| `varchar` | `text`, `string` |
| `string` | `text` |
| `date` | `datetime`, `timestamp` |

A change of base type that is not in this table is `breaking` (`column_type_changed`). That covers a narrowing such as `bigint` to `int`, a synonym such as `integer` to `int`, and a move out of a family such as `int` to `float`, `float` to `decimal` or `numeric`, or `time` to `timestamp` or `datetime`. `int` to `decimal(5,0)` is `breaking` because the new type declares parameters, while `int` to a bare `decimal` widens.

**The same type with other parameters** is compared parameter by parameter:

- A bigger parameter is a widening only for a type whose parameter is a length or a precision: `varchar`, `varchar2`, `nvarchar`, `nvarchar2`, `char`, `nchar`, `character`, `string`, `text`, `varbinary`, `float`, `time`, `timestamp` (also `timestamp_ntz`, `timestamp_ltz` and `timestamp_tz`), `datetime`, `datetime2` and the decimal family (`decimal`, `dec`, `numeric`, `number`, `bignumeric`). On any other type, such as `geometry` or `binary`, a bigger parameter is `breaking`.
- A decimal's precision and scale are compared as its integer digits (precision minus scale) and its scale. It widens only when neither falls.
- A narrowing is a change where no parameter grows and one shrinks (for a decimal: its integer digits and its scale): `breaking`, kind `column_type_changed`.
- Parameters that move in different directions, a parameter on one side only, or a different number of parameters are `breaking`, kind `column_type_param_changed`.

A widening is `non_breaking` with kind `column_type_widened`:

| Old | New | Why |
| --- | --- | --- |
| `varchar(50)` | `varchar(100)` | A bigger length |
| `timestamp(3)` | `timestamp(6)` | A bigger precision |
| `decimal(10,2)` | `decimal(12,2)` | Precision grew and scale held |
| `decimal(10,2)` | `decimal(12,4)` | Integer digits held (8) and scale grew (2 to 4) |

A narrowing is `breaking` with kind `column_type_changed`:

| Old | New | Why |
| --- | --- | --- |
| `varchar(100)` | `varchar(50)` | A smaller length |
| `decimal(10,2)` | `decimal(6,2)` | Integer digits fell from 8 to 4 |

A change that is neither is `breaking` with kind `column_type_param_changed`:

| Old | New | Why |
| --- | --- | --- |
| `varchar` | `varchar(10)` | Only the new type has a parameter |
| `decimal(10,2)` | `decimal` | Only the old type has parameters |
| `decimal(10,2)` | `decimal(12,1)` | Precision grew, scale fell |
| `decimal(10,2)` | `decimal(11,4)` | Scale grew, integer digits fell from 8 to 7 |
| `geometry(4326)` | `geometry(32633)` | The parameter is a spatial reference id, not a size |
| `binary(16)` | `binary(32)` | `binary` is not a length or precision type |

**Type text the diff cannot order:**

- A type name with a non-ASCII character is compared as written, so it matches no other type name, and the finding says why.
- Parameters that are not plain integers, such as `enum('a','b')` or `varchar(max)`, cannot be ordered. The type is a different type when its text differs after ASCII case folding, so `enum('a','b')` to `enum('a','b','c')` and `varchar(max)` to `varchar(200)` are `breaking` (`column_type_changed`). Case inside quotes is still folded: `enum('a')` and `enum('A')` compare equal and report nothing.
- Formatting alone is not a type change. Whitespace around integer parameters, or leading zeros in them, is `info` (`column_type_normalized`): `decimal(10, 2)` to `decimal(10,2)`. A change of ASCII case reports nothing: `varchar` to `VARCHAR`. Whitespace inside text the diff cannot order is a difference: `enum('a', 'b')` to `enum('a','b')` is `breaking` (`column_type_changed`).

A nested field (`fields[]` under a column) follows the same rules, and its kinds start with `nested_`, such as `nested_column_type_changed`.

### Findings that change for a contract already compared

*(Not yet in a release, [forge-cli #789](https://github.com/Agenticstiger/forge-cli/pull/789), [#802](https://github.com/Agenticstiger/forge-cli/pull/802).)*

A contract that keeps its columns at `exposes[].schema` was compared on 0.26.0, and the new rules change what it reports: type changes are judged more strictly, `required: true` counts as NOT NULL, and a repeated name is a finding. Each row was one change to one column, run on 0.26.0 and on the branch of forge-cli #802 (measured). [forge-cli #805](https://github.com/Agenticstiger/forge-cli/pull/805) refuses a pre-0.7 contract, as [Both contracts must be valid](#both-contracts-must-be-valid) says, so in a release that carries it these rows no longer apply:

| Change | On 0.26.0 | Now |
| --- | --- | --- |
| `int` to `float` | `non_breaking` | `breaking` |
| `int` to `decimal(5,0)` | `non_breaking` | `breaking` |
| `time` to `timestamp` | `non_breaking` | `breaking` |
| `float` to `decimal` | `non_breaking` | `breaking` |
| `decimal(10,2)` to `decimal(11,4)` | `non_breaking` | `breaking` |
| `geometry(4326)` to `geometry(32633)` | `non_breaking` | `breaking` |
| `varchar` to `varchar(10)` | `info` | `breaking` |
| `decimal(10,2)` to `decimal` | `info` | `breaking` |
| `enum('a','b')` to `enum('a','b','c')` | `info` | `breaking` |
| A column added with `required: true` | `non_breaking` | `breaking` |
| `required: true` added to a column | no finding | `breaking` |
| A column declared twice | no finding | `breaking` |

### A name declared twice

*(Not yet in a release, [forge-cli #802](https://github.com/Agenticstiger/forge-cli/pull/802).)*

The comparison matches exposes, columns and nested fields by name and keeps the last of a repeated name, so an earlier declaration is not compared with the baseline. A name that the **new** contract declares more than once is therefore `breaking` (an expose is matched by its `exposeId`, or its `id`):

| Repeated | `kind` |
| --- | --- |
| Expose id | `expose_duplicate_id` |
| Column | `column_duplicate_name` |
| Nested field | `nested_field_duplicate_name` |

A finding for an expose is at `exposes[N]`, the last declaration. One for a column is at `exposes[N].contract.schema.<column>`, or at `exposes[N].schema.<column>` for a flat column, as for [column changes](#which-column-changes-are-breaking). One for a nested field is at the column's path, then `.fields.<field>`. The diff reports a repeat in an expose both files have and in an expose that is new, and whatever the baseline holds (measured). So a contract that already declares a name twice is reported against itself until one declaration is removed. This is the `csv-basics` template with its `email` column declared twice, compared with itself (measured):

```bash
fluid diff customers.fluid.yaml --baseline customers.fluid.yaml --fail-on-breaking
```

```text
BREAKING (1)
------------
  column_duplicate_name            exposes[0].contract.schema.email: column 'email' is declared 2 times in expose 'customers_clean'; keep one (a later declaration hides an earlier one)

Summary: 1 breaking, 0 non-breaking, 0 info
```

The run exits `1`. Remove one `email` declaration from the new file, and the run exits `0` with `No changes detected.`, though the baseline still declares it twice (measured).

### What is not compared

**Column order.** Moving a column prints `No changes detected.` (measured). [`fluid contract-tests`](./contract-tests.md) fails on it.

With forge-cli [#789](https://github.com/Agenticstiger/forge-cli/pull/789) and [#802](https://github.com/Agenticstiger/forge-cli/pull/802) alone, three more changes to a 0.7.x contract report nothing, or less than they could (measured on the branch of #802):

- Changing a column's `sensitivity` from `internal` to `pii` is not a finding.
- Raising the `severity` of a rule in `exposes[].contract.dq` from `warn` to `error` is not a finding. `quality_severity_escalated` is reported only for `exposes[].quality.tests[]`, which `fluid validate` rejects in a 0.7.x contract.
- A column that becomes nullable is `non_breaking` (`column_nullable_loosened`), even when it carries a `primary-key` tag, a `semanticType` of `identifier` or a `labels.constraint` of `primary_key`. The `primary_key_nullable` finding needs a `primaryKey`, which `fluid validate` rejects in a 0.7.x contract.

[forge-cli #805](https://github.com/Agenticstiger/forge-cli/pull/805) compares all three; see the **Columns** and **Quality severity escalation** items above.

### Both contracts must be valid

*(Not yet in a release, [forge-cli #805](https://github.com/Agenticstiger/forge-cli/pull/805).)* Version diff validates both files before it compares them, against the schema their `fluidVersion` names, as `fluid plan` does. The rules read only the shapes a schema allows, so through 0.26.0 a contract no schema accepts could hide a change: a column retyped from `decimal(18,2)` to the number `18` passed `--fail-on-breaking` with exit 0. An invalid file now stops the run with exit 2, and nothing is printed to stdout or written to `--out`:

```text
❌ diff_contract_invalid  [ERR_DIFF_CONTRACT_INVALID]
  invalid: ['new']
  errors: {'new': ['exposes[0].contract.schema[5].type: 18 is not valid under any of the given schemas']}
  message: ``fluid diff --baseline`` compares valid contracts only: the new contract new.fluid.yaml has 1 error(s). Run ``fluid validate new.fluid.yaml`` for the full report.
```

Each schema error is also logged as `diff_contract_schema_error`. A pre-0.7 contract is refused with the upgrade `fluid validate` asks for, so a pre-0.7 baseline cannot be diffed against its 0.7.x rewrite: compare two 0.7.x revisions.

With `--baseline`, the command exits `0` when no breaking change gates the run, `1` when `--fail-on-breaking` finds one, and `2` when a contract is not valid or an argument is wrong. Exit 2 is `diff(1)`'s "trouble", so an invalid contract never reads as either verdict. A file that cannot be loaded at all exits 1 with `diff_failed`, as in the `$ref` example below.

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
