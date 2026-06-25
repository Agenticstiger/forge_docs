# Local Provider

**Status:** ✅ Production Ready  
**Docs Baseline:** CLI `0.8.11`<br>
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
pip install data-product-forge duckdb
```

### Minimal Contract

```yaml
fluidVersion: "0.7.3"
kind: DataProduct
id: example.local_analytics_v1
name: Local Analytics
domain: example

metadata:
  layer: Bronze
  owner:
    team: data-analytics
    email: team@example.com

builds:
  - id: build_customers
    pattern: embedded-logic
    engine: sql
    properties:
      sql: |
        SELECT * FROM read_csv_auto('./data/customers.csv')
    outputs:
      - customers

exposes:
  - exposeId: customers
    kind: table
    binding:
      platform: local
      format: parquet
      location:
        path: ./runtime/out/customers.parquet
    contract:
      schema:
        - name: customer_id
          type: STRING
          required: true
```

**Execute:**

```bash
fluid apply contract.fluid.yaml --provider local
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

The local provider needs no contract-level configuration block. It is selected at
the command line with `--provider local`, and DuckDB itself is managed for you (an
in-memory database during a run, or a session-scoped file so tables created by one
build are visible to the next).

What you *do* configure per output is the `binding` on each expose — the format and
the path the local provider writes to:

```yaml
exposes:
  - exposeId: customers
    kind: table
    binding:
      platform: local
      format: parquet            # or csv
      location:
        path: ./runtime/out/customers.parquet
    contract:
      schema:
        - name: customer_id
          type: STRING
          required: true
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

Analyze local CSV/Parquet files. Source files are read directly inside the build
SQL with DuckDB's `read_csv_auto` / `read_parquet` functions:

```yaml
builds:
  - id: build_monthly_revenue
    pattern: embedded-logic
    engine: sql
    properties:
      sql: |
        SELECT
          DATE_TRUNC('month', sale_date) as month,
          SUM(amount) as revenue
        FROM read_csv_auto('./data/sales_*.csv')
        GROUP BY month
    outputs:
      - monthly_revenue

exposes:
  - exposeId: monthly_revenue
    kind: view
    binding:
      platform: local
      format: parquet
      location:
        path: ./runtime/out/monthly_revenue.parquet
    contract:
      schema:
        - name: month
          type: TIMESTAMP
        - name: revenue
          type: NUMERIC
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

Read Parquet rather than CSV in your build SQL — it is typically ~10x faster and
carries its own schema:

```yaml
builds:
  - id: build_events
    pattern: embedded-logic
    engine: sql
    properties:
      sql: |
        SELECT * FROM read_parquet('./data/events.parquet')
    outputs:
      - events
```

Pick `format: parquet` on the expose `binding` too, so outputs are written in the
faster format.

### 2. Push Work Into SQL

DuckDB is a columnar engine — filter and aggregate inside the build SQL rather than
post-processing. Project only the columns you need and let `WHERE` / `GROUP BY` run
in the engine.

### 3. Optimize Memory

DuckDB memory and thread settings are managed by the local provider, not declared
in the contract. For large datasets, prefer Parquet inputs and narrow projections so
less data is held in memory at once.

---

## Example Workflows

### Load and Transform CSVs

```yaml
fluidVersion: "0.7.3"
kind: DataProduct
id: example.csv_pipeline_v1
name: CSV Pipeline
domain: example

metadata:
  layer: Silver
  owner:
    team: data-analytics
    email: team@example.com

builds:
  - id: build_customer_orders
    pattern: embedded-logic
    engine: sql
    properties:
      sql: |
        SELECT
          c.customer_id,
          c.name,
          c.email,
          COUNT(o.order_id) as total_orders,
          SUM(o.amount) as total_spent
        FROM read_csv_auto('./raw/customers.csv') c
        LEFT JOIN read_csv_auto('./raw/orders.csv') o
          ON c.customer_id = o.customer_id
        GROUP BY c.customer_id, c.name, c.email
    outputs:
      - customer_orders

exposes:
  - exposeId: customer_orders
    kind: table
    binding:
      platform: local
      format: parquet
      location:
        path: ./runtime/out/customer_orders.parquet
    contract:
      schema:
        - name: customer_id
          type: STRING
          required: true
        - name: name
          type: STRING
        - name: email
          type: STRING
          sensitivity: pii
        - name: total_orders
          type: INTEGER
        - name: total_spent
          type: NUMERIC
```

### Parquet Data Lake

```yaml
fluidVersion: "0.7.3"
kind: DataProduct
id: example.data_lake_v1
name: Data Lake Events
domain: example

metadata:
  layer: Silver
  owner:
    team: data-analytics
    email: team@example.com

builds:
  - id: build_daily_events
    pattern: embedded-logic
    engine: sql
    properties:
      sql: |
        SELECT
          DATE(event_time) as date,
          event_type,
          COUNT(*) as event_count
        FROM read_parquet('./lake/events/**/*.parquet')   -- wildcard glob
        WHERE event_time >= CURRENT_DATE - INTERVAL '7 days'
        GROUP BY date, event_type
    outputs:
      - daily_events

exposes:
  - exposeId: daily_events
    kind: view
    binding:
      platform: local
      format: parquet
      location:
        path: ./runtime/out/daily_events.parquet
    contract:
      schema:
        - name: date
          type: DATE
        - name: event_type
          type: STRING
        - name: event_count
          type: INTEGER
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

**1. Update the expose binding:**

```yaml
exposes:
  - exposeId: customer_orders
    kind: table
    binding:
      platform: gcp                 # Changed from 'local'
      format: bigquery_table        # Changed from 'parquet'
      location:
        project: my-project-id
        dataset: analytics
        table: customer_orders
    # contract.schema, builds, governance — all unchanged
```

**2. Deploy:**

```bash
fluid apply contract.fluid.yaml --provider gcp
```

**That's it!** Your local development becomes cloud production.

---

## Next Steps

- **[Local Walkthrough](/forge_docs/walkthrough/local)** - Complete tutorial
- **[GCP Walkthrough](/forge_docs/walkthrough/gcp)** - Migrate to cloud
- **[CLI Reference](/forge_docs/cli/)** - Local provider commands

---

*Perfect for development. Deploy to GCP when ready.*
