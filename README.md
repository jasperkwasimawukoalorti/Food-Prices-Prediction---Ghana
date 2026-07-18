# Food Security — West Africa: What Moves the Price of Food

Capstone project — Thrive Africa / capstone-projects-march-2026, Project 4 (Food Security, Route A · integration).

## Business question

Is the rise in staple food prices in Ghana driven by weather, currency, or season — and where is it heading?

## Data

- **WFP food prices** (HDX) — market × commodity × date × pricetype, Ghana, 2006–2023. Filtered to Wholesale, normalized to price-per-KG. See [`docs/data_dictionary.md`](docs/data_dictionary.md) for the full cleaning rules.
- **Open-Meteo weather** — daily rainfall/temperature, downsampled to monthly, 2015–2023.
- **World Bank CPI** — annual, broadcast across each year's 12 months, used to deflate prices to real terms.

## Pipeline

```
Extract (requests, wbgapi, CSV)
   -> Load (DuckDB, sql/01_staging.sql)
   -> Clean (sql/02_clean.sql — pricetype filter, unit normalization)
   -> Model schema + Transform (sql/03_marts.sql — region x month mart)
   -> Analyse (sql/04_analysis.sql — LAG, rolling avg, volatility rank)
   -> Predict (scikit-learn, in the notebook)
   -> Dashboard (dashboard/streamlit_app.py)
```

## How to run

1. `pip install -r requirements.txt`
2. The dataset (`data/wfp_food_prices_gha.csv`) is committed directly in this repo — no separate download needed. If you replace it with a fresher pull from [data.humdata.org](https://data.humdata.org/dataset/wfp-food-prices-for-ghana), **check for an HXL tag row first** (is row 2 real data, or does it look like `#date,#adm1+name,...`?). If there's no HXL row, do **not** pass `skip=1` to `read_csv_auto` — it will corrupt the header. `sql/01_staging.sql` already reflects the no-skip version for this dataset.
3. Run `notebooks/04_food_security_integration_SOLVED.ipynb` top to bottom (Kernel → Restart & Run All).
4. `streamlit run dashboard/streamlit_app.py` — builds `project.duckdb` automatically on first run if it doesn't exist yet.

## Deploying to Streamlit Community Cloud

Before deploying, **verify on GitHub's own file browser** (not just locally) that these are all present at the repo root, sitting next to each other:

```
sql/            (all four .sql files)
src/db.py
data/wfp_food_prices_gha.csv
dashboard/streamlit_app.py
```

If `git status` shows files as committed locally but they don't appear on GitHub's web UI, the push didn't actually complete — re-run `git push` and check for errors, rather than assuming a successful `git commit` means the files reached GitHub. A missing `sql/` folder on the deployed container is the single most common cause of a `FileNotFoundError` in the app logs referencing `sql/01_staging.sql`.

## Data cleaning rules applied

- `pricetype` filtered to Wholesale only (Retail is 100% WFP-estimated in this file).
- `priceflag` **not** filtered — both `actual` and `aggregate` rows are kept, for series continuity.
- `price` normalized to price-per-KG; non-weight-quoted commodities (Yam, Plantains, Eggs) are excluded from `avg_price`/`real_price`, since there's no valid KG conversion for them.

Full detail: [`docs/data_dictionary.md`](docs/data_dictionary.md).

## Findings

*(fill in after running section 4 of the notebook — pull your two chart takeaways here)*

- [ ] Price trend + rolling average — headline observation
- [ ] Volatility ranking — which region/commodity is riskiest

## Model

Baseline (naive persistence) vs. `LinearRegression` on lag + rolling average + rainfall + month-of-year, evaluated with chronological train/test split and MAE. *(fill in your actual MAE numbers from section 5 of the notebook)*

## Recommendation

*(fill in your 3–5 sentence recommendation from the notebook's final section)*

## Live dashboard

*(fill in after deploying — see the "Build Your Product Into a Real App" guide for Streamlit Community Cloud deployment steps)*

## Repo structure

```
project/
├── README.md
├── requirements.txt
├── .gitignore
├── data/
│   ├── wfp_food_prices_gha.csv       # full raw file — committed directly (see note above)
│   └── sample_wfp_food_prices_gha.csv  # small committed sample for reviewers
├── sql/
│   ├── 01_staging.sql
│   ├── 02_clean.sql
│   ├── 03_marts.sql
│   └── 04_analysis.sql
├── notebooks/
│   └── 04_food_security_integration_SOLVED.ipynb
├── src/
│   └── db.py                          # shared build logic (notebook + dashboard both use this)
├── dashboard/
│   └── streamlit_app.py
└── docs/
    └── data_dictionary.md
```
