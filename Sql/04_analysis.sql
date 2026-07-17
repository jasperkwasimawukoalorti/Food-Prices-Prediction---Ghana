-- 04_analysis.sql
-- The window-function analysis: month-over-month change, rolling average,
-- and volatility ranking, for one chosen staple commodity.
-- Run after 03_marts.sql.

-- Set the staple to analyse: edit this to any commodity present in
-- region_month_mart (see SELECT DISTINCT commodity FROM region_month_mart).
-- Maize is the default: largest single commodity by row count, and the one
-- named in the brief's stretch goal (cross-country staple comparison).

WITH region_volatility AS (
    SELECT
        region,
        STDDEV(avg_price) OVER (PARTITION BY region) AS region_price_stddev
    FROM region_month_mart
    WHERE commodity = 'Maize'
)
SELECT
    m.region,
    m.month,
    m.avg_price,
    m.real_price,
    m.rainfall_mm,
    LAG(m.avg_price) OVER (PARTITION BY m.region ORDER BY m.month) AS prev_month_price,
    (m.avg_price - LAG(m.avg_price) OVER (PARTITION BY m.region ORDER BY m.month))
        / NULLIF(LAG(m.avg_price) OVER (PARTITION BY m.region ORDER BY m.month), 0) * 100
        AS mom_pct_change,
    AVG(m.avg_price) OVER (
        PARTITION BY m.region ORDER BY m.month
        ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
    ) AS rolling_3mo_avg,
    RANK() OVER (ORDER BY v.region_price_stddev DESC) AS volatility_rank
FROM region_month_mart m
JOIN (SELECT DISTINCT region, region_price_stddev FROM region_volatility) v
    ON m.region = v.region
WHERE m.commodity = 'Maize'
ORDER BY m.region, m.month;
