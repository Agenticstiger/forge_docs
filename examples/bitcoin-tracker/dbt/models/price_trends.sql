{{
  config(
    materialized='view',
    description='Bitcoin price trends with moving averages and deviation analysis'
  )
}}

-- Price trends with moving averages
-- Calculates 7-day and 30-day moving averages for trend analysis
SELECT 
  price_timestamp,
  price_usd,
  price_eur,
  price_gbp,
  
  -- 7-day moving average (168 hours)
  AVG(price_usd) OVER (
    ORDER BY price_timestamp
    ROWS BETWEEN 167 PRECEDING AND CURRENT ROW
  ) as ma_7day_usd,
  
  -- 30-day moving average (720 hours)
  AVG(price_usd) OVER (
    ORDER BY price_timestamp
    ROWS BETWEEN 719 PRECEDING AND CURRENT ROW
  ) as ma_30day_usd,
  
  -- Deviation from 7-day MA
  price_usd - AVG(price_usd) OVER (
    ORDER BY price_timestamp
    ROWS BETWEEN 167 PRECEDING AND CURRENT ROW
  ) as deviation_from_7day_ma,
  
  -- Percent deviation from 7-day MA
  ROUND(
    (price_usd - AVG(price_usd) OVER (
      ORDER BY price_timestamp
      ROWS BETWEEN 167 PRECEDING AND CURRENT ROW
    )) / NULLIF(AVG(price_usd) OVER (
      ORDER BY price_timestamp
      ROWS BETWEEN 167 PRECEDING AND CURRENT ROW
    ), 0) * 100,
    2
  ) as pct_deviation_from_7day_ma,
  
  -- Trend indicator (above/below MA)
  CASE 
    WHEN price_usd > AVG(price_usd) OVER (
      ORDER BY price_timestamp
      ROWS BETWEEN 167 PRECEDING AND CURRENT ROW
    ) THEN 'ABOVE_MA'
    ELSE 'BELOW_MA'
  END as trend_vs_7day_ma,
  
  -- Market metrics
  market_cap_usd,
  volume_24h_usd,
  price_change_24h_percent

FROM {{ source('crypto_data', 'bitcoin_prices') }}

ORDER BY price_timestamp DESC
