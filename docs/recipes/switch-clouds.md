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

::: warning Editing `binding` is the only way to retarget *(since 0.15.0)*
`--provider` is not a retargeting switch. It disambiguates a contract that spans
clouds or declares none, and *since 0.15.0* a `--provider` that contradicts every
cloud the contract declares is rejected before anything is written — on both
`fluid generate iac` and `fluid apply`. Before that release it emitted a
resource-free module and exited 0, or, where a binding was shape-compatible across
clouds, emitted the wrong cloud's resources. Do the edit below; do not pass
`--provider`.
:::

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
export SNOWFLAKE_ACCOUNT=myorg-myaccount
export SNOWFLAKE_USER=...
fluid apply contract.fluid.yaml --yes
```

`SNOWFLAKE_ACCOUNT` in the `<org>-<account>` form is enough: *since 0.15.0* fluid
derives the `SNOWFLAKE_ORGANIZATION_NAME` + `SNOWFLAKE_ACCOUNT_NAME` pair the v2
OpenTofu provider requires and blanks the legacy variable, which that provider
rejects outright. For a bare account locator (`xy12345`), set the two v2 variables
yourself — see
[Accepted `SNOWFLAKE_ACCOUNT` formats](/forge_docs/providers/snowflake.html#accepted-snowflake-account-formats).

## What stays the same

- `fluidVersion`, `kind`, `id`, `name`, `metadata` — untouched.
- `builds[]` — untouched if it's `embedded-logic` SQL.
- `exposes[].contract.schema` — untouched.
- `exposes[].contract.dq.rules` — untouched.
- `accessPolicy.grants[]` — `principal:` strings change to match the cloud's IAM format (e.g. `group:` for GCP, `role:` for Snowflake), but the structure is the same.
- `agentPolicy` — untouched.

## See also

- [Concepts → Builds, Exposes, Bindings](/forge_docs/concepts/builds-exposes-bindings.html) — full `binding.platform` and `binding.format` enums.
- [Walkthroughs](/forge_docs/walkthrough/local) — step-by-step deploy guides per cloud.
- [`examples/sovereignty-platform-swap`](https://github.com/Agenticstiger/forge-cli/tree/main/examples/sovereignty-platform-swap) — the same product (`analytics.eu.customer_events_v1`) compiled against AWS, GCP and Snowflake, with the `binding` block as the only difference between the three contract files. Its README walks `validate` → `policy-check` → three `generate iac` runs → the ODPS / ODCS export, with a cleanup step, and never passes `--provider`. The contracts declare `fluidVersion: 0.7.6`, a preview version — valid because they name it explicitly, and still never the default for an untagged contract.
