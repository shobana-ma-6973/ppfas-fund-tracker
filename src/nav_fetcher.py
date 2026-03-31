"""
PPFAS Flexi Cap Fund - NAV Data Fetcher
Fetches historical NAV data from MFAPI (free, no auth required).
"""

import requests
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

MFAPI_URL = "https://api.mfapi.in/mf/{scheme_code}"


def fetch_nav_history(scheme_code: int = 122639) -> pd.DataFrame:
    """
    Fetch full NAV history for the given mutual fund scheme.
    Returns a DataFrame with columns: [date, nav]
    """
    url = MFAPI_URL.format(scheme_code=scheme_code)
    logger.info(f"Fetching NAV data from {url}")

    response = requests.get(url, timeout=30)
    response.raise_for_status()
    data = response.json()

    if data.get("status") == "FAIL" or "data" not in data:
        raise ValueError(f"MFAPI returned error: {data}")

    meta = data.get("meta", {})
    logger.info(f"Fund: {meta.get('fund_house')} - {meta.get('scheme_name')}")

    records = data["data"]
    df = pd.DataFrame(records)
    df["date"] = pd.to_datetime(df["date"], format="%d-%m-%Y")
    df["nav"] = pd.to_numeric(df["nav"], errors="coerce")
    df = df.dropna(subset=["nav"])
    df = df.sort_values("date").reset_index(drop=True)

    logger.info(f"Fetched {len(df)} NAV records from {df['date'].min()} to {df['date'].max()}")
    return df


def get_current_nav(scheme_code: int = 122639) -> dict:
    """Get the latest NAV value and date."""
    df = fetch_nav_history(scheme_code)
    latest = df.iloc[-1]
    return {
        "nav": float(latest["nav"]),
        "date": latest["date"].strftime("%Y-%m-%d"),
        "scheme_code": scheme_code,
    }


def save_nav_history(df: pd.DataFrame, filepath: str = "data/nav_history.csv"):
    """Save NAV history to CSV."""
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(filepath, index=False)
    logger.info(f"Saved {len(df)} records to {filepath}")


def load_nav_history(filepath: str = "data/nav_history.csv") -> pd.DataFrame:
    """Load NAV history from CSV."""
    df = pd.read_csv(filepath, parse_dates=["date"])
    df["nav"] = pd.to_numeric(df["nav"], errors="coerce")
    return df.sort_values("date").reset_index(drop=True)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    df = fetch_nav_history()
    save_nav_history(df)
    current = get_current_nav()
    print(f"Latest NAV: ₹{current['nav']:.4f} as of {current['date']}")
