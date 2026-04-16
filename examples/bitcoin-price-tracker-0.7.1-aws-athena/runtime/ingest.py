#!/usr/bin/env python3
"""
Bitcoin Price Ingestion Pipeline for AWS Athena - FLUID 0.7.1

Fetches Bitcoin price from CoinGecko API and stores in S3 as Parquet,
queryable via AWS Athena.

Platform: AWS Athena + S3
Architecture: Serverless, declarative data product pattern
"""

import os
import sys
import json
import requests
import tempfile
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Dict, Any, Optional

# Structured logging
def log(level: str, message: str, **kwargs):
    """Structured logging for observability."""
    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
    emoji = {
        'DEBUG': '🔍',
        'INFO': 'ℹ️',
        'SUCCESS': '✅',
        'WARNING': '⚠️',
        'ERROR': '❌'
    }.get(level, 'ℹ️')
    
    print(f"[{timestamp}] {emoji} {level:7} | {message}")
    if kwargs:
        for key, value in kwargs.items():
            print(f"                          {key}: {value}")


def load_contract(contract_path: Path) -> Dict[str, Any]:
    """Load FLUID contract and extract AWS configuration."""
    import yaml
    
    log('DEBUG', f'Looking for contract at: {contract_path}')
    
    if not contract_path.exists():
        raise FileNotFoundError(f"Contract not found: {contract_path}")
    
    with open(contract_path) as f:
        contract = yaml.safe_load(f)
    
    # Extract AWS binding configuration
    exposes = contract.get('exposes', [])
    if not exposes:
        raise ValueError("Contract must have at least one expose")
    
    binding = exposes[0].get('binding', {})
    location = binding.get('location', {})
    
    # Resolve environment variable templates
    def resolve_template(value: str) -> str:
        """Resolve {{ env.VAR }} patterns from os.environ."""
        if isinstance(value, str) and value.startswith('{{ env.'):
            env_var = value.split('{{ env.')[1].split(' }}')[0].strip()
            resolved = os.environ.get(env_var)
            if resolved:
                return resolved
            log('WARNING', f'Env var {env_var} not set, template unresolved')
            return value
        return value
    
    bucket = resolve_template(location.get('bucket', ''))
    region = resolve_template(location.get('region', ''))
    
    # Fallback: derive missing values from AWS context (matches planner convention)
    if not region or '{{' in region:
        region = os.environ.get('AWS_DEFAULT_REGION', 'eu-central-1')
        log('INFO', f'Region derived from fallback: {region}')
    
    if not bucket or '{{' in bucket:
        try:
            import boto3
            account_id = boto3.client('sts', region_name=region).get_caller_identity()['Account']
            bucket = f"{account_id}-fluid-data"
            log('INFO', f'Bucket auto-derived from STS: {bucket}')
        except Exception as e:
            log('ERROR', f'Cannot derive bucket from STS: {e}')
            raise ValueError(
                "S3_BUCKET env var not set and STS lookup failed. "
                "Set S3_BUCKET or configure AWS credentials."
            )

    config = {
        'platform': binding.get('platform'),
        'database': location.get('database'),
        'table': location.get('table'),
        'bucket': bucket,
        'path': location.get('path', 'data/'),
        'region': region,
    }
    
    log('SUCCESS', 'Contract loaded successfully', config=json.dumps(config, indent=2))
    
    return config


def fetch_bitcoin_price() -> Dict[str, Any]:
    """Fetch current Bitcoin price from CoinGecko API."""
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {
        "ids": "bitcoin",
        "vs_currencies": "usd,eur,gbp",
        "include_market_cap": "true",
        "include_24hr_vol": "true",
        "include_24hr_change": "true",
        "include_last_updated_at": "true"
    }
    
    log('INFO', 'Fetching Bitcoin price from CoinGecko API', url=url)
    
    start = datetime.now(timezone.utc)
    response = requests.get(url, params=params, timeout=10)
    elapsed_ms = (datetime.now(timezone.utc) - start).total_seconds() * 1000
    
    response.raise_for_status()
    data = response.json()
    
    bitcoin_data = data.get('bitcoin', {})
    
    log('SUCCESS', f'API call completed in {elapsed_ms:.0f}ms',
        status_code=response.status_code,
        price_usd=bitcoin_data.get('usd'),
        price_eur=bitcoin_data.get('eur'),
        price_gbp=bitcoin_data.get('gbp'),
        change_24h=f"{bitcoin_data.get('usd_24h_change', 0):.2f}%")
    
    return bitcoin_data


def transform_to_schema(bitcoin_data: Dict[str, Any]) -> Dict[str, Any]:
    """Transform API data to contract schema."""
    now = datetime.now(timezone.utc)
    last_updated_unix = bitcoin_data.get('last_updated_at')
    last_updated = datetime.fromtimestamp(last_updated_unix, tz=timezone.utc) if last_updated_unix else now
    
    def safe_decimal(value: Any, decimals: int = 2) -> Optional[Decimal]:
        if value is None:
            return None
        try:
            return Decimal(str(round(float(value), decimals)))
        except (ValueError, TypeError):
            return None
    
    record = {
        'price_timestamp': now.isoformat(),
        'price_usd': safe_decimal(bitcoin_data.get('usd')),
        'price_eur': safe_decimal(bitcoin_data.get('eur')),
        'price_gbp': safe_decimal(bitcoin_data.get('gbp')),
        'market_cap_usd': safe_decimal(bitcoin_data.get('usd_market_cap'), decimals=2),
        'volume_24h_usd': safe_decimal(bitcoin_data.get('usd_24h_vol'), decimals=2),
        'price_change_24h_pct': safe_decimal(bitcoin_data.get('usd_24h_change'), decimals=4),
        'last_updated': last_updated.isoformat(),
        'ingestion_timestamp': now.isoformat()
    }
    
    log('INFO', 'Transformed API data to schema',
        fields=len(record),
        price_usd=f"${record['price_usd']:,.2f}" if record['price_usd'] else None,
        market_cap=f"${record['market_cap_usd']:,.0f}" if record['market_cap_usd'] else None,
        volume_24h=f"${record['volume_24h_usd']:,.0f}" if record['volume_24h_usd'] else None)
    
    return record


def load_to_athena_s3(record: Dict[str, Any], bucket: str, path: str, region: str, database: str, table: str) -> bool:
    """Load data to S3 as Parquet for Athena querying."""
    log('INFO', 'Loading data to S3 for Athena',
        bucket=bucket,
        path=path,
        database=database,
        table=table,
        region=region)
    
    try:
        import boto3
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as e:
        log('ERROR', f'Missing dependency: {e}')
        log('INFO', 'Install with: pip install boto3 pyarrow')
        return False
    
    try:
        s3 = boto3.client('s3', region_name=region)
        
        # Convert Decimal to float for Parquet
        parquet_record = {}
        for key, value in record.items():
            if isinstance(value, Decimal):
                parquet_record[key] = float(value)
            else:
                parquet_record[key] = value
        
        # Create PyArrow table
        table_pa = pa.table({
            key: [value] for key, value in parquet_record.items()
        })
        
        # Write to Parquet in memory
        with tempfile.NamedTemporaryFile(suffix='.parquet', delete=False) as tmp:
            tmp_path = tmp.name
        
        pq.write_table(table_pa, tmp_path)
        file_size_kb = os.path.getsize(tmp_path) / 1024
        
        # Upload to S3 with partitioning by date
        now = datetime.now(timezone.utc)
        date_partition = now.strftime('%Y/%m/%d')
        ts_label = now.strftime('%Y%m%d_%H%M%S')
        s3_key = f"{path}{date_partition}/bitcoin_price_{ts_label}.parquet"
        
        log('INFO', f'Uploading to S3: s3://{bucket}/{s3_key}')
        
        with open(tmp_path, 'rb') as f:
            s3.put_object(Bucket=bucket, Key=s3_key, Body=f)
        
        # Cleanup temp file
        os.unlink(tmp_path)
        
        log('SUCCESS', 'Data loaded to S3 successfully',
            s3_uri=f's3://{bucket}/{s3_key}',
            file_size_kb=f'{file_size_kb:.1f}')
        
        return True
        
    except Exception as e:
        log('ERROR', f'S3 load failed: {e}')
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main pipeline execution."""
    pipeline_start = datetime.now(timezone.utc)
    
    print("=" * 80)
    print("🚀 Bitcoin Price Ingestion Pipeline - FLUID 0.7.1 (AWS Athena)")
    print("=" * 80)
    
    log('INFO', 'Pipeline started', timestamp=pipeline_start.isoformat())
    
    try:
        # Step 1: Load contract
        contract_path = Path(__file__).parent.parent / 'contract.fluid.yaml'
        config = load_contract(contract_path)
        
        log('INFO', f'Configuration loaded from contract ({config["platform"]})',
            database=config['database'],
            table=config['table'],
            bucket=config['bucket'],
            region=config['region'])
        
        # Step 2: Fetch data
        log('INFO', '=== STEP 2: Fetch Bitcoin Price ===')
        bitcoin_data = fetch_bitcoin_price()
        
        # Step 3: Transform
        log('INFO', '=== STEP 3: Transform to Schema ===')
        record = transform_to_schema(bitcoin_data)
        
        # Step 4: Load
        log('INFO', '=== STEP 4: Load to S3/Athena ===')
        success = load_to_athena_s3(
            record,
            config['bucket'],
            config['path'],
            config['region'],
            config['database'],
            config['table']
        )
        
        if not success:
            sys.exit(1)
        
        pipeline_duration = (datetime.now(timezone.utc) - pipeline_start).total_seconds()
        
        print("=" * 80)
        log('SUCCESS', f'Pipeline completed in {pipeline_duration:.2f}s',
            platform=config['platform'],
            btc_price=f"${record['price_usd']:,.2f}" if record['price_usd'] else None,
            change_24h=f"{record['price_change_24h_pct']:.2f}%" if record['price_change_24h_pct'] else None,
            market_cap=f"${record['market_cap_usd']:,.0f}" if record['market_cap_usd'] else None,
            volume_24h=f"${record['volume_24h_usd']:,.0f}" if record['volume_24h_usd'] else None)
        print("=" * 80)
        
    except Exception as e:
        pipeline_duration = (datetime.now(timezone.utc) - pipeline_start).total_seconds()
        print("=" * 80)
        log('ERROR', f'Pipeline completed with errors after {pipeline_duration:.2f}s')
        print("=" * 80)
        raise


if __name__ == '__main__':
    main()
