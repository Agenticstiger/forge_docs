# GCP Provider

**Status:** ✅ Production Ready  
**Docs Baseline:** CLI `0.8.0`<br>
**Services:** BigQuery, Cloud Storage, IAM, Cloud Run, Pub/Sub

::: warning Compatibility note
This page preserves some older examples for compatibility context. Current scaffolds emit `fluidVersion: 0.7.2`, and orchestration docs now prefer `fluid generate schedule --scheduler airflow`.
:::

---

## Overview

The Google Cloud Platform provider is the flagship Fluid Forge implementation, offering production-grade support for BigQuery, Cloud Storage, and comprehensive GCP services.

### Why GCP?

- **Serverless Analytics** - BigQuery eliminates infrastructure management
- **Cost-Effective** - Pay-per-query pricing with generous free tier
- **Enterprise Scale** - Petabyte-scale analytics out of the box
- **ML Integration** - Native BigQuery ML and Vertex AI
- **Security Built-In** - Column-level security, data masking, audit logs

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
fluidVersion: "0.7"
kind: DataProduct
exposeId: my-data-product

binding:
  provider: gcp
  project: my-project-id
  region: us-central1

exposes:
  - type: dataset
    name: analytics
    
    tables:
      - name: customers
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
| Policy Tags | ✅ Full | Column-level security (Phase 1-3) |
| Data Masking | ✅ Full | Dynamic data masking |
| Row-Level Security | 🔜 Q2 2026 | RLS policies |

### ✅ Cloud Storage

| Feature | Support | Notes |
|---------|---------|-------|
| Buckets | ✅ Full | Multi-region, versioning |
| Objects | ✅ Full | Upload, download, lifecycle |
| Lifecycle Policies | ✅ Full | Auto-delete, archival |
| Signed URLs | ✅ Full | Temporary access |
| Notifications | ✅ Full | Pub/Sub integration |

### ✅ Airflow DAG Generation (v0.7.1)

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

**Performance:**
- Average generation time: 0.8-2ms
- Average output size: 2-10KB
- Test coverage: 100% (all provider tests passing)

### ✅ IAM & Security

| Feature | Support | Notes |
|---------|---------|-------|
| Service Accounts | ✅ Full | Auto-creation, key management |
| IAM Bindings | ✅ Full | Least-privilege access |
| Policy Tags | ✅ Full | Taxonomy management |
| Audit Logs | ✅ Full | Admin, data access logs |
| VPC Service Controls | 🔜 Q2 2026 | Network isolation |

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

```yaml
platform:
  provider: gcp
  
  # Required
  project: my-project-id
  region: us-central1
  
  # Optional
  location: US  # BigQuery multi-region (US, EU)
  zone: us-central1-a  # Specific zone for compute
  
  # Cost controls
  cost_controls:
    enable_bi_engine: true  # Query acceleration
    bi_engine_gb: 10  # BI Engine cache size
    default_table_expiration_days: 365
    max_bytes_billed: 10000000000  # 10 GB query limit
  
  # Networking
  network:
    vpc: default
    subnet: default
    private_google_access: true
  
  # Labels (applied to all resources)
  labels:
    environment: production
    team: data-engineering
    cost-center: analytics
```

---

## BigQuery Best Practices

### Partitioning

Partition tables by date for performance and cost savings:

```yaml
tables:
  - name: events
    partitioning:
      field: event_timestamp
      type: DAY  # or HOUR, MONTH, YEAR
      require_partition_filter: true  # Enforce partitioned queries
      expiration_days: 90  # Auto-delete old partitions
```

**Cost savings:** Up to 90% reduction for time-based queries

### Clustering

Cluster columns for better query performance:

```yaml
tables:
  - name: events
    clustering:
      fields: [user_id, event_type, country]  # Max 4 fields
```

**Performance:** Up to 10x faster queries on clustered columns

### Materialized Views

Pre-compute aggregations:

```yaml
tables:
  - name: daily_metrics
    materialized: true
    
    query: |
      SELECT 
        DATE(event_timestamp) as date,
        user_id,
        COUNT(*) as event_count,
        SUM(revenue) as total_revenue
      FROM `${project}.events.raw_events`
      GROUP BY date, user_id
    
    # Refresh settings
    refresh:
      enabled: true
      interval_minutes: 60  # Refresh hourly
```

**Benefit:** Sub-second queries on complex aggregations

---

## Security & Governance

### Column-Level Security

Protect sensitive data with policy tags:

```yaml
governance:
  policy_tags:
    - taxonomy: data_classification
      tags:
        - name: PII
          description: Personally Identifiable Information
          columns: [email, phone, ssn]
        
        - name: Financial
          description: Financial data
          columns: [salary, credit_card]

tables:
  - name: customers
    schema:
      - name: email
        type: STRING
        policy_tag: PII  # Restricted access
      
      - name: name
        type: STRING  # No policy tag = public
```

**IAM Integration:**
```bash
# Grant access to PII data
gcloud data-catalog taxonomies add-iam-policy-binding \
  data_classification \
  --member="user:analyst@company.com" \
  --role="roles/datacatalog.categoryFineGrainedReader"
```

### Data Masking

Automatically mask sensitive data:

```yaml
governance:
  data_masking:
    - column: email
      masking_type: DEFAULT  # user@example.com → u***@e***.com
      policy_tag: PII
    
    - column: credit_card
      masking_type: SHA256  # One-way hash
      policy_tag: Financial
```

### Access Control

Define granular permissions:

```yaml
access:
  dataset_access:
    - role: READER
      members:
        - user:analyst@company.com
        - group:data-analysts@company.com
        - domain:company.com  # Everyone in domain
    
    - role: WRITER
      members:
        - serviceAccount:etl@project.iam.gserviceaccount.com
    
    - role: OWNER
      members:
        - user:data-admin@company.com
  
  table_access:
    - table: customers
      role: READER
      members:
        - user:marketing@company.com
```

---

## Loading Data

### From Cloud Storage

```yaml
tables:
  - name: sales
    load_from_gcs:
      uri: gs://my-bucket/data/*.csv
      format: CSV
      schema_auto_detect: true
      skip_leading_rows: 1
      allow_jagged_rows: false
      encoding: UTF-8
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

```yaml
buckets:
  - name: analytics-archive
    storage_class: NEARLINE  # For infrequent access
    
    lifecycle:
      - action: SetStorageClass
        storage_class: COLDLINE
        age_days: 90  # Move to coldline after 90 days
      
      - action: Delete
        age_days: 365  # Delete after 1 year
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

Train models directly in BigQuery:

```yaml
routines:
  - name: churn_prediction_model
    type: ML_MODEL
    
    training_query: |
      CREATE OR REPLACE MODEL `${project}.${dataset}.churn_model`
      OPTIONS(
        model_type='LOGISTIC_REG',
        input_label_cols=['churned']
      ) AS
      SELECT 
        * EXCEPT(customer_id)
      FROM `${project}.${dataset}.customer_features`
```

### Authorized Views

Share data without granting direct access:

```yaml
views:
  - name: public_customer_summary
    authorized: true  # Can access source tables user can't see
    
    authorized_datasets:
      - project: partner-project
        dataset: shared_data
    
    query: |
      SELECT 
        customer_id,
        total_purchases,
        avg_order_value
        -- Excludes PII like email, name
      FROM `${project}.${dataset}.customers`
```

---

## Monitoring

### Built-in Metrics

Fluid Forge automatically exports metrics:

```yaml
monitoring:
  enabled: true
  
  metrics:
    - name: query_performance
      query: |
        SELECT 
          AVG(total_slot_ms) as avg_slot_ms,
          MAX(total_bytes_processed) as max_bytes
        FROM `region-us`.INFORMATION_SCHEMA.JOBS_BY_PROJECT
        WHERE DATE(creation_time) = CURRENT_DATE()
    
  alerts:
    - name: high_query_cost
      condition: max_bytes > 10000000000  # 10 GB
      notification: slack://data-team
```

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
- ✅ Row-Level Security (RLS) policies
- ✅ Dataflow integration
- ✅ Cloud Composer orchestration
- ✅ VPC Service Controls

### Q3 2026
- ✅ BigQuery Omni (multi-cloud)
- ✅ Data transfer service automation
- ✅ Advanced BI Engine features
- ✅ Cross-project analytics

---

## Next Steps

- **[Getting Started](/forge_docs/getting-started/)** - First GCP deployment
- **[GCP Walkthrough](/forge_docs/walkthrough/gcp)** - Hands-on tutorial  
- **[CLI Reference](/forge_docs/cli/)** - GCP-specific commands
- **[Governance Guide](/forge_docs/advanced/governance)** - Security deep-dive

---

*GCP Provider maintained by the Fluid Forge core team*
