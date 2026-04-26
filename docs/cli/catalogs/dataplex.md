# Google Dataplex Catalog

Source-side catalog adapter for **Google Dataplex** — Google Cloud's
universal metadata catalog. Wraps three Dataplex SDK clients
(catalog, lineage, glossary) so one adapter call materialises all
three signal sources.

> **Recommended for:** GCP-native teams using Dataplex for governance.
> Pairs with [BigQuery](bigquery.md) for richer warehouse metadata
> + Dataplex's aspect-types (data-quality scores, freshness SLAs)
> and business glossary.

## Install

```bash
pip install "data-product-forge[gcp]"
```

Same extra as BigQuery — installs `google-cloud-dataplex` and
`google-cloud-bigquery` together.

## Privileges to grant

The adapter is **read-only on metadata**.

```bash
# Required: read entries (tables) from any registered entry-group.
gcloud projects add-iam-policy-binding my-proj \
  --member="user:analyst@example.com" \
  --role="roles/dataplex.metadataReader"

# Optional: read lineage links.
gcloud projects add-iam-policy-binding my-proj \
  --member="user:analyst@example.com" \
  --role="roles/datalineage.viewer"

# Optional: read business glossary.
gcloud projects add-iam-policy-binding my-proj \
  --member="user:analyst@example.com" \
  --role="roles/dataplex.glossaryReader"
```

If lineage / glossary roles are missing, the adapter soft-fails on
those reads (forge still works).

## Authentication methods

Same as BigQuery — Dataplex uses the same Google auth stack.

| Method | When to use | Setup |
|---|---|---|
| **`adc`** ★ | Default | `gcloud auth application-default login`. |
| `service_account_json` | CI | Path to SA JSON key file. |
| `service_account_email` | GKE / Cloud Run | Email of workload-identity SA. |

## Setup

```bash
fluid ai setup --source dataplex --name dataplex-prod
# ? Catalog: dataplex
# ? Project: my-proj
# ? Location: EU                   (or US, asia-northeast1, ...)
# ? Auth method:
#   ★ adc (recommended)
#     service_account_json
#     service_account_email
# ? Default entry-group: @bigquery (default; matches BQ-imported entries)
# ✓ Saved to ~/.fluid/sources.yaml
```

## Three-client construction

When the adapter constructs SDK clients, it materialises all three
at once (catalog / lineage / glossary). They're cached on the
adapter instance — second call returns the cached dict. This pattern
keeps the construction code in one place; per-call lifecycle is
managed by `fluid mcp serve` (server exits when stdin closes; no
long-lived state).

## End-to-end demo

```bash
fluid ai setup --source dataplex --name dataplex-prod

# Use the default entry group (@bigquery — covers all BQ tables).
fluid forge data-model from-source \
  --source dataplex \
  --credential-id dataplex-prod \
  --database my-proj --schema analytics \
  --technique data-vault-2 \
  -o analytics.fluid.yaml

# Or scope by an explicit entry group:
fluid forge data-model from-source \
  --source dataplex \
  --credential-id dataplex-prod \
  --catalog '@custom-entry-group' \
  --database my-proj \
  -o custom.fluid.yaml
```

## What lands where

| Dataplex source | Forge output |
|---|---|
| Entry `displayName` | `OSIDataset.fields[].expression.description` |
| Entry description | `OSIDataset.fields[].expression.description` |
| Entry `aspect_types[].record` (DQ scores, freshness SLA) | `dataQuality.slas[]` (Fluid contract) |
| Glossary terms | `OSI.ai_context.synonyms` + `examples` |
| Lineage links | `metadata.lineage.upstream[]` + DV2 link inference |
| Aspect type `governance.classification` | `agentPolicy.sensitiveData[]` |

## Soft-fail on optional reads

If the lineage API isn't enabled on the project, or the glossary
read role is missing, the adapter returns empty results for those
reads instead of erroring. The whole forge isn't blocked — you get
a working contract, just without lineage / glossary signal.

```bash
# Enable lineage + glossary explicitly:
gcloud services enable datalineage.googleapis.com dataplex.googleapis.com
```

## Common errors

### `CatalogConfigError: google-cloud-dataplex missing`
Run `pip install "data-product-forge[gcp]"`.

### `CatalogPermissionError: roles/dataplex.metadataReader required`
Suggestion list contains the IAM binding command.

### Glossary terms come back empty
Likely no glossary configured in the project, or missing
`roles/dataplex.glossaryReader`. Adapter soft-fails — forge still
works.

### Lineage entries come back empty
Likely the Lineage API isn't enabled on the project, or the
`roles/datalineage.viewer` role is missing. Adapter soft-fails.

## See also

- [Catalog index](README.md)
- [BigQuery catalog](bigquery.md) — pairs with Dataplex
- [GCP provider page](../../providers/gcp.md)
