# Bitcoin Price Tracker — AWS Athena Example

**FLUID Forge v0.7.1** · Declarative Data Product on AWS (Athena + S3)

This example demonstrates a contract-driven ETL pipeline that fetches Bitcoin prices from the CoinGecko API and stores them as Parquet in S3, queryable via AWS Athena.

Includes two contract variants:
- **`contract.fluid.yaml`** — Standard Parquet on Athena (3 currencies)
- **`contract-iceberg.fluid.yaml`** — Apache Iceberg table format (7 currencies, hidden partitioning, ACID)

---

## Prerequisites

```bash
# AWS CLI configured with valid credentials
aws sts get-caller-identity

# Python 3.11+
python3 --version

# FLUID Forge CLI installed
fluid --version
```

## Quick Start

### 1. Install Dependencies

```bash
cd bitcoin-price-tracker-0.7.1-aws-athena
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit with your AWS credentials and S3 bucket name
nano .env
source .env
```

### 3. Plan & Deploy Infrastructure

```bash
# Preview what FLUID will create (S3 bucket, Glue database, Athena table)
fluid plan contract.fluid.yaml

# Apply — creates the infrastructure declaratively
fluid apply contract.fluid.yaml
```

### 4. Run the Ingestion

```bash
# Execute the build defined in the contract
fluid execute contract.fluid.yaml
```

### 5. Query Your Data

```sql
-- In the AWS Athena console
SELECT * FROM crypto_data.bitcoin_prices
ORDER BY price_timestamp DESC
LIMIT 10;
```

---

## Iceberg Variant

The Iceberg contract adds ACID transactions, time-travel, and hidden partitioning.

```bash
# Plan & apply the Iceberg table
fluid plan contract-iceberg.fluid.yaml
fluid apply contract-iceberg.fluid.yaml

# Run the 7-currency ingestion
fluid execute contract-iceberg.fluid.yaml
```

The Iceberg contract fetches 7 currencies (USD, EUR, GBP, JPY, CNY, INR, AUD) and configures:
- Hidden partitioning by `day(price_timestamp)`
- Sort order on `price_timestamp ASC`
- Zstd compression
- Iceberg format version 2

---

## Project Structure

```
├── contract.fluid.yaml          # Standard Athena/Parquet contract (3 currencies)
├── contract-iceberg.fluid.yaml  # Iceberg variant (7 currencies, ACID)
├── runtime/
│   ├── ingest.py                # ETL script for standard contract
│   └── ingest_iceberg.py        # ETL script for Iceberg contract
├── requirements.txt             # Python dependencies
├── .env.example                 # Environment variable template
└── README.md
```

## Contract Schema

### Standard (`contract.fluid.yaml`)

| Field | Type | Description |
|-------|------|-------------|
| `price_timestamp` | timestamp | UTC time of price recording |
| `price_usd` | decimal(18,2) | Bitcoin price in USD |
| `price_eur` | decimal(18,2) | Bitcoin price in EUR |
| `price_gbp` | decimal(18,2) | Bitcoin price in GBP |
| `market_cap_usd` | decimal(20,2) | Market capitalization |
| `volume_24h_usd` | decimal(20,2) | 24h trading volume |
| `price_change_24h_pct` | decimal(10,4) | 24h price change % |
| `last_updated` | timestamp | Source data timestamp |
| `ingestion_timestamp` | timestamp | Pipeline ingestion time |

### Iceberg (`contract-iceberg.fluid.yaml`)

Extends the standard schema with 4 additional currency prices: JPY, CNY, INR, AUD.

---

## Architecture

```
contract.fluid.yaml
    │
    ├── fluid plan   → Preview actions (S3, Glue, Athena)
    ├── fluid apply  → Create infrastructure
    └── fluid execute → Run runtime/ingest.py
                            │
                            ├── Fetch from CoinGecko API
                            ├── Transform to contract schema
                            └── Write Parquet to S3
                                    │
                                    └── Query via Athena
```

## Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `AWS_REGION` | AWS region | `us-east-1` |
| `AWS_ACCESS_KEY_ID` | IAM access key | — |
| `AWS_SECRET_ACCESS_KEY` | IAM secret key | — |
| `S3_BUCKET` | Target S3 bucket name | `my-fluid-data-bucket` |
