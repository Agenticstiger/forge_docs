#!/usr/bin/env python3
"""
Bitcoin Price Ingestion Script - Enhanced with Structured Logging
Fetches real-time Bitcoin price data from CoinGecko API and loads to BigQuery.

This script is called by the FLUID build system according to execution configuration.
"""
import os
import sys
from datetime import datetime, timezone
import requests
from google.cloud import bigquery
import json
import yaml
from pathlib import Path
import tempfile


def log(level, message, **kwargs):
    """Structured logging with timestamp and level."""
    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
    icon = {
        'INFO': 'ℹ️ ',
        'SUCCESS': '✅',
        'WARNING': '⚠️ ',
        'ERROR': '❌',
        'DEBUG': '🔍'
    }.get(level, '  ')
    
    print(f"[{timestamp}] {icon} {level:7s} | {message}")
    
    # Print additional context if provided
    for key, value in kwargs.items():
        if isinstance(value, (dict, list)):
            print(f"{'':23s}   {key}: {json.dumps(value, indent=2, default=str)}")
        else:
            print(f"{'':23s}   {key}: {value}")


def load_contract_config():
    """Load configuration from FLUID contract.fluid.yaml."""
    contract_path = Path(__file__).parent.parent / 'contract.fluid.yaml'
    
    log('DEBUG', f"Looking for contract at: {contract_path}")
    
    if not contract_path.exists():
        log('WARNING', f"Contract file not found")
        return None
    
    try:
        with open(contract_path, 'r') as f:
            contract = yaml.safe_load(f)
        
        exposes = contract.get('exposes', [])
        if exposes:
            binding = exposes[0].get('binding', {})
            location = binding.get('location', {})
            
            config = {
                'project': location.get('project'),
                'dataset': location.get('dataset'),
                'table': location.get('table'),
                'region': location.get('region')
            }
            
            log('SUCCESS', 'Contract loaded successfully', config=config)
            return config
        else:
            log('WARNING', 'No exposes found in contract')
            return None
            
    except Exception as e:
        log('ERROR', f"Failed to load contract: {e}")
        return None


def fetch_bitcoin_price():
    """Fetch Bitcoin price data from CoinGecko API."""
    api_url = "https://api.coingecko.com/api/v3/simple/price"
    
    params = {
        'ids': 'bitcoin',
        'vs_currencies': 'usd,eur,gbp',
        'include_market_cap': 'true',
        'include_24hr_vol': 'true',
        'include_24hr_change': 'true',
        'include_last_updated_at': 'true'
    }
    
    log('INFO', 'Fetching Bitcoin price from CoinGecko API', url=api_url)
    
    try:
        start = datetime.now(timezone.utc)
        response = requests.get(api_url, params=params, timeout=10)
        elapsed_ms = (datetime.now(timezone.utc) - start).total_seconds() * 1000
        
        response.raise_for_status()
        data = response.json()
        
        bitcoin_data = data['bitcoin']
        
        log('SUCCESS', f'API call completed in {elapsed_ms:.0f}ms',
            status_code=response.status_code,
            price_usd=bitcoin_data.get('usd'),
            price_eur=bitcoin_data.get('eur'),
            price_gbp=bitcoin_data.get('gbp'),
            change_24h=f"{bitcoin_data.get('usd_24h_change', 0):.2f}%")
        
        return bitcoin_data
    
    except requests.exceptions.HTTPError as e:
        log('ERROR', f'API HTTP error: {e.response.status_code}', 
            reason=e.response.reason,
            url=e.response.url)
        raise
    except requests.exceptions.Timeout:
        log('ERROR', 'API request timed out after 10 seconds')
        raise
    except requests.exceptions.RequestException as e:
        log('ERROR', f'API request failed: {e}')
        raise


def transform_to_bigquery_record(bitcoin_data):
    """Transform API response to BigQuery schema format."""
    now = datetime.now(timezone.utc)
    
    # Convert Unix timestamp to datetime
    last_updated_unix = bitcoin_data.get('last_updated_at')
    last_updated = datetime.fromtimestamp(last_updated_unix, tz=timezone.utc) if last_updated_unix else now
    
    # BigQuery NUMERIC has precision limits - round to 9 decimal places
    def safe_numeric(value, decimals=9):
        """Convert to float and round to avoid BigQuery NUMERIC precision errors."""
        return round(float(value), decimals) if value is not None else 0.0
    
    record = {
        'price_timestamp': now.isoformat(),
        'price_usd': safe_numeric(bitcoin_data.get('usd')),
        'price_eur': safe_numeric(bitcoin_data.get('eur')),
        'price_gbp': safe_numeric(bitcoin_data.get('gbp')),
        'market_cap_usd': safe_numeric(bitcoin_data.get('usd_market_cap'), decimals=2),
        'volume_24h_usd': safe_numeric(bitcoin_data.get('usd_24h_vol'), decimals=2),
        'price_change_24h': safe_numeric(bitcoin_data.get('usd_24h_change'), decimals=4),
        'last_updated': last_updated.isoformat(),
        'ingestion_timestamp': now.isoformat()
    }
    
    log('INFO', 'Transformed API data to BigQuery record',
        fields=len(record),
        price_usd=f"${record['price_usd']:,.2f}",
        market_cap=f"${record['market_cap_usd']:,.0f}",
        volume_24h=f"${record['volume_24h_usd']:,.0f}")
    
    return record


def load_to_bigquery(record, project, dataset, table):
    """Load record to BigQuery using batch load (free tier compatible)."""
    
    table_id = f"{project}.{dataset}.{table}"
    
    log('INFO', f'Preparing BigQuery load', table=table_id)
    
    try:
        client = bigquery.Client(project=project)
        
        # Get table metadata and count rows before insert
        try:
            table_ref = client.get_table(table_id)
            rows_before = table_ref.num_rows
            log('INFO', f'Table verified', 
                rows=rows_before,
                created=table_ref.created.isoformat() if table_ref.created else 'unknown',
                size_mb=round(table_ref.num_bytes / 1024 / 1024, 2) if table_ref.num_bytes else 0)
        except Exception as e:
            log('ERROR', f'Table not accessible: {e}')
            log('WARNING', 'Run "fluid apply contract.fluid.yaml" first to create infrastructure')
            return False
        
        # Batch load (free tier compatible)
        log('INFO', 'Using batch load (free tier compatible)')
        
        job_config = bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
            autodetect=False,
            write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
        )
        
        # Write to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write(json.dumps(record) + '\n')
            temp_file = f.name
        
        log('DEBUG', f'Created temp file: {temp_file}')
        
        # Load from file
        start = datetime.now(timezone.utc)
        with open(temp_file, 'rb') as source_file:
            job = client.load_table_from_file(
                source_file,
                table_id,
                job_config=job_config
            )
            
            log('INFO', f'Load job submitted', job_id=job.job_id)
            
            # Wait for completion
            job.result()
            
        elapsed_ms = (datetime.now(timezone.utc) - start).total_seconds() * 1000
        
        # Cleanup
        os.unlink(temp_file)
        
        # Verify insert by querying latest row (avoiding policy-tagged columns)
        # Note: price_usd/eur/gbp have policy tags that may require fine-grained reader permission
        # We query non-protected columns to verify the insert succeeded
        query = f"""
            SELECT price_timestamp, price_change_24h, ingestion_timestamp
            FROM `{table_id}`
            ORDER BY ingestion_timestamp DESC
            LIMIT 1
        """
        
        try:
            latest = list(client.query(query).result())[0]
            log('SUCCESS', f'Record loaded successfully in {elapsed_ms:.0f}ms',
                job_id=job.job_id,
                rows_loaded=job.output_rows,
                latest_timestamp=latest['ingestion_timestamp'].isoformat())
        except Exception as verify_err:
            # If verification query fails (e.g., policy tag permissions), that's ok
            # The load job succeeded - we just can't verify by querying
            log('WARNING', f'Record loaded but verification query failed: {verify_err}',
                job_id=job.job_id,
                rows_loaded=job.output_rows,
                note='Load succeeded but query blocked by policy tags - this is expected without fine-grained reader permission')
        
        return True
    
    except Exception as e:
        log('ERROR', f'BigQuery load failed: {e}')
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main execution flow."""
    pipeline_start = datetime.now(timezone.utc)
    
    print("\n" + "=" * 80)
    print("🚀 Bitcoin Price Ingestion Pipeline - FLUID 0.7.1")
    print("=" * 80)
    log('INFO', f'Pipeline started', timestamp=pipeline_start.isoformat())
    print()
    
    # Load configuration from contract (single source of truth)
    contract_config = load_contract_config()
    
    # DECLARATIVE ARCHITECTURE:
    # Contract is the ONLY source of truth - no environment variable overrides
    # This ensures consistency between 'fluid apply' and 'fluid execute'
    
    if not contract_config:
        log('ERROR', 'Contract configuration required - cannot proceed without contract')
        log('ERROR', 'Ensure contract.fluid.yaml is accessible and properly formatted')
        raise RuntimeError('Contract file is required for declarative execution')
    
    # Read ONLY from contract - no fallbacks, no env var overrides
    project = contract_config.get('project')
    dataset = contract_config.get('dataset')
    table = contract_config.get('table')
    
    # Validate required fields
    if not all([project, dataset, table]):
        log('ERROR', 'Contract missing required fields',
            project=project,
            dataset=dataset,
            table=table)
        raise ValueError('Contract must specify project, dataset, and table')
    
    log('INFO', 'Configuration loaded from contract',
        project=project,
        dataset=dataset,
        table=table)
    print()
    
    try:
        # Step 1: Fetch data
        log('INFO', '=== STEP 1: Fetch Bitcoin Price ===')
        bitcoin_data = fetch_bitcoin_price()
        print()
        
        # Step 2: Transform
        log('INFO', '=== STEP 2: Transform to BigQuery Schema ===')
        record = transform_to_bigquery_record(bitcoin_data)
        print()
        
        # Step 3: Load
        log('INFO', '=== STEP 3: Load to BigQuery ===')
        success = load_to_bigquery(record, project, dataset, table)
        print()
        
        # Summary
        pipeline_duration = (datetime.now(timezone.utc) - pipeline_start).total_seconds()
        
        print("=" * 80)
        if success:
            log('SUCCESS', f'Pipeline completed in {pipeline_duration:.2f}s',
                btc_price=f"${record['price_usd']:,.2f}",
                change_24h=f"{record['price_change_24h']:.2f}%",
                market_cap=f"${record['market_cap_usd']:,.0f}",
                volume_24h=f"${record['volume_24h_usd']:,.0f}")
            print("=" * 80 + "\n")
            return 0
        else:
            log('ERROR', f'Pipeline completed with errors after {pipeline_duration:.2f}s')
            print("=" * 80 + "\n")
            return 1
    
    except Exception as e:
        pipeline_duration = (datetime.now(timezone.utc) - pipeline_start).total_seconds()
        print()
        print("=" * 80)
        log('ERROR', f'Pipeline failed after {pipeline_duration:.2f}s: {e}')
        import traceback
        traceback.print_exc()
        print("=" * 80 + "\n")
        return 1


if __name__ == '__main__':
    sys.exit(main())
