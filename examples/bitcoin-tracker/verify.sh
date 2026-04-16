#!/bin/bash
# Verification script for Bitcoin Tracker GCP example

set -e

echo "========================================================================"
echo "📊 BITCOIN PRICE TRACKER GCP - VERIFICATION"
echo "========================================================================"
echo ""

# 1. Validate contract
echo "✅ Step 1: Validating contract..."
fluid validate contract.fluid.yaml
echo ""

# 2. Check file structure
echo "✅ Step 2: Checking file structure..."
if [ -f "runtime/ingest_bitcoin_prices.py" ]; then
    echo "  ✓ runtime/ingest_bitcoin_prices.py found"
else
    echo "  ✗ runtime/ingest_bitcoin_prices.py not found!"
    exit 1
fi

if [ -f "dbt/models/daily_price_summary.sql" ]; then
    echo "  ✓ dbt/models/daily_price_summary.sql found"
else
    echo "  ✗ dbt/models/daily_price_summary.sql not found!"
    exit 1
fi

if [ -f "dbt/models/price_trends.sql" ]; then
    echo "  ✓ dbt/models/price_trends.sql found"
else
    echo "  ✗ dbt/models/price_trends.sql not found!"
    exit 1
fi
echo ""

# 3. Show contract structure
echo "✅ Step 3: Contract structure..."
echo "  Builds:"
grep -A 1 "^  - id:" contract.fluid.yaml | grep "id:" | sed 's/^/    /'
echo ""
echo "  Exposes:"
grep "exposeId:" contract.fluid.yaml | sed 's/^/    /'
echo ""

# 4. Check Python dependencies
echo "✅ Step 4: Checking Python dependencies..."
if python3 -c "import requests" 2>/dev/null; then
    echo "  ✓ requests installed"
else
    echo "  ⚠ requests not installed (pip install -r requirements.txt)"
fi

if python3 -c "import google.cloud.bigquery" 2>/dev/null; then
    echo "  ✓ google-cloud-bigquery installed"
else
    echo "  ⚠ google-cloud-bigquery not installed (pip install -r requirements.txt)"
fi
echo ""

echo "========================================================================"
echo "✨ Verification complete! Example is ready."
echo ""
echo "Next steps (requires GCP project):"
echo "  1. Set: export GCP_PROJECT_ID=your-project-id"
echo "  2. Authenticate: gcloud auth application-default login"
echo "  3. Deploy: fluid apply contract.fluid.yaml --provider gcp"
echo "  4. Ingest: python runtime/ingest_bitcoin_prices.py"
echo "  5. Transform: cd dbt && dbt run --profiles-dir ."
echo "========================================================================"
