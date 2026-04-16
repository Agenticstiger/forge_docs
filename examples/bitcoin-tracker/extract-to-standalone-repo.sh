#!/bin/bash
# Extract bitcoin-tracker to standalone repository
# Usage: ./extract-to-standalone-repo.sh [output-directory]

set -e

# Configuration
OUTPUT_DIR="${1:-/tmp/bitcoin-price-tracker}"
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "════════════════════════════════════════════════════════════"
echo "Bitcoin Tracker → Standalone Repository Extraction"
echo "════════════════════════════════════════════════════════════"
echo "Source: ${SOURCE_DIR}"
echo "Output: ${OUTPUT_DIR}"
echo ""

# Create output directory
if [ -d "${OUTPUT_DIR}" ]; then
    read -p "Output directory exists. Remove and recreate? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "${OUTPUT_DIR}"
    else
        echo "❌ Aborted"
        exit 1
    fi
fi

mkdir -p "${OUTPUT_DIR}"
cd "${OUTPUT_DIR}"

echo "📂 Creating directory structure..."
mkdir -p scripts docs dbt .github/workflows

echo ""
echo "📋 Copying core files..."

# Root level files
cp "${SOURCE_DIR}/contract.fluid.yaml" .
cp "${SOURCE_DIR}/Jenkinsfile" .
cp "${SOURCE_DIR}/requirements.txt" .

# Scripts
echo "  → scripts/"
cp "${SOURCE_DIR}/load_bitcoin_price_batch.py" scripts/
cp "${SOURCE_DIR}/ingest_bitcoin_prices.py" scripts/
cp "${SOURCE_DIR}/run-complete-example.sh" scripts/
cp "${SOURCE_DIR}/validate-jenkinsfile.sh" scripts/
chmod +x scripts/*.sh

# Documentation
echo "  → docs/"
cp "${SOURCE_DIR}/DECLARATIVE_DESIGN.md" docs/
cp "${SOURCE_DIR}/OPPORTUNITIES.md" docs/
cp "${SOURCE_DIR}/IMPROVEMENTS.md" docs/
cp "${SOURCE_DIR}/JENKINS_QUICKREF.md" docs/
cp "${SOURCE_DIR}/QUICK_REFERENCE.md" docs/QUICKREF.md

# dbt
echo "  → dbt/"
cp -r "${SOURCE_DIR}/dbt/"* dbt/
# Clean dbt artifacts
rm -rf dbt/target/* dbt/logs/*

echo ""
echo "📝 Creating .gitignore..."
cat > .gitignore << 'EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
ENV/
.venv
*.egg-info/
dist/
build/

# dbt
dbt/target/
dbt/dbt_packages/
dbt/logs/
dbt/.user.yml

# FLUID runtime
runtime/
*.log
*.json

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db

# Secrets
*.key
*.json.secret
.env
credentials.json
service-account-*.json

# Temporary files
tmp/
temp/
*.tmp
*.bak
EOF

echo ""
echo "📝 Creating README.md..."
cat > README.md << 'EOF'
# Bitcoin Price Tracker

Real-time Bitcoin price tracking data product built with FLUID framework.

## 🚀 Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt
pip install dbt-core dbt-bigquery

# 2. Configure GCP
export GCP_PROJECT_ID="your-project-id"
gcloud auth application-default login

# 3. Run complete example
./scripts/run-complete-example.sh
```

## 📊 Data Products

| Resource | Type | Description | Fields |
|----------|------|-------------|--------|
| `bitcoin_prices` | Table | Raw price data | 8 fields (price_usd, market_cap, etc.) |
| `daily_price_summary` | View | Daily OHLC + volatility | 15 fields |
| `price_trends` | View | Moving averages | 12 fields |

## 🏗️ Architecture

```
CoinGecko API → Python → BigQuery Table → dbt → Views
                   ↓
              Jenkins CI/CD
```

## 📋 Development Workflow

```bash
# Create feature branch
git checkout -b feature/add-new-metric

# Update contract
vim contract.fluid.yaml

# Validate
python3 -m fluid_build.cli validate contract.fluid.yaml

# Test locally
./scripts/run-complete-example.sh

# Commit and push
git add .
git commit -m "feat: Add new metric"
git push origin feature/add-new-metric

# Create PR → Jenkins CI/CD runs → Merge → Deploy
```

## 🔧 CI/CD Pipeline

- **Push to `develop`** → Deploy to staging
- **Push to `main`** → Deploy to production (requires approval)

See [Jenkinsfile](Jenkinsfile) for details.

## 📚 Documentation

- [Quick Reference](docs/QUICKREF.md) - Commands and troubleshooting
- [Declarative Design](docs/DECLARATIVE_DESIGN.md) - Best practices
- [Jenkins Guide](docs/JENKINS_QUICKREF.md) - CI/CD details
- [Known Issues](docs/OPPORTUNITIES.md) - Limitations and workarounds

## 🏷️ Governance

**Classification:** Public (no PII)

**Labels:**
- `cost-center: engineering`
- `data-classification: public`
- `cost-allocation: crypto-team`
- `sla-tier: silver`

**Access:**
- **Readers:** data-analysts@, data-scientists@
- **Writers:** ingestion@ service account

## 🛠️ Tech Stack

- **Framework:** FLUID 0.7.1
- **Platform:** GCP BigQuery
- **Transformations:** dbt
- **CI/CD:** Jenkins
- **Language:** Python 3.8+

## 📈 Metrics

- **Data Freshness:** < 1 hour
- **Daily Updates:** ~24 records
- **Storage Cost:** < $0.01/month
- **Query Cost:** Free tier

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'feat: Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## 📄 License

MIT License - see [LICENSE](LICENSE) file

---

Built with ❤️ using [FLUID Framework](https://github.com/your-org/fluid-mono)
EOF

echo ""
echo "📝 Creating LICENSE..."
cat > LICENSE << 'EOF'
MIT License

Copyright (c) 2026 FLUID Data Products

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
EOF

echo ""
echo "📝 Creating CHANGELOG.md..."
cat > CHANGELOG.md << 'EOF'
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial release of Bitcoin Price Tracker data product
- FLUID 0.7.1 contract with comprehensive governance
- Jenkins CI/CD pipeline
- dbt transformations (OHLC, moving averages)
- Complete documentation

## [1.0.0] - 2026-01-21

### Added
- Bitcoin price ingestion from CoinGecko API
- BigQuery table: `bitcoin_prices`
- dbt views: `daily_price_summary`, `price_trends`
- FinOps labels for cost tracking
- Data quality tests
- Automated deployment pipeline

### Technical Details
- Platform: GCP BigQuery
- Region: us-central1
- Update Frequency: Hourly (manual trigger)
- Data Retention: 90 days
EOF

echo ""
echo "📝 Creating GitHub Actions workflow (optional)..."
cat > .github/workflows/ci.yml << 'EOF'
name: CI/CD Pipeline

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main, develop ]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.8'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install dbt-core dbt-bigquery
      
      - name: Validate FLUID contract
        run: |
          python3 -m fluid_build.cli validate contract.fluid.yaml
      
      - name: Validate Jenkinsfile
        run: |
          ./scripts/validate-jenkinsfile.sh
  
  test:
    needs: validate
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.8'
      
      - name: Install dependencies
        run: |
          pip install dbt-core dbt-bigquery pytest
      
      - name: Run dbt tests
        env:
          GCP_PROJECT_ID: ${{ secrets.GCP_PROJECT_ID }}
        run: |
          cd dbt
          dbt test --project-dir . --profiles-dir .
EOF

echo ""
echo "🔧 Initializing Git repository..."
git init
git add .
git commit -m "Initial commit: Bitcoin price tracker data product

- FLUID 0.7.1 contract with comprehensive governance
- Jenkins CI/CD pipeline with 7 stages
- dbt transformations (OHLC, moving averages, trends)
- Python ingestion scripts for CoinGecko API
- Complete documentation and quick references
- One-command automation script
- Label-based FinOps tracking

Data Products:
- bitcoin_prices (table): Raw price data
- daily_price_summary (view): Daily aggregations
- price_trends (view): Moving averages

Tech Stack: FLUID + BigQuery + dbt + Jenkins + Python"

echo ""
echo "✅ Extraction complete!"
echo ""
echo "════════════════════════════════════════════════════════════"
echo "Next Steps:"
echo "════════════════════════════════════════════════════════════"
echo ""
echo "1. Add Git remote:"
echo "   cd ${OUTPUT_DIR}"
echo "   git remote add origin ssh://admin@synology:/volume1/git/bitcoin-price-tracker.git"
echo ""
echo "2. Create develop branch:"
echo "   git checkout -b develop"
echo "   git push -u origin develop"
echo ""
echo "3. Push main branch:"
echo "   git checkout main"
echo "   git push -u origin main"
echo ""
echo "4. Create initial tag:"
echo "   git tag -a v1.0.0 -m 'Initial release'"
echo "   git push --tags"
echo ""
echo "5. Configure Jenkins multibranch pipeline:"
echo "   - Job name: bitcoin-price-tracker"
echo "   - Source: Git SCM"
echo "   - Repository URL: ssh://admin@synology:/volume1/git/bitcoin-price-tracker.git"
echo "   - Script path: Jenkinsfile"
echo ""
echo "6. Test the workflow:"
echo "   git checkout develop"
echo "   git checkout -b feature/test-cicd"
echo "   # Make a small change"
echo "   git commit -am 'test: Trigger Jenkins build'"
echo "   git push origin feature/test-cicd"
echo "   # Watch Jenkins build"
echo ""
echo "════════════════════════════════════════════════════════════"
echo ""
echo "📂 Repository ready at: ${OUTPUT_DIR}"
echo ""
