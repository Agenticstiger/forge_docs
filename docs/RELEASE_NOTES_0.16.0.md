---
title: Release notes — CLI 0.16.0
description: What changed in data-product-forge 0.15.1 through 0.16.2, what can break on upgrade, and what to check — generated code that runs and cannot be injected, and one contract landing where it says on AWS and Google Cloud.
---

# Fluid Forge Docs Baseline: CLI `0.16.0`

**Release dates:** `0.15.1`, `0.15.2` and `0.15.3` on September 15, 2026; `0.16.0`, `0.16.1`
and `0.16.2` on September 23, 2026.
**Status:** Superseded by [`0.17.0`](./RELEASE_NOTES_0.17.0.md). The current baseline is
[`0.18.1`](./RELEASE_NOTES_0.18.0.md). Supersedes [`0.15.0`](./RELEASE_NOTES_0.15.0.md).

This baseline covers six CLI releases. None of `0.15.1` to `0.16.2` had a docs pass of its own,
so they are documented together here. To move a project from `0.15.x` to today's release, use
the [upgrade guide](./upgrading.md), which has a checklist for each version after this one.

## Headline

Code that FLUID generates now runs as generated, and contract values are escaped in the
scheduler code it emits.

- **Two security fixes in `0.16.0`.** A `stages[].name` such as `../../../../ESCAPED` made
  `fluid generate transformation` write outside its output directory. And contract values
  were pasted into generated Airflow, Prefect and Dagster code unescaped, so a quote in a
  contract's `name` or a build's `script` ran as Python when the scheduler loaded the file.
- **The generated SQL project runs.** Each multi-stage script now creates the view the next
  stage reads (`CREATE OR REPLACE VIEW`), and binds the inputs the contract declares. That is
  a behaviour change: see the checklist.
- **One contract applied to AWS and to Google Cloud lands where it says (`0.16.2`).** The AWS
  region comes from the binding, not the shell. A BigQuery binding loads its rows into the
  table. `binding.location.project` is honoured. Athena can read the Glue Parquet tables FLUID creates.
- **The CLI's own links go to real pages (`0.15.1`–`0.15.3`).** Typed errors, scaffolded
  contracts and the validator pointed at documentation domains that did not exist, or at one
  owned by an unrelated company; `fluid --help` pointed at the schema repository instead of
  the docs site.

`pip install --upgrade data-product-forge` gives you the current release, not this one. Pin
`0.16.2` only if you are stepping through versions one at a time.

::: tip Who should upgrade
Anyone who runs `fluid generate transformation`, `fluid generate schedule` or the Airflow,
Prefect or Dagster code the cloud providers emit, on contracts they did not write. Anyone
running the generated SQL scripts against Snowflake or Databricks, where the new views drop
grants. Anyone applying to **AWS** from a shell whose default region differs from the
binding's. Anyone with a **BigQuery** binding, a **dbt** multi-stage build, a
`consumes[].upstreamDigest` pin, or a `fluid import airbyte` job.
:::

## Upgrade checklist

Work through this before you upgrade a CI lane from `0.15.x`.

1. **Expect generated SQL scripts to create views.** Each multi-stage script now carries
   `CREATE OR REPLACE VIEW <output> AS …`, and its header says which it is:
   `-- Materialises: <name>  (CREATE OR REPLACE VIEW)` or `-- Not materialised: <reason>`.
   On Snowflake and Databricks, `OR REPLACE` drops the grants on an existing view, and a
   Snowflake stream over it goes stale. A script whose output name matches an existing
   **table** fails instead of converting it. Re-grant after running, or rename the output.
2. **Expect dbt multi-stage models to be renamed.** Models are now named after
   `stages[].outputs` (`customer_360_master.sql`), not after the stage
   (`stage_4_rfm_calculation.sql`). The contract's data tests now attach to real models, so
   the deliberate `fluid_*` sentinel tests (checks dbt cannot express) fail loudly where they
   were silently attached to nothing. Update anything that refers to the old model names.
3. **Treat the federation digest gate as a warning.** `fluid apply` no longer aborts when a
   `consumes[].upstreamDigest` pin cannot be confirmed. It logs `apply_consumes_drift` at
   WARNING and applies. If CI must block on it, fail the job on that log line. Step 11 of the
   [`0.15.0` checklist](./RELEASE_NOTES_0.15.0.md), which says the apply exits 1, no longer
   holds.
4. **Check the region of every AWS contract you applied before `0.16.2`.** The AWS provider
   now takes its region from the bindings when they all name one. If a contract was first
   applied from a shell in another region, `fluid apply` refuses with
   `opentofu_region_moved` and names both regions. Either set `location.region` to the region
   the resources are in, or empty and remove them there, then apply again.
5. **Check AWS Parquet tables that Athena must read.** Tables created before `0.16.2` have
   no Hive input format or SerDe, and Athena fails with
   `HIVE_UNSUPPORTED_FORMAT: Unable to create input format`. As of `0.16.2`, new tables
   declare them. Whether a re-apply updates an existing table was not checked here, so run
   `fluid apply --dry-run` and look for an in-place change to the table's storage descriptor.
6. **Point `fluid import airbyte` at your server.** Pass `--server-url`, or set
   `FLUID_IMPORT_AIRBYTE_URL`. With neither, the import refuses before it opens a connection.
7. **Check where a bucket-bound DuckDB build lands.** A binding with `location.bucket` now
   writes to `s3://<bucket>/<path>`, as its Glue table already said. Before `0.16.0` the rows
   went to a local directory and the build reported success.
8. **Using the container image?** There is no `0.16.0` image: the first image after `0.15.3`
   is `0.16.1`, on Python 3.14.

::: warning Behaviour changes that can newly fail
1. **Generated SQL creates views**, which drops grants on Snowflake and Databricks and fails
   on a same-name table.
2. **dbt sentinel tests fire**, because the contract's tests now attach to models.
3. **`opentofu_region_moved`** stops an AWS apply whose state is in another region.
4. **A contract with a path-escaping or colliding stage name** fails generation with
   `generated_path_outside_output_dir` or `generated_path_collision`.
5. **A federated `consumes[]` entry that names `upstreamWorkspace` without `upstreamDigest`**
   fails validation (fluid-schema `0.7.6` only).
6. **A BigQuery load that cannot be done** (more than one stream, a sink other than Parquet, a
   mode other than `full_refresh` or `incremental_append`, a missing `gcp` extra) is refused
   before any work runs.
:::

## What changed in `0.16.2`

`0.16.2` makes one contract applied to AWS and to Google Cloud do what it says on both.

### AWS resources are created in the binding's region

The AWS provider took its region from the environment only, so a contract bound to
`eu-west-1`, applied from a shell set to `us-east-1`, created its bucket and Glue database in
`us-east-1` while the sovereignty check passed for `eu-west-1`. When every AWS binding names
the same region, that region now goes on the provider block and wins over the environment.
Bindings that span regions keep the environment's region, with a warning. A jurisdiction
(`EU`), a Google region or an unresolved `{{ env.AWS_REGION }}` placeholder is not pinned.

Pinning the region changes where a re-apply looks, so the apply first reads the regions its
state records. If they differ, it stops:

```text
opentofu_region_moved: state holds this contract's resources in <old-region>, but its
bindings name <new-region>. Applying would create them again in <new-region> and leave the
originals unmanaged
```

### BigQuery bindings load their rows

A DuckDB build with a `bigquery_table` binding wrote Parquet to `gs://` and loaded nothing
into the table. It now stages the file under `.fluid/staging/` and runs one BigQuery load job
into the declared table, with the table's own schema. Authentication is Application Default
Credentials, so gcloud ADC, a VM service account and Workload Identity Federation need no
extra configuration. A load that fails, finds no table, or loads a different row count fails
the build.

### Also in `0.16.2`

- `binding.location.project` is honoured for the dataset and the table. It was ignored.
- In a contract with two builds, each build writes to the expose its `outputs` names. The
  second build used to write to the first expose, and on BigQuery truncated its table.
- The BigQuery IaC maps column types BigQuery does not have (`VARCHAR`, `UUID`, `SMALLINT`,
  `TIMESTAMPTZ`, `BLOB`) to ones it does.
- [`fluid verify`](./cli/verify.md) compares BigQuery types by meaning, so `INT64` reported as
  `INTEGER` is no longer drift.
- Glue Parquet tables declare the input format, output format and SerDe Athena needs.

## What changed in `0.16.1`

The release workflow scans the container image with Grype and fails on a fixable High. The
`0.16.0` job failed that gate on CVE-2026-82049 in the Python 3.13 interpreter, so no `0.16.0`
image was pushed. `0.16.1` moves the image to `python:3.14-slim` and is the first image
published since `0.15.3`. Its PyPI wheel has the same content as `0.16.0`'s.

## What changed in `0.16.0`

### Security

- **Generated files stay inside `--output`.** `fluid generate transformation` built each path
  from contract fields such as `stages[].name`, which the schema does not constrain. Every
  path is now checked against the output root before anything is written; an escape raises
  `generated_path_outside_output_dir`, and two names that land on one file raise
  `generated_path_collision`.
- **Contract values are escaped in generated scheduler code.** The Airflow DAG generator and
  the AWS, GCP and Snowflake Prefect and Dagster emitters pasted contract values into Python
  source. A quote closed the string literal and the rest of the value ran when the scheduler
  parsed or imported the file. Values now go through shell quoting, Python-literal quoting and
  identifier sanitising.

This matters wherever whoever runs `generate` did not write the contract, for example a
contract pulled from another team's registry.

### Changed

- **Generated SQL creates views.** See step 1 of the checklist. The single-stage
  `embedded-logic` pattern is unchanged.
- **dbt models are named after their declared output.** See step 2. Generated dbt YAML now
  parses on dbt-core 1.8 through dbt-oss 2.0, and `dbt-core` is capped below 2.0 wherever FLUID
  installs dbt.
- **The federated-digest gate warns.** Its verdict depends on another team's registry being
  reachable, so a hard failure let their outage block your apply. Findings log as
  `apply_consumes_drift: <n> federated consumes[] entries could not be confirmed in sync (…).
  Applying anyway.` with a JSON payload carrying `counts_by_kind`, `drift_count` and
  `unreachable_count`. Each finding has a `violation_kind`: `drift`, `unreachable`,
  `unpinned`, `unknown-workspace` or `not-wired`. `--no-verify-federation` skips the check
  and logs a warning that it was skipped. `FLUID_FEDERATION_TIMEOUT_SECONDS` (default 30) bounds each git operation, which
  could previously hang an apply.
- **Shipped templates and examples declare `fluidVersion: "0.7.5"`**, the stable schema.

### Added

- **`consumes[].upstreamWorkspace` and `consumes[].upstreamDigest`**, in the `0.7.6` preview
  schema only. `upstreamWorkspace` names a workspace from `federation/upstreams.yaml`;
  `upstreamDigest` pins it as `sha256:<64 hex>`. Declaring the workspace without the digest
  fails validation. Before this release the apply-time gate existed, but a contract carrying
  these keys failed validation first.
- **An engine that ignores `consumes[]` says so.** Only the dbt engine wires `consumes[]`
  (into `models/sources.yml`). The `sql`, `spark`, `glue`, `dataform` and `dataflow` engines
  now warn once per build, naming each upstream they will not wire.

### Fixed

- A binding that names a bucket lands its data in that bucket, and `fluid verify` reads an
  `aws` binding from S3 rather than as a local file (verified against a real AWS account).
- Generated SQL scripts register the inputs the contract declares, so a project that applied
  cleanly also runs standalone.
- Generated CI pipelines no longer call `fluid` commands and flags that do not
  exist. They are replaced, and a test parses each emitted invocation against the CLI.
- Two `actionId`s that differ only in punctuation no longer collapse onto one Airflow task.
- `fluid apply` says when `consumes[]` entries are unbound, instead of implying they are wired.
- `fluid init --template multiple-outputs` scaffolds a contract that validates.
- One unreachable federated upstream no longer hides drift in another, and an unreachable
  registry is reported as `unreachable`, not as missing FLUID code.

## What changed in `0.15.1`–`0.15.3`

Three patches, all about where the CLI sends you. If your terminal output differs from an
older page of these docs in its links, this is why.

- **Typed errors link to real pages.** A typed error prints an
  `[ERR_<EVENT>]` code, suggestions, and a `📖` link. The link pointed at a domain with no DNS
  record; it now resolves through a map of pages this site serves, and a topic with no page
  goes to [Production troubleshooting](./advanced/production-troubleshooting.md):

  ```console
  $ fluid validate no-such.fluid.yaml
  ❌ Contract file not found: None
     [ERR_CONTRACT_FILE_NOT_FOUND]
     💡 Check the file path is correct
     💡 Ensure you're in the correct directory
     💡 Verify file permissions
     📖 https://agenticstiger.github.io/forge_docs/advanced/production-troubleshooting.html
  ```

  (Output from `0.18.1`. The message prints `None` where the path belongs.)
- **Validator and template links no longer go to `docs.fluid.io`**, a live site owned by an
  unrelated company.
- **`fluid` and `fluid --help`** show separate `Docs` and `Spec` lines, and the footer credits
  Agentics Transformation Limited.
- **`fluid --version`** no longer prints a `next:` milestone that had already shipped.
- **Scaffolded files link to real pages**: line 2 of a new contract, and the README of a
  generated Airflow DAG.
- **`fluid apply --help` and `fluid market --help`** link to pages that exist; `fluid demo`
  failures point at forge-cli's issue tracker.
- **Links no longer wrap mid-URL** in a narrow terminal, so they stay clickable.

## See also

- [Upgrade guide](./upgrading.md)
- [OpenTofu state](./concepts/state.md),
  [Environments and overlays](./concepts/environments-and-overlays.md)
- [`0.17.0` release notes](./RELEASE_NOTES_0.17.0.md)
- [`fluid apply`](./cli/apply.md), [`fluid verify`](./cli/verify.md),
  [`fluid generate`](./cli/generate.md)
- [AWS provider](./providers/aws.md), [GCP provider](./providers/gcp.md)
- [forge-cli CHANGELOG](https://github.com/Agenticstiger/forge-cli/blob/main/CHANGELOG.md)
