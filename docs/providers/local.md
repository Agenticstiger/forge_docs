# Local Provider

**Status:** ✅ Production Ready  
**Version:** 1.0.0  
**Database:** DuckDB, SQLite

---

## Overview

The Local provider enables rapid development and testing without cloud costs. Perfect for:

- 📚 Learning Fluid Forge
- 🧪 Testing contracts before cloud deployment
- 💻 Local data analysis with DuckDB
- 🔬 CI/CD testing pipelines

---

## Quick Start

### Installation

```bash
pip install fluid-forge duckdb
```

### Minimal Contract

```yaml
metadata:
  name: local-analytics
  version: 1.0.0

platform:
  provider: local
  database_path: ./analytics.duckdb
  schema: main

assets:
  - type: table
    name: customers
    
    query: |
      SELECT * FROM read_csv_auto('./data/customers.csv')
```

**Execute:**

```bash
fluid apply contract.yaml --provider local
```

---

## Supported Features

### ✅ DuckDB Features

| Feature | Support | Notes |
|---------|---------|-------|
| Tables | ✅ Full | CREATE TABLE, materialized |
| Views | ✅ Full | Standard SQL views |
| CSV/Parquet Loading | ✅ Full | Auto-schema detection |
| SQL Transformations | ✅ Full | Full SQL:2016 support |
| Indexes | ✅ Full | B-tree, ART indexes |
| CTEs & Window Functions | ✅ Full | Advanced SQL |
| JSON/Arrays | ✅ Full | Nested data structures |

### ⏳ Limitations

- ❌ No IAM/authentication (local only)
- ❌ No partitioning (not needed for small data)
- ❌ No distributed queries
- ⚠️ Limited to single machine memory

---

## Configuration

```yaml
platform:
  provider: local
  
  # Database file path
  database_path: ./my_database.duckdb
  
  # Optional schema name
  schema: analytics  # Default: main
  
  # DuckDB settings
  settings:
    memory_limit: 4GB
    threads: 4
    temp_directory: /tmp/duckdb
```

---

## Use Cases

### 1. Development & Testing

Develop contracts locally, then deploy to cloud:

```bash
# Test locally
fluid apply contract.yaml --provider local

# Deploy to GCP when ready
fluid apply contract.yaml --provider gcp --project my-project
```

### 2. Data Analysis

Analyze local CSV/Parquet files:

```yaml
sources:
  - name: sales_data
    type: csv
    path: ./data/sales_*.csv

assets:
  - type: view
    name: monthly_revenue
    query: |
      SELECT 
        DATE_TRUNC('month', sale_date) as month,
        SUM(amount) as revenue
      FROM read_csv_auto('${sources.sales_data.path}')
      GROUP BY month
```

### 3. CI/CD Testing

Test contracts in GitHub Actions:

```yaml
# .github/workflows/test.yml
- name: Test Fluid Contract
  run: |
    fluid apply contract.yaml --provider local
    fluid verify contract.yaml --provider local
```

---

## Performance Tips

### 1. Use Parquet Instead of CSV

```yaml
sources:
  - name: large_dataset
    type: parquet  # 10x faster than CSV
    path: ./data/events.parquet
```

### 2. Create Indexes

```yaml
tables:
  - name: customers
    indexes:
      - columns: [customer_id]
        unique: true
      - columns: [country, signup_date]
```

### 3. Optimize Memory

```yaml
platform:
  provider: local
  settings:
    memory_limit: 8GB  # Increase for large datasets
    max_memory: 80%    # Use up to 80% of available RAM
```

---

## Example Workflows

### Load and Transform CSVs

```yaml
metadata:
  name: csv-pipeline
  version: 1.0.0

platform:
  provider: local
  database_path: ./analytics.duckdb

sources:
  - name: customers
    type: csv
    path: ./raw/customers.csv
  
  - name: orders
    type: csv
    path: ./raw/orders.csv

assets:
  - type: table
    name: customer_orders
    materialized: true
    
    query: |
      SELECT 
        c.customer_id,
        c.name,
        c.email,
        COUNT(o.order_id) as total_orders,
        SUM(o.amount) as total_spent
      FROM read_csv_auto('${sources.customers.path}') c
      LEFT JOIN read_csv_auto('${sources.orders.path}') o
        ON c.customer_id = o.customer_id
      GROUP BY c.customer_id, c.name, c.email
```

### Parquet Data Lake

```yaml
platform:
  provider: local
  database_path: ./data_lake.duckdb

sources:
  - name: events
    type: parquet
    path: ./lake/events/**/*.parquet  # Wildcard glob

assets:
  - type: view
    name: daily_events
    query: |
      SELECT 
        DATE(event_time) as date,
        event_type,
        COUNT(*) as event_count
      FROM read_parquet('${sources.events.path}')
      WHERE event_time >= CURRENT_DATE - INTERVAL '7 days'
      GROUP BY date, event_type
```

---

## Querying Results

### Python

```python
import duckdb

conn = duckdb.connect('analytics.duckdb')

# Query data
df = conn.execute("""
    SELECT * FROM main.customers
    WHERE total_spent > 1000
""").fetchdf()

print(df.head())
conn.close()
```

### DuckDB CLI

```bash
duckdb analytics.duckdb

-- Interactive SQL
SELECT * FROM main.customers LIMIT 10;

-- Export to CSV
COPY (SELECT * FROM main.customer_summary) 
TO 'export.csv' WITH (HEADER, DELIMITER ',');

-- Export to Parquet
COPY main.customer_summary TO 'export.parquet';
```

---

## Cloud Migration

When ready to move to production:

**1. Update contract:**

```yaml
# Change provider from 'local' to 'gcp'
platform:
  provider: gcp  # Changed!
  project: my-project-id
  region: us-central1

# Rest stays the same!
assets:
  - type: dataset
    name: analytics
    # ... same tables and views
```

**2. Deploy:**

```bash
fluid apply contract.yaml --provider gcp
```

**That's it!** Your local development becomes cloud production.

---

## Next Steps

- **[Local Walkthrough](/walkthrough/local)** - Complete tutorial
- **[GCP Walkthrough](/walkthrough/gcp)** - Migrate to cloud
- **[CLI Reference](/cli/)** - Local provider commands

---

*Perfect for development. Deploy to GCP when ready.*
