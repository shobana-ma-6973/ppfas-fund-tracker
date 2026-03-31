"""
PPFAS Flexi Cap Fund - Rolling Returns Calculator
Computes rolling returns from historical NAV data.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


def calculate_rolling_returns(
    df: pd.DataFrame,
    window_years: int = 3,
    nav_col: str = "nav",
    date_col: str = "date",
) -> pd.DataFrame:
    """
    Calculate rolling returns over a specified window in years.

    For each date, computes the annualized return from (date - window_years) to date.
    CAGR formula: (end_nav / start_nav)^(1/years) - 1

    Args:
        df: DataFrame with date and nav columns
        window_years: Rolling window in years (default: 3)

    Returns:
        DataFrame with columns: [date, nav, rolling_return_pct]
    """
    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col])
    df = df.sort_values(date_col).reset_index(drop=True)
    df.set_index(date_col, inplace=True)

    window_days = window_years * 365
    rolling_returns = []

    for current_date in df.index:
        target_date = current_date - timedelta(days=window_days)
        # Find the closest available date to the target
        past_dates = df.index[df.index <= target_date]

        if len(past_dates) == 0:
            rolling_returns.append(np.nan)
            continue

        closest_past_date = past_dates[-1]
        actual_days = (current_date - closest_past_date).days

        if actual_days < (window_days - 30):  # Allow 30-day tolerance
            rolling_returns.append(np.nan)
            continue

        start_nav = df.loc[closest_past_date, nav_col]
        end_nav = df.loc[current_date, nav_col]

        if start_nav <= 0:
            rolling_returns.append(np.nan)
            continue

        # CAGR calculation
        years = actual_days / 365.25
        cagr = (end_nav / start_nav) ** (1 / years) - 1
        rolling_returns.append(round(cagr * 100, 2))

    df["rolling_return_pct"] = rolling_returns
    df = df.reset_index()

    valid_returns = df.dropna(subset=["rolling_return_pct"])
    logger.info(
        f"Computed {len(valid_returns)} rolling {window_years}Y returns "
        f"(range: {valid_returns['rolling_return_pct'].min():.2f}% to "
        f"{valid_returns['rolling_return_pct'].max():.2f}%)"
    )

    return df


def get_return_summary(df: pd.DataFrame) -> dict:
    """
    Get a summary of rolling returns for display.
    """
    valid = df.dropna(subset=["rolling_return_pct"])

    if valid.empty:
        return {"error": "No rolling return data available"}

    latest = valid.iloc[-1]

    return {
        "current_rolling_return": float(latest["rolling_return_pct"]),
        "current_date": latest["date"].strftime("%Y-%m-%d"),
        "average_rolling_return": round(float(valid["rolling_return_pct"].mean()), 2),
        "min_rolling_return": round(float(valid["rolling_return_pct"].min()), 2),
        "max_rolling_return": round(float(valid["rolling_return_pct"].max()), 2),
        "min_date": valid.loc[valid["rolling_return_pct"].idxmin(), "date"].strftime("%Y-%m-%d"),
        "max_date": valid.loc[valid["rolling_return_pct"].idxmax(), "date"].strftime("%Y-%m-%d"),
    }


def calculate_point_to_point_returns(df: pd.DataFrame) -> dict:
    """
    Calculate standard point-to-point returns (1M, 3M, 6M, 1Y, 3Y, 5Y).
    """
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    latest_date = df["date"].max()
    latest_nav = float(df.iloc[-1]["nav"])

    periods = {
        "1M": 30,
        "3M": 91,
        "6M": 182,
        "1Y": 365,
        "3Y": 1095,
        "5Y": 1825,
    }

    returns = {}
    for label, days in periods.items():
        target_date = latest_date - timedelta(days=days)
        past = df[df["date"] <= target_date]

        if past.empty:
            returns[label] = None
            continue

        start_nav = float(past.iloc[-1]["nav"])
        actual_days = (latest_date - past.iloc[-1]["date"]).days
        years = actual_days / 365.25

        if years < 1:
            # Absolute return for sub-year periods
            ret = ((latest_nav / start_nav) - 1) * 100
        else:
            # CAGR for 1Y+
            ret = ((latest_nav / start_nav) ** (1 / years) - 1) * 100

        returns[label] = round(ret, 2)

    returns["as_of_date"] = latest_date.strftime("%Y-%m-%d")
    returns["latest_nav"] = latest_nav
    return returns


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    from nav_fetcher import fetch_nav_history, save_nav_history

    df = fetch_nav_history()
    save_nav_history(df)

    # Rolling returns
    df_rolling = calculate_rolling_returns(df, window_years=3)
    summary = get_return_summary(df_rolling)
    print("\n=== 3-Year Rolling Return Summary ===")
    for k, v in summary.items():
        print(f"  {k}: {v}")

    # Point-to-point returns
    p2p = calculate_point_to_point_returns(df)
    print("\n=== Point-to-Point Returns ===")
    for k, v in p2p.items():
        print(f"  {k}: {v}")
