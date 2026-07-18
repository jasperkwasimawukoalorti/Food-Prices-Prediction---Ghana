-- 03_marts.sql
-- Builds the region x month fact table used by every downstream section.
-- Run after 02_clean.sql, and after weather_daily / cpi have been registered
-- (see notebooks/04_food_security_integration_SOLVED.ipynb, Section 1).

-- Down-sample weather from daily to monthly (rainfall summed, temperature averaged)
CREATE OR REPLACE TABLE weather_monthly AS
SELECT
    DATE_TRUNC('month', time) AS month,
    SUM(precipitation_sum)    AS rainfall_mm,
    AVG(temperature_2m_max)   AS avg_temp_c
FROM weather_daily
GROUP BY 1
ORDER BY 1;

-- Collapse cleaned prices to region x commodity x month (price_per_kg, not raw price)
CREATE OR REPLACE TABLE prices_monthly AS
SELECT
    region,
    commodity,
    DATE_TRUNC('month', date) AS month,
    AVG(price_per_kg) AS avg_price   -- NOTE: this is Wholesale, price-per-KG, cleaned.
                                       -- Keeping the name avg_price for compatibility
                                       -- with downstream sections -- see docs/data_dictionary.md.
FROM prices_clean
WHERE price_per_kg IS NOT NULL
GROUP BY 1, 2, 3;

-- The hard join: monthly prices <- monthly weather (grain match)
--                monthly prices <- annual CPI (grain broadcast, one row -> many months)
CREATE OR REPLACE TABLE region_month_mart AS
SELECT
    p.region,
    p.commodity,
    p.month,
    p.avg_price,
    w.rainfall_mm,
    w.avg_temp_c,
    c.FP_CPI_TOTL AS cpi,
    p.avg_price / (c.FP_CPI_TOTL / 100.0) AS real_price
FROM prices_monthly p
LEFT JOIN weather_monthly w
    ON p.month = w.month
LEFT JOIN cpi c
    ON EXTRACT(YEAR FROM p.month) = c.year
ORDER BY p.region, p.commodity, p.month;

-- NOTE: weather only covers 2015-2023 while prices go back to 2006, so
-- rainfall_mm/avg_temp_c will be NULL for 2006-2014 rows -- expected, not a bug.
-- PATCHED: cpi.year is now a plain integer, fetched directly from the World
-- Bank REST API in src/db.py rather than via wbgapi -- see the comment there
-- for why (a real deploy hit "Values list 'c' does not have a column named
-- 'time'" because wbgapi's DataFrame() shape isn't stable across versions).
