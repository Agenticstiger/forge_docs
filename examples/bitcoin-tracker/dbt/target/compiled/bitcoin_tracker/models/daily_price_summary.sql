

-- Daily Bitcoin price summary
-- Calculates daily OHLC (Open, High, Low, Close) and volatility metrics
WITH daily_data AS (
  SELECT 
    DATE(price_timestamp) as date,
    price_usd,
    price_eur,
    price_gbp,
    market_cap_usd,
    volume_24h_usd,
    price_timestamp,
    ROW_NUMBER() OVER (PARTITION BY DATE(price_timestamp) ORDER BY price_timestamp ASC) as first_row,
    ROW_NUMBER() OVER (PARTITION BY DATE(price_timestamp) ORDER BY price_timestamp DESC) as last_row
  FROM `dust-labs-485011`.`crypto_data`.`bitcoin_prices`
)
SELECT 
  date,
  
  -- Price statistics
  MIN(price_usd) as min_price_usd,
  MAX(price_usd) as max_price_usd,
  AVG(price_usd) as avg_price_usd,
  MAX(CASE WHEN first_row = 1 THEN price_usd END) as open_price_usd,
  MAX(CASE WHEN last_row = 1 THEN price_usd END) as close_price_usd,
  
  -- Volatility
  STDDEV(price_usd) as daily_volatility,
  MAX(price_usd) - MIN(price_usd) as price_range,
  
  -- Volume and market cap
  AVG(market_cap_usd) as avg_market_cap_usd,
  AVG(volume_24h_usd) as avg_volume_24h_usd,
  
  -- Additional metrics
  AVG(price_eur) as avg_price_eur,
  AVG(price_gbp) as avg_price_gbp,
  COUNT(*) as data_points,
  MIN(price_timestamp) as first_update,
  MAX(price_timestamp) as last_update

FROM daily_data
GROUP BY date
ORDER BY date DESC