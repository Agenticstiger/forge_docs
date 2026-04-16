# Walkthrough: Local Development

**Time:** 10 minutes | **Difficulty:** Beginner | **Prerequisites:** Python 3.9+, pip

---

## Overview

Build a **Netflix customer viewing analytics pipeline** entirely on your laptop — no cloud account, no credentials, no cost. This walkthrough uses CSV files, DuckDB, and declarative SQL transformations embedded in a Fluid Forge contract.

### What You'll Build

- Customer genre preference analysis
- Engagement scoring pipeline
- All running locally with the `local` provider

### What You'll Learn

- Writing a Fluid Forge contract from scratch
- Using the `builds` section for declarative SQL transformations
- The `validate → plan → apply` workflow
- How the local provider processes CSV data with DuckDB

---

## Step 1: Setup

### Install Fluid Forge

```bash
pip install fluid-forge
```

### Verify Installation

```bash
fluid version

# Should show:
# Fluid Forge CLI v0.7.7
# Providers: local (production), gcp (production)
```

### Create Project Directory

```bash
mkdir netflix-preferences-local
cd netflix-preferences-local
```

---

## Step 2: Create Sample Data

Let's create sample Netflix customer and viewing history data.

### Create Customer Data

```bash
mkdir -p data

cat > data/customers.csv << 'EOF'
customer_id,email,name,country,signup_date,subscription_tier,age,gender
CUST001,alice.wonder@email.com,Alice Wonderland,US,2023-01-15,Premium,28,F
CUST002,bob.builder@email.com,Bob Builder,UK,2023-02-20,Standard,35,M
CUST003,charlie.brown@email.com,Charlie Brown,CA,2023-03-10,Premium,42,M
CUST004,diana.prince@email.com,Diana Prince,US,2023-04-05,Basic,31,F
CUST005,eve.jackson@email.com,Eve Jackson,AU,2023-05-12,Standard,27,F
EOF
```

### Create Viewing History Data

```bash
cat > data/viewing_history.csv << 'EOF'
view_id,customer_id,content_id,content_title,content_type,genre,watch_date,watch_duration_minutes,completion_percent,rating
VIEW001,CUST001,CONT101,Stranger Things S4,Series,Sci-Fi,2024-01-10,65,85,5
VIEW002,CUST001,CONT102,The Crown S6,Series,Drama,2024-01-11,58,95,4
VIEW003,CUST001,CONT103,Glass Onion,Movie,Mystery,2024-01-12,139,100,5
VIEW004,CUST002,CONT104,Wednesday S1,Series,Comedy,2024-01-10,45,75,4
VIEW005,CUST002,CONT101,Stranger Things S4,Series,Sci-Fi,2024-01-11,65,90,5
VIEW006,CUST002,CONT105,The Witcher S3,Series,Fantasy,2024-01-13,52,80,3
VIEW007,CUST003,CONT106,Breaking Bad,Series,Thriller,2024-01-09,58,100,5
VIEW008,CUST003,CONT107,Extraction 2,Movie,Action,2024-01-10,111,100,4
VIEW009,CUST003,CONT108,The Gray Man,Movie,Action,2024-01-14,122,95,4
VIEW010,CUST004,CONT102,The Crown S6,Series,Drama,2024-01-11,58,100,5
VIEW011,CUST004,CONT109,Bridgerton S3,Series,Romance,2024-01-12,61,88,5
VIEW012,CUST004,CONT110,Emily in Paris S4,Series,Comedy,2024-01-13,33,55,3
VIEW013,CUST005,CONT103,Glass Onion,Movie,Mystery,2024-01-10,139,100,5
VIEW014,CUST005,CONT111,Love is Blind S5,Series,Reality,2024-01-11,48,90,4
VIEW015,CUST005,CONT112,Squid Game S2,Series,Thriller,2024-01-15,60,100,5
EOF
```

---

## Step 3: Create the Fluid Forge Contract

Create `contract.fluid.yaml` with **declarative SQL transformations**:

```yaml
fluidVersion: "0.7.1"
kind: DataProduct
id: entertainment.netflix_preferences_local
name: Netflix Customer Preferences - Local
description: |
  Netflix customer viewing preferences and analytics built locally using CSV files.
  Demonstrates declarative data transformations with embedded SQL logic.

domain: Entertainment

tags:
  - streaming
  - customer-analytics
  - local-dev

labels:
  team: data-analytics
  environment: local

metadata:
  layer: Gold
  owner:
    team: customer-analytics
    email: analytics@netflix.local

# Declarative data transformations using DuckDB SQL
builds:
  - id: generate_genre_preferences
    description: Calculate genre viewing preferences for each customer
    pattern: embedded-logic
    engine: sql
    properties:
      sql: |
        SELECT 
          c.customer_id,
          c.name as customer_name,
          v.genre,
          COUNT(*) as total_views,
          SUM(v.watch_duration_minutes) as total_minutes,
          ROUND(AVG(v.completion_percent), 2) as avg_completion,
          ROUND(AVG(v.rating), 2) as avg_rating
        FROM read_csv_auto('data/customers.csv') c
        JOIN read_csv_auto('data/viewing_history.csv') v
          ON c.customer_id = v.customer_id
        GROUP BY c.customer_id, c.name, v.genre
        ORDER BY c.customer_id, total_views DESC
    outputs:
      - genre_preferences

  - id: generate_engagement_summary
    description: Calculate customer engagement metrics and scores
    pattern: embedded-logic
    engine: sql
    properties:
      sql: |
        WITH customer_stats AS (
          SELECT 
            c.customer_id,
            c.name as customer_name,
            c.subscription_tier,
            COUNT(v.view_id) as total_views,
            ROUND(SUM(v.watch_duration_minutes) / 60.0, 2) as total_watch_hours,
            ROUND(AVG(v.completion_percent), 2) as avg_completion_rate,
            FIRST(v.genre ORDER BY COUNT(*) OVER (PARTITION BY c.customer_id, v.genre) DESC) as favorite_genre
          FROM read_csv_auto('data/customers.csv') c
          LEFT JOIN read_csv_auto('data/viewing_history.csv') v
            ON c.customer_id = v.customer_id
          GROUP BY c.customer_id, c.name, c.subscription_tier
        ),
        max_values AS (
          SELECT 
            MAX(total_views) as max_views,
            MAX(total_watch_hours) as max_hours
          FROM customer_stats
        )
        SELECT 
          cs.customer_id,
          cs.customer_name,
          cs.subscription_tier,
          cs.total_views,
          cs.total_watch_hours,
          cs.avg_completion_rate,
          cs.favorite_genre,
          ROUND(
            (cs.total_views::FLOAT / mv.max_views * 40) +
            (cs.total_watch_hours::FLOAT / mv.max_hours * 30) +
            (cs.avg_completion_rate / 100.0 * 30),
            2
          ) as engagement_score
        FROM customer_stats cs
        CROSS JOIN max_values mv
        ORDER BY engagement_score DESC
    outputs:
      - engagement_summary

exposes:
  - exposeId: customer_profiles
    kind: table
    title: Customer Profiles
    version: 1.0.0
    
    contract:
      schema:
        - name: customer_id
          type: STRING
          required: true
        - name: email
          type: STRING
          required: true
          sensitivity: pii
        - name: name
          type: STRING
          required: true
    
    binding:
      platform: local
      format: csv
      location:
        path: ./data/customers.csv

  - exposeId: genre_preferences
    kind: view
    title: Genre Preferences by Customer
    version: 1.0.0
    
    contract:
      schema:
        - name: customer_id
          type: STRING
        - name: customer_name
          type: STRING
        - name: genre
          type: STRING
        - name: total_views
          type: INTEGER
        - name: avg_completion
          type: FLOAT
    
    binding:
      platform: local
      format: csv
      location:
        path: ./output/genre_preferences.csv

  - exposeId: engagement_summary
    kind: view
    title: Customer Engagement Summary
    version: 1.0.0
    
    contract:
      schema:
        - name: customer_id
          type: STRING
        - name: customer_name
          type: STRING
        - name: engagement_score
          type: FLOAT
    
    binding:
      platform: local
      format: csv
      location:
        path: ./output/engagement_summary.csv
```

---

## Step 4: Validate the Contract

Check that your contract is well-formed:

```bash
fluid validate contract.fluid.yaml

# Expected output:
# ✅ Valid FLUID contract (schema v0.7.1)
# Validation completed in 0.004s
```

---

## Step 5: Execute the Declarative Transformations

Run the contract with the local provider to execute the SQL transformations:

```bash
fluid apply contract.fluid.yaml --provider local

# Expected output:
# 🏠 Local Provider Execution
# 
# ⏳ Executing build: generate_genre_preferences...
#   ✅ SQL transformation completed (15 rows)
#   📄 Output written to: ./output/genre_preferences.csv
# 
# ⏳ Executing build: generate_engagement_summary...
#   ✅ SQL transformation completed (5 rows)
#   📄 Output written to: ./output/engagement_summary.csv
# 
# ✨ Execution successful!
```

---

## Step 6: Query Your Data

Now you can explore the generated outputs:

### View Genre Preferences

```bash
cat output/genre_preferences.csv | column -t -s,
```

Expected output:
```
customer_id  customer_name     genre     total_views  total_minutes  avg_completion  avg_rating
CUST001      Alice Wonderland  Sci-Fi    1            65             85.0            5.0
CUST001      Alice Wonderland  Drama     1            58             95.0            4.0
CUST002      Bob Builder       Sci-Fi    1            65             90.0            5.0
...
```

### View Engagement Summary

```bash
cat output/engagement_summary.csv | column -t -s,
```

Expected output:
```
customer_id  customer_name     subscription_tier  total_views  total_watch_hours  engagement_score
CUST003      Charlie Brown     Premium            3            4.92               100.0
CUST001      Alice Wonderland  Premium            3            4.37               95.5
...
```

---

## Step 7: Understand the Declarative Pattern

The `builds` section makes this data product **fully declarative**:

### Pattern: embedded-logic

```yaml
builds:
  - id: generate_genre_preferences
    pattern: embedded-logic    # SQL is embedded in the contract
    engine: sql                 # Uses DuckDB SQL engine
    properties:
      sql: |
        SELECT ...            # Declarative transformation
    outputs:
      - genre_preferences     # Links to exposes section
```

**Benefits**:
- ✅ **No external code dependencies** - Everything in one contract
- ✅ **Version controlled** - SQL transformations tracked with contract
- ✅ **Portable** - Works across local, GCP, Snowflake with provider changes
- ✅ **Testable** - Can validate SQL syntax and logic
- ✅ **Auditable** - Clear data lineage from source to output

---

## Step 8: Add More Analytics

Extend the contract with additional transformations:

```yaml
builds:
  - id: generate_content_performance
    description: Analyze content performance metrics
    pattern: embedded-logic
    engine: sql
    properties:
      sql: |
        SELECT 
          content_title,
          content_type,
          genre,
          COUNT(DISTINCT customer_id) as unique_viewers,
          COUNT(*) as total_views,
          ROUND(AVG(completion_percent), 2) as avg_completion,
          ROUND(AVG(rating), 2) as avg_rating
        FROM read_csv_auto('data/viewing_history.csv')
        GROUP BY content_title, content_type, genre
        ORDER BY total_views DESC
    outputs:
      - content_performance

exposes:
  - exposeId: content_performance
    kind: view
    title: Content Performance Metrics
    version: 1.0.0
    contract:
      schema:
        - name: content_title
          type: STRING
        - name: avg_rating
          type: FLOAT
    binding:
      platform: local
      format: csv
      location:
        path: ./output/content_performance.csv
```

Then re-run:
```bash
fluid apply contract.fluid.yaml --provider local
```

---

## What You've Learned

✅ Created a declarative data product with Fluid Forge 0.7.1  
✅ Used `builds` section for embedded SQL transformations  
✅ Processed CSV data sources with DuckDB  
✅ Generated analytical views declaratively  
✅ Validated and executed locally without cloud dependencies  

---

## Next Steps

### 🚀 Deploy to GCP

Ready to move to production? Just change the provider:

```yaml
exposes:
  - exposeId: genre_preferences
    binding:
      platform: gcp           # Changed from 'local'
      format: bigquery_table  # Changed from 'csv'
      location:
        project: my-project
        dataset: netflix_analytics
        table: genre_preferences
```

Then:
```bash
fluid apply contract.fluid.yaml --provider gcp
```

### 🤖 Generate Airflow DAG

Schedule daily analytics updates:

```bash
fluid generate-airflow contract.fluid.yaml \
  --output netflix_analytics_dag.py \
  --schedule "0 2 * * *"  # Daily at 2 AM
```

### 🔒 Add Governance

Add data policies to the contract:

```yaml
exposes:
  - exposeId: customer_profiles
    policy:
      classification: Internal
      privacy:
        masking:
          - column: email
            strategy: hash
            params:
              algorithm: SHA256
```

### 📊 Add Data Quality

Include validation rules:

```yaml
builds:
  - id: generate_genre_preferences
    dataQuality:
      rules:
        - name: positive_view_counts
          query: |
            SELECT COUNT(*) as violations
            FROM genre_preferences
            WHERE total_views <= 0
          expect: { violations: 0 }
```

---

## Full Example

Check out the complete working example:

```bash
cd examples/netflix-preferences-local
fluid validate contract.fluid.yaml
fluid apply contract.fluid.yaml --provider local
```

---

## Ready for Production?

👉 **[Deploy to GCP →](/walkthrough/gcp)**

Learn how to deploy to BigQuery, set up scheduled ingestion, and implement governance policies.
