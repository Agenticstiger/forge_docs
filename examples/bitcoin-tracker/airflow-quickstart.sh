#!/bin/bash
# Bitcoin Tracker - Airflow Quick Start
# This script sets up a local Airflow environment for the Bitcoin tracker

set -e

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║     Bitcoin Tracker - Airflow Setup                           ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
PROJECT_DIR=$(pwd)
AIRFLOW_HOME=${AIRFLOW_HOME:-$HOME/airflow}
GCP_PROJECT_ID=${GCP_PROJECT_ID:-<<YOUR_PROJECT_HERE>>}

echo -e "${BLUE}Configuration:${NC}"
echo "  Project Directory: $PROJECT_DIR"
echo "  Airflow Home: $AIRFLOW_HOME"
echo "  GCP Project: $GCP_PROJECT_ID"
echo ""

# Step 1: Check Python version
echo -e "${BLUE}STEP 1: Checking Python version...${NC}"
PYTHON_VERSION=$(python3 --version | awk '{print $2}')
echo "  Python version: $PYTHON_VERSION"
if ! python3 -c 'import sys; assert sys.version_info >= (3, 8)' 2>/dev/null; then
    echo -e "${YELLOW}⚠️  Python 3.8+ required${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Python version OK${NC}"
echo ""

# Step 2: Install Airflow dependencies
echo -e "${BLUE}STEP 2: Installing Airflow dependencies...${NC}"
pip3 install -q \
  apache-airflow==2.8.0 \
  apache-airflow-providers-google==10.12.0 \
  requests \
  google-cloud-bigquery \
  dbt-bigquery

echo -e "${GREEN}✓ Dependencies installed${NC}"
echo ""

# Step 3: Generate Airflow DAG
echo -e "${BLUE}STEP 3: Generating Airflow DAGs...${NC}"

# Create airflow/dags directory
mkdir -p airflow/dags

# Generate basic DAG using scaffold-composer
export FLUID_PROVIDER=gcp
export FLUID_PROJECT=$GCP_PROJECT_ID

python3 -m fluid_build.cli scaffold-composer contract.fluid.yaml \
  --out-dir airflow/dags

echo -e "${GREEN}✓ Generated basic DAG: airflow/dags/crypto_bitcoin_prices_gcp.py${NC}"

# Copy enhanced DAG if it exists
if [ -f "bitcoin_tracker_enhanced.py" ]; then
    cp bitcoin_tracker_enhanced.py airflow/dags/
    echo -e "${GREEN}✓ Copied enhanced DAG${NC}"
fi

# Copy ingestion script to dags folder (so Airflow can import it)
cp ingest_bitcoin_prices.py airflow/dags/
echo -e "${GREEN}✓ Copied ingestion script${NC}"
echo ""

# Step 4: Initialize Airflow
echo -e "${BLUE}STEP 4: Initializing Airflow database...${NC}"

export AIRFLOW_HOME=$AIRFLOW_HOME
export AIRFLOW__CORE__DAGS_FOLDER=$PROJECT_DIR/airflow/dags
export AIRFLOW__CORE__LOAD_EXAMPLES=False
export AIRFLOW__CORE__MAX_ACTIVE_RUNS_PER_DAG=1

# Initialize Airflow DB
airflow db init > /dev/null 2>&1

echo -e "${GREEN}✓ Airflow database initialized${NC}"
echo ""

# Step 5: Create admin user
echo -e "${BLUE}STEP 5: Creating Airflow admin user...${NC}"

# Check if user already exists
if airflow users list 2>/dev/null | grep -q "admin"; then
    echo -e "${YELLOW}⚠️  Admin user already exists${NC}"
else
    airflow users create \
      --username admin \
      --firstname Admin \
      --lastname User \
      --role Admin \
      --email admin@example.com \
      --password admin > /dev/null 2>&1
    
    echo -e "${GREEN}✓ Admin user created${NC}"
    echo "  Username: admin"
    echo "  Password: admin"
fi
echo ""

# Step 6: Set environment variables
echo -e "${BLUE}STEP 6: Configuring environment variables...${NC}"

cat > airflow/.env << EOF
# Airflow Configuration
export AIRFLOW_HOME=$AIRFLOW_HOME
export AIRFLOW__CORE__DAGS_FOLDER=$PROJECT_DIR/airflow/dags
export AIRFLOW__CORE__LOAD_EXAMPLES=False

# GCP Configuration
export GCP_PROJECT_ID=$GCP_PROJECT_ID
export FLUID_PROVIDER=gcp
export FLUID_PROJECT=$GCP_PROJECT_ID
export BQ_DATASET=crypto_data
export BQ_TABLE=bitcoin_prices

# Optional: GCP Service Account
# export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json
EOF

echo -e "${GREEN}✓ Created airflow/.env${NC}"
echo ""

# Step 7: Test DAG syntax
echo -e "${BLUE}STEP 7: Testing DAG syntax...${NC}"

python3 -c "import sys; sys.path.insert(0, 'airflow/dags'); import crypto_bitcoin_prices_gcp" 2>/dev/null
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Basic DAG syntax valid${NC}"
else
    echo -e "${YELLOW}⚠️  Could not validate basic DAG${NC}"
fi

if [ -f "airflow/dags/bitcoin_tracker_enhanced.py" ]; then
    python3 -c "import sys; sys.path.insert(0, 'airflow/dags'); import bitcoin_tracker_enhanced" 2>/dev/null
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Enhanced DAG syntax valid${NC}"
    fi
fi
echo ""

# Step 8: Create startup scripts
echo -e "${BLUE}STEP 8: Creating startup scripts...${NC}"

# Webserver script
cat > airflow/start-webserver.sh << 'EOF'
#!/bin/bash
source .env
echo "Starting Airflow webserver on http://localhost:8080"
echo "Username: admin"
echo "Password: admin"
airflow webserver --port 8080
EOF
chmod +x airflow/start-webserver.sh

# Scheduler script
cat > airflow/start-scheduler.sh << 'EOF'
#!/bin/bash
source .env
echo "Starting Airflow scheduler..."
airflow scheduler
EOF
chmod +x airflow/start-scheduler.sh

# Combined startup script
cat > airflow/start-all.sh << 'EOF'
#!/bin/bash
source .env

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║     Starting Airflow - Bitcoin Tracker                        ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "Webserver: http://localhost:8080"
echo "Username: admin"
echo "Password: admin"
echo ""
echo "Press Ctrl+C to stop all services"
echo ""

# Start webserver in background
airflow webserver --port 8080 > /tmp/airflow-webserver.log 2>&1 &
WEBSERVER_PID=$!

# Start scheduler in background
airflow scheduler > /tmp/airflow-scheduler.log 2>&1 &
SCHEDULER_PID=$!

# Wait for user interrupt
trap "kill $WEBSERVER_PID $SCHEDULER_PID; exit" INT TERM

echo "✓ Webserver started (PID: $WEBSERVER_PID)"
echo "✓ Scheduler started (PID: $SCHEDULER_PID)"
echo ""
echo "Logs:"
echo "  Webserver: /tmp/airflow-webserver.log"
echo "  Scheduler: /tmp/airflow-scheduler.log"
echo ""

wait
EOF
chmod +x airflow/start-all.sh

echo -e "${GREEN}✓ Created startup scripts${NC}"
echo "  - airflow/start-webserver.sh"
echo "  - airflow/start-scheduler.sh"
echo "  - airflow/start-all.sh"
echo ""

# Final summary
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                 ✅ SETUP COMPLETE                              ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo -e "${GREEN}Next Steps:${NC}"
echo ""
echo "1. Source environment variables:"
echo "   ${BLUE}source airflow/.env${NC}"
echo ""
echo "2. Start Airflow (choose one):"
echo ""
echo "   Option A - Start all services:"
echo "   ${BLUE}./airflow/start-all.sh${NC}"
echo ""
echo "   Option B - Start separately (2 terminals):"
echo "   Terminal 1: ${BLUE}./airflow/start-webserver.sh${NC}"
echo "   Terminal 2: ${BLUE}./airflow/start-scheduler.sh${NC}"
echo ""
echo "3. Access Airflow UI:"
echo "   URL: ${BLUE}http://localhost:8080${NC}"
echo "   Username: ${BLUE}admin${NC}"
echo "   Password: ${BLUE}admin${NC}"
echo ""
echo "4. Enable and trigger DAG:"
echo "   - Toggle DAG: ${BLUE}crypto_bitcoin_prices_gcp${NC}"
echo "   - Click 'Trigger DAG' button"
echo ""
echo "5. View execution logs in UI or:"
echo "   ${BLUE}airflow dags list-runs -d crypto_bitcoin_prices_gcp${NC}"
echo ""
echo -e "${YELLOW}Important:${NC}"
echo "  - Ensure GCP authentication is configured:"
echo "    ${BLUE}gcloud auth application-default login${NC}"
echo ""
echo "  - Or set service account key:"
echo "    ${BLUE}export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json${NC}"
echo ""
echo "📖 Full documentation: AIRFLOW_INTEGRATION.md"
echo ""
