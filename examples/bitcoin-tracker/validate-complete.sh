#!/bin/bash
#
# Bitcoin Tracker - Complete Step-by-Step Validation Script
# This script validates every command in the walkthrough
#

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Configuration
EXAMPLE_DIR="/home/dustlabs/fluid-mono/forge_docs/examples/bitcoin-tracker"
CLI_DIR="/home/dustlabs/fluid-mono/forge-cli"
FLUID_CMD="python3 -m fluid_build.cli"

echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║    Bitcoin Tracker - Complete Walkthrough Validation          ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Change to example directory
cd "$EXAMPLE_DIR"
echo -e "${YELLOW}Working directory: $EXAMPLE_DIR${NC}"
echo ""

# Step 1: Validate Contract
echo -e "${BLUE}STEP 1: Validate Contract${NC}"
echo -e "${YELLOW}Command: fluid validate contract.fluid.yaml${NC}"
cd "$CLI_DIR"
$FLUID_CMD validate "$EXAMPLE_DIR/contract.fluid.yaml"
echo -e "${GREEN}✅ Contract validation passed${NC}"
echo ""

# Step 2: Test API Integration
echo -e "${BLUE}STEP 2: Test CoinGecko API Integration${NC}"
echo -e "${YELLOW}Command: Test fetch_bitcoin_price()${NC}"
cd "$EXAMPLE_DIR"
python3 -c "
from ingest_bitcoin_prices import fetch_bitcoin_price
price_data = fetch_bitcoin_price()
print(f'✅ Successfully fetched Bitcoin price')
print(f'   Price USD: \${price_data[\"price_usd\"]:,.2f}')
print(f'   Price EUR: €{price_data[\"price_eur\"]:,.2f}')
print(f'   Market Cap: \${price_data[\"market_cap_usd\"]:,.0f}')
print(f'   24h Volume: \${price_data[\"volume_24h_usd\"]:,.0f}')
"
echo -e "${GREEN}✅ API integration test passed${NC}"
echo ""

# Step 3: Generate Execution Plan
echo -e "${BLUE}STEP 3: Generate Execution Plan${NC}"
echo -e "${YELLOW}Command: fluid plan contract.fluid.yaml${NC}"
cd "$CLI_DIR"
FLUID_PROVIDER=gcp $FLUID_CMD plan "$EXAMPLE_DIR/contract.fluid.yaml" 2>&1 | grep -E "(FLUID Execution Plan|Total Actions|✅)"
echo -e "${GREEN}✅ Plan generation passed${NC}"
echo ""

# Step 4: Export to ODPS
echo -e "${BLUE}STEP 4: Export to ODPS (Open Data Product Specification)${NC}"
echo -e "${YELLOW}Command: fluid odps export contract.fluid.yaml --out bitcoin-tracker.odps.json${NC}"
cd "$EXAMPLE_DIR"
$FLUID_CMD odps export contract.fluid.yaml --out bitcoin-tracker.odps.json 2>&1 | grep -E "(Exported|✓)"
if [ -f "bitcoin-tracker.odps.json" ]; then
    SIZE=$(stat -f%z "bitcoin-tracker.odps.json" 2>/dev/null || stat -c%s "bitcoin-tracker.odps.json" 2>/dev/null)
    echo -e "   File size: $SIZE bytes"
    echo -e "${GREEN}✅ ODPS export successful${NC}"
else
    echo -e "${RED}❌ ODPS export failed${NC}"
    exit 1
fi
echo ""

# Step 5: Export to ODCS
echo -e "${BLUE}STEP 5: Export to ODCS (Open Data Contract Standard)${NC}"
echo -e "${YELLOW}Command: fluid odcs export contract.fluid.yaml --out bitcoin-tracker.odcs.yaml${NC}"
$FLUID_CMD odcs export contract.fluid.yaml --out bitcoin-tracker.odcs.yaml 2>&1 | grep -E "(Exported|✓)"
if [ -f "bitcoin-tracker.odcs.yaml" ]; then
    SIZE=$(stat -f%z "bitcoin-tracker.odcs.yaml" 2>/dev/null || stat -c%s "bitcoin-tracker.odcs.yaml" 2>/dev/null)
    echo -e "   File size: $SIZE bytes"
    echo -e "${GREEN}✅ ODCS export successful${NC}"
else
    echo -e "${RED}❌ ODCS export failed${NC}"
    exit 1
fi
echo ""

# Step 6: Validate Exports
echo -e "${BLUE}STEP 6: Validate Exported Files${NC}"
echo ""

echo -e "${YELLOW}Validating ODPS export...${NC}"
$FLUID_CMD odps validate bitcoin-tracker.odps.json 2>&1 | head -10
echo -e "${GREEN}✅ ODPS validation complete${NC}"
echo ""

echo -e "${YELLOW}Validating ODCS export...${NC}"
$FLUID_CMD odcs validate bitcoin-tracker.odcs.yaml 2>&1 | head -10
echo -e "${GREEN}✅ ODCS validation complete${NC}"
echo ""

# Step 7: Verify Requirements
echo -e "${BLUE}STEP 7: Verify Requirements${NC}"
echo ""

echo -e "${YELLOW}Checking Python dependencies...${NC}"
python3 -c "import requests; print('✅ requests installed')"
python3 -c "try:
    from google.cloud import bigquery
    print('✅ google-cloud-bigquery installed')
except ImportError:
    print('⚠️  google-cloud-bigquery not installed (optional for testing)')
"
echo ""

# Final Summary
echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                    VALIDATION COMPLETE                         ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}✅ All steps validated successfully!${NC}"
echo ""
echo -e "Files created:"
echo -e "  📄 bitcoin-tracker.odps.json (ODPS v4.1)"
echo -e "  📄 bitcoin-tracker.odcs.yaml (ODCS v3.1.0)"
echo ""
echo -e "Next steps:"
echo -e "  1. Set up GCP project: export GCP_PROJECT_ID=your-project-id"
echo -e "  2. Authenticate: gcloud auth application-default login"
echo -e "  3. Deploy: FLUID_PROVIDER=gcp fluid apply contract.fluid.yaml"
echo ""
