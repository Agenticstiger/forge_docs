# `fluid verify`

Stage 9 of the 11-stage pipeline. `fluid verify` reads what the build produced and compares it with the contract: a local file, a BigQuery table, an S3 prefix behind a Glue table, or a Snowflake table. Which checks run depends on that target.

## Syntax

```bash
fluid verify CONTRACT
```

`CONTRACT` is a contract YAML or a stage-1 bundle (`.tgz`). A relative `binding.location.path` resolves against the directory of the source contract, not the working directory, so the file the build wrote is the file verify reads wherever you run it from. A bundle records its source contract's directory.

## Examples

```bash
fluid verify contract.fluid.yaml
fluid verify contract.fluid.yaml --strict
fluid verify contract.fluid.yaml --expose orders
fluid verify contract.fluid.yaml --show-diffs
fluid verify runtime/bundle.tgz --env aws --strict --out runtime/verify-report.json
fluid verify contract.fluid.yaml --env aws --strict --state-drift
fluid verify contract.fluid.yaml --reconcile-dbt --strict          # contract <-> dbt schema drift
fluid verify contract.fluid.yaml --reconcile-lineage --strict      # contract <-> observed/published lineage
fluid verify contract.fluid.yaml --reconcile-dbt --reconcile-lineage --warn-only   # report, never fail
```

### What a failure looks like

A local CSV whose file has a column the contract does not declare:

```bash
fluid verify contract.fluid.yaml --strict
echo $?
```

```text
📋 Verifying: orders
   Format: csv
   Target: /.../output/orders.csv

   🔴 Severity: CRITICAL (Impact: HIGH)
   ...
   📊 Rows: 1

   🔍 Dimension 1: Schema Structure
      ❌ FAIL - Schema structure mismatch
         ✅ Matching: 3/3
         ⚠️  Not declared in the contract: note

   ⚪ Data types, constraints, location: not checked for local files (column names, row count and
masked-value shapes only)
...
1
```

Without `--strict` the same run reports the drift and exits `0`. Remove the extra column, or declare it in the contract, and the run exits `0` with `Match: 1`.

## Key options

| Option | Description |
| --- | --- |
| `--expose`, `--expose-id` | Verify only a specific expose |
| `--strict` | Exit non-zero on CRITICAL drift (see [Severity](#severity)). Non-critical drift (nullable-vs-required constraints, extra columns in a warehouse table) is reported and downgraded to a warning. Verification errors fail with or without `--strict`. |
| `--fail-on-warning` | Exit non-zero on any mismatch, including the non-critical drift `--strict` downgrades. Use it for a CI gate that must not let a required-to-nullable change through. Works with or without `--strict`. |
| `--out` | Write the JSON verification report to this path. No default: omit it and no report file is written. |
| `--show-diffs` | Show field-by-field differences |
| `--reconcile-dbt` | Cross-check the contract schema against the build's dbt project (`models/**/schema.yml`) and flag drift. Static, warehouse-free. |
| `--reconcile-lineage` | Cross-check declared lineage against local run evidence and the catalog publish payload. Local-only, no network. |
| `--state-drift` | Also refresh the OpenTofu state that `fluid apply` keeps for a cloud contract, and fail on resources changed outside the apply, as [`fluid diff`](./diff.md) does. Skipped, with a note, when no state is reachable. |
| `--state-backend` | With `--state-drift`: the remote state `fluid apply` used. Defaults to `$FLUID_STATE_BACKEND`, else local; `""` forces local. |
| `--workspace-dir DIR` | With `--state-drift`: the directory `fluid apply` ran in. Default `.`. |
| `--warn-only` | Downgrade `--reconcile-dbt`, `--reconcile-lineage` and `--state-drift` drift to a warning (exit `0`). |
| `--athena-output-location S3_URI` | Where Athena writes the row-count query result. Env `FLUID_ATHENA_OUTPUT_LOCATION`. See [S3 and Glue](#s3-and-glue-athena). |
| `--athena-workgroup NAME` | Athena workgroup for the row-count query. Env `FLUID_ATHENA_WORKGROUP`, default `primary`. |
| `--athena-timeout SECONDS` | Stop the Athena row-count query and fail after this long. Env `FLUID_ATHENA_TIMEOUT_SECONDS`, default `300`. |
| `--env` | Apply an environment overlay. See [Per-environment overlays](../recipes/per-environment-overlays.md). An environment with no overlay logs `overlay_not_found` and runs on the base contract; [`--env` and environment overlays](./validate.md#env-and-environment-overlays) says when it fails instead. A stage-1 bundle built for another env is refused with `bundle_env_mismatch`. |

For the Athena options the flag wins over the environment variable.

## What gets checked

`fluid verify` picks a verifier from each expose's binding. Each expose gets one status in the summary and the JSON report: a match, a mismatch, an error (the target could not be checked), or `unsupported` (no verifier for it).

| Binding | Verifier |
| --- | --- |
| `format: csv`, `parquet`, `pq` or `local`, or no format, with no cloud binding | [Local file](#local-files) |
| `format: bigquery_table`, or a `gcp` binding that provisions a BigQuery table or view | [BigQuery](#bigquery) |
| `platform: aws`, `format: parquet` (or no format), with `location.database`, `table` and `bucket` | [S3 and Glue](#s3-and-glue-athena) |
| `format: snowflake_table` or `snowflake_view` | [Snowflake](#snowflake) |
| Another `gcp` binding (a GCS bucket, a Pub/Sub topic, an Iceberg warehouse) | `unsupported` |
| Another `aws` or `azure` binding that names a bucket | `unsupported` |
| Any other format | `unsupported` |

An `unsupported` expose prints `Skipped`, is counted separately in the summary and never fails the run. It means `fluid verify` did not check it, not that the check passed:

```text
📋 Verifying: events
   Format: pubsub_topic
...
   ⏭️  Skipped: No verifier for this GCP binding (format: pubsub_topic); `fluid apply` provisions
it, stage 9 does not reconcile it
```

This table lists the dimensions each verifier reports. A blank cell means the dimension is not checked for that target.

| Dimension | Local file | BigQuery | S3 and Glue | Snowflake |
| --- | --- | --- | --- | --- |
| Schema structure (column names) | yes | yes | yes | yes |
| Data types | | yes | yes | yes |
| Constraints (`nullable` vs `required`) | | yes | | yes |
| Location | | region | S3 location | |
| `row_count` against the build's run records | | yes | yes | |
| `masking` | yes | yes | yes | |
| `retention` | | yes | yes | |
| `encryption` | | yes | yes | |
| `columnRestrictions` | | yes | yes | |

`retention`, `encryption` and `columnRestrictions` run only when the expose declares the matching field. Each one reads the live platform, so a check that cannot run is an error: it fails `fluid verify` with or without `--strict`.

### Severity

Each mismatch is scored:

| Severity | When it fires | Remediation |
| --- | --- | --- |
| CRITICAL | A missing column, a type mismatch, a region or location mismatch, an empty table, a row count that breaks the build's rule, a cleartext value in a masked column, a retention, encryption or column-restriction mismatch. For a local file, any column mismatch, extra columns included. | Manual intervention (table recreation, migration, or a rebuild of the output). |
| WARNING | `nullable` vs `required` mismatch (BigQuery and Snowflake). | Manual recommended; non-breaking but worth addressing. |
| INFO | A column in a warehouse or Glue table that the contract does not declare. An empty table in a reference-only contract with no run of its own. | Update the contract if the column is intentional. |
| SUCCESS | Everything matches. | No action. |

`--strict` fails on CRITICAL. `--fail-on-warning` also fails on WARNING and INFO. The JSON report carries the severity under `results.<expose>.severity.level`, so CI dashboards can key off it for red, amber and green.

### Exit codes

| Result | Exit code |
| --- | --- |
| An expose could not be verified: authentication failure, unreachable target, missing object, a failed Athena or BigQuery query, or a governance check that could not run | `1`, always |
| CRITICAL drift | `1` with `--strict`, otherwise `0` |
| Any non-critical mismatch | `1` with `--fail-on-warning`, otherwise `0` |
| `--reconcile-dbt` drift | `1`, unless `--warn-only` |
| `--reconcile-lineage` critical drift | `1` with `--strict`, unless `--warn-only` |
| `--state-drift`: resources changed outside the apply | `1`, unless `--warn-only` |
| `--state-drift`: the state could not be refreshed | `1`; `--warn-only` does not downgrade it |
| `unsupported` exposes | Not counted |

A contract file that cannot be read, or an unknown `--expose`, exits `1` before any target is checked.

::: tip Upgrading: a stage 9 that passed before can fail now
- An S3 and Glue binding was `unsupported` before 0.16.3, so it was never checked. It now is, including an Athena query, and 0.16.5 added the masking, lifecycle and key checks.
- A BigQuery table gets the row count and masking checks from 0.17.0, and that query needs `bigquery.jobs.create`.
- A local file whose columns differ from the contract, an extra column or the one-column placeholder an `amend` apply lands, is CRITICAL since 0.16.3, so `--strict` fails on it.
- A relative local output path resolves against the contract's directory since 0.16.3, and `{{ env.NAME }}` in a local path resolves as the build writes it since 0.16.4. Verify no longer reads from the working directory.
:::

### Local files

A local CSV or Parquet output has two checked dimensions: `schema_structure` and, when the expose declares `policy.privacy.masking`, `masking`. The row count is reported, not compared. The file is read with DuckDB, which needs the `local` extra.

- Any structure mismatch is CRITICAL, extra columns included. The file is the product, so a column the contract does not declare is a broken output. That includes the one-column placeholder that an `amend` apply lands: `--strict` fails on it.
- `{{ env.NAME }}` in a local path resolves as the build writer resolves it. A variable that is not set resolves to the empty string, on both sides.
- Verify reads the output file under the DuckDB sandbox's read rules. See the [DuckDB sandbox](../advanced/duckdb-sandbox.md).

### BigQuery

A BigQuery table is checked for the warehouse dimensions: structure, types, constraints and the dataset's region. `{{ env.X }}` in the binding resolves as `fluid apply` resolves it. A binding with no `project` uses the project from `GOOGLE_PROJECT`, `GOOGLE_CLOUD_PROJECT`, `GCLOUD_PROJECT` or `CLOUDSDK_CORE_PROJECT`, then the one Application Default Credentials carry. With none of them, the expose is an error that names the table.

Column types are compared after BigQuery's legacy names are folded into the standard ones (`INTEGER` and `INT64`, `FLOAT` and `FLOAT64`, `BOOLEAN` and `BOOL`, `RECORD` and `STRUCT`), so a correct `BOOL` column is not drift.

One GoogleSQL query then adds two dimensions:

| Dimension | What it checks | Fails as |
| --- | --- | --- |
| `row_count` | `COUNT(*)` held to the run records of the build that loads the expose (see [Row counts](#row-counts-and-run-records)). | An empty table is CRITICAL, except in a reference-only contract with no run of its own, where it is INFO. A count that breaks the build's rule is CRITICAL. |
| `masking` | For each `policy.privacy.masking` rule, the non-null values that do not have the strategy's shape. Only counts leave the query. | One such value is CRITICAL. |

The query needs `bigquery.jobs.create` on the project (`roles/bigquery.jobUser`) as well as read access to the table. A query that cannot run is an error. With `BIGQUERY_EMULATOR_HOST` set, the client talks to that host with anonymous credentials.

When the expose declares them, three governance dimensions read the live dataset and table:

| Dimension | Declared by | What it checks |
| --- | --- | --- |
| `retention` | `exposes[].lifecycle {retention, expire: true}` | The table is partitioned by day (on `binding.location.partitionBy` when it names a column, else ingestion time), its partitions expire after exactly the retention period, and the table itself has no expiration time. |
| `encryption` | `exposes[].binding.encryption.kms` | `kmsKeyName` of the table, and of the dataset's default when the product owns the dataset, is the declared key. |
| `columnRestrictions` | `exposes[].policy.authz.columnRestrictions` | Each restricted column carries a policy tag, the fine-grained readers on the tag are exactly the readers the contract derives, and the tag's taxonomy enforces fine-grained access control. |

A mismatch is CRITICAL. `retention` and `encryption` come from `lifecycle.expire` and `binding.encryption.kms`, which are in contract schema 0.7.6, a preview schema selected with `fluidVersion: "0.7.6"`. `columnRestrictions` is in 0.7.5. The `columnRestrictions` check calls the Data Catalog API with Application Default Credentials and reads the taxonomy (Data Catalog `GET`) and each policy tag's IAM policy (`getIamPolicy`), so the credentials need the matching Data Catalog read permissions. No emulator serves Data Catalog, so under `BIGQUERY_EMULATOR_HOST` the readers of the tagged columns are not checked and the dimension reports `unsupported`.

On 4 October 2026 the FLUID team ran `fluid verify` against real BigQuery for 11 products deployed from the same base contracts through a `gcp` overlay. Each passed its retention (DAY partitions with `expiration_ms`), encryption (a Cloud KMS key per dataset) and column-restriction (Data Catalog policy tags) checks. That is one run on one estate. In the same run, a principal outside the allowed readers who selected a restricted column was refused by BigQuery in this form:

```text
User has neither fine-grained reader nor masked get permission to get data protected by policy tag "<taxonomy> : <tag>" on column <project>.<dataset>.<table>.<column>.
```

### S3 and Glue (Athena)

A `platform: aws` binding with a `bucket`, `path`, `database` and `table` is provisioned by `fluid apply` as an S3 prefix plus a Glue table. Verify reads it in the binding's region. The checks:

| Check | How | Fails as |
| --- | --- | --- |
| The table exists | `glue:GetTable` | Error. In a reference-only contract, INFO. |
| Columns match the contract | Glue columns and partition keys against `contract.schema`, types folded through the Hive type map `fluid apply` declares them with | A missing column or changed type is CRITICAL; an extra column is INFO. |
| The table reads the binding's prefix | The Glue storage location against `s3://<bucket>/<path>` | CRITICAL. |
| Athena can read it | `SELECT COUNT(*)` through Athena, polled until it finishes or `--athena-timeout` passes | A failed, cancelled or timed-out query is an error. |
| It serves what the build landed | The count against the build's run records (see [Row counts](#row-counts-and-run-records)) | CRITICAL. An empty table is CRITICAL, except in a reference-only contract with no run of its own. |
| Masked columns landed treated | The same query counts non-null values of each masked column that lack the strategy's shape | One such value is CRITICAL. A masked column the Glue table lacks, or `k_anonymity`, fails too. |
| Retention (with `lifecycle {retention, expire: true}`) | `s3:GetLifecycleConfiguration`: the earliest `Expiration.Days` among the enabled prefix rules covering the binding's prefix must equal the retention in days. A rule that expires some of the objects sooner also fails. | CRITICAL. A configuration that cannot be read is an error. |
| Encryption (with `binding.encryption.kms` other than `none`) | `kms:DescribeKey` must answer `Enabled`, then `s3:HeadObject` on up to 1000 objects under the prefix must show `aws:kms` with that key | A disabled key or a wrong object is CRITICAL. No object yet is INFO. A call that fails is an error. |
| Column restrictions (with `policy.authz.columnRestrictions`) | `lakeformation:ListPermissions`: no principal's `SELECT` may reach a column the contract restricts from it | CRITICAL. |

Glue declares no nullability, so the constraints dimension has nothing to compare. The Lake Formation check lists the table permissions the caller can see, so it must run as a Lake Formation administrator. When the contract's own grants are not in the listing, it reports an error rather than a pass.

The result location, first match wins:

1. A workgroup with managed query results, or one that enforces its own output location: the workgroup's.
2. `--athena-output-location` or `FLUID_ATHENA_OUTPUT_LOCATION`.
3. The workgroup's configured output location.
4. `s3://<binding bucket>/.fluid/athena-results/`.

A result location inside the table's own prefix is refused or replaced, so that Athena's result files never land among the table's data. The JSON report records the location used and why under `results.<expose>.athena.output_location_source`.

The identity running `fluid verify` needs:

- Glue: `glue:GetTable` and `glue:GetDatabase`, plus `glue:GetPartitions` for a partitioned table.
- Athena: `athena:StartQueryExecution`, `GetQueryExecution`, `GetQueryResults` and `StopQueryExecution` on the workgroup, and `athena:GetWorkGroup` to read the workgroup's configuration.
- S3: `s3:GetObject` on the data prefix, read and write on the results prefix, and `s3:ListBucket`, `s3:GetBucketLocation` and `s3:ListBucketMultipartUploads` on the bucket.
- `s3:GetLifecycleConfiguration` for a declared retention; `kms:DescribeKey` for a declared key, and `kms:GenerateDataKey` and `kms:Decrypt` when the result is encrypted with it.
- For a prefix registered with Lake Formation, `lakeformation:GetDataAccess` and a Lake Formation `SELECT` grant on the table.

boto3 comes from the `aws` extra. Without it, the check is an error that names the extra.

### Row counts and run records

The count is compared with the run records the build wrote under `.fluid/runs/<contract id>/<build id>/runs/` next to the contract. A CI pipeline that runs verify in a separate stage has to carry that directory over, or no comparison happens. A run counts as this table's when its record says it landed rows in it: `facets.landed` for an S3 prefix, `facets.bigquery_load` for a BigQuery table. A run that landed somewhere else, such as a local run from the same contract directory, is passed over. The newest run that is this table's sets the rule, by the mode it recorded:

| Recorded mode | Rule |
| --- | --- |
| `full_refresh` | `equal`: the count equals that run's `records_total`. |
| `incremental_append` | `at_least_cumulative`: the count is at least the sum of `records_total` over the runs back to the last `full_refresh`. |
| Anything else | `reported`: a merge, dedup, CDC or streaming load can update or delete rows, so the count bounds nothing. |

The count is reported, and only an empty table fails, in cases such as: there is no run record, no run that landed in this table, a failed newest run, more than one build writes the expose (there is no single run to compare), or the newest run did not record its row count from the write. S3 also needs a build with `pattern: acquisition`; BigQuery also reads the run records of embedded-SQL builds.

### Snowflake

A Snowflake table is checked for structure, types and constraints. The count of rows is reported in the metadata and is not compared with the build.

## Reference-only contracts

For contracts where `builds[].pattern` is `hybrid-reference`, `reference`, or `external-reference`, the target tables are materialised by an externally-owned dbt or Airflow project, not by `fluid apply`. On the first pipeline run the external DAG has not run yet, so a missing table is expected state, not a verification failure.

`fluid verify` detects this mode from `builds[].pattern` and downgrades a missing target to `INFO`:

```text
(contract is reference-only — missing tables will be reported as INFO,
not treated as verification failures)

📋 Verifying: subscriber360_core
   Format: snowflake_table
   Target: TELCO_LAB.TELCO_FLUID_DEMO.SUBSCRIBER360_CORE_V1
   🔵 INFO: Table not found: ... (reference-only — external pipeline owns creation)
```

The downgrade is narrow:

- Only a target that does not exist (`result["exists"] is False`) is downgraded, along with an empty table that has no run of its own to compare with.
- Authentication, configuration and connection errors still fail the run, whether or not `--strict` is set.
- Contracts with another pattern (imperative, declarative) keep the original behaviour: a missing table is an error.

## Reconcile: contract and dbt schema (`--reconcile-dbt`)

A **static, warehouse-free** cross-check that the contract's promised columns (`exposes[].contract.schema`) agree with what the build's dbt project declares (`models/**/schema.yml`). It never connects to a warehouse and never runs dbt. It surfaces:

- a column the contract promises that dbt doesn't model,
- a dbt column the contract never exposes,
- a declared type that disagrees (compared conservatively through coarse type families, so `NUMBER(38,0)` vs `integer` is not flagged across adapters).

Drift exits non-zero unless `--warn-only` is set, independent of `--strict`: you asked for the check, so its drift gates on its own. The JSON report (`--out`) carries the detail under `report["reconcile"]`.

## Reconcile: contract and published lineage (`--reconcile-lineage`)

A **local-only** cross-check (no network) that the contract's declared lineage, `consumes[]` upstream refs and `exposes[]` output ports, agrees with:

1. **Observed run evidence**: the run records and cursor state the build runners persist under `.fluid/` (which source streams were actually read).
2. **The publish payload**: the lineage edges the catalog registrar would push, rebuilt locally from the contract.

| Drift class | Severity | Meaning |
| --- | --- | --- |
| `declared_but_never_read` | soft | A `consumes[]` entry with no run or cursor evidence. Never fails: the product may not have run yet. With no run evidence at all, the check degrades to a note. |
| `read_but_undeclared` | **critical** | A stream a runner read that is neither a `consumes[]` ref nor a declared acquisition source stream. Data flowed in that the contract never admits to. |
| `publish_payload_mismatch` | **critical** | The lineage edges or assets the registrar would publish disagree with the contract. |

Critical drift fails the run under `--strict` unless `--warn-only` is set; soft drift never fails. dbt run records are handled separately: their streams are executed nodes, not upstream reads, so they are excluded from the undeclared-read check with a note. The JSON report carries the detail under `report["reconcile_lineage"]`.

## Apply state drift (`--state-drift`)

`--state-drift` runs the pass [`fluid diff`](./diff.md) runs over the state `fluid apply` keeps: it refreshes the OpenTofu state and reports resources changed outside the apply. Run it from the directory `fluid apply` ran in, or pass `--workspace-dir`; for remote state, name the backend with `--state-backend` or `FLUID_STATE_BACKEND`. With no state in reach, the section prints a note and the run's drift comes from the live checks alone:

```text
================================================================================
🧭 Apply State Drift
================================================================================
State drift check: not run (no apply state for this contract at .fluid/iac/gcp/gold_events_v1: run from the directory `fluid apply` ran in (or pass --workspace-dir), or name the remote state with --state-backend / FLUID_STATE_BACKEND). Drift comes from the live checks alone.
```

## dbt test results (transformation checks)

When the product's build ran via dbt (`fluid apply --mode amend-and-build`), the runner parses `target/run_results.json` into run records, and `fluid verify` adds transformation-side checks next to the acquisition probes: **`dbt_tests_passed`** and **`no_error_severity_failures`**. Both are critical, so a failing contract-derived dbt test gates the exit code under `--strict`. See [`fluid runs status`](./runs.md) for the run-record view of the same data.

## Notes

- Use `verify` after apply, or in CI, when you need contract-to-runtime confidence.
- Use [`fluid test`](./test.md) when you want broader live-resource validation.
- The JSON report contains per-expose severity, the dimensional breakdown and remediation actions.
