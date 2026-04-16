#!/usr/bin/env python3
"""
Bitcoin price ingestion from CoinGecko API to BigQuery.
Referenced by contract.fluid.yaml as hybrid-reference pattern.
"""
import requests
from google.cloud import bigquery
from datetime import datetime
import os
import sys


def main():
    """Fetch Bitcoin price from CoinGecko API and insert to BigQuery"""
    print("🚀 Starting Bitcoin price ingestion...")
    
    # Fetch from CoinGecko API (free tier, no auth required)
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {
        "ids": "bitcoin",
        "vs_currencies": "usd,eur,gbp",
        "include_market_cap": "true",
        "include_24hr_vol": "true",
        "include_24hr_change": "true"
    }
    
    try:
        print("📡 Fetching Bitcoin price from CoinGecko API...")
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()["bitcoin"]
        print(f"✅ API response received: ${data['usd']:,.2f}")
    except requests.RequestException as e:
        print(f"❌ Error fetching from API: {e}")
        sys.exit(1)
    
    # Prepare row for BigQuery
    row = {
        "price_timestamp": datetime.now().isoformat(),
        "price_usd": float(data["usd"]),
        "price_eur": float(data["eur"]),
        "price_gbp": float(data["gbp"]),
        "market_cap_usd": float(data["usd_market_cap"]),
        "volume_24h_usd": float(data["usd_24h_vol"]),
        "price_change_24h_percent": float(data.get("usd_24h_change", 0.0)),
        "ingestion_timestamp": datetime.now().isoformat()
    }
    
    # Insert to BigQuery
    project_id = os.getenv("GCP_PROJECT_ID", "<<YOUR_PROJECT_HERE>>")
    dataset_id = "crypto_data"
    table_id = "bitcoin_prices"
    
    try:
        print(f"💾 Inserting to BigQuery: {project_id}.{dataset_id}.{table_id}")
        client = bigquery.Client(project=project_id)
        table_ref = f"{project_id}.{dataset_id}.{table_id}"
        
        errors = client.insert_rows_json(table_ref, [row])
        
        if errors:
            print(f"❌ BigQuery insert errors: {errors}")
            sys.exit(1)
        
        print(f"✅ Successfully inserted Bitcoin price")
        print(f"\n📊 Summary:")
        print(f"   Price USD: ${row['price_usd']:,.2f}")
        print(f"   Price EUR: €{row['price_eur']:,.2f}")
        print(f"   Price GBP: £{row['price_gbp']:,.2f}")
        print(f"   Market Cap: ${row['market_cap_usd']:,.0f}")
        print(f"   24h Volume: ${row['volume_24h_usd']:,.0f}")
        print(f"   24h Change: {row['price_change_24h_percent']:+.2f}%")
        print(f"   Timestamp: {row['price_timestamp']}")
        
        return row
        
    except Exception as e:
        print(f"❌ Error inserting to BigQuery: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
