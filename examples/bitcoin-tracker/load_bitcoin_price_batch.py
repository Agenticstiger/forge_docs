#!/usr/bin/env python3
"""
Bitcoin price ingestion using batch load (free tier compatible)
"""
import requests
from google.cloud import bigquery
from datetime import datetime
import os
import json
import tempfile

def fetch_bitcoin_price():
    """Fetch current Bitcoin price from CoinGecko API"""
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {
        "ids": "bitcoin",
        "vs_currencies": "usd,eur,gbp",
        "include_market_cap": "true",
        "include_24hr_vol": "true",
        "include_24hr_change": "true",
    }
    
    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()["bitcoin"]
    
    return {
        "price_timestamp": datetime.now().isoformat(),
        "price_usd": float(data["usd"]),
        "price_eur": float(data["eur"]),
        "price_gbp": float(data["gbp"]),
        "market_cap_usd": float(data["usd_market_cap"]),
        "volume_24h_usd": float(data["usd_24h_vol"]),
        "price_change_24h_percent": float(data.get("usd_24h_change", 0.0)),
        "ingestion_timestamp": datetime.now().isoformat()
    }

def load_to_bigquery_batch(row, project_id, dataset_id="crypto_data", table_id="bitcoin_prices"):
    """Load Bitcoin price using batch load (free tier)"""
    client = bigquery.Client(project=project_id)
    table_ref = f"{project_id}.{dataset_id}.{table_id}"
    
    # Write to temp JSON file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(row, f)
        temp_file = f.name
    
    try:
        # Configure load job
        job_config = bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
            write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
        )
        
        # Load from file
        with open(temp_file, 'rb') as source_file:
            job = client.load_table_from_file(source_file, table_ref, job_config=job_config)
        
        job.result()  # Wait for completion
        
        print(f"✅ Loaded Bitcoin price: ${row['price_usd']:,.2f} at {row['price_timestamp']}")
        print(f"📊 Market Cap: ${row['market_cap_usd']:,.0f}")
        print(f"📈 24h Volume: ${row['volume_24h_usd']:,.0f}")
        print(f"📉 24h Change: {row['price_change_24h_percent']:.2f}%")
        
    finally:
        os.unlink(temp_file)

if __name__ == "__main__":
    project_id = os.getenv("GCP_PROJECT_ID", "<<YOUR_PROJECT_HERE>>")
    
    print(f"🚀 Fetching Bitcoin price...")
    price_data = fetch_bitcoin_price()
    
    print(f"💾 Loading to BigQuery (project: {project_id})...")
    load_to_bigquery_batch(price_data, project_id)
