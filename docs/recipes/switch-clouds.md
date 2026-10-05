---
title: "Recipe — switch clouds by editing only binding"
description: Move a working local contract to BigQuery, S3 + Glue or Snowflake by editing its binding block; everything else in the contract stays as it is.
---

# Recipe: switch clouds by editing only `binding`

**Time:** 5 minutes · **Audience:** anyone with a working local contract

## Problem

You prototyped a data product on `platform: local` (DuckDB and Parquet) and
want it on a cloud warehouse, without rewriting the contract.

## Solution

Edit the expose's `binding` block: `platform`, `format`, and the `location`
keys the target needs. Nothing outside `binding` changes. Validate, then apply.

To run the product on several clouds at once rather than move it, keep the
local binding in the base contract and put each cloud's binding in an overlay:
see [One contract, two clouds](./one-contract-two-clouds.md).

## Local → GCP / BigQuery

```diff
 exposes:
   - exposeId: customer_events
     binding:
-      platform: local
-      format: parquet
-      location:
-        path: output/customer_events.parquet
+      platform: gcp
+      format: bigquery_table
+      location:
+        project: acme-analytics-prod
+        dataset: customer_analytics
+        table: customer_events
+        region: europe-west3
```

```bash
pip install "data-product-forge[gcp]"
gcloud auth application-default login
fluid validate contract.fluid.yaml
fluid apply contract.fluid.yaml --mode amend-and-build --yes
```

## Local → AWS / S3 + Glue

```diff
     binding:
-      platform: local
-      format: parquet
-      location:
-        path: output/customer_events.parquet
+      platform: aws
+      format: parquet
+      location:
+        bucket: <your-bucket>
+        path: silver/customer_events/     # bucket-relative prefix
+        database: customer_analytics      # Glue database
+        table: customer_events            # Glue table
+        region: eu-central-1
```

Bucket names are global: write a bucket you own in place of `<your-bucket>`.
`location.path` is the prefix inside the bucket where the data lands; it is
always treated as a prefix. There is no `prefix:` key: the schema rejects one
("Additional properties are not allowed ('prefix' was unexpected)").

```bash
pip install "data-product-forge[aws]"
aws configure
fluid validate contract.fluid.yaml
fluid apply contract.fluid.yaml --mode amend-and-build --yes
```

## Local → Snowflake

```diff
     binding:
-      platform: local
-      format: parquet
-      location:
-        path: output/customer_events.parquet
+      platform: snowflake
+      format: snowflake_table
+      location:
+        database: ACME
+        schema: CUSTOMER_ANALYTICS
+        table: CUSTOMER_EVENTS
```

```bash
pip install "data-product-forge[snowflake]"
export SNOWFLAKE_ACCOUNT=myorg-myaccount
export SNOWFLAKE_USER=<user>
fluid validate contract.fluid.yaml
fluid apply contract.fluid.yaml --yes
```

`SNOWFLAKE_ACCOUNT` in the `<org>-<account>` form is enough: fluid derives the
`SNOWFLAKE_ORGANIZATION_NAME` + `SNOWFLAKE_ACCOUNT_NAME` pair the v2 OpenTofu
provider requires. For a bare account locator (`xy12345`), set the two v2
variables yourself; see
[Accepted `SNOWFLAKE_ACCOUNT` formats](../providers/snowflake.md#accepted-snowflake-account-formats).

## Check what you would deploy

`fluid generate iac` writes the OpenTofu module `fluid apply` would apply,
offline. For the three bindings above:

| Binding | Resources emitted |
|---|---|
| `platform: gcp` | `google_bigquery_dataset`, `google_bigquery_table` |
| `platform: aws` | `aws_s3_bucket`, `aws_glue_catalog_database`, `aws_glue_catalog_table` |
| `platform: snowflake` | `snowflake_database`, `snowflake_schema`, `snowflake_table` |

```console
$ fluid generate iac contract.fluid.yaml --out iac
...
Wrote OpenTofu module: iac/main.tf.json  (provider: gcp, 2 resources)
```

## Changing only `platform` is not enough

`platform` alone leaves a location the target cannot use. `fluid validate`
warns, and `fluid generate iac` and `fluid apply` refuse to emit an empty
module:

```console
$ fluid validate contract.fluid.yaml        # platform: gcp, format: parquet, location.path
...
 1. expose 'customer_events': platform=gcp resolves to no GCP resource — binding.format is 'parquet' and binding.location names none of dataset (BigQuery), bucket (Cloud Storage), topic (Pub/Sub). `fluid generate iac` and `fluid apply` would emit nothing for this port. Add the binding.location key for the container it lives in.

$ fluid generate iac contract.fluid.yaml --out iac
CLI command error
❌ generate_iac_empty_module  [ERR_GENERATE_IAC_EMPTY_MODULE]
  error: emitted no gcp resources — the module at iac/main.tf.json would provision nothing.
...
```

## Do not pass `--provider` to retarget

`--provider` is not a retargeting switch. It disambiguates a contract that
spans clouds or declares none. A `--provider` that contradicts every cloud the
contract declares is rejected before anything is written, on
`fluid generate iac` and on `fluid apply` (`ERR_GENERATE_IAC_PROVIDER_MISMATCH`).
Edit `binding` instead.

## What stays the same

Check it: strip the `binding:` block from each version and the remainder is
byte-identical.

```console
$ for c in contract.fluid.yaml contract.gcp.yaml contract.aws.yaml contract.snowflake.yaml; do
>   awk '/^    binding:/{skip=1; next} /^    contract:/{skip=0} !skip' "$c" | shasum
> done
<sha>  -
<sha>  -
<sha>  -
<sha>  -
```

The four lines are equal; the digest itself depends on your contract.

The `awk` filter assumes `binding:` sits directly before `contract:` in each
expose, as in this contract. The forge-cli repository's
[`examples/sovereignty-platform-swap`](https://github.com/Agenticstiger/forge-cli/tree/main/examples/sovereignty-platform-swap)
runs the same check on one product bound to AWS, GCP and Snowflake.

So `fluidVersion`, `id`, `metadata`, the embedded-SQL `builds[]`, the schema,
`dq.rules`, `sovereignty` and `agentPolicy` carry over unchanged. Two things
still depend on the target:

- **Principals.** On GCP, `accessPolicy.grants[].principal` values must be real
  IAM members: a placeholder such as `group:analysts@acme.example` (a reserved
  domain) or a bare `analysts` is refused at `fluid validate`. On AWS,
  `accessPolicy.grants` are not emitted; who reads a Glue table is the
  binding's `governance.lakeFormation.grants`. With `fluidVersion: "0.7.6"`,
  `binding.principals` maps logical principals per cloud so the grants
  themselves stay unchanged; see
  [Governance parity](../concepts/governance-parity.md#logical-principals-and-binding-principals).
- **Region under `sovereignty`.** A strict `sovereignty` block requires
  `location.region` (or `location.location`) to be in an allowed region of the
  target cloud; a binding with no region is refused on GCP.

## See also

- [One contract, two clouds](./one-contract-two-clouds.md) — keep both clouds
  with `--env` overlays.
- [Environments and overlays](../concepts/environments-and-overlays.md) — how
  `--env` finds and merges the overlay.
- [Preview fields](../reference/preview-fields.md#mapping-principals-per-cloud) —
  `binding.principals`, which needs `fluidVersion: "0.7.6"`.
- [Builds, exposes, bindings](../concepts/builds-exposes-bindings.md) — the
  `binding.platform` and `binding.format` values.
- [Governance parity](../concepts/governance-parity.md) — what retention,
  encryption and column restrictions become on each cloud.
- [Walkthroughs](../walkthrough/local.md) — step-by-step deploy guides per
  cloud.
