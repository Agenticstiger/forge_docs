#!/bin/bash
# Verification script for Netflix Preferences Local example

set -e

echo "========================================================================"
echo "📺 NETFLIX PREFERENCES LOCAL - VERIFICATION"
echo "========================================================================"
echo ""

# 1. Validate contract
echo "✅ Step 1: Validating contract..."
fluid validate contract.fluid.yaml
echo ""

# 2. Check data files exist
echo "✅ Step 2: Checking data files..."
if [ -f "data/customers.csv" ]; then
    echo "  ✓ customers.csv found ($(wc -l < data/customers.csv) lines)"
else
    echo "  ✗ customers.csv not found!"
    exit 1
fi

if [ -f "data/viewing_history.csv" ]; then
    echo "  ✓ viewing_history.csv found ($(wc -l < data/viewing_history.csv) lines)"
else
    echo "  ✗ viewing_history.csv not found!"
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

echo "========================================================================"
echo "✨ Verification complete! Example is ready to use."
echo ""
echo "Next steps:"
echo "  1. Run: fluid apply contract.fluid.yaml --provider local"
echo "  2. Check: ls -la output/"
echo "  3. View: cat output/engagement_summary.csv"
echo "========================================================================"
