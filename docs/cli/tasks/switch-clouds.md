---
title: Switch clouds with one line
description: Take a working data product on one cloud and redeploy it on another. ~5 minutes end-to-end.
---

# Task: Switch clouds with one line

You have a working data product on one cloud (say, local DuckDB) and you want to redeploy it on another (say, GCP BigQuery). The whole point of Forge's contract-first model is that this is a **one-line YAML change + a re-apply**.

Time: ~5 minutes assuming the target cloud is already credentialed.

## What you start with

A working contract on the original cloud. For this walkthrough we'll start with the local quickstart:

```bash
fluid init btc-tracker --quickstart
cd btc-tracker
fluid apply contract.fluid.yaml --yes
# ✓ Pipeline complete · runtime/out/bitcoin_prices.parquet (24 rows)
```

This produced a Parquet artifact via the `local` provider on DuckDB. Now we want the same product on BigQuery.

## Step 1 — install the target provider

```bash
pip install "data-product-forge[gcp]"
fluid providers
# Lists: local ✓, gcp ✓
```

GCP credentials are picked up via Application Default Credentials (`gcloud auth application-default login`). No Forge-specific auth setup.

## Step 2 — change one line in the contract

Open `contract.fluid.yaml` and find the `binding` block:

```yaml
exposes:
  - exposeId: bitcoin_prices
    binding:
      platform: local              # ← change this
      format: parquet
      location:
        path: ./runtime/out/bitcoin_prices.parquet
```

Change to:

```yaml
exposes:
  - exposeId: bitcoin_prices
    binding:
      platform: gcp                # ← here
      format: bigquery_table
      location:
        project: your-gcp-project
        dataset: crypto
        table: bitcoin_prices
        region: europe-west3
```

Three keys move (`platform`, `format`, `location`). Everything else — schema, dq.rules, accessPolicy, agentPolicy, sovereignty — stays **byte-identical**. Confirm with `git diff`:

```bash
git diff contract.fluid.yaml
# - platform: local
# - format: parquet
# - location: { path: ./runtime/out/bitcoin_prices.parquet }
# + platform: gcp
# + format: bigquery_table
# + location: { project: your-gcp-project, dataset: crypto, table: bitcoin_prices, region: europe-west3 }
```

## Step 3 — re-validate against the new platform

```bash
fluid validate contract.fluid.yaml
# ✓ Schema 0.7.2 — passed
# ✓ binding.platform=gcp — supported (provider gcp installed)
# ✓ binding.location complete (project, dataset, table)
# ✓ Contract validation passed
```

## Step 4 — preview what will change

```bash
fluid plan contract.fluid.yaml --env prod
# Plan summary:
#   + ensure  dataset    crypto (region=europe-west3)
#   + create  table      crypto.bitcoin_prices
#   + grant   role/dataViewer  (from accessPolicy.grants)
#   + run     build      bitcoin_price_ingestion (sql)
```

The planner is deterministic — same contract + same deployed state = same plan. The plan is **bound** (cryptographically) to the next apply step (stage 6 → 7 of the canonical pipeline).

## Step 5 — apply

```bash
fluid apply contract.fluid.yaml --env prod --yes
# ⏳ Acquiring lease on gold.crypto.bitcoin_tracker_v1...
# ⏳ Ensuring BigQuery dataset crypto...
# ✓ dataset crypto exists
# ⏳ Creating table crypto.bitcoin_prices...
# ✓ table crypto.bitcoin_prices created
# ⏳ Running bitcoin_price_ingestion (BigQuery SQL)...
# ✓ transformation complete (24 rows in)
# ⏳ Applying IAM bindings...
# ✓ BigQuery roles/dataViewer granted to group:analysts@company.com
# ✓ Pipeline complete in 4.83 s
```

The same data product is now on BigQuery. Same schema, same governance, same dq.rules.

## Step 6 — verify against the deployed state

```bash
fluid verify contract.fluid.yaml --env prod --strict
# ✓ Schema matches deployed state
# ✓ accessPolicy.grants match BigQuery IAM bindings
# ✓ dq.rules satisfied (24 rows pass completeness)
# ✓ Verify passed
```

## What happens if I want to switch again?

Same pattern — change `binding.platform` to `aws` (or `snowflake`), re-`apply`. The provider for the target cloud handles its own dialect/SDK quirks; the contract stays identical.

## What you DIDN'T have to do

- Rewrite SQL for a new dialect (Forge handles dialect translation when `engine: sql`; rare cases that genuinely need a hand-tuned dialect can use `engine: dbt` with target-specific macros)
- Re-author IAM in a new cloud's syntax (`accessPolicy.grants` → native IAM happens at `policy-apply`)
- Re-write your Airflow DAG (`fluid generate schedule --scheduler airflow` regenerates with the new platform)
- Re-test quality rules (the same `dq.rules` block runs against the new cloud's storage)

## See also

- [GCP walkthrough](/forge_docs/walkthrough/gcp) — full GCP-specific deployment guide
- [Snowflake walkthrough](/forge_docs/walkthrough/snowflake) — Snowflake team collaboration flow
- [Providers vs platforms](/concepts/providers-vs-platforms) — how the abstraction works
- [Same contract demo](/see-it-run.html#_0-03-per-data-product) — frame-perfect cast of this exact swap on screen
