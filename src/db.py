"""
src/db.py

Builds project.duckdb from the raw sources + sql/ files, in order.
Used by both the notebooks and the Streamlit dashboard, so the mart logic
lives in exactly one place (the sql/ files) instead of being duplicated.

Usage:
    from src.db import build_database
    con = build_database()

Or from the command line:
    python src/db.py
"""
import duckdb
import pandas as pd
import requests
import wbgapi as wb
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SQL_DIR = REPO_ROOT / "sql"
DB_PATH = REPO_ROOT / "project.duckdb"


def build_database(db_path: Path = DB_PATH) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(str(db_path))

    # --- Live sources (weather + CPI) -- registered before running the SQL files,
    # since 03_marts.sql joins against weather_daily and cpi by name. ---
    r = requests.get(
        "https://archive-api.open-meteo.com/v1/archive",
        params={
            "latitude": 5.60, "longitude": -0.19,
            "start_date": "2015-01-01", "end_date": "2023-12-31",
            "daily": "precipitation_sum,temperature_2m_max", "timezone": "auto",
        },
    ).json()
    wx = pd.DataFrame(r["daily"])
    wx["time"] = pd.to_datetime(wx["time"])
    con.register("weather_daily", wx)

    cpi = wb.data.DataFrame("FP.CPI.TOTL", "GHA", time=range(2015, 2024), labels=False).reset_index()
    con.register("cpi", cpi)

    # --- Run the staged SQL files in order ---
    for sql_file in ["01_staging.sql", "02_clean.sql", "03_marts.sql"]:
        sql_text = (SQL_DIR / sql_file).read_text()
        # 01_staging.sql expects the raw CSV at data/wfp_food_prices_gha.csv
        con.execute(sql_text)
        print(f"ran {sql_file}")

    return con


if __name__ == "__main__":
    con = build_database()
    print(con.sql("SELECT COUNT(*) AS rows FROM region_month_mart").df())
    con.close()
