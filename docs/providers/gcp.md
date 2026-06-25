# GCP Provider

**Status:** ✅ Production Ready  
**Docs Baseline:** CLI `0.9.0`<br>
**Services:** BigQuery, Cloud Storage, IAM, Cloud Run, Pub/Sub

> **Why it matters**
> Ship the same contract to BigQuery without a GCP-specific rewrite.
> Set `binding.platform: gcp` and Forge compiles to BigQuery DDL + IAM and OpenTofu from the same file.

::: warning Compatibility note
This page preserves some older examples for compatibility context. Current scaffolds emit `fluidVersion: 0.7.5`, and orchestration docs now prefer `fluid generate schedule --scheduler airflow`.
:::

---

## Overview

The Google Cloud Platform provider is the flagship Fluid Forge implementation, offering production-grade support for BigQuery, Cloud Storage, and comprehensive GCP services.

### Why GCP?

- **Serverless Analytics** - BigQuery eliminates infrastructure management
- **Cost-Effective** - Pay-per-query pricing with generous free tier
- **Enterprise Scale** - Petabyte-scale analytics out of the box
- **ML Integration** - Native BigQuery ML and Vertex AI
- **IAM Access Control** - Dataset/table-level IAM bindings compiled from the contract

---

## Quick Start

### Prerequisites

```bash
# Install gcloud SDK
curl https://sdk.cloud.google.com | bash

# Authenticate
gcloud auth application-default login

# Set project
gcloud config set project YOUR_PROJECT_ID

# Enable APIs
gcloud services enable bigquery.googleapis.com
gcloud services enable storage.googleapis.com
```

### Minimal Contract

```yaml
fluidVersion: "0.7.4"
kind: DataProduct
id: analytics.customers_v1
name: Customer Analytics
domain: analytics

metadata:
  layer: Bronze
  owner:
    team: data-engineering
    email: data-engineering@company.com

exposes:
  - exposeId: customers
    kind: table
    binding:
      platform: gcp
      format: bigquery_table
      location:
        project: my-project-id
        dataset: analytics
        table: customers
    contract:
      schema:
        - name: id
          type: INTEGER
          required: true
        - name: name
          type: STRING
```

**Deploy:**

```bash
fluid apply contract.yaml --provider gcp
```

**Generate Orchestration Code:**

```bash
# Generate Airflow DAG
fluid generate-airflow contract.yaml -o dags/my_pipeline.py

# Export to Dagster
fluid export contract.yaml --engine dagster -o pipelines/

# Export to Prefect
fluid export contract.yaml --engine prefect -o flows/
```

---

## Supported Features

### ✅ BigQuery

| Feature | Support | Notes |
|---------|---------|-------|
| Datasets | ✅ Full | Multi-region, labels, access control |
| Tables | ✅ Full | Partitioning, clustering, expiration |
| Views | ✅ Full | Standard and materialized views |
| External Tables | ✅ Full | GCS, Google Sheets, Bigtable |
| Routines | ✅ Full | UDFs, stored procedures |
| Authorized Views | ✅ Full | Fine-grained access control |
| Policy Tags | 🔜 Not yet | Column-level security via Data Catalog taxonomies is not emitted by the contract — manage with `gcloud` |
| Data Masking | 🔜 Not yet | BigQuery dynamic data masking is not emitted by the contract |
| Row-Level Security | 🔜 Not yet | No `CREATE ROW ACCESS POLICY` is emitted; row-level governance is roadmap |

### ✅ Cloud Storage

| Feature | Support | Notes |
|---------|---------|-------|
| Buckets | ✅ Full | Multi-region, versioning |
| Objects | ✅ Full | Upload, download, lifecycle |
| Lifecycle Policies | ✅ Full | Auto-delete, archival |
| Signed URLs | ✅ Full | Temporary access |
| Notifications | ✅ Full | Pub/Sub integration |

### ✅ Airflow DAG Generation

| Feature | Support | Notes |
|---------|---------|-------|
| Airflow DAGs | ✅ Full | Cloud Composer compatible |
| BigQuery Operators | ✅ Full | Query, table, dataset, view operations |
| GCS Operators | ✅ Full | Bucket and object management |
| Pub/Sub Operators | ✅ Full | Topic and subscription operations |
| Dataflow Operators | ✅ Full | Beam pipeline execution |
| Contract Validation | ✅ Full | Structure checks + circular dependency detection |
| Dagster Pipelines | ✅ Full | Type-safe ops with resources |
| Prefect Flows | ✅ Full | Retry logic and deployment configs |

### ✅ IAM & Security

| Feature | Support | Notes |
|---------|---------|-------|
| Service Accounts | ✅ Full | Auto-creation, key management |
| IAM Bindings | ✅ Full | Least-privilege access (dataset/table-level) |
| Policy Tags | 🔜 Not yet | Data Catalog taxonomies are not a contract construct — manage with `gcloud` |
| Audit Logs | ✅ Full | Admin, data access logs |
| VPC Service Controls | 🔜 Not yet | Network isolation is roadmap |

### ⏳ Cloud Run (Preview)

| Feature | Support | Notes |
|---------|---------|-------|
| Services | ✅ Beta | Container deployment |
| Jobs | ✅ Beta | Batch processing |
| Auto-scaling | ✅ Beta | Request-based scaling |
| Custom Domains | 🔜 Q2 2026 | HTTPS endpoints |

---

## Configuration

### Provider Settings

The GCP provider needs no contract-level provider block. It is selected from
each expose's `binding.platform`, so `--provider gcp` is optional for `plan`,
`apply`, and `verify`. What you configure per output is the `binding` — the
`format` and the BigQuery `location` coordinates:

```yaml
exposes:
  - exposeId: events
    kind: table
    binding:
      platform: gcp
      format: bigquery_table
      location:
        project: my-project-id
        dataset: analytics
        table: events
        region: US        # BigQuery multi-region (US, EU)
    contract:
      schema:
        - name: id
          type: INTEGER
          required: true
```

Project, region, BI Engine sizing, default table expiration, and networking
are environment-level GCP settings rather than contract fields. Apply them with
`gcloud`, project-level IAM, or your environment configuration. Resource labels
can be attached per expose with `binding.labels`.

> Note: cost-control knobs such as `enable_bi_engine`, `max_bytes_billed`, and
> VPC networking have no current contract-schema equivalent — manage them
> outside the contract.

---

## BigQuery Best Practices

### Partitioning

Partition tables by date for performance and cost savings. BigQuery-specific
table options live under `binding.properties`, which accepts provider-specific
keys:

```yaml
exposes:
  - exposeId: events
    kind: table
    binding:
      platform: gcp
      format: bigquery_table
      location:
        project: my-project-id
        dataset: events
        table: events
      properties:
        partitioning:
          field: event_timestamp
          type: DAY  # or HOUR, MONTH, YEAR
          require_partition_filter: true  # Enforce partitioned queries
          expiration_days: 90  # Auto-delete old partitions
    contract:
      schema:
        - name: event_timestamp
          type: TIMESTAMP
          required: true
```

**Cost savings:** Up to 90% reduction for time-based queries

### Clustering

Cluster columns for better query performance:

```yaml
exposes:
  - exposeId: events
    kind: table
    binding:
      platform: gcp
      format: bigquery_table
      location:
        project: my-project-id
        dataset: events
        table: events
      properties:
        clustering:
          fields: [user_id, event_type, country]  # Max 4 fields
    contract:
      schema:
        - name: user_id
          type: STRING
          required: true
```

**Performance:** Up to 10x faster queries on clustered columns

### Materialized Views

Pre-compute aggregations. Expose the result as a `view` and produce it with a
`builds[]` entry holding the SQL:

```yaml
builds:
  - id: build_daily_metrics
    pattern: embedded-logic
    engine: sql
    properties:
      sql: |
        SELECT
          DATE(event_timestamp) as date,
          user_id,
          COUNT(*) as event_count,
          SUM(revenue) as total_revenue
        FROM `${project}.events.raw_events`
        GROUP BY date, user_id
    outputs:
      - daily_metrics

exposes:
  - exposeId: daily_metrics
    kind: view
    binding:
      platform: gcp
      format: bigquery_table
      location:
        project: my-project-id
        dataset: events
        table: daily_metrics
      properties:
        materialized: true
        refresh_interval_minutes: 60  # Refresh hourly
    contract:
      schema:
        - name: date
          type: DATE
          required: true
        - name: user_id
          type: STRING
        - name: event_count
          type: INTEGER
        - name: total_revenue
          type: NUMERIC
```

**Benefit:** Sub-second queries on complex aggregations

---

## Security & Governance

### Column-Level Security

Protect sensitive data per expose. Classification, reader/writer roles, and
column restrictions live under the expose's `policy` block; column sensitivity
is declared on each schema field:

```yaml
exposes:
  - exposeId: customers
    kind: table
    binding:
      platform: gcp
      format: bigquery_table
      location:
        project: my-project-id
        dataset: analytics
        table: customers
    policy:
      classification: Confidential
      authn: iam
      authz:
        readers:
          - group:data-analysts@company.com
        columnRestrictions:
          - principal: "group:interns@company.com"
            columns: [email, phone, ssn]
            access: deny
    contract:
      schema:
        - name: email
          type: STRING
          sensitivity: pii        # Restricted access
        - name: name
          type: STRING            # No sensitivity flag = public
```

> Note: BigQuery policy-tag taxonomies are not a contract-schema construct.
> Express column sensitivity with `schema[].sensitivity` and restrict access
> with `policy.authz.columnRestrictions`; manage the underlying Data Catalog
> taxonomy with `gcloud`.

**IAM Integration:**
```bash
# Grant access to PII data
gcloud data-catalog taxonomies add-iam-policy-binding \
  data_classification \
  --member="user:analyst@company.com" \
  --role="roles/datacatalog.categoryFineGrainedReader"
```

### Data Masking

::: warning Declarative only
`policy.privacy.masking` is a valid schema field, but the GCP provider does **not** currently
emit any BigQuery dynamic-masking or Data Catalog data-policy resource from it. Today the block
records masking *intent* as contract metadata; it does not provision masking infrastructure.
Apply BigQuery masking with `gcloud` / Data Catalog data policies until this is wired in.
:::

Declare masking intent on the expose with `policy.privacy.masking`:

```yaml
exposes:
  - exposeId: customers
    kind: table
    binding:
      platform: gcp
      format: bigquery_table
      location:
        project: my-project-id
        dataset: analytics
        table: customers
    policy:
      classification: Confidential
      authn: iam
      privacy:
        masking:
          - column: email
            strategy: partial      # user@example.com → u***@e***.com
          - column: credit_card
            strategy: hash         # One-way hash
            params:
              algorithm: SHA256
    contract:
      schema:
        - name: email
          type: STRING
          sensitivity: pii
        - name: credit_card
          type: STRING
          sensitivity: pii
```

### Access Control

Define granular permissions with the root-level `accessPolicy` block. Forge
compiles `accessPolicy.grants` into IAM bindings:

```yaml
accessPolicy:
  grants:
    - principal: "group:data-analysts@company.com"
      permissions: [read, select]
    - principal: "user:analyst@company.com"
      permissions: [read, select]
    - principal: "serviceAccount:etl@project.iam.gserviceaccount.com"
      permissions: [write, insert, update]
      resources:
        - customers
    - principal: "user:data-admin@company.com"
      permissions: [read, write, create]
```

> Note: dataset/table-level OWNER roles and domain-wide grants map to GCP IAM
> roles applied outside the contract. Use `resources` on a grant to scope a
> principal to a specific expose.

---

## Loading Data

### From Cloud Storage

Load from GCS with a `builds[]` entry that produces the table:

```yaml
builds:
  - id: build_sales
    pattern: acquisition
    engine: sql
    properties:
      source_uri: gs://my-bucket/data/*.csv
      source_format: CSV
      skip_leading_rows: 1
    outputs:
      - sales

exposes:
  - exposeId: sales
    kind: table
    binding:
      platform: gcp
      format: bigquery_table
      location:
        project: my-project-id
        dataset: analytics
        table: sales
    contract:
      schema:
        - name: order_id
          type: STRING
          required: true
```

### From Local Files

```bash
# Use bq CLI for one-time loads
bq load \
  --source_format=CSV \
  --skip_leading_rows=1 \
  my_dataset.my_table \
  data/file.csv
```

### Streaming Inserts

```python
from google.cloud import bigquery

client = bigquery.Client()
table_id = "project.dataset.table"

rows = [
    {"name": "Alice", "age": 30},
    {"name": "Bob", "age": 25}
]

errors = client.insert_rows_json(table_id, rows)
if not errors:
    print("Rows inserted successfully")
```

---

## Cost Optimization

### Query Optimization

```sql
-- ❌ BAD: Scans entire table
SELECT * FROM `project.dataset.events`
WHERE DATE(event_time) = '2026-01-20'

-- ✅ GOOD: Uses partition filter
SELECT * FROM `project.dataset.events`
WHERE event_time >= '2026-01-20'
  AND event_time < '2026-01-21'
```

### Storage Classes

Expose a GCS dataset as a `file` binding. Bucket-specific options such as
storage class and lifecycle rules are provider-specific keys under
`binding.properties`:

```yaml
exposes:
  - exposeId: analytics_archive
    kind: file
    binding:
      platform: gcp
      format: gcs_file
      location:
        bucket: analytics-archive
        path: archive/
      properties:
        storage_class: NEARLINE   # For infrequent access
        lifecycle:
          - action: SetStorageClass
            storage_class: COLDLINE
            age_days: 90          # Move to coldline after 90 days
          - action: Delete
            age_days: 365         # Delete after 1 year
    contract:
      schema:
        - name: record_id
          type: STRING
          required: true
```

### Cost Monitoring

```bash
# Check current month costs
bq query --use_legacy_sql=false \
  'SELECT 
    SUM(total_bytes_processed) / POW(10, 12) as tb_processed,
    SUM(total_bytes_processed) / POW(10, 12) * 5 as estimated_cost_usd
  FROM `region-us`.INFORMATION_SCHEMA.JOBS
  WHERE DATE(creation_time) >= DATE_TRUNC(CURRENT_DATE(), MONTH)'
```

---

## Advanced Features

### BigQuery ML

Train models directly in BigQuery. The training SQL lives in a `builds[]`
entry; expose the trained model with `kind: model`:

```yaml
builds:
  - id: build_churn_model
    pattern: embedded-logic
    engine: sql
    properties:
      sql: |
        CREATE OR REPLACE MODEL `${project}.${dataset}.churn_model`
        OPTIONS(
          model_type='LOGISTIC_REG',
          input_label_cols=['churned']
        ) AS
        SELECT
          * EXCEPT(customer_id)
        FROM `${project}.${dataset}.customer_features`
    outputs:
      - churn_prediction_model

exposes:
  - exposeId: churn_prediction_model
    kind: model
    binding:
      platform: gcp
      format: bigquery_table
      location:
        project: my-project-id
        dataset: ml
        table: churn_model
    contract:
      schema:
        - name: predicted_churned
          type: BOOLEAN
```

### Authorized Views

Share data without granting direct access. Expose the view with `kind: view`
and produce it with a `builds[]` query:

```yaml
builds:
  - id: build_public_customer_summary
    pattern: embedded-logic
    engine: sql
    properties:
      sql: |
        SELECT
          customer_id,
          total_purchases,
          avg_order_value
          -- Excludes PII like email, name
        FROM `${project}.${dataset}.customers`
    outputs:
      - public_customer_summary

exposes:
  - exposeId: public_customer_summary
    kind: view
    binding:
      platform: gcp
      format: bigquery_table
      location:
        project: my-project-id
        dataset: analytics
        table: public_customer_summary
      properties:
        authorized: true   # Can access source tables the caller can't see
    contract:
      schema:
        - name: customer_id
          type: STRING
          required: true
        - name: total_purchases
          type: INTEGER
        - name: avg_order_value
          type: NUMERIC
```

---

## Monitoring

### Built-in Metrics

Declare metrics and alert channels per expose with the `observability` block:

```yaml
exposes:
  - exposeId: events
    kind: table
    binding:
      platform: gcp
      format: bigquery_table
      location:
        project: my-project-id
        dataset: analytics
        table: events
    observability:
      metrics:
        - name: query_performance
          source: bigquery
          sli: latency
      alert:
        channels:
          - slack://data-team
    contract:
      schema:
        - name: event_id
          type: STRING
          required: true
```

> Note: the contract `observability` block declares named metrics and alert
> channels, not arbitrary SQL. Custom cost queries against
> `INFORMATION_SCHEMA.JOBS_BY_PROJECT` and numeric breach thresholds have no
> contract-schema equivalent — run them as scheduled BigQuery jobs outside the
> contract.

---

## Troubleshooting

### "Access Denied" Errors

Grant yourself BigQuery Admin:
```bash
gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="user:YOUR_EMAIL" \
  --role="roles/bigquery.admin"
```

### "Quota Exceeded"

Request quota increase:
```bash
gcloud services quota list \
  --service=bigquery.googleapis.com \
  --consumer="projects/PROJECT_ID"
```

### Slow Queries

Enable query plan visualization:
```sql
-- Add to query
OPTIONS(use_query_cache=false)

-- View execution plan
SELECT * FROM `region-us`.INFORMATION_SCHEMA.JOBS_BY_PROJECT
WHERE job_id = 'YOUR_JOB_ID'
```

---

## Limitations

- **Max dataset size:** Unlimited
- **Max table size:** 10 TB (contact support for larger)
- **Max query size:** 100 KB SQL text
- **Max columns:** 10,000 per table
- **Max concurrent queries:** 100 (can be increased)
- **Query timeout:** 6 hours (distributed queries)

---

## Roadmap

### Q2 2026
- 🔜 Row-Level Security (RLS) policies
- 🔜 Dataflow integration
- 🔜 Cloud Composer orchestration
- 🔜 VPC Service Controls
- 🔜 BigQuery policy tags / column-level taxonomies
- 🔜 BigQuery dynamic data masking

### Q3 2026
- 🔜 BigQuery Omni (multi-cloud)
- 🔜 Data transfer service automation
- 🔜 Advanced BI Engine features
- 🔜 Cross-project analytics

---

## Next Steps

- **[Getting Started](/forge_docs/getting-started/)** - First GCP deployment
- **[GCP Walkthrough](/forge_docs/walkthrough/gcp)** - Hands-on tutorial  
- **[CLI Reference](/forge_docs/cli/)** - GCP-specific commands
- **[Governance Guide](/forge_docs/advanced/governance)** - Security deep-dive

---

*GCP Provider maintained by the Fluid Forge core team*
