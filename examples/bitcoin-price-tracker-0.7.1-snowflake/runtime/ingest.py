#!/usr/bin/env python3
"""
Bitcoin Price Ingestion Pipeline for Snowflake - FLUID 0.7.1

Fetches Bitcoin price from CoinGecko API and loads to Snowflake.

Platform: Snowflake Data Cloud
Architecture: Declarative data product pattern
"""

import os
import sys
import json
import re
import requests
import snowflake.connector
import yaml
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional


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
            if isinstance(value, (dict, list)):
                print(f"                          {key}: {json.dumps(value, indent=2, default=str)}")
            else:
                print(f"                          {key}: {value}")


def load_contract(contract_path: Path) -> Dict[str, Any]:
    """Load FLUID contract and extract Snowflake configuration."""
    log('DEBUG', f'Looking for contract at: {contract_path}')

    if not contract_path.exists():
        raise FileNotFoundError(f"Contract not found: {contract_path}")

    with open(contract_path) as f:
        contract = yaml.safe_load(f)

    exposes = contract.get('exposes', [])
    if not exposes:
        raise ValueError("Contract must have at least one expose")

    binding = exposes[0].get('binding', {})
    location = binding.get('location', {})

    # Resolve {{ env.VAR }} templates
    def resolve_template(value: str) -> str:
        if isinstance(value, str) and '{{' in value:
            match = re.search(r'\{\{\s*env\.(\w+)\s*\}\}', value)
            if match:
                env_var = match.group(1)
                resolved = os.environ.get(env_var)
                if resolved:
                    return resolved
                log('WARNING', f'Env var {env_var} not set, template unresolved')
        return value if isinstance(value, str) else ''

    config = {
        'platform': binding.get('platform'),
        'account': resolve_template(location.get('account', '')),
        'database': location.get('database'),
        'schema': location.get('schema'),
        'table': location.get('table'),
    }

    log('SUCCESS', 'Contract loaded successfully', config=config)
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

    try:
        start = datetime.now(timezone.utc)
        response = requests.get(url, params=params, timeout=10)
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
            reason=e.response.reason)
        raise
    except requests.exceptions.Timeout:
        log('ERROR', 'API request timed out after 10s')
        raise
    except requests.exceptions.RequestException as e:
        log('ERROR', f'API request failed: {e}')
        raise


def transform_to_schema(bitcoin_data: Dict[str, Any]) -> Dict[str, Any]:
    """Transform API data to contract schema."""
    now = datetime.now(timezone.utc)
    last_updated_unix = bitcoin_data.get('last_updated_at')
    last_updated = datetime.fromtimestamp(last_updated_unix, tz=timezone.utc) if last_updated_unix else now

    def safe_numeric(value: Any, decimals: int = 2) -> float:
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

    log('INFO', 'Transformed API data to schema',
        fields=len(record),
        price_usd=f"${record['price_usd']:,.2f}",
        market_cap=f"${record['market_cap_usd']:,.0f}",
        volume_24h=f"${record['volume_24h_usd']:,.0f}")

    return record


def load_to_snowflake(record: Dict[str, Any], account: str, database: str,
                      schema: str, table: str) -> bool:
    """Load data to Snowflake table."""
    log('INFO', 'Loading data to Snowflake',
        account=account,
        database=database,
        schema=schema,
        table=table)

    try:
        user = os.environ.get('SNOWFLAKE_USER')
        password = os.environ.get('SNOWFLAKE_PASSWORD')
        warehouse = os.environ.get('SNOWFLAKE_WAREHOUSE', 'COMPUTE_WH')
        role = os.environ.get('SNOWFLAKE_ROLE', 'SYSADMIN')

        if not user or not password:
            raise ValueError('SNOWFLAKE_USER and SNOWFLAKE_PASSWORD must be set')

        conn = snowflake.connector.connect(
            account=account,
            user=user,
            password=password,
            warehouse=warehouse,
            database=database,
            schema=schema,
            role=role
        )

        cursor = conn.cursor()

        try:
            cursor.execute(f"USE WAREHOUSE {warehouse}")
        except Exception as wh_error:
            log('ERROR', f'Warehouse {warehouse} not accessible',
                error=str(wh_error))
            raise

        cursor.execute(f"USE DATABASE {database}")
        cursor.execute(f"USE SCHEMA {schema}")

        insert_sql = f"""
        INSERT INTO {table} (
            price_timestamp, price_usd, price_eur, price_gbp,
            market_cap_usd, volume_24h_usd, price_change_24h,
            last_updated, ingestion_timestamp
        ) VALUES (
            %(price_timestamp)s, %(price_usd)s, %(price_eur)s, %(price_gbp)s,
            %(market_cap_usd)s, %(volume_24h_usd)s, %(price_change_24h)s,
            %(last_updated)s, %(ingestion_timestamp)s
        )
        """

        cursor.execute(insert_sql, record)
        conn.commit()

        log('SUCCESS', 'Data loaded to Snowflake successfully', rows_inserted=1)

        cursor.close()
        conn.close()
        return True

    except Exception as e:
        log('ERROR', f'Snowflake load failed: {e}')
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main pipeline execution."""
    pipeline_start = datetime.now(timezone.utc)

    print("=" * 80)
    print("🚀 Bitcoin Price Ingestion Pipeline - FLUID 0.7.1 (Snowflake)")
    print("=" * 80)

    log('INFO', 'Pipeline started', timestamp=pipeline_start.isoformat())

    try:
        # Step 1: Load contract
        contract_path = Path(__file__).parent.parent / 'contract.fluid.yaml'
        config = load_contract(contract_path)

        account = config['account']
        database = config['database']
        schema = config['schema']
        table = config['table']

        if not all([account, database, schema, table]):
            log('ERROR', 'Contract missing required Snowflake fields', config=config)
            raise ValueError('Contract must specify account, database, schema, and table')

        log('INFO', 'Configuration loaded from contract (Snowflake)',
            account=account, database=database, schema=schema, table=table)

        # Step 2: Fetch data
        log('INFO', '=== STEP 2: Fetch Bitcoin Price ===')
        bitcoin_data = fetch_bitcoin_price()

        # Step 3: Transform
        log('INFO', '=== STEP 3: Transform to Schema ===')
        record = transform_to_schema(bitcoin_data)

        # Step 4: Load
        log('INFO', '=== STEP 4: Load to Snowflake ===')
        success = load_to_snowflake(record, account, database, schema, table)

        if not success:
            sys.exit(1)

        pipeline_duration = (datetime.now(timezone.utc) - pipeline_start).total_seconds()

        print("=" * 80)
        log('SUCCESS', f'Pipeline completed in {pipeline_duration:.2f}s',
            platform='snowflake',
            btc_price=f"${record['price_usd']:,.2f}",
            change_24h=f"{record['price_change_24h']:.2f}%",
            market_cap=f"${record['market_cap_usd']:,.0f}",
            volume_24h=f"${record['volume_24h_usd']:,.0f}")
        print("=" * 80)

    except Exception as e:
        pipeline_duration = (datetime.now(timezone.utc) - pipeline_start).total_seconds()
        print("=" * 80)
        log('ERROR', f'Pipeline failed after {pipeline_duration:.2f}s: {e}')
        import traceback
        traceback.print_exc()
        print("=" * 80)
        raise


if __name__ == '__main__':
    main()
