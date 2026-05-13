---
title: "Recipe — switch clouds with one line"
description: Take an existing local contract and redeploy it to BigQuery / Athena / Snowflake.
---

# Recipe: switch clouds with one line

**Time:** 1 minute · **Audience:** anyone with a working local contract

## Problem

You've prototyped a data product on `platform: local` (DuckDB / Parquet) and want to ship it to a real cloud — without rewriting the contract.

## Solution

Change the `binding.platform`, swap `format` + `location` to match the new platform's vocabulary, and re-run `fluid apply`. The schema, dq rules, accessPolicy, and agentPolicy stay byte-for-byte identical.

## Local → GCP / BigQuery

```diff
 exposes:
   - exposeId: bitcoin_prices
     binding:
-      platform: local
-      format: parquet
-      location:
-        path: ./runtime/out/bitcoin_prices.parquet
+      platform: gcp
+      format: bigquery_table
+      location:
+        project: my-project
+        dataset: crypto_data
+        table: bitcoin_prices
+        region: europe-west3
```

```bash
pip install "data-product-forge[gcp]"
gcloud auth application-default login
fluid apply contract.fluid.yaml --yes
```

## Local → AWS / Athena

```diff
     binding:
-      platform: local
-      format: parquet
-      location:
-        path: ./runtime/out/bitcoin_prices.parquet
+      platform: aws
+      format: s3_file
+      location:
+        bucket: example-data-lake
+        prefix: crypto/bitcoin_prices/
+        region: eu-west-1
```

```bash
pip install "data-product-forge[aws]"
aws configure
fluid apply contract.fluid.yaml --yes
```

## Local → Snowflake

```diff
     binding:
-      platform: local
-      format: parquet
-      location:
-        path: ./runtime/out/bitcoin_prices.parquet
+      platform: snowflake
+      format: snowflake_table
+      location:
+        database: PROD
+        schema: GOLD
+        table: BITCOIN_PRICES
```

```bash
pip install "data-product-forge[snowflake]"
export SNOWFLAKE_ACCOUNT=...
export SNOWFLAKE_USER=...
fluid apply contract.fluid.yaml --yes
```

## What stays the same

- `fluidVersion`, `kind`, `id`, `name`, `metadata` — untouched.
- `builds[]` — untouched if it's `embedded-logic` SQL.
- `exposes[].contract.schema` — untouched.
- `exposes[].contract.dq.rules` — untouched.
- `accessPolicy.grants[]` — `principal:` strings change to match the cloud's IAM format (e.g. `group:` for GCP, `role:` for Snowflake), but the structure is the same.
- `agentPolicy` — untouched.

## See also

- [Concepts → Builds, Exposes, Bindings](/concepts/builds-exposes-bindings.md) — full `binding.platform` and `binding.format` enums.
- [Walkthroughs](/forge_docs/walkthrough/local) — step-by-step deploy guides per cloud.
