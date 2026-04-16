#!/usr/bin/env python3
"""
Bitcoin price ingestion from CoinGecko API to BigQuery
Free tier API - no authentication required
"""
import requests
from google.cloud import bigquery
from datetime import datetime
import os
import sys


def fetch_bitcoin_price():
    """Fetch current Bitcoin price from CoinGecko API"""
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {
        "ids": "bitcoin",
        "vs_currencies": "usd,eur,gbp",
        "include_market_cap": "true",
        "include_24hr_vol": "true",
        "include_24hr_change": "true",
        "include_last_updated_at": "true"
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()["bitcoin"]
        
        return {
            "price_timestamp": datetime.now().isoformat(),
            "price_usd": data["usd"],
            "price_eur": data["eur"],
            "price_gbp": data["gbp"],
            "market_cap_usd": data["usd_market_cap"],
            "volume_24h_usd": data["usd_24h_vol"],
            "price_change_24h_percent": data.get("usd_24h_change", 0.0),
            "ingestion_timestamp": datetime.now().isoformat()
        }
    except requests.RequestException as e:
        print(f"❌ Error fetching Bitcoin price: {e}")
        sys.exit(1)


def insert_to_bigquery(row, project_id, dataset_id="crypto_data", table_id="bitcoin_prices"):
    """Insert Bitcoin price data into BigQuery"""
    try:
        client = bigquery.Client(project=project_id)
        table_ref = f"{project_id}.{dataset_id}.{table_id}"
        
        errors = client.insert_rows_json(table_ref, [row])
        
        if errors:
            raise Exception(f"BigQuery insert errors: {errors}")
        
        print(f"✅ Inserted Bitcoin price: ${row['price_usd']:,.2f} at {row['price_timestamp']}")
        return True
    except Exception as e:
        print(f"❌ Error inserting to BigQuery: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # Get project ID from environment or command line
    project_id = os.getenv("GCP_PROJECT_ID")
    
    if not project_id and len(sys.argv) > 1:
        project_id = sys.argv[1]
    
    if not project_id:
        print("❌ Error: GCP_PROJECT_ID environment variable not set")
        print("Usage: python ingest_bitcoin_prices.py [PROJECT_ID]")
        print("   or: export GCP_PROJECT_ID=your-project-id && python ingest_bitcoin_prices.py")
        sys.exit(1)
    
    print(f"🚀 Fetching Bitcoin price for project: {project_id}")
    
    # Fetch price
    price_data = fetch_bitcoin_price()
    
    # Insert to BigQuery
    insert_to_bigquery(price_data, project_id)
    
    # Print summary
    print(f"\n📊 Summary:")
    print(f"   Price USD: ${price_data['price_usd']:,.2f}")
    print(f"   Price EUR: €{price_data['price_eur']:,.2f}")
    print(f"   Price GBP: £{price_data['price_gbp']:,.2f}")
    print(f"   Market Cap: ${price_data['market_cap_usd']:,.0f}")
    print(f"   24h Volume: ${price_data['volume_24h_usd']:,.0f}")
    print(f"   24h Change: {price_data['price_change_24h_percent']:,.2f}%")
