# Netflix Customer Preferences - Local Development

This example demonstrates a **Netflix customer viewing preferences data product** built entirely with local CSV files. Perfect for development, testing, and learning Fluid Forge without cloud dependencies.

## What's Included

- **Sample data**: 5 customers and 15 viewing history records
- **Declarative contract**: Complete Fluid Forge v0.7.1 data product specification
- **Multiple outputs**: Customer profiles, viewing history, genre preferences, engagement metrics
- **Analytics script**: Python script demonstrating data analysis workflows

## Quick Start

### 1. Validate the Contract

```bash
cd examples/netflix-preferences-local
fluid validate contract.fluid.yaml
```

Expected output:
```
✅ Valid FLUID contract (schema v0.7.1)
Validation completed in 0.002s
```

### 2. Run the Analytics

```bash
python3 analyze.py
```

This will:
- Load customer and viewing data from CSV files
- Calculate genre preferences by customer
- Generate engagement scores
- Analyze content performance
- Create output files in `./output/` directory

### 3. View the Results

Check the generated analytics:

```bash
ls -la output/
cat output/genre_preferences.csv
cat output/engagement_summary.csv
```

## Data Product Structure

### Sources (Input CSV Files)

1. **customers.csv**: Customer demographic and subscription data
   - customer_id, email, name, country, signup_date, subscription_tier, age, gender

2. **viewing_history.csv**: Complete viewing history with metrics
   - view_id, customer_id, content_id, content_title, content_type, genre, watch_date, watch_duration_minutes, completion_percent, rating

### Exposes (Output Data Assets)

1. **customer_profiles** (table)
   - Customer demographic information
   - Subscription details

2. **viewing_history** (table)
   - Detailed viewing sessions
   - Watch metrics and ratings

3. **genre_preferences** (view)
   - Genre preferences by customer
   - Total views, minutes watched, average completion
   - Average ratings per genre

4. **engagement_summary** (view)
   - Customer engagement metrics
   - Subscription tier analysis
   - Calculated engagement scores (0-100)

## Sample Queries

### Genre Preferences

```python
import pandas as pd

# Load genre preferences
genre_prefs = pd.read_csv('output/genre_preferences.csv')

# Top genres for a specific customer
customer_genres = genre_prefs[genre_prefs['customer_id'] == 'CUST001']
print(customer_genres.sort_values('total_views', ascending=False))
```

### Engagement Analysis

```python
# Load engagement summary
engagement = pd.read_csv('output/engagement_summary.csv')

# High engagement customers
high_engagement = engagement[engagement['engagement_score'] >= 80]
print(high_engagement)

# Engagement by subscription tier
tier_engagement = engagement.groupby('subscription_tier')['engagement_score'].mean()
print(tier_engagement)
```

## Key Metrics Explained

### Engagement Score (0-100)

Calculated as:
- **40%** - Viewing frequency (number of views)
- **30%** - Watch time (total hours watched)
- **30%** - Completion rate (% of content finished)

Higher scores indicate more engaged customers.

### Completion Percent

Percentage of content completed:
- **100%** - Watched entire content
- **<50%** - May indicate content doesn't match preferences
- **>80%** - High engagement with content

## Extending This Example

### Add More Data

Append new records to the CSV files:

```bash
echo "CUST006,frank@email.com,Frank Ocean,US,2023-06-15,Premium,33,M" >> data/customers.csv

echo "VIEW016,CUST006,CONT113,The Witcher S3,Series,Fantasy,2024-01-16,52,95,5" >> data/viewing_history.csv
```

Then re-run the analysis:
```bash
python3 analyze.py
```

### Add New Views

Create additional analytical views in the contract:

```yaml
  - exposeId: content_recommendations
    kind: view
    title: Content Recommendations
    description: Personalized content recommendations based on viewing patterns
    contract:
      schema:
        - name: customer_id
          type: STRING
        - name: recommended_genre
          type: STRING
        - name: confidence_score
          type: FLOAT
    binding:
      platform: local
      format: csv
      location:
        path: ./output/recommendations.csv
```

### Deploy to Cloud

Ready for production? Update the contract to use cloud storage:

```yaml
exposes:
  - exposeId: customer_profiles
    kind: table
    binding:
      platform: gcp
      format: bigquery_table
      location:
        project: my-project
        dataset: netflix_analytics
        table: customer_profiles
```

Then deploy:
```bash
fluid apply contract.fluid.yaml --provider gcp
```

## Next Steps

- **📊 [Add Visualizations](docs/add-visualizations.md)** - Create charts and dashboards
- **🤖 [Generate Airflow DAG](docs/generate-dag.md)** - Schedule daily updates
- **☁️ [Deploy to GCP](docs/deploy-gcp.md)** - Move to production
- **🔒 [Add Governance](docs/add-governance.md)** - Implement data policies

## Troubleshooting

### "File not found" error

Make sure you're in the correct directory:
```bash
cd examples/netflix-preferences-local
```

### "pandas not installed"

Install required dependencies:
```bash
pip install pandas
```

### "Permission denied"

Make the analyze script executable:
```bash
chmod +x analyze.py
```

## Learn More

- **[Fluid Forge Documentation](../../docs/README.md)**
- **[Local Development Walkthrough](../../docs/walkthrough/local.md)**
- **[Validation Reference](../../docs/cli/validate.md)**
