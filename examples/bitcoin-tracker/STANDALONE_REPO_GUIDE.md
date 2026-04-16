# Extracting Bitcoin Tracker as Standalone Repository

This guide shows how to extract the Bitcoin tracker example into a standalone Git repository for realistic data product development workflows.

## 🎯 Why Separate Repository?

### Benefits

**Development Workflow:**
- ✅ Test full Git flow (branch → commit → PR → merge)
- ✅ Trigger Jenkins builds on push/PR
- ✅ Realistic code review process
- ✅ Tag releases for production deployments

**Template for Real Projects:**
- ✅ Reusable structure for new data products
- ✅ Proven CI/CD pipeline
- ✅ Example governance patterns
- ✅ Documentation templates

**Framework Refinement:**
- ✅ Test CLI changes against real project
- ✅ Identify boilerplate improvements
- ✅ Validate contract schema evolution
- ✅ Discover missing features

## 📂 Repository Structure

```
bitcoin-price-tracker/          # Root of standalone repo
├── .git/
├── .gitignore
├── README.md                   # Project-specific README
├── Jenkinsfile                 # CI/CD pipeline
├── contract.fluid.yaml         # Data product contract
├── requirements.txt            # Python dependencies
├── .github/                    # GitHub/Gitea workflows (optional)
│   └── workflows/
│       └── ci.yml
├── dbt/                        # Transformations
│   ├── dbt_project.yml
│   ├── profiles.yml
│   └── models/
├── scripts/                    # Renamed from root-level scripts
│   ├── load_bitcoin_price_batch.py
│   └── run-complete-example.sh
├── docs/                       # Project documentation
│   ├── QUICKREF.md
│   ├── DECLARATIVE_DESIGN.md
│   └── OPPORTUNITIES.md
└── .fluid/                     # Framework metadata (optional)
    └── version.txt
```

## 🚀 Step-by-Step Setup

### Step 1: Create Repository on Synology

```bash
# SSH into Synology
ssh admin@your-synology.local

# Navigate to Git directory
cd /volume1/git

# Create bare repository
git init --bare bitcoin-price-tracker.git

# Set description
echo "Bitcoin Price Tracker - FLUID Data Product Example" > bitcoin-price-tracker.git/description

# Enable post-receive hook for Jenkins (optional)
cat > bitcoin-price-tracker.git/hooks/post-receive << 'EOF'
#!/bin/bash
# Trigger Jenkins build on push
curl -X POST http://jenkins:8080/job/bitcoin-tracker/build \
     --user jenkins:API_TOKEN
EOF
chmod +x bitcoin-price-tracker.git/hooks/post-receive
```

### Step 2: Extract and Initialize Local Repository

```bash
# From your workstation
cd /tmp

# Create new directory for standalone repo
mkdir bitcoin-price-tracker
cd bitcoin-price-tracker

# Initialize Git
git init

# Copy files from fluid-mono (excluding git history)
cp -r ~/fluid-mono/forge_docs/examples/bitcoin-tracker/* .

# Reorganize structure
mkdir -p scripts docs

# Move scripts
mv load_bitcoin_price_batch.py scripts/
mv ingest_bitcoin_prices.py scripts/
mv run-complete-example.sh scripts/
mv validate-jenkinsfile.sh scripts/

# Move docs
mv DECLARATIVE_DESIGN.md docs/
mv OPPORTUNITIES.md docs/
mv IMPROVEMENTS.md docs/
mv JENKINS_QUICKREF.md docs/
mv QUICK_REFERENCE.md docs/QUICKREF.md

# Keep at root
# - README.md
# - Jenkinsfile
# - contract.fluid.yaml
# - requirements.txt
# - dbt/
```

### Step 3: Create .gitignore

```bash
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
runtime/*.json
runtime/*.log
runtime/plan*.json

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
```

### Step 4: Create Repository README

```bash
cat > README.md << 'EOF'
# Bitcoin Price Tracker

Real-time Bitcoin price tracking data product built with FLUID framework.

## 🚀 Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure GCP
export GCP_PROJECT_ID="your-project-id"
gcloud auth application-default login

# 3. Run complete example
./scripts/run-complete-example.sh
```

## 📊 Data Products

This repository produces:
- **bitcoin_prices** - Raw price data (table)
- **daily_price_summary** - Daily OHLC aggregations (view)
- **price_trends** - Moving averages and trends (view)

## 🏗️ Architecture

```
CoinGecko API → Python Script → BigQuery Table → dbt → Views
```

## 📋 Development Workflow

```bash
# 1. Create feature branch
git checkout -b feature/add-new-field

# 2. Update contract
vim contract.fluid.yaml

# 3. Validate locally
python3 -m fluid_build.cli validate contract.fluid.yaml

# 4. Test changes
./scripts/run-complete-example.sh

# 5. Commit and push
git add contract.fluid.yaml
git commit -m "feat: Add new price field"
git push origin feature/add-new-field

# 6. Create PR → Jenkins runs CI/CD → Merge → Deploy
```

## 🔧 CI/CD

This project uses Jenkins for automated deployments:
- **Push to `develop`** → Deploy to staging
- **Push to `main`** → Deploy to production (with approval)

See [Jenkinsfile](Jenkinsfile) for pipeline details.

## 📚 Documentation

- [Quick Reference](docs/QUICKREF.md)
- [Declarative Design Patterns](docs/DECLARATIVE_DESIGN.md)
- [Jenkins CI/CD Guide](docs/JENKINS_QUICKREF.md)
- [Known Issues](docs/OPPORTUNITIES.md)

## 🏷️ Governance

**Labels:**
- `cost-center: engineering`
- `data-classification: public`
- `cost-allocation: crypto-team`

**Access Policy:**
- Readers: `data-analysts@company.com`, `data-scientists@company.com`
- Writers: `ingestion@company.iam.gserviceaccount.com`

## 🛠️ Technology Stack

- **Framework:** FLUID 0.7.1
- **Platform:** Google Cloud Platform (BigQuery)
- **Transformations:** dbt
- **Orchestration:** Apache Airflow (optional)
- **CI/CD:** Jenkins
- **Language:** Python 3.8+

## 📄 License

MIT License - see LICENSE file
EOF
```

### Step 5: Create Initial Commit

```bash
# Stage all files
git add .

# Create initial commit
git commit -m "Initial commit: Bitcoin price tracker data product

- FLUID 0.7.1 contract with comprehensive governance
- Jenkins CI/CD pipeline
- dbt transformations (OHLC, moving averages)
- Python ingestion scripts
- Complete documentation"

# Add remote
git remote add origin ssh://admin@your-synology.local:/volume1/git/bitcoin-price-tracker.git

# Push to main
git branch -M main
git push -u origin main
```

### Step 6: Create Branch Structure

```bash
# Create develop branch for staging
git checkout -b develop
git push -u origin develop

# Create gitflow structure
git checkout main
git tag v1.0.0
git push --tags

# Back to develop for daily work
git checkout develop
```

## 🔄 Branching Strategy

### GitFlow Model

```
main (production)
  ↓
  └─ v1.0.0 (tag)
  └─ v1.1.0 (tag)
  
develop (staging)
  ↓
  └─ feature/add-eur-prices
  └─ feature/hourly-aggregation
  └─ hotfix/fix-null-prices
```

### Branch Naming

```bash
# Features (new functionality)
git checkout -b feature/add-volume-weighted-price develop

# Hotfixes (urgent production fixes)
git checkout -b hotfix/fix-data-freshness main

# Releases (prepare for production)
git checkout -b release/1.1.0 develop
```

### Example Workflow

```bash
# 1. Start feature
git checkout develop
git pull origin develop
git checkout -b feature/add-7day-volatility

# 2. Make changes
vim contract.fluid.yaml
vim dbt/models/daily_price_summary.sql

# 3. Validate locally
python3 -m fluid_build.cli validate contract.fluid.yaml
cd dbt && dbt test

# 4. Commit
git add .
git commit -m "feat: Add 7-day rolling volatility metric

- Added volatility_7d field to daily_price_summary
- Updated dbt model with STDDEV calculation
- Added dbt test for positive volatility"

# 5. Push and create PR
git push origin feature/add-7day-volatility

# 6. Create PR: feature → develop
# Jenkins runs CI/CD, deploys to staging

# 7. After testing, merge to develop
git checkout develop
git merge --no-ff feature/add-7day-volatility
git push origin develop

# 8. Create release
git checkout -b release/1.1.0 develop
git push origin release/1.1.0

# 9. Merge to main for production
git checkout main
git merge --no-ff release/1.1.0
git tag -a v1.1.0 -m "Release 1.1.0: Added 7-day volatility"
git push origin main --tags
```

## 🤖 Jenkins Configuration

### Multibranch Pipeline

Create Jenkins multibranch pipeline job:

```groovy
// In Jenkins
New Item → Multibranch Pipeline
  Name: bitcoin-price-tracker
  Branch Sources → Git
    Remote URL: ssh://admin@synology:/volume1/git/bitcoin-price-tracker.git
    Credentials: synology-git-credentials
  Build Configuration
    Script Path: Jenkinsfile
  Scan Multibranch Pipeline Triggers
    ✓ Periodically if not otherwise run (15 minutes)
```

### Branch-Specific Deployment

Update Jenkinsfile to handle branches:

```groovy
pipeline {
    agent any
    
    environment {
        // Determine environment from branch
        DEPLOY_ENV = "${env.BRANCH_NAME == 'main' ? 'production' : 'staging'}"
        GCP_PROJECT_ID = "${env.BRANCH_NAME == 'main' ? 'prod-project' : 'staging-project'}"
    }
    
    stages {
        stage('Deploy') {
            steps {
                script {
                    if (env.BRANCH_NAME == 'main') {
                        // Production requires approval
                        input message: 'Deploy to production?'
                    }
                    sh "./scripts/run-complete-example.sh"
                }
            }
        }
    }
}
```

## 🔗 Integration with fluid-mono

Keep the standalone repo connected to the main framework:

### Option 1: Git Submodule (Not Recommended)

```bash
# In fluid-mono
cd examples
git submodule add ssh://synology/bitcoin-price-tracker.git bitcoin-tracker
```

**Pros:** Keeps example in fluid-mono  
**Cons:** Submodule complexity, harder to sync

### Option 2: Separate Repos + Periodic Sync (Recommended)

```bash
# Create sync script in fluid-mono
cat > sync-bitcoin-tracker-example.sh << 'EOF'
#!/bin/bash
# Sync changes from standalone repo to example directory

STANDALONE_REPO="ssh://synology/bitcoin-price-tracker.git"
EXAMPLE_DIR="examples/bitcoin-tracker"

# Clone latest
git clone ${STANDALONE_REPO} /tmp/bitcoin-tracker-sync

# Copy contract and docs back to fluid-mono
cp /tmp/bitcoin-tracker-sync/contract.fluid.yaml ${EXAMPLE_DIR}/
cp /tmp/bitcoin-tracker-sync/Jenkinsfile ${EXAMPLE_DIR}/
cp -r /tmp/bitcoin-tracker-sync/docs/* ${EXAMPLE_DIR}/

# Clean up
rm -rf /tmp/bitcoin-tracker-sync

echo "✅ Synced bitcoin-tracker from standalone repo"
EOF
chmod +x sync-bitcoin-tracker-example.sh
```

### Option 3: Completely Separate (Best for Testing)

Keep them independent:
- **fluid-mono** - Framework development
- **bitcoin-price-tracker** - Real-world testing/template

Manually port improvements both ways as needed.

## 📈 Testing Framework Changes

With standalone repo, you can test CLI changes:

```bash
# 1. Make changes to fluid_build CLI in fluid-mono
cd ~/fluid-mono/fluid_build
vim cli.py

# 2. Install locally
pip install -e .

# 3. Test in standalone repo
cd ~/bitcoin-price-tracker
python3 -m fluid_build.cli validate contract.fluid.yaml

# 4. If it works, commit to both repos
cd ~/fluid-mono
git commit -m "feat(cli): Improve validation error messages"

cd ~/bitcoin-price-tracker
# Update requirements.txt to use new version
git commit -m "chore: Update fluid-forge to v0.8.0"
```

## 🎯 Next Steps

1. **Create Repository** on Synology Git server
2. **Extract Example** using steps above
3. **Configure Jenkins** multibranch pipeline
4. **Test Workflow** with a feature branch
5. **Document Learnings** to improve both repos
6. **Create Templates** based on this pattern

## 💡 Pro Tips

- **Use Tags** for production releases (`v1.0.0`, `v1.1.0`)
- **Protect Branches** - Require PR for main/develop
- **Enforce Tests** - Jenkins must pass before merge
- **Automate Versioning** - Bump version in contract on release
- **Generate Changelog** from commit messages
- **Mirror to GitHub** for public showcase (optional)

## 🔒 Security Notes

- Add `.gitignore` for secrets (service account keys)
- Use environment variables for credentials
- Never commit `GOOGLE_APPLICATION_CREDENTIALS`
- Store secrets in Jenkins credentials store
- Use SSH keys for Git authentication

---

**Result:** You now have a realistic data product repository that mirrors how teams would use FLUID in production! 🚀
