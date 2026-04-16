# Declarative Design Principles - Bitcoin Tracker Example

## Overview

This example demonstrates **declarative, governance-first data product design** using FLUID 0.7.1.

## ✅ What Makes This Declarative

### 1. **Multi-Level Metadata Architecture**

```yaml
# Product level - Business context
labels:
  cost-center: "engineering"
  business-unit: "data-platform"
  data-classification: "public"

# Expose level - Resource tracking
labels:
  cost-allocation: crypto-team
  sla-tier: gold
  data-owner: data-engineering

# Field level - Governance enforcement
- name: price_usd
  sensitivity: none
  semanticType: currency
  tags: [metric, price-data]
  labels:
    unit: "usd"
```

**Why this matters:**
- ✅ Labels propagate automatically to BigQuery tables
- ✅ Enables cost tracking without manual tagging
- ✅ Governance policies enforced at field level
- ✅ Self-documenting schema with business context

---

### 2. **Separation of Concerns**

| Concern | Where Declared | Example |
|---------|---------------|---------|
| **What** (Schema) | `contract.schema` | Field names, types, descriptions |
| **Where** (Platform) | `binding.location` | GCP project, dataset, table |
| **Who** (Access) | `policy.authz` | Reader/writer groups |
| **Why** (Business) | `metadata.businessContext` | Domain, subdomain |
| **How** (Build) | `builds[]` | Python ingestion, dbt transformations |
| **Cost** (FinOps) | `labels` | cost-center, team, allocation |

**Benefits:**
- 🎯 Each concern managed independently
- 🔄 Easy to change platforms without touching business logic
- 📊 Cost tracking separate from technical implementation
- 🔐 Security policies separate from schema definitions

---

### 3. **Semantic Richness**

Every field includes:

```yaml
- name: market_cap_usd
  type: FLOAT64
  required: true
  description: "Total market capitalization in USD"
  sensitivity: none              # Data classification
  semanticType: currency         # Machine-readable type
  businessName: "Market Cap"     # Human-readable name
  tags:
    - metric                     # Discovery/categorization
    - market-data
  labels:
    aggregation: "sum"           # Processing hints
```

**Why this matters:**
- 🤖 Enables automated data quality checks
- 📖 Self-documenting for analysts
- 🔍 Searchable via semantic types
- 🏷️ Organized by business meaning

---

### 4. **Policy as Code**

```yaml
policy:
  classification: Public  # Data sensitivity level
  
  authz:
    readers:
      - group:data-analysts@company.com
      - serviceAccount:airflow@company.iam.gserviceaccount.com
    writers:
      - serviceAccount:ingestion@company.iam.gserviceaccount.com
```

**Declarative benefits:**
- ✅ Version-controlled access policies
- ✅ Clear audit trail (Git history)
- ✅ Automated IAM provisioning
- ✅ No manual role assignments

---

### 5. **Build Pattern Abstraction**

```yaml
builds:
  - id: ingest_bitcoin_prices
    pattern: hybrid-reference    # Declarative pattern
    engine: python               # Execution engine
    repository: ./runtime        # Code location
    properties:
      model: ingest_bitcoin_prices
    
    outputs:
      - bitcoin_prices_table    # Links to exposes[]
```

**Key principles:**
- 📦 **Hybrid-reference pattern**: Code lives externally, referenced declaratively
- 🔗 **Output linkage**: `outputs` connects builds to `exposes`
- 🎛️ **Engine abstraction**: Can swap Python → Spark without changing contract
- 📂 **Repository pattern**: Code and contract separate but linked

---

### 6. **FinOps Integration**

```yaml
# Product-level cost tracking
labels:
  cost-center: "engineering"
  billing-tag: "crypto-analytics"

# Expose-level allocation
labels:
  cost-allocation: crypto-team
  sla-tier: gold
```

**Automated outcomes:**
- 💰 BigQuery tables auto-tagged for cost reports
- 📊 Chargeback to `cost-center: engineering`
- 🎯 Team attribution via `cost-allocation: crypto-team`
- 💹 SLA tracking via `sla-tier: gold`

Query costs by label:
```sql
SELECT 
  REGEXP_EXTRACT(labels, r'cost-center:([^,}]+)') as cost_center,
  SUM(size_bytes) * 0.02 / POW(10,9) as monthly_cost_usd
FROM INFORMATION_SCHEMA.TABLE_OPTIONS
WHERE option_name = 'labels'
GROUP BY cost_center;
```

---

## 🎯 Design Principles Applied

### 1. **Declarative Over Imperative**

❌ **Imperative (bad)**:
```python
# Create table
client.create_table(...)
# Grant access
client.grant_access(...)
# Add labels
client.update_labels(...)
```

✅ **Declarative (good)**:
```yaml
exposes:
  - exposeId: bitcoin_prices_table
    binding: { ... }
    policy: { ... }
    labels: { ... }
```

### 2. **Single Source of Truth**

All metadata lives in one contract:
- ✅ Schema definitions
- ✅ Access policies
- ✅ Cost allocation
- ✅ Data lineage
- ✅ Quality rules
- ✅ Business context

### 3. **Composability**

```yaml
# Reusable patterns
tags:
  - metric          # All numeric fields
  - price-data      # Specific domain
  - time-series     # Processing pattern

labels:
  unit: "usd"       # Standardized attributes
  aggregation: "sum"
```

### 4. **Progressive Enhancement**

Start minimal, add as needed:

```yaml
# v1.0 - Basic schema
schema:
  - name: price_usd
    type: FLOAT64

# v1.1 - Add semantics
  - name: price_usd
    type: FLOAT64
    semanticType: currency

# v1.2 - Add governance
  - name: price_usd
    type: FLOAT64
    semanticType: currency
    sensitivity: none
    tags: [metric, price-data]
```

---

## 📊 Real-World Benefits

### Before (Manual BigQuery)
```python
# 100+ lines of Python
from google.cloud import bigquery

client = bigquery.Client(project="my-project")

schema = [
    bigquery.SchemaField("price_timestamp", "TIMESTAMP", mode="REQUIRED"),
    bigquery.SchemaField("price_usd", "FLOAT64", mode="REQUIRED"),
    # ... 6 more fields
]

table = bigquery.Table(
    "my-project.crypto_data.bitcoin_prices",
    schema=schema
)

table.time_partitioning = bigquery.TimePartitioning(
    type_=bigquery.TimePartitioningType.DAY,
    field="price_timestamp",
    expiration_ms=7776000000  # 90 days
)

table.labels = {
    "environment": "production",
    "cost_center": "engineering"
}

table = client.create_table(table)

# Manual IAM bindings
# Manual monitoring setup
# Manual documentation
```

### After (Declarative FLUID)
```yaml
# 200 lines of YAML - but includes:
# - Full schema with business context
# - Access policies
# - Cost tracking
# - Data quality rules
# - Build orchestration
# - Lineage tracking
# - All metadata

fluidVersion: "0.7.1"
kind: DataProduct
exposes:
  - exposeId: bitcoin_prices_table
    contract: { schema: [...] }
    binding: { ... }
    policy: { ... }
    labels: { ... }
```

**Key differences:**
- ✅ **Version controlled** - Contract in Git
- ✅ **Self-documenting** - Business context included
- ✅ **Reproducible** - `fluid apply` creates identical resources
- ✅ **Validated** - Schema enforced before deployment
- ✅ **Governed** - Policies declared upfront

---

## 🚀 Next Level: Multi-Environment

```yaml
# Base contract
exposes:
  - exposeId: bitcoin_prices_table
    binding:
      platform: gcp
      location:
        project: ${PROJECT_ID}  # Environment variable
        region: ${REGION}

# dev environment
PROJECT_ID=dev-crypto
REGION=us-central1

# prod environment  
PROJECT_ID=prod-crypto
REGION=us-east1
```

Same contract → Multiple environments → Zero code changes!

---

## 📚 Summary

This example is **declarative and sensible** because:

1. ✅ **Complete metadata** at all levels (product/expose/field)
2. ✅ **Separation of concerns** (what/where/who/why/how)
3. ✅ **Policy as code** (access, classification, governance)
4. ✅ **FinOps integration** (cost tracking via labels)
5. ✅ **Build abstraction** (hybrid-reference pattern)
6. ✅ **Semantic richness** (business context + technical spec)
7. ✅ **Single source of truth** (one contract, all metadata)
8. ✅ **Version controlled** (Git-friendly YAML)
9. ✅ **Validated** (schema enforcement)
10. ✅ **Reproducible** (idempotent deployments)

**Result**: A production-ready, governed, cost-tracked data product defined in ~200 lines of YAML instead of 500+ lines of Python/Terraform!
