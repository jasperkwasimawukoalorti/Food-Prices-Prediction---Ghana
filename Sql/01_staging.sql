-- 01_staging.sql
-- Load the three raw sources into DuckDB. Run this first.
--
-- PATCHED: the original starter loader used skip=1, assuming an HXL tag row
-- on line 2 of the CSV. This download has no such row -- skip=1 corrupts the
-- header and crashes on a later type-conversion error. Confirmed by testing
-- against the real file; do not reintroduce skip=1 unless you've verified
-- your own download actually has an HXL row (check: is row 2 real data, or
-- does it look like "#date,#adm1+name,...")?

CREATE OR REPLACE TABLE prices AS
SELECT * FROM read_csv_auto('data/wfp_food_prices_gha.csv');

-- weather_daily and cpi are loaded from live APIs (Open-Meteo, World Bank via
-- wbgapi) in the notebook's Python loader cell, then registered into DuckDB
-- with con.register(). They aren't plain CSVs, so they're not staged here --
-- see notebooks/04_food_security_integration_SOLVED.ipynb, Section 1.
