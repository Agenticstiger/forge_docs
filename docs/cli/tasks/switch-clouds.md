---
title: Switch clouds by editing only binding
description: Take a data product that runs locally and redeploy it on GCP BigQuery by editing its binding block, then validate, preview, apply and verify.
---

# Task: Switch clouds by editing only `binding`

You have a data product running locally on DuckDB, and you want it on GCP
BigQuery. The contract's `binding` block says where the product lives; you edit
that block and nothing else, then re-apply.

Time: about 5 minutes once the target cloud is credentialed.

To keep the local version and add the cloud one, or to run on AWS and GCP at
the same time, use overlays instead: see
[One contract, two clouds](../../recipes/one-contract-two-clouds.md).

## What you start with

A contract with one embedded-SQL build that reads `data/events.csv` and lands a
Parquet file (the base contract of
[One contract, two clouds](../../recipes/one-contract-two-clouds.md), without
its governance block):

```console
$ fluid apply contract.fluid.yaml --mode amend-and-build --yes
...
🔷 Build 'load_events' (embedded-SQL / local DuckDB)
   ✅ Completed in 1.31s — 1 action(s) executed
...
```

## Step 1 — install the target provider

```bash
pip install "data-product-forge[gcp]"
gcloud auth application-default login
```

The `gcp` extra is needed by the build as well as the apply: an embedded-SQL
build whose expose is a BigQuery table loads its result through the BigQuery
API. Without it the build stops with "the expose is a BigQuery table, and this
install cannot load one".

## Step 2 — edit the binding

```yaml
exposes:
  - exposeId: customer_events
    binding:
      platform: local
      format: parquet
      location:
        path: output/customer_events.parquet
```

becomes

```yaml
exposes:
  - exposeId: customer_events
    binding:
      platform: gcp
      format: bigquery_table
      location:
        project: acme-analytics-prod
        dataset: customer_analytics
        table: customer_events
        region: europe-west3
```

Three keys move: `platform`, `format` and `location`. Changing `platform`
alone is not enough; validate warns that the binding "resolves to no GCP
resource", and generate and apply refuse an empty module.

## Step 3 — validate

```console
$ fluid validate contract.fluid.yaml
✅ Valid FLUID contract (schema v0.7.5)
Validation completed in 0.001s
```

If the contract has `accessPolicy.grants`, their principals must now be real
IAM members (`group:analysts@<your-domain>`, with the domain of your own
groups); a placeholder in a reserved domain such as `.example` is refused here.

## Step 4 — preview

`fluid generate iac` writes the OpenTofu module apply will run, offline:

```console
$ fluid generate iac contract.fluid.yaml --out iac
...
Wrote OpenTofu module: iac/main.tf.json  (provider: gcp, 2 resources)
```

The two resources are a `google_bigquery_dataset` and a
`google_bigquery_table`. `fluid apply --dry-run` goes one step further and runs
`tofu plan`:

```console
$ fluid apply contract.fluid.yaml --mode amend-and-build --dry-run
...
OpenTofu engine — provider: gcp
  module:      .fluid/iac/gcp/analytics_customer_events_v1/main.tf.json
  state:       local
  credentials: none detected in environment
  tofu plan: +2 ~0 -0
dry-run: plan only — not applying.
...
```

For a pipeline, `fluid plan` writes the `plan.json` a later
`fluid apply plan.json` is bound to.

## Step 5 — apply

```bash
fluid apply contract.fluid.yaml --mode amend-and-build --yes
```

Apply creates the dataset and table with OpenTofu, then runs the build, which
loads the query result into the table. The state is local
(`.fluid/iac/gcp/<id>/terraform.tfstate`) unless `--state-backend` or
`FLUID_STATE_BACKEND` names a bucket; in CI, use a bucket. See
[OpenTofu state](../../concepts/state.md).

## Step 6 — verify

```bash
fluid verify contract.fluid.yaml --strict
```

`fluid verify` reads the live table: the schema, and the row count against the
build's run records. When the contract declares retention, a key or column
restrictions, it checks those on the live table too (see
[Governance parity](../../concepts/governance-parity.md)). It does not check
dataset grants.

## Switching again

The same edit takes the product to AWS (`platform: aws`, `format: parquet`,
`location: {bucket, path, database, table, region}`) or Snowflake
(`platform: snowflake`, `format: snowflake_table`,
`location: {database, schema, table}`). The
[switch-clouds recipe](../../recipes/switch-clouds.md) has each diff and a check
that nothing outside `binding` changed.

The previous cloud's resources and state stay where they were: apply does not
remove them when the binding moves away.

## See also

- [GCP walkthrough](../../walkthrough/gcp.md)
- [Providers vs platforms](../../concepts/providers-vs-platforms.md)
- [Governance parity](../../concepts/governance-parity.md)
