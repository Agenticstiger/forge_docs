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

::: tip "Production" scopes the plan/apply core, not every sub-feature
The "✅ Production" / GA status above refers to the provisioning core (plan/apply via OpenTofu,
code generation, standards export). Fine-grained **governance** does not have parity across the
three clouds: AWS Lake Formation is supported; Snowflake masking / row-access policies are Beta
(created but not yet attached); and GCP fine-grained controls (RLS, policy tags, data masking,
VPC-SC) are roadmap, not shipped. See each provider page for the current governance surface.
:::

---

## AWS Provider

**Status:** ✅ Production Ready (GA since CLI v0.8.0)

### Infrastructure Deployment (Available Now)

`fluid apply` compiles the contract to OpenTofu (`main.tf.json`) and runs `tofu` — the older
per-service "action handler" code has been retired in favour of this model. Resources emitted
by the AWS IaC plugin include:

- ✅ Amazon S3 — Buckets, versioning, tags, cross-account bucket policy
- ✅ AWS Glue — Data catalog databases and tables (with column comments / table parameters)
- ✅ AWS Lake Formation — Admins, LF-tags (TBAC), location registration, principal/column grants, row filters
- ✅ AWS IAM — Role and policy bindings from `accessPolicy`

> Other AWS services may be reachable through the IaC layer, but they are no longer modelled as
> discrete "service action handlers". `fluid generate iac <contract>` shows exactly what is emitted.

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
- Valid Python syntax
- Error handling and retries
- Logging and monitoring integration
- Resource cleanup and rollback

---

## Snowflake Provider

**Status:** ✅ Production Ready (GA since CLI v0.8.0)

### Infrastructure Deployment (Available Now)

Full plan/apply lifecycle. The Snowflake IaC plugin emits:

- ✅ Databases & Schemas — Lifecycle management
- ✅ Tables & Views — DDL with clustering
- ✅ Streams & Tasks — CDC streams and scheduled tasks
- ✅ Procedures & Functions — Stored procedures and UDFs
- ✅ RBAC Grants — `GRANT ... TO ROLE` from the contract
- 🧪 Masking & Row-Access policies — policy objects created, not yet attached (Beta)

> Snowpipe, Snowpark, and Data Sharing are **not yet** emitted by the Snowflake plugin — see
> the [Snowflake provider page](/forge_docs/providers/snowflake) for the current surface.

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
- ✅ Table and view creation with clustering
- ✅ Streams, tasks, procedures, and functions
- ✅ RBAC grants from the contract

---

## GCP Provider

**Status:** ✅ Production Ready (GA since CLI v0.8.0)

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

### ODPS (Open Data Product Specification)

**Status:** ✅ Available Now

```bash
fluid export-odps contract.yaml --out catalog/
fluid odps validate catalog/product.yaml
```

### ODCS (Open Data Contract Standard)

**Status:** ✅ Available Now

```bash
fluid odcs export contract.yaml -o contracts/
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
fluidVersion: "0.7.3"
kind: DataProduct
id: analytics.multi_cloud_analytics
name: Multi-Cloud Analytics

metadata:
  layer: Gold
  owner:
    team: data-engineering
    email: data-engineering@company.com

exposes:
  - exposeId: analytics
    kind: table
    title: Multi-Cloud Analytics Table
    version: "1.0.0"

    binding:
      platform: gcp                # or aws, snowflake
      format: bigquery_table       # provider-specific format
      location:
        project: my-project
        dataset: analytics
        table: analytics

    contract:
      schema:
        - name: id
          type: STRING
          required: true
```

The same contract structure works across GCP, AWS, and Snowflake — just change `binding.platform` (and the matching `binding.format` / `binding.location`).

---

## Request a Provider

Vote for providers or request new ones:

- 🗳️ [Provider Feature Requests](https://github.com/Agenticstiger/forge-cli/issues?q=is%3Aissue+is%3Aopen+label%3Aprovider)
- 💬 [GitHub Discussions](https://github.com/Agenticstiger/forge-cli/discussions)
- 📋 [Open a provider request issue](https://github.com/Agenticstiger/forge-cli/issues/new?labels=provider-request)

---

## Next Steps

**Available Now:**
- **[GCP Provider](/forge_docs/providers/gcp)** - Production ready
- **[Local Provider](/forge_docs/providers/local)** - Development & testing

**Get Started:**
- **[GCP Walkthrough](/forge_docs/walkthrough/gcp)** - Deploy to Google Cloud
- **[Local Walkthrough](/forge_docs/walkthrough/local)** - Try it locally first

---

*Building the future of declarative data infrastructure, one provider at a time.*
