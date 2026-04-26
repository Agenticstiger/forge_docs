# BigQuery Catalog

Source-side catalog adapter for **Google BigQuery**. Reads
`INFORMATION_SCHEMA.TABLES`, `.COLUMNS`, `.TABLE_OPTIONS` (description
and labels), `.KEY_COLUMN_USAGE` + `.CONSTRAINT_COLUMN_USAGE` (PK/FK),
and `.PARTITIONS` (partition keys + clustering keys for downstream
dbt config emission).

> **Pairs with [Dataplex](dataplex.md)** for richer metadata
> (aspect-types, business glossary, lineage). Use BigQuery alone
> for projects without Dataplex enabled.

## Install

```bash
pip install "data-product-forge[gcp]"
```

Adds `google-cloud-bigquery` and `google-cloud-dataplex` (one extra
covers both adapters). Default install ships without them.

## Privileges to grant

The adapter is **read-only on metadata**.

```bash
# Grant the project-level role that exposes INFORMATION_SCHEMA reads.
gcloud projects add-iam-policy-binding my-proj \
  --member="user:analyst@example.com" \
  --role="roles/bigquery.metadataViewer"

# (Or, on a single dataset:)
bq update --source-policy 'roles/bigquery.metadataViewer:user:analyst@example.com' \
  my-proj:analytics
```

`metadataViewer` is the minimum — it covers
`INFORMATION_SCHEMA.TABLES/COLUMNS/TABLE_OPTIONS` and
`KEY_COLUMN_USAGE`. No `bigquery.dataViewer` needed (the adapter
never queries data tables).

## Authentication methods

| Method | When to use | Setup |
|---|---|---|
| **`adc`** ★ | Default — Application Default Credentials | `gcloud auth application-default login`; the adapter inherits. |
| `service_account_json` | CI / scripted runs | Path to a service-account JSON key file. |
| `service_account_email` | Workload identity (GKE / Cloud Run) | Email of the workload-identity-bound service account. |

★ `adc` is the recommended path. Works on every workstation that has
`gcloud` installed, no extra config.

## Setup

```bash
fluid ai setup --source bigquery --name bq-prod
# ? Catalog: bigquery
# ? Project: my-proj
# ? Auth method:
#   ★ adc (recommended)
#     service_account_json
#     service_account_email
# ? Default location: US           (or EU, asia-northeast1, ...)
# ? Default dataset:  analytics
# ✓ Saved to ~/.fluid/sources.yaml
```

Or env vars:

```bash
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/sa.json    # only for service_account_json
gcloud auth application-default login                     # for adc
```

## End-to-end demo

```bash
fluid ai setup --source bigquery --name bq-prod

fluid forge data-model from-source \
  --source bigquery \
  --credential-id bq-prod \
  --database my-proj --schema analytics \
  --technique dimensional \
  -o analytics.fluid.yaml

fluid generate transformation analytics.fluid.yaml -o ./dbt_analytics --dbt-validate
```

## What lands where

| BigQuery source | Forge output |
|---|---|
| Table description | `OSIDataset.fields[].expression.description` |
| Column description | `OSIDataset.fields[].expression.description` |
| Primary key | `OSIDataset.primary_key[]` |
| Foreign key | `OSIRelationship[]` |
| Table labels (`domain` etc.) | `metadata.domain` + industry hint |
| Partition column | dbt `partition_by` config in `TransformPlan` |
| Clustering keys | dbt `cluster_by` config |
| Table description (TABLE_OPTIONS) | `metadata.lineage.upstream[]` (when `description` references upstream) |

## Project IDs with hyphens are honored

BigQuery project IDs allow hyphens (e.g. `my-proj`). The adapter's
identifier validator allows hyphens in the project segment but NOT
in dataset / table names (BigQuery rejects them there). Dataset and
table names follow the standard `^[A-Za-z_][A-Za-z0-9_]*$` pattern.

## Common errors

### `CatalogConfigError: google-cloud-bigquery missing`
Run `pip install "data-product-forge[gcp]"`.

### `CatalogPermissionError: bigquery.tables.get denied`
Suggestion list contains the IAM binding command:
```bash
gcloud projects add-iam-policy-binding my-proj \
  --member="user:analyst@example.com" \
  --role="roles/bigquery.metadataViewer"
```

### `CatalogConnectionError: 404 Not found: Dataset my-proj:analytics`
Verify the dataset exists in the configured project's location.
Datasets are location-scoped — a US dataset is invisible from an
EU client unless the location is set correctly.

### Want lineage / glossary / quality scores
Pair with the [Dataplex adapter](dataplex.md) — same project, same
auth, complementary metadata coverage.

## See also

- [Catalog index](README.md)
- [Dataplex catalog](dataplex.md) — semantic + governance overlay
- [GCP provider page](../../providers/gcp.md) — for the publish-target
  side.
