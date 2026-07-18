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

DESIGN NOTE (learned from a real deploy failure): duckdb.connect(path) creates
the file on disk immediately, before any SQL runs. If something fails partway
through the build (e.g. a missing sql/ file), the half-built file is still
left on disk. On every later run, the app sees "file exists" and skips
rebuilding, then fails trying to open the corrupt file -- turning one
recoverable error into a permanently broken deployment until a manual
reboot. To avoid that: build into a temp file, only move it into place on
success, and always clean up on failure.
"""
import os
import uuid
import duckdb
import pandas as pd
import requests
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SQL_DIR = REPO_ROOT / "sql"
DATA_DIR = REPO_ROOT / "data"
DB_PATH = REPO_ROOT / "project.duckdb"

REQUIRED_SQL_FILES = ["01_staging.sql", "02_clean.sql", "03_marts.sql"]
REQUIRED_TABLE = "region_month_mart"


class BuildError(RuntimeError):
    """Raised with a clear, specific message instead of letting a raw
    FileNotFoundError/ConnectionException/CatalogException surface, since
    those are easy to misread as three unrelated bugs instead of one cause."""


def _check_prerequisites():
    missing_sql = [f for f in REQUIRED_SQL_FILES if not (SQL_DIR / f).exists()]
    if missing_sql:
        raise BuildError(
            f"Missing SQL file(s): {missing_sql} in {SQL_DIR}. "
            "This means the sql/ folder wasn't pushed to GitHub, or isn't at "
            "the repo root alongside dashboard/ and src/. Check the repo's "
            "file browser on GitHub directly to confirm."
        )
    csv_path = DATA_DIR / "wfp_food_prices_gha.csv"
    if not csv_path.exists():
        raise BuildError(
            f"Missing {csv_path}. The full CSV must be committed to the repo "
            "for a cloud deployment to see it -- Streamlit Cloud only has "
            "what's actually in GitHub, there is no manual file-placement "
            "step like there is on your own machine."
        )


def build_database(db_path: Path = DB_PATH) -> duckdb.DuckDBPyConnection:
    _check_prerequisites()

    # If another concurrent request already finished building while we were
    # checking, just use its result instead of racing it. This is the actual
    # fix for a real failure: concurrent cold-start requests all saw "no file
    # yet" at once and collided on a shared temp filename before this fix.
    if db_path.exists():
        try:
            probe = duckdb.connect(str(db_path), read_only=True)
            probe.sql(f"SELECT 1 FROM {REQUIRED_TABLE} LIMIT 1")
            probe.close()
            return duckdb.connect(str(db_path))
        except Exception:
            pass  # existing file is stale/corrupt -- fall through and rebuild

    # Unique per attempt (pid + random suffix) so concurrent builds never
    # write to the same temp file, regardless of how many requests arrive
    # at once on a cold start.
    tmp_path = db_path.with_name(f"{db_path.stem}.{os.getpid()}.{uuid.uuid4().hex[:8]}.building.duckdb")

    con = None
    try:
        con = duckdb.connect(str(tmp_path))

        # --- Live sources (weather + CPI) -- registered before running the
        # SQL files, since 03_marts.sql joins against them by name. ---
        r = requests.get(
            "https://archive-api.open-meteo.com/v1/archive",
            params={
                "latitude": 5.60, "longitude": -0.19,
                "start_date": "2015-01-01", "end_date": "2023-12-31",
                "daily": "precipitation_sum,temperature_2m_max", "timezone": "auto",
            },
            timeout=30,
        ).json()
        wx = pd.DataFrame(r["daily"])
        wx["time"] = pd.to_datetime(wx["time"])
        con.register("weather_daily", wx)

        # PATCHED: previously used wbgapi's wb.data.DataFrame(...), which
        # returns a DIFFERENT column shape depending on wbgapi's installed
        # version (sometimes wide, with years as column names, not a "time"
        # column at all) -- confirmed live on a real deploy as
        # "BinderException: Values list 'c' does not have a column named
        # 'time'". Fetching directly from the World Bank's REST API instead
        # gives a stable, documented JSON shape we parse ourselves, with no
        # dependency on a third-party library's internal reshaping.
        r = requests.get(
            "https://api.worldbank.org/v2/country/GHA/indicator/FP.CPI.TOTL",
            params={"date": "2015:2023", "format": "json", "per_page": "100"},
            timeout=30,
        ).json()
        cpi = pd.DataFrame(r[1])[["date", "value"]].copy()
        cpi["year"] = cpi["date"].astype(int)
        cpi = cpi.rename(columns={"value": "FP_CPI_TOTL"})[["year", "FP_CPI_TOTL"]]
        con.register("cpi", cpi)

        # --- Run the staged SQL files in order ---
        for sql_file in REQUIRED_SQL_FILES:
            sql_text = (SQL_DIR / sql_file).read_text()
            con.execute(sql_text)

        # Verify the build actually produced the table we need, rather than
        # silently succeeding on a file that's missing what the app expects.
        tables = con.sql("SELECT table_name FROM information_schema.tables").df()["table_name"].tolist()
        if REQUIRED_TABLE not in tables:
            raise BuildError(f"Build completed but {REQUIRED_TABLE} was not created. Tables present: {tables}")

        con.close()
        con = None

        # Atomic swap -- only replace the real DB file once the build is
        # fully verified. A failure above never touches db_path at all.
        # If another concurrent attempt already finished and swapped in a
        # good file while we were building, prefer theirs and discard ours
        # rather than erroring -- either file is equally valid, no need to
        # fight over it.
        if db_path.exists():
            try:
                probe = duckdb.connect(str(db_path), read_only=True)
                probe.sql(f"SELECT 1 FROM {REQUIRED_TABLE} LIMIT 1")
                probe.close()
                tmp_path.unlink()
                return duckdb.connect(str(db_path))
            except Exception:
                db_path.unlink()
        os.replace(tmp_path, db_path)

    except Exception:
        if con is not None:
            con.close()
        if tmp_path.exists():
            tmp_path.unlink()
        raise

    return duckdb.connect(str(db_path))


if __name__ == "__main__":
    con = build_database()
    print(con.sql(f"SELECT COUNT(*) AS rows FROM {REQUIRED_TABLE}").df())
    con.close()
