# Provider Roadmap

## Current Status

| Provider | Plan / Apply | Code Generation | Data Catalog | Availability |
|----------|-------------|-----------------|--------------|--------------|  
| **GCP** | ✅ Production | ✅ Airflow, Dagster, Prefect | ✅ ODPS, ODCS | Available Now |
| **AWS** | ✅ Production | ✅ Airflow, Dagster, Prefect | ✅ ODPS, ODCS | Available Now |
| **Snowflake** | ✅ Production | ✅ Airflow, Dagster, Prefect | ✅ ODPS, ODCS | Available Now |
| **Local (DuckDB)** | ✅ Production | N/A | N/A | Available Now |
| **ODPS** | ✅ Production | N/A | ✅ Export | Available Now |
| **ODCS** | ✅ Production | N/A | ✅ Export | Available Now |
| **Datamesh Manager** | ✅ Production | N/A | ✅ Catalog | Available Now |
| **Azure** | 🔜 Planned | 🔜 Planned | 🔜 Planned | Q3 2026 |
| **Databricks** | 🔜 Planned | 🔜 Planned | 🔜 Planned | Q4 2026 |

**Legend:**
- **Plan / Apply**: `fluid plan` + `fluid apply` — Deploy actual cloud resources
- **Code Generation**: `fluid generate-airflow` / `fluid export` — Generate orchestration code
- **Data Catalog**: `fluid odps` / `fluid odcs` — Export to open data standards

---

## AWS Provider

**Status:** ✅ Production Ready (v0.7.1)

### Infrastructure Deployment (Available Now)

Full plan/apply lifecycle with 13 service action handlers:

- ✅ Amazon S3 — Bucket creation, versioning, tags
- ✅ AWS Glue — Data catalog, databases, tables
- ✅ Amazon Athena — Query execution
- ✅ Amazon Redshift — Data warehouse operations
- ✅ AWS Lambda — Functions, event source mappings, triggers
- ✅ Amazon EventBridge — Scheduled rules
- ✅ AWS Step Functions — Workflow orchestration
- ✅ Amazon SNS — Notifications
- ✅ Amazon SQS — Message queues
- ✅ Amazon Kinesis — Streaming
- ✅ Amazon CloudWatch — Monitoring
- ✅ AWS Secrets Manager — Secret management
- ✅ AWS IAM — Role and policy automation

### Code Generation (Available Now)

Generate production-ready orchestration code:

```bash
# Generate Airflow DAG
fluid generate-airflow aws-contract.yaml -o dags/aws_pipeline.py

# With verbose output
```bash
# Airflow
fluid generate-airflow aws-contract.yaml -o dags/pipeline.py --verbose

# Dagster
fluid export aws-contract.yaml --engine dagster -o pipelines/

# Prefect
fluid export aws-contract.yaml --engine prefect -o flows/
```

**Generated Code Quality:**
- Valid Python syntax (100% compilation success)
- Proper error handling and retries
- Logging and monitoring integration
- Resource cleanup and rollback

---

## Snowflake Provider

**Status:** ✅ Production Ready (v0.7.1)

### Infrastructure Deployment (Available Now)

Full plan/apply lifecycle:

- ✅ Virtual Warehouses — Compute provisioning
- ✅ Databases & Schemas — Lifecycle management
- ✅ Tables & Views — DDL with clustering
- ✅ Snowpipe — Streaming ingestion
- ✅ Snowpark — Python in Snowflake
- ✅ Data Sharing — Cross-account access

### Code Generation (Available Now)

```bash
# Airflow
fluid generate-airflow snowflake-contract.yaml -o dags/snowflake_pipeline.py

# Dagster
fluid export snowflake-contract.yaml --engine dagster -o pipelines/

# With environment overlay
fluid generate-airflow snowflake-contract.yaml --env prod -o dags/prod_pipeline.py
```

**Supported Operations:**
- ✅ Database and schema creation
- ✅ Table creation with clustering
- ✅ SQL query execution
- ✅ Data loading from S3/GCS
- ✅ Warehouse management

---

## GCP Provider

**Status:** ✅ Production Ready (v0.7.1)

The flagship provider with the most mature implementation:

- ✅ BigQuery — Datasets, tables, views, routines
- ✅ Cloud Storage — Buckets and objects
- ✅ Pub/Sub — Topics and subscriptions
- ✅ Cloud Functions — Serverless compute
- ✅ Cloud Composer — Managed Airflow
- ✅ Dataflow — Streaming and batch
- ✅ IAM — Automated role bindings

### Code Generation

```bash
# All three engines supported
fluid generate-airflow gcp-contract.yaml -o dags/pipeline.py
fluid export gcp-contract.yaml --engine dagster -o pipelines/
fluid export gcp-contract.yaml --engine prefect -o flows/
```

---

## Data Catalog Providers

### ODPS (Open Data Product Standard)

**Status:** ✅ Available Now

```bash
fluid export-odps contract.yaml -o catalog/
fluid odps validate catalog/product.yaml
```

### ODCS (Open Data Contract Standard)

**Status:** ✅ Available Now

```bash
fluid export-odcs contract.yaml -o contracts/
fluid odcs validate contracts/contract.yaml
```

### Datamesh Manager

**Status:** ✅ Available Now

```bash
fluid market list
fluid publish contract.yaml
```

---

## Planned Providers

### Azure (Q3 2026)

**Target Services:**

- Azure Data Lake Gen2 — Storage
- Azure Synapse Analytics — Warehouse
- Azure Databricks — Spark platform
- Azure Functions — Serverless compute
- Azure Data Factory — Orchestration

### Databricks (Q4 2026)

**Target Services:**

- Databricks SQL — Analytics
- Delta Lake — Storage format
- MLflow — ML lifecycle
- Unity Catalog — Governance

---

## Community Providers

Want a provider not on the roadmap? **Contribute!**

Fluid Forge is designed for extensibility. Community providers welcome for:

- Apache Iceberg
- Apache Hudi
- ClickHouse
- Trino/Presto
- PostgreSQL
- MySQL/MariaDB

**How to contribute:**

1. Implement `BaseProvider` interface
2. Add provider-specific actions
3. Write tests
4. Submit PR!

---

## Multi-Cloud Features

### Cross-Cloud Data Products

Deploy the same contract to multiple clouds:

```yaml
fluidVersion: "0.7"
kind: DataProduct
exposeId: multi-cloud-analytics

binding:
  provider: gcp          # or aws, snowflake
  project: my-project

exposes:
  - type: dataset
    name: analytics
```

The same contract structure works across GCP, AWS, and Snowflake — just change the `binding.provider` field.

---

## Request a Provider

Vote for providers or request new ones:

- 🗳️ [Provider Feature Requests](https://github.com/Agenticstiger/forge-cli/issues?q=is%3Aissue+is%3Aopen+label%3Aprovider)
- 💬 [Discord Discussion](https://github.com/Agenticstiger/forge-cli/discussions)
- 📧 Email: https://github.com/Agenticstiger/forge-cli/issues/new?labels=provider-request

---

## Next Steps

**Available Now:**
- **[GCP Provider](/providers/gcp)** - Production ready
- **[Local Provider](/providers/local)** - Development & testing

**Get Started:**
- **[GCP Walkthrough](/walkthrough/gcp)** - Deploy to Google Cloud
- **[Local Walkthrough](/walkthrough/local)** - Try it locally first

---

*Building the future of declarative data infrastructure, one provider at a time.*
