# Data Dictionary

## Source files

| File | Source | Grain |
|---|---|---|
| `data/wfp_food_prices_gha.csv` | WFP via HDX (data.humdata.org) | one row per market × commodity × date × pricetype |
| `weather_daily` (registered, not a file) | Open-Meteo archive API | one row per day, 2015–2023 only |
| `cpi` (registered, not a file) | World Bank REST API directly (indicator `FP.CPI.TOTL`) — not `wbgapi`, see note below | one row per year |

## `prices` (raw, loaded as-is by `sql/01_staging.sql`)

| Column | Type | Notes |
|---|---|---|
| `date` | DATE | always the 15th of the month |
| `admin1` | VARCHAR | region (10 values) |
| `admin2`, `market`, `market_id`, `latitude`, `longitude` | — | location detail, not used downstream |
| `category` | VARCHAR | 4 broad food categories |
| `commodity`, `commodity_id` | — | 26 distinct commodities |
| `unit` | VARCHAR | 17 distinct values — mixes weight (`KG`, `100 KG`...) and count (`Bunch`, `100 Tubers`, `pcs`) units |
| `priceflag` | VARCHAR | `actual` (observed) / `aggregate` (WFP-estimated) / `actual,aggregate` |
| `pricetype` | VARCHAR | `Wholesale` or `Retail` |
| `currency` | VARCHAR | GHS for every row |
| `price` | DOUBLE | in local currency, in the stated `unit` — **do not average this directly**, see cleaning rules below |
| `usdprice` | DOUBLE | WFP's own USD conversion, unused here |

## `prices_clean` (built by `sql/02_clean.sql`)

Same columns as `prices`, filtered to `pricetype = 'Wholesale'`, plus:

| Column | Meaning |
|---|---|
| `price_per_kg` | `price` normalized to price-per-kilogram for weight-quoted units. `NULL` for count-quoted commodities (Yam, Plantains, Eggs) — there's no valid weight conversion for those. |

## `region_month_mart` (built by `sql/03_marts.sql`) — the table everything downstream reads from

| Column | Meaning |
|---|---|
| `region` | Admin1 region |
| `commodity` | Commodity name |
| `month` | First day of month, e.g. `2023-02-01` |
| `avg_price` | Mean **Wholesale, price-per-KG**, cleaned (see cleaning rules) — **not** the raw `price` column |
| `real_price` | `avg_price` deflated by CPI (inflation-adjusted, per KG) |
| `rainfall_mm` | Total monthly rainfall (Open-Meteo). `NULL` before 2015 — weather coverage starts then. |
| `avg_temp_c` | Mean daily max temperature that month. Same 2015+ caveat. |
| `cpi` | Annual CPI value, broadcast across that year's 12 months |

## Documented cleaning rules (applied in `sql/02_clean.sql`)

1. **Pricetype** — filtered to `Wholesale` only. It's the only pricetype with any directly-observed (`actual`) rows; `Retail` is 100% WFP-estimated in this file, and the two price levels aren't comparable.
2. **Priceflag** — *not* filtered. Both `actual` and `aggregate` rows are kept, so the region × month series stays continuous for the window-function and forecasting sections.
3. **Units** — normalized to price-per-KG for weight-quoted commodities. Count-quoted commodities (Yam — `100 Tubers`, Plantains — `Bunch`, Eggs — `30 pcs`) are excluded from `avg_price`/`real_price` — they remain in `prices_clean` with `price_per_kg = NULL` for anyone who wants to analyse them in their native unit instead.

## Known gaps

- The CPI source was switched from the `wbgapi` Python package to a direct call to the World Bank's REST API (`api.worldbank.org/v2/...`). `wbgapi`'s `wb.data.DataFrame()` output shape isn't stable across versions — a real deployment hit `BinderException: Values list "c" does not have a column named "time"` because the installed version didn't return the expected `time` column at all. The direct REST call gives a fixed, documented JSON shape and produces a plain integer `year` column instead of a `time` column formatted like `"YR2015"`.

- Weather data starts in 2015; prices go back to 2006. Expect `NULL` rainfall/temperature for 2006–2014.
- Row counts jump sharply from 2018 (582) to 2019 (3,409) to 2020+ (~5,000–6,500/year) — this reflects WFP expanding market/commodity coverage, not a real price event. Treat any trend spanning that boundary with that caveat in mind.
