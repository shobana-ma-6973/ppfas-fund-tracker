"""
PPFAS Flexi Cap Fund - NAV Averages Calculator
Computes monthly, 3-month, 6-month averages up to 5 years.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


def calculate_monthly_averages(df: pd.DataFrame, years: int = 5) -> pd.DataFrame:
    """
    Calculate monthly average NAV for the last N years.

    Returns DataFrame with columns: [year, month, month_name, avg_nav, min_nav, max_nav, data_points]
    """
    cutoff = df["date"].max() - pd.DateOffset(years=years)
    df_filtered = df[df["date"] >= cutoff].copy()

    df_filtered["year"] = df_filtered["date"].dt.year
    df_filtered["month"] = df_filtered["date"].dt.month

    monthly = (
        df_filtered.groupby(["year", "month"])
        .agg(avg_nav=("nav", "mean"), min_nav=("nav", "min"), max_nav=("nav", "max"), data_points=("nav", "count"))
        .reset_index()
    )
    monthly["month_name"] = monthly.apply(
        lambda r: datetime(int(r["year"]), int(r["month"]), 1).strftime("%b %Y"), axis=1
    )
    monthly = monthly.sort_values(["year", "month"], ascending=[False, False]).reset_index(drop=True)
    monthly["avg_nav"] = monthly["avg_nav"].round(4)
    monthly["min_nav"] = monthly["min_nav"].round(4)
    monthly["max_nav"] = monthly["max_nav"].round(4)

    return monthly


def calculate_rolling_averages(df: pd.DataFrame) -> dict:
    """
    Calculate rolling average NAV for various windows.

    Returns dict with keys: 1M, 3M, 6M, 1Y, 2Y, 3Y, 5Y
    Each value is a dict with avg_nav and change_pct (vs current NAV).
    """
    latest_nav = float(df.iloc[-1]["nav"])
    latest_date = df["date"].max()

    windows = {
        "1M": 30,
        "3M": 91,
        "6M": 182,
        "1Y": 365,
        "2Y": 730,
        "3Y": 1095,
        "5Y": 1825,
    }

    averages = {}
    for label, days in windows.items():
        cutoff = latest_date - pd.Timedelta(days=days)
        window_data = df[df["date"] >= cutoff]
        if len(window_data) > 0:
            avg = float(window_data["nav"].mean())
            change_pct = ((latest_nav - avg) / avg) * 100
            averages[label] = {
                "avg_nav": round(avg, 4),
                "change_pct": round(change_pct, 2),
                "data_points": len(window_data),
            }
        else:
            averages[label] = {"avg_nav": None, "change_pct": None, "data_points": 0}

    return averages


def get_nav_summary(df: pd.DataFrame) -> dict:
    """
    Get a comprehensive NAV summary for the daily email.
    """
    latest_nav = float(df.iloc[-1]["nav"])
    latest_date = df["date"].max().strftime("%d %b %Y")

    # Previous day NAV
    if len(df) >= 2:
        prev_nav = float(df.iloc[-2]["nav"])
        prev_date = df["date"].iloc[-2].strftime("%d %b %Y")
        day_change = latest_nav - prev_nav
        day_change_pct = (day_change / prev_nav) * 100
    else:
        prev_nav = None
        prev_date = None
        day_change = None
        day_change_pct = None

    return {
        "latest_nav": latest_nav,
        "latest_date": latest_date,
        "prev_nav": prev_nav,
        "prev_date": prev_date,
        "day_change": round(day_change, 4) if day_change is not None else None,
        "day_change_pct": round(day_change_pct, 2) if day_change_pct is not None else None,
        "rolling_averages": calculate_rolling_averages(df),
        "monthly_averages": calculate_monthly_averages(df, years=5),
    }
