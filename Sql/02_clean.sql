-- 02_clean.sql
-- Applies the three cleaning rules found by testing against the real WFP file.
-- Run after 01_staging.sql.
--
-- Rule 1 (pricetype): filter to Wholesale only. It's the only pricetype with
--   any 'actual' (directly observed) rows -- 'Retail' in this file is 100%
--   'aggregate' (WFP-estimated). Wholesale and Retail are not the same price
--   series and shouldn't be averaged together.
--
-- Rule 2 (priceflag): NOT filtered -- both 'actual' and 'aggregate' rows are
--   kept, so the region x month series stays continuous for the window-
--   function and forecasting sections downstream.
--
-- Rule 3 (unit): price is normalized to price-per-KG wherever the unit is
--   weight-based ("100 KG" -> divide by 100, "KG" -> use as-is). Count-based
--   units (Yam = "100 Tubers", Plantains = "Bunch", Eggs = "30 pcs") have no
--   valid conversion to weight, so those rows get price_per_kg = NULL rather
--   than a fabricated number. They stay in the table for anyone who wants to
--   analyse them in their native unit; they're just excluded from any
--   AVG(price_per_kg), since SQL's AVG() skips NULLs automatically.

CREATE OR REPLACE TABLE prices_clean AS
SELECT
    admin1 AS region,
    commodity,
    date,
    pricetype,
    priceflag,
    unit,
    price,
    CASE
        WHEN unit = 'KG'     THEN price
        WHEN unit LIKE '%KG' THEN price / TRY_CAST(REPLACE(unit, ' KG', '') AS DOUBLE)
        ELSE NULL
    END AS price_per_kg
FROM prices
WHERE pricetype = 'Wholesale';

-- Sanity check: which commodities/units get excluded from price_per_kg, and how many rows.
-- SELECT commodity, unit, COUNT(*) AS n
-- FROM prices_clean WHERE price_per_kg IS NULL
-- GROUP BY 1, 2 ORDER BY n DESC;
