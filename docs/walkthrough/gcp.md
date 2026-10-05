# Walkthrough: Deploy to Google Cloud Platform

**Time:** 20 minutes  
**Difficulty:** Intermediate  
**Prerequisites:** GCP account, gcloud CLI, Python 3.10+, [OpenTofu](https://opentofu.org/docs/intro/install/) (`tofu`) on your `PATH` (or pass `--ensure-opentofu` to `fluid apply`)

<CliCast
  src="/forge_docs/demos/gcp-quickstart.svg"
  title="The same contract on BigQuery — change the binding, redeploy"
  caption="Click play above: the Customer 360 quickstart contract, re-pointed from local DuckDB to BigQuery by changing the expose binding. Three keys change together: `binding.platform`, `binding.format` and `binding.location`; see [Switch clouds](../cli/tasks/switch-clouds.md). The walkthrough below hand-builds a different example step by step, with auth + contract editing."
  width="920"
  insight="Same contract. The binding changed (platform: local → platform: gcp, with the format and location to match). | BigQuery dataset, table, and view — all created from the YAML you already had. | Schema, dq.rules and the build stages — unchanged from the local run."
/>

::: warning Which schema version this page uses
The contract below declares `fluidVersion: "0.7.6"`, the **preview** schema. It is the first schema that has `exposes[].lifecycle.expire`, which is what turns a retention period into a BigQuery partition expiry (Step 3). `0.7.5` is the latest stable schema and rejects that key (`exposes[0].lifecycle: Additional properties are not allowed ('expire' was unexpected)`). `fluid init --quickstart` scaffolds `0.7.5`, so if you start from a scaffold, change the version line by hand. For the stable and preview schemas, see [Getting started](../getting-started/README.md).
:::

---

## Overview

This walkthrough deploys a **Bitcoin price tracking data product** to **Google Cloud Platform**. Fluid Forge creates the BigQuery dataset and table from a contract; a small Python script loads prices from the CoinGecko API.

::: tip Working Example
A runnable example with deployment scripts for US and Germany regions is in [examples/bitcoin-tracker](https://github.com/Agenticstiger/forge_docs/tree/main/examples/bitcoin-tracker). It is a separate, larger example (dbt builds, Airflow, Jenkins); the contract on this page is a smaller one written for this walkthrough.
:::

### What You'll Build

- A BigQuery dataset and a day-partitioned table, created by `fluid apply`
- A 90-day retention rule declared in the contract and enforced as a partition expiry
- Dataset-level access for an analyst group and an ingestion service account
- A Python ingestion script and an hourly Cloud Scheduler trigger (these live outside the contract)

### What You'll Learn

- How a contract maps to BigQuery resources, and what `fluid apply` runs
- How to declare retention, and what it does to existing data
- What `fluid verify` compares against the live table
- Which parts of a typical GCP setup Fluid Forge does not manage in 0.18.1

---

## Step 1: GCP Setup

### Create GCP Project

::: warning Substitute your own project id
`my-project-id` is a placeholder. Project ids are unique across the whole of Google Cloud, so this
one will not be free: replace it with your own everywhere it appears on this page (the contract,
the commands and the Python), and set `GCP_PROJECT_ID` before running any of the Python. The
scripts below deliberately have no default, so an unset variable stops them rather than writing to
a project you do not own.
:::

```bash
# Create project (or use existing) - swap in your own id
gcloud projects create my-project-id \
  --name="Fluid Forge Crypto Tracker"

# Set as active project
gcloud config set project my-project-id

# Link billing account (required for BigQuery)
# Get billing account ID
gcloud billing accounts list

# Link it to project
gcloud billing projects link my-project-id \
  --billing-account=XXXXXX-XXXXXX-XXXXXX
```

::: tip Free Tier
BigQuery has a monthly free tier for queries and storage (limits are set by Google and change; see the [BigQuery pricing page](https://cloud.google.com/bigquery/pricing)). One table that receives a row an hour stays far inside it. The CoinGecko API has a free tier with rate limits.
:::

### Enable Required APIs

```bash
gcloud services enable bigquery.googleapis.com
gcloud services enable storage.googleapis.com
gcloud services enable cloudresourcemanager.googleapis.com
gcloud services enable iam.googleapis.com
```

Encrypting the table with a Cloud KMS key (the optional section after Step 6) also needs `cloudkms.googleapis.com`.

### Authenticate

`fluid apply` runs OpenTofu, and the OpenTofu Google provider reads Application Default Credentials:

```bash
# Authenticate with your Google account
gcloud auth application-default login

# Verify authentication
gcloud auth application-default print-access-token > /dev/null && echo "ADC works"
```

---

## Step 2: Create API Ingestion Script

Fluid Forge provisions the table. Loading rows into it is your code. This script fetches the current Bitcoin price from CoinGecko and streams one row into BigQuery.

### Create `ingest_bitcoin_prices.py`

```python
#!/usr/bin/env python3
"""
Bitcoin price ingestion from CoinGecko API to BigQuery
"""
import requests
from google.cloud import bigquery
from datetime import datetime, timezone
import os
import sys

def fetch_bitcoin_price():
    """Fetch current Bitcoin price from CoinGecko API"""
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {
        "ids": "bitcoin",
        "vs_currencies": "usd,eur,gbp",
        "include_market_cap": "true",
        "include_24hr_vol": "true",
        "include_24hr_change": "true",
        "include_last_updated_at": "true"
    }

    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()["bitcoin"]
    now = datetime.now(timezone.utc).isoformat()

    return {
        "price_timestamp": now,
        "price_usd": data["usd"],
        "price_eur": data["eur"],
        "price_gbp": data["gbp"],
        "market_cap_usd": data["usd_market_cap"],
        "volume_24h_usd": data["usd_24h_vol"],
        "price_change_24h_percent": data.get("usd_24h_change", 0.0),
        "ingestion_timestamp": now
    }

def insert_to_bigquery(row, project_id, dataset_id="crypto_data", table_id="bitcoin_prices"):
    """Insert Bitcoin price data into BigQuery"""
    client = bigquery.Client(project=project_id)
    table_ref = f"{project_id}.{dataset_id}.{table_id}"

    errors = client.insert_rows_json(table_ref, [row])

    if errors:
        raise Exception(f"BigQuery insert errors: {errors}")

    print(f"Inserted Bitcoin price: ${row['price_usd']:,.2f} at {row['price_timestamp']}")

if __name__ == "__main__":
    # No default project: an unset variable stops the script rather than
    # writing to whichever project happens to own that id.
    project_id = os.getenv("GCP_PROJECT_ID")

    if not project_id and len(sys.argv) > 1:
        project_id = sys.argv[1]

    if not project_id:
        print("Error: GCP_PROJECT_ID environment variable not set")
        print("Usage: python ingest_bitcoin_prices.py [PROJECT_ID]")
        print("   or: export GCP_PROJECT_ID=your-project-id && python ingest_bitcoin_prices.py")
        sys.exit(1)

    # Fetch price
    price_data = fetch_bitcoin_price()

    # Insert to BigQuery
    insert_to_bigquery(price_data, project_id)

    print(f"Market Cap: ${price_data['market_cap_usd']:,.0f}")
    print(f"24h Volume: ${price_data['volume_24h_usd']:,.0f}")
```

Install dependencies:
```bash
pip install requests google-cloud-bigquery
```

---

## Step 3: Create the Contract

Create `contract.fluid.yaml`:

```yaml
fluidVersion: "0.7.6"
kind: DataProduct
id: crypto.bitcoin_prices_gcp
name: bitcoin-prices-gcp
description: Bitcoin price tracking on BigQuery, fed hourly from the CoinGecko API.

tags:
  - crypto
  - bitcoin
  - time-series

metadata:
  layer: Gold
  owner:
    team: data-engineering
    email: data-eng@company.com

# Who may read and write. On GCP this becomes dataset-level IAM.
accessPolicy:
  grants:
    - principal: "group:data-analysts@company.com"
      permissions: [read, select]
    - principal: "serviceAccount:ingestion@my-project-id.iam.gserviceaccount.com"
      permissions: [write, insert, update]

exposes:
  - exposeId: bitcoin_prices_table
    kind: table
    description: Bitcoin prices from the CoinGecko API
    tags:
      - raw-data
      - non-pii

    # Keep 90 days. Partitions older than that expire.
    lifecycle:
      retention: P90D
      expire: true

    binding:
      platform: gcp
      format: bigquery_table
      location:
        project: my-project-id
        dataset: crypto_data
        table: bitcoin_prices
        region: us-central1
        partitionBy: [price_timestamp]

    policy:
      classification: Public

    contract:
      schema:
        - name: price_timestamp
          type: TIMESTAMP
          required: true
          description: When the price was recorded
          sensitivity: none
          semanticType: timestamp
        - name: price_usd
          type: FLOAT64
          required: true
          description: Bitcoin price in USD
          sensitivity: none
          semanticType: currency
        - name: price_eur
          type: FLOAT64
          required: true
          description: Bitcoin price in EUR
          sensitivity: none
          semanticType: currency
        - name: price_gbp
          type: FLOAT64
          required: true
          description: Bitcoin price in GBP
          sensitivity: none
          semanticType: currency
        - name: market_cap_usd
          type: FLOAT64
          required: true
          description: Total market capitalization in USD
          sensitivity: none
          semanticType: currency
        - name: volume_24h_usd
          type: FLOAT64
          required: true
          description: 24-hour trading volume in USD
          sensitivity: none
          semanticType: currency
        - name: price_change_24h_percent
          type: FLOAT64
          required: false
          description: 24-hour price change percentage
          sensitivity: none
          semanticType: percentage
        - name: ingestion_timestamp
          type: TIMESTAMP
          required: true
          description: When the row was written to BigQuery
          sensitivity: internal
          semanticType: timestamp
```

What each block does on GCP:

| Block | What `fluid apply` emits |
| --- | --- |
| `binding.location` (`project`, `dataset`, `table`, `region`) | One `google_bigquery_dataset` and one `google_bigquery_table`. `region` becomes the dataset location. |
| `lifecycle.retention` + `lifecycle.expire: true` | `time_partitioning` on the table: type `DAY`, and `expiration_ms` set to the retention period (`P90D` is `7776000000` ms). |
| `binding.location.partitionBy` | The column the partitions are cut on. It is an **array** naming one `DATE`, `TIMESTAMP` or `DATETIME` column; a scalar fails `fluid validate`. It takes effect only together with `lifecycle.expire: true`. With `expire: true` and no `partitionBy`, the table is partitioned by ingestion time. |
| `accessPolicy.grants` | `google_bigquery_dataset_iam_member` resources: `read`/`select` become `roles/bigquery.dataViewer`, `write`/`insert`/`update` become `roles/bigquery.dataEditor`. |
| `contract.schema` | The table schema (`name`, `type`, `mode` and `description` per column). |

As of 0.18.1 the GCP emitter does not write the expose `description` and `tags`, `policy.classification`, or the per-column `sensitivity` and `semanticType` into the BigQuery resources. They stay in the contract, and the exports in Step 9a read from it.

::: warning Keys that look like they configure BigQuery and do not
`binding.properties.partitioning` (with `expirationDays` or `expiration_days`), `binding.properties.clustering` and `policy.authz.readers` / `writers` are not read by the GCP emitter. A contract that uses them validates, plans and applies, and produces a table with **no** partitioning, no expiry and no IAM grants. Use `lifecycle` and `location.partitionBy` for partitioning and expiry, and `accessPolicy.grants` for access. As of 0.18.1 the emitter writes no clustering at all.
:::

::: warning Contract labels do not reach BigQuery
The labels on the tables and the dataset are `managed_by: fluid` and `fluid_contract: <contract id with dots as underscores>`. A `labels:` map on the contract, the expose or the binding is not copied to them. Use the `fluid_contract` label for cost attribution (Step 11).
:::

---

## Step 4: Validate the Contract

```bash
fluid validate contract.fluid.yaml
```

Output:

```text
bigquery_retention_event_time exposes[bitcoin_prices_table]: partitioned by price_timestamp, so each row expires P90D after the date in price_timestamp, not after it was written (a backfill of older rows is deleted at once). Drop binding.location.partitionBy to count from landing, as the S3 rule does.
✅ Valid FLUID contract (schema v0.7.6)
Validation completed in 0.015s
```

The first line is a warning, not an error. With `partitionBy`, retention counts from the **date in the column**, not from when the row was written, so loading old rows into the table deletes them at once. The ingestion script here writes the current time, so the two are the same. If you backfill history, remove `partitionBy` and BigQuery partitions by ingestion time instead.

Validation checks the contract against the schema version it declares. It does not check your GCP project.

---

## Step 5: Preview the Plan

```bash
fluid plan contract.fluid.yaml
```

```text
============================================================
FLUID Execution Plan
============================================================
Contract: bitcoin-prices-gcp
Version: 0.7.6
Total Actions: 1
============================================================

1. provision_bitcoin_prices_table (provisionDataset)

✅ Plan saved to: .../plan.json
```

`fluid plan` lists one provisioning action for the table. It does not call Google Cloud and does not list the individual BigQuery resources. To see those, use the dry-run in Step 6.

The contract's `binding.platform: gcp` selects the provider, and `binding.location.project` names the project, so you do not need `--provider`, `--project`, `FLUID_PROVIDER` or `FLUID_PROJECT` here.

---

## Step 6: Deploy to GCP

### Preview the infrastructure

```bash
fluid apply contract.fluid.yaml --dry-run
```

The GCP provider applies through OpenTofu. A dry-run writes the OpenTofu module, runs `tofu plan` against your project with your Application Default Credentials, and stops. The `bigquery_retention_event_time` warning from validate prints here too, before the OpenTofu block, and is trimmed from the sample:

```text
OpenTofu engine — provider: gcp
  module:      .fluid/iac/gcp/crypto_bitcoin_prices_gcp/main.tf.json
  state:       local
  credentials: ...

  tofu plan: +5 ~0 -0

dry-run: plan only — not applying.
```

`+5` is the five resources this contract creates. Open `.fluid/iac/gcp/crypto_bitcoin_prices_gcp/main.tf.json` to read them:

| Resource | Why |
| --- | --- |
| `google_bigquery_dataset` | `crypto_data`, location `us-central1`, labels `managed_by` and `fluid_contract` |
| `google_bigquery_table` | `bitcoin_prices` with the schema, and `time_partitioning` (below) |
| `terraform_data` | A marker that holds the partition column; see [Changing retention later](#changing-retention-later) |
| `google_bigquery_dataset_iam_member` (two) | The analyst group as `roles/bigquery.dataViewer`, the ingestion service account as `roles/bigquery.dataEditor` |

The table's partitioning, from the emitted module:

```json
"time_partitioning": {
  "expiration_ms": 7776000000,
  "field": "price_timestamp",
  "type": "DAY"
}
```

### Apply

```bash
fluid apply contract.fluid.yaml --yes
```

This creates the dataset, the table and the two IAM members. State is local by default (the `state:` line above); pass `--state-backend gcs://<bucket>/<prefix>` when more than one person or a CI job applies the same contract (see [`fluid apply`](../cli/apply.md)). Keep `.fluid/` out of version control. If `tofu` is not installed, add `--ensure-opentofu` to download a pinned build.

Check the result with `bq`:

```bash
bq show --format=prettyjson my-project-id:crypto_data.bitcoin_prices | jq '{timePartitioning, labels}'
```

The `timePartitioning` object shows `type: DAY`, `field: price_timestamp` and `expirationMs: "7776000000"`, and `labels` shows the two Fluid labels.

::: tip Apply output
`fluid apply` prints the OpenTofu plan and apply progress for your project; this page shows only the lines that were reproduced offline (the dry-run above). Your apply log will differ in the resource ids and timings.
:::

### Optional: encrypt the table with a Cloud KMS key

Add an `encryption` block next to `location`, and enable `cloudkms.googleapis.com` first:

```yaml
    binding:
      platform: gcp
      format: bigquery_table
      location:
        # ...unchanged
      encryption:
        kms: product
```

With `kms: product`, the emitted module gains a key ring and a key named `bigquery` in the dataset's location, with a rotation period of 90 days (`7776000s`). For this contract the key ring is `fluid-crypto_bitcoin_prices_gcp-crypto_data`. The module grants `roles/cloudkms.cryptoKeyEncrypterDecrypter` on the key to the project's BigQuery service agent and sets the key as the dataset default and on the table. The table waits for that grant.

- `kms: projects/<project>/locations/<loc>/keyRings/<ring>/cryptoKeys/<key>` uses a key you already own; you grant the service agent yourself.
- `kms: none` is Google-managed encryption.
- Applying needs the caller to hold `roles/cloudkms.admin`. Cloud KMS key rings cannot be deleted once created, so a `tofu destroy` leaves the ring behind.
- Tables of one dataset must agree on one key; mixed settings are refused.

Running `fluid apply --dry-run` on this variant writes a module with `google_kms_key_ring`, `google_kms_crypto_key`, `google_kms_crypto_key_iam_member` and a `data.google_bigquery_default_service_account` lookup. The lookup calls the BigQuery API, so unlike the plain contract, this dry-run needs working credentials to reach `tofu plan`.

---

## Step 7: Ingest the First Bitcoin Price

Run the ingestion script to load the first price data point:

```bash
# Set environment variable
export GCP_PROJECT_ID=my-project-id

# Run ingestion
python ingest_bitcoin_prices.py
```

The script prints the price it inserted (the values are whatever CoinGecko returns when you run it):

```text
Inserted Bitcoin price: $<price> at <timestamp>
Market Cap: $<market cap>
24h Volume: $<volume>
```

Check the row:

```bash
bq query --use_legacy_sql=false \
  'SELECT * FROM `crypto_data.bitcoin_prices` ORDER BY price_timestamp DESC LIMIT 1'
```

::: warning The first rows may not show up in a query for a short while
BigQuery streaming inserts land in a streaming buffer. A `SELECT` normally sees them within seconds, but DML (`UPDATE`, `DELETE`) on those rows is blocked for a while after the insert.
:::

---

## Step 8: Query Your Data in BigQuery

### Using BigQuery Console

1. Open [BigQuery Console](https://console.cloud.google.com/bigquery)
2. Navigate to your project → `crypto_data` dataset
3. Run queries:

```sql
-- Latest prices
SELECT * FROM `crypto_data.bitcoin_prices`
ORDER BY price_timestamp DESC
LIMIT 10;

-- Daily summary statistics
SELECT
  DATE(price_timestamp) as date,
  AVG(price_usd) as avg_price_usd,
  MIN(price_usd) as min_price_usd,
  MAX(price_usd) as max_price_usd,
  STDDEV(price_usd) as daily_volatility,
  SUM(volume_24h_usd) as total_volume_usd
FROM `crypto_data.bitcoin_prices`
GROUP BY DATE(price_timestamp)
ORDER BY date DESC;
```

### Using bq CLI

```bash
# Query from command line
bq query --use_legacy_sql=false \
  'SELECT
    price_timestamp,
    price_usd,
    price_eur,
    market_cap_usd / 1000000000 as market_cap_billions
  FROM `crypto_data.bitcoin_prices`
  ORDER BY price_timestamp DESC
  LIMIT 5'

# Export to CSV in a bucket you own
bq extract \
  --destination_format CSV \
  crypto_data.bitcoin_prices \
  gs://<your-bucket>/bitcoin_prices_*.csv
```

### A view for the daily summary (outside the contract)

A view over the table is plain BigQuery SQL:

```bash
bq query --use_legacy_sql=false \
  'CREATE OR REPLACE VIEW `crypto_data.daily_summary` AS
   SELECT DATE(price_timestamp) AS date,
          AVG(price_usd) AS avg_price_usd,
          MIN(price_usd) AS min_price_usd,
          MAX(price_usd) AS max_price_usd
   FROM `crypto_data.bitcoin_prices`
   GROUP BY date'
```

Fluid Forge does not manage this view. As of 0.18.1 a contract cannot declare a BigQuery view: the GCP emitter recognises `binding.format: bigquery_view` with a `location.query`, but none of the bundled schemas (0.7.1 to 0.7.6) accepts either, so `fluid validate` rejects them. An expose declared as `kind: view` with `format: bigquery_table` is created as an empty **table**. To produce a derived table from SQL, write a second data product whose embedded-SQL build reads this one through `consumes[]`; the build reads the upstream BigQuery table through the API and loads its result into the first expose's BigQuery table (see [`fluid apply`](../cli/apply.md)).

---

## Step 9: Verify Deployment

```bash
fluid verify contract.fluid.yaml --out verify.json
```

`fluid verify` reads the live table with your credentials and compares it with the contract. For a BigQuery table it reports these dimensions, and `verify.json` holds each one under `dimensions`:

| Dimension | Compared with |
| --- | --- |
| `structure` | Column names and count |
| `types` | Each column's BigQuery type |
| `constraints` | `required` against `REQUIRED` / `NULLABLE` |
| `location` | `binding.location.region` against the dataset location |
| `retention` | `lifecycle` against the table's partition expiry (only when the expose declares it) |
| `encryption` | `binding.encryption` against the table's key (only when declared) |
| `columnRestrictions` | Policy tags against the contract's column restrictions (only when declared) |
| `row_count` | The table's row count (taken with a query), compared with the rows a Fluid build recorded when it loaded the table, when such a run record exists |

Severity levels and flags such as `--strict` are in the [`fluid verify` reference](../cli/verify.md). Measured against real BigQuery on 4 October 2026: products deployed with `fluid apply` passed `fluid verify`, including the retention and encryption dimensions.

---

## Step 9a: Export to Open Standards (ODPS & ODCS)

Fluid Forge can export your data product to industry-standard formats for catalogs and contract tooling.

### Export to ODPS (Open Data Product Specification)

The [Open Data Product Specification](https://github.com/Open-Data-Product-Initiative) is a vendor-neutral standard for describing data products. `--spec odps-4.1` writes the LF/ODPI v4.1 JSON document:

```bash
fluid odps export contract.fluid.yaml --spec odps-4.1 --out bitcoin-tracker.odps.json
```

```text
✓ Exported to ODPS v4.1 (LF/ODPI): bitcoin-tracker.odps.json
  Specification: https://github.com/Open-Data-Product-Initiative/v4.1
```

Without `--spec`, `fluid odps export` writes Bitol ODPS v1.0.0 (one product document plus one ODCS contract per output port), as YAML. The start of the v4.1 file for this contract:

```json
{
  "schema": "https://github.com/Open-Data-Product-Initiative/v4.1/blob/main/source/schema/odps.json",
  "version": "4.1",
  "product": {
    "details": {
      "en": {
        "name": "bitcoin-prices-gcp",
        "productID": "crypto.bitcoin_prices_gcp",
        "visibility": "private",
        "status": "draft",
        ...
```

### Export to ODCS (Open Data Contract Standard)

The [Open Data Contract Standard](https://github.com/bitol-io/open-data-contract-standard) from Bitol.io describes the schema, quality rules and servers of one dataset:

```bash
fluid odcs export contract.fluid.yaml --output bitcoin-tracker.odcs.yaml
```

```text
Exported ODCS contract: bitcoin-tracker.odcs.yaml
✓ Exported to bitcoin-tracker.odcs.yaml
```

### Validate the Exported Files

`fluid odps validate` checks Bitol ODPS v1.0.0 unless you name the spec, so pass `--spec odps-4.1` for the file above:

```bash
fluid odps validate bitcoin-tracker.odps.json --spec odps-4.1
fluid odcs validate bitcoin-tracker.odcs.yaml
```

```text
✓ ODPS v4.1 file is valid: bitcoin-tracker.odps.json
  Schema: https://github.com/Open-Data-Product-Initiative/v4.1/blob/main/source/schema/odps.json
✓ jsonschema: clean
```

Without `--spec odps-4.1`, the v4.1 file fails validation with `'apiVersion' is a required property`, because it is checked against the other standard. The [`fluid odps`](../cli/odps.md), [`fluid odcs`](../cli/odcs.md) and [`fluid generate standard`](../cli/generate.md) pages list the formats.

---

## Step 10: Set Up Scheduled Ingestion

The hourly load is your code on your scheduler. Fluid Forge does not deploy it.

### Option 1: Cloud Scheduler and a Cloud Function

Create `main.py` for the Cloud Function:

```python
import functions_framework
from ingest_bitcoin_prices import fetch_bitcoin_price, insert_to_bigquery
import os

@functions_framework.http
def main(request):
    """HTTP Cloud Function for Bitcoin price ingestion"""
    # No default: refuse to run rather than write to some other account's project.
    project_id = os.getenv("GCP_PROJECT_ID")
    if not project_id:
        return {"status": "error", "message": "GCP_PROJECT_ID is not set on this function"}, 500

    try:
        price_data = fetch_bitcoin_price()
        insert_to_bigquery(price_data, project_id)

        return {
            "status": "success",
            "price_usd": price_data["price_usd"],
            "timestamp": price_data["price_timestamp"]
        }, 200
    except Exception as e:
        return {"status": "error", "message": str(e)}, 500
```

Deploy it so that only Cloud Scheduler can call it. The function writes to your warehouse, so do not deploy it with `--allow-unauthenticated`:

```bash
# Deploy Cloud Function (requires authentication to invoke)
gcloud functions deploy bitcoin-price-ingestion \
  --runtime python310 \
  --trigger-http \
  --no-allow-unauthenticated \
  --entry-point main \
  --source . \
  --service-account=ingestion@my-project-id.iam.gserviceaccount.com \
  --set-env-vars GCP_PROJECT_ID=my-project-id \
  --region us-central1

# Create Cloud Scheduler job (runs hourly), authenticating as a service account
# that holds the Cloud Functions invoker role on the function
gcloud scheduler jobs create http bitcoin-hourly-ingest \
  --schedule="0 * * * *" \
  --uri="https://us-central1-my-project-id.cloudfunctions.net/bitcoin-price-ingestion" \
  --http-method=GET \
  --oidc-service-account-email=scheduler@my-project-id.iam.gserviceaccount.com \
  --location=us-central1
```

The function runs as `ingestion@...`, the account named in the contract's `accessPolicy` write grant, so the dataset grant that `fluid apply` created is the one the function uses.

### Option 2: Apache Airflow

`fluid generate schedule` generates Airflow, Dagster and Prefect artifacts from a contract's `builds[]` and `orchestration` block. The contract on this page has neither: the ingestion is outside the contract, and `fluid generate schedule contract.fluid.yaml` asks for `orchestration.engine` or `--scheduler`; with `--scheduler airflow` it stops with `Contract missing 'orchestration' section`. When your contract declares builds, follow [Declarative Airflow integration](./airflow-declarative.md). The older `fluid generate-airflow` command still runs; it prints `Note: 'generate-airflow' is deprecated. Use 'fluid generate schedule --scheduler airflow' instead.`

---

## Step 11: Attribute Costs

The tables and the dataset that Fluid Forge creates carry two labels: `managed_by=fluid` and `fluid_contract=<contract id>`. The contract id has `.` replaced with `_`: for this contract, `crypto_bitcoin_prices_gcp`.

```bash
bq show --format=prettyjson my-project-id:crypto_data.bitcoin_prices | jq '.labels'
```

```json
{
  "fluid_contract": "crypto_bitcoin_prices_gcp",
  "managed_by": "fluid"
}
```

Group Cloud Billing export rows by the `fluid_contract` label to see cost per data product.

Team or cost-centre labels that you declare in the contract (a `labels:` map) are not carried to these resources in 0.18.1, so they cannot be used for chargeback.

---

## Changing retention later

Three changes to the contract behave differently once the table holds data:

| Change | What the plan does |
| --- | --- |
| `retention: P90D` to `P30D` | An in-place update of `expiration_ms`. Partitions older than the new period expire. |
| Adding `lifecycle.expire: true` to a table that exists, or changing the partition column | A **replacement** of the table: BigQuery cannot partition an existing table. `fluid apply` refuses it unless you pass `--allow-data-loss`, and the next load starts from an empty table. |
| Removing `expire: true` | Also a replacement (BigQuery cannot un-partition a table), gated the same way. |

The replacement comes from the `terraform_data` resource that holds the partition column and type: the table's `replace_triggered_by` names it, and the period is deliberately left out of it, which is why a new period is only an update. Plan with `fluid plan` and `fluid apply --dry-run` before you change either key on a live product. The rules for `--allow-data-loss` are in the [`fluid apply`](../cli/apply.md) reference.

---

## What You've Learned

- A contract's `binding.location` becomes a BigQuery dataset and table, applied through OpenTofu.
- `lifecycle` (with `expire: true`) and `location.partitionBy` set partitioning and expiry; `binding.properties.partitioning` is not read.
- `accessPolicy.grants` become dataset IAM members.
- `fluid verify` compares the live table, including retention and encryption when declared.
- Loading rows, scheduling the load, and views are outside the contract in 0.18.1.

---

## Next Steps

### More assets in the same dataset

Add another `exposes[]` entry with its own `binding.location.table`:

```yaml
  - exposeId: ethereum_prices_table
    kind: table
    binding:
      platform: gcp
      format: bigquery_table
      location:
        project: my-project-id
        dataset: crypto_data
        table: ethereum_prices
        region: us-central1
```

Re-run `fluid plan` and `fluid apply --dry-run`: the new table is added and the existing one is untouched. Tables of one dataset must use the same region.

### BI Dashboards

Connect Looker, Tableau, or Looker Studio:
- Dataset: `my-project-id.crypto_data`
- Table: `bitcoin_prices`, and any view you created in Step 8
- Credentials: a service account with the BigQuery Data Viewer role

### Price alerts

Find significant price changes:

```sql
SELECT
  price_timestamp,
  price_usd,
  price_change_24h_percent
FROM `crypto_data.bitcoin_prices`
WHERE ABS(price_change_24h_percent) > 5.0  -- more than 5% change
ORDER BY price_timestamp DESC;
```

### BigQuery ML

```sql
CREATE MODEL `crypto_data.bitcoin_price_forecast`
OPTIONS(
  model_type='ARIMA_PLUS',
  time_series_timestamp_col='price_timestamp',
  time_series_data_col='price_usd'
) AS
SELECT
  price_timestamp,
  price_usd
FROM `crypto_data.bitcoin_prices`;
```

---

## Troubleshooting

### "Permission denied" errors

The identity you applied with needs to create datasets and tables and to set dataset IAM. For a throwaway project, grant yourself BigQuery Admin:
```bash
gcloud projects add-iam-policy-binding my-project-id \
  --member="user:YOUR_EMAIL@example.com" \
  --role="roles/bigquery.admin"
```

### `opentofu_plan_failed` before anything is created

The OpenTofu provider could not authenticate or reach the API. Run `gcloud auth application-default login`, confirm the project id, and confirm the BigQuery API is enabled. `fluid apply --dry-run` reproduces the failure without changing anything.

### Re-running apply

`fluid apply` is incremental against the OpenTofu state in `.fluid/iac/gcp/<contract id>/`. Re-running it with an unchanged contract plans no changes. If you delete `.fluid/` or run from another machine without a shared `--state-backend`, OpenTofu has no record of the dataset and will try to create it again.

### CoinGecko API rate limits

The free tier allows a small number of calls a minute. For production:
- Use a CoinGecko paid API plan
- Retry with exponential backoff
- Cache responses

### Slow queries

Filter on the partition column so BigQuery reads only the partitions it needs:
```sql
-- Prunes partitions
SELECT * FROM `crypto_data.bitcoin_prices`
WHERE price_timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY);

-- Reads every partition
SELECT * FROM `crypto_data.bitcoin_prices`
WHERE price_usd > 40000;
```

---

## Clean Up (Optional)

Destroy what Fluid Forge created with the module it wrote, so that the state stays consistent:

```bash
tofu -chdir=.fluid/iac/gcp/crypto_bitcoin_prices_gcp destroy
```

Then remove what you created by hand:

```bash
# Delete Cloud Function
gcloud functions delete bitcoin-price-ingestion --region us-central1

# Delete Cloud Scheduler job
gcloud scheduler jobs delete bitcoin-hourly-ingest --location us-central1

# Or delete the whole project (removes everything in it)
gcloud projects delete my-project-id
```

---

## Next

- [CLI Reference](../cli/README.md) — the Fluid Forge commands
- [GCP Provider Guide](../providers/gcp.md) — what the GCP provider supports
- [Local Walkthrough](./local.md) — test the same contract locally with DuckDB first
- [Declarative Airflow integration](./airflow-declarative.md) — schedule builds from a contract
