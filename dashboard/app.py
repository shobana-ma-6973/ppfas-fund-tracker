"""
PPFAS Flexi Cap Fund - Streamlit Dashboard
Interactive dashboard showing fund performance metrics.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import sys
import os
from pathlib import Path

# Resolve project root (works both locally and on Streamlit Cloud)
# Streamlit Cloud sets cwd to repo root; locally we may be in dashboard/
_project_root = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(_project_root / "src"))
sys.path.insert(0, str(_project_root))
os.chdir(_project_root)  # Ensure data/ paths resolve from repo root

from nav_fetcher import fetch_nav_history, save_nav_history, load_nav_history
from returns_calculator import (
    calculate_rolling_returns,
    get_return_summary,
    calculate_point_to_point_returns,
)
from factsheet_parser import load_factsheet_data, fetch_and_parse_factsheet

# ── Page Config ──────────────────────────────────────────────
st.set_page_config(
    page_title="PPFAS Flexi Cap Fund Tracker",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ───────────────────────────────────────────────
st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(135deg, #1e3a5f 0%, #2d5a87 100%);
        padding: 20px;
        border-radius: 12px;
        color: white;
        text-align: center;
    }
    .metric-card h3 { margin: 0; font-size: 14px; opacity: 0.8; }
    .metric-card h1 { margin: 5px 0 0 0; font-size: 28px; }
    .stMetric > div { background-color: #f0f2f6; border-radius: 10px; padding: 10px; }
</style>
""", unsafe_allow_html=True)


# ── Data Loading ─────────────────────────────────────────────
@st.cache_data(ttl=3600)  # Cache for 1 hour
def load_data():
    """Load or fetch NAV data."""
    nav_file = Path("data/nav_history.csv")
    nav_file.parent.mkdir(parents=True, exist_ok=True)
    if nav_file.exists():
        df = load_nav_history(str(nav_file))
        # Refresh if data is older than 1 day
        if (pd.Timestamp.now() - df["date"].max()).days > 1:
            df = fetch_nav_history()
            save_nav_history(df, str(nav_file))
    else:
        df = fetch_nav_history()
        save_nav_history(df, str(nav_file))
    return df


@st.cache_data(ttl=3600)
def load_factsheet():
    """Load factsheet data — try cached file first, then fetch live."""
    fs_file = Path("data/factsheet_data.json")
    if fs_file.exists():
        data = load_factsheet_data(str(fs_file))
        if data and data.get("aum") and data["aum"] != "N/A":
            return data
    # No cached data or AUM missing — fetch fresh from PPFAS website
    try:
        data = fetch_and_parse_factsheet()
        if data and data.get("aum") and data["aum"] != "N/A":
            return data
    except Exception:
        pass
    # Return cached data even if AUM is N/A, or None
    if fs_file.exists():
        return load_factsheet_data(str(fs_file))
    return None


# ── Main App ─────────────────────────────────────────────────
def main():
    st.title("📊 PPFAS Flexi Cap Fund Tracker")
    st.caption("Parag Parikh Flexi Cap Fund - Direct Growth (Scheme Code: 122639)")

    # Load data
    with st.spinner("Loading NAV data..."):
        df = load_data()

    factsheet = load_factsheet()

    # ── Sidebar ──────────────────────────────────────────────
    with st.sidebar:
        st.header("⚙️ Settings")
        rolling_window = st.selectbox("Rolling Return Window", [1, 2, 3, 5], index=2)

        st.divider()
        st.caption(f"Data from: {df['date'].min().strftime('%d %b %Y')}")
        st.caption(f"Data to: {df['date'].max().strftime('%d %b %Y')}")
        st.caption(f"Total records: {len(df):,}")

        if st.button("🔄 Refresh Data"):
            st.cache_data.clear()
            st.rerun()

    # ── Key Metrics Row ──────────────────────────────────────
    p2p = calculate_point_to_point_returns(df)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(
            "Latest NAV",
            f"₹{p2p['latest_nav']:.2f}",
            f"As of {p2p['as_of_date']}",
        )
    with col2:
        aum = factsheet.get("aum", "N/A") if factsheet else "N/A"
        st.metric("AUM", aum)
    with col3:
        ret_1y = p2p.get("1Y")
        st.metric(
            "1Y Return",
            f"{ret_1y:.2f}%" if ret_1y is not None else "N/A",
            delta=f"{ret_1y:.2f}%" if ret_1y is not None else None,
        )
    with col4:
        ret_3y = p2p.get("3Y")
        st.metric(
            "3Y CAGR",
            f"{ret_3y:.2f}%" if ret_3y is not None else "N/A",
            delta=f"{ret_3y:.2f}%" if ret_3y is not None else None,
        )

    st.divider()

    # ── NAV Chart ────────────────────────────────────────────
    nav_header_col, nav_filter_col = st.columns([3, 1])
    with nav_header_col:
        st.subheader("📈 NAV History")
    with nav_filter_col:
        date_range = st.selectbox(
            "Chart Range",
            ["1 Month", "3 Months", "6 Months", "1 Year", "3 Years", "5 Years", "All Time"],
            index=4,
        )

    range_days = {
        "1 Month": 30, "3 Months": 91, "6 Months": 182,
        "1 Year": 365, "3 Years": 1095, "5 Years": 1825, "All Time": None,
    }
    days = range_days[date_range]

    if days:
        cutoff = df["date"].max() - pd.Timedelta(days=days)
        df_plot = df[df["date"] >= cutoff]
    else:
        df_plot = df

    fig_nav = px.line(
        df_plot, x="date", y="nav",
        title=f"NAV Trend ({date_range})",
        labels={"date": "Date", "nav": "NAV (₹)"},
    )
    fig_nav.update_layout(
        hovermode="x unified",
        plot_bgcolor="white",
        xaxis=dict(gridcolor="#eee"),
        yaxis=dict(gridcolor="#eee"),
    )
    fig_nav.update_traces(line_color="#1e3a5f", line_width=2)
    st.plotly_chart(fig_nav, use_container_width=True)

    # ── Returns Section ──────────────────────────────────────
    st.subheader("📊 Returns")

    col_ret1, col_ret2 = st.columns(2)

    with col_ret1:
        st.markdown("**Point-to-Point Returns**")
        returns_data = []
        for period in ["1M", "3M", "6M", "1Y", "3Y", "5Y"]:
            val = p2p.get(period)
            returns_data.append({
                "Period": period,
                "Return (%)": f"{val:.2f}%" if val is not None else "N/A",
                "Type": "Absolute" if period in ["1M", "3M", "6M"] else "CAGR",
            })
        st.dataframe(pd.DataFrame(returns_data), use_container_width=True, hide_index=True)

    with col_ret2:
        st.markdown(f"**{rolling_window}-Year Rolling Return**")
        df_rolling = calculate_rolling_returns(df, window_years=rolling_window)
        summary = get_return_summary(df_rolling)

        if "error" not in summary:
            st.write(f"Current: **{summary['current_rolling_return']:.2f}%**")
            st.write(f"Average: **{summary['average_rolling_return']:.2f}%**")
            st.write(f"Min: **{summary['min_rolling_return']:.2f}%** ({summary['min_date']})")
            st.write(f"Max: **{summary['max_rolling_return']:.2f}%** ({summary['max_date']})")

    # Rolling Returns Chart
    df_rolling_valid = df_rolling.dropna(subset=["rolling_return_pct"])
    if not df_rolling_valid.empty:
        fig_rolling = px.line(
            df_rolling_valid, x="date", y="rolling_return_pct",
            title=f"{rolling_window}-Year Rolling Returns (%)",
            labels={"date": "Date", "rolling_return_pct": "Return (%)"},
        )
        fig_rolling.update_layout(
            hovermode="x unified",
            plot_bgcolor="white",
            xaxis=dict(gridcolor="#eee"),
            yaxis=dict(gridcolor="#eee"),
        )
        fig_rolling.add_hline(
            y=df_rolling_valid["rolling_return_pct"].mean(),
            line_dash="dash", line_color="orange",
            annotation_text=f"Avg: {df_rolling_valid['rolling_return_pct'].mean():.2f}%",
        )
        fig_rolling.update_traces(line_color="#2d8a4e", line_width=1.5)
        st.plotly_chart(fig_rolling, use_container_width=True)

    st.divider()

    # ── Factsheet Data (Allocations) ─────────────────────────
    if factsheet:
        st.subheader("📋 Portfolio Allocation (from Factsheet)")

        col_s, col_c = st.columns(2)

        with col_s:
            sectors = factsheet.get("sector_allocation", {})
            if sectors:
                st.markdown("**Sector-wise Allocation**")
                df_sectors = pd.DataFrame(
                    list(sectors.items()), columns=["Sector", "Allocation (%)"]
                ).sort_values("Allocation (%)", ascending=False)

                fig_sector = px.bar(
                    df_sectors, x="Allocation (%)", y="Sector",
                    orientation="h", title="Sector Allocation",
                    color="Allocation (%)",
                    color_continuous_scale="Blues",
                )
                fig_sector.update_layout(
                    showlegend=False, plot_bgcolor="white",
                    yaxis=dict(autorange="reversed"),
                    height=max(400, len(sectors) * 35),
                )
                st.plotly_chart(fig_sector, use_container_width=True)
            else:
                st.info("Sector allocation data not available in factsheet")

        with col_c:
            categories = factsheet.get("category_allocation", {})
            if categories:
                st.markdown("**Category-wise Allocation**")
                df_cat = pd.DataFrame(
                    list(categories.items()), columns=["Category", "Allocation (%)"]
                )

                fig_cat = px.pie(
                    df_cat, values="Allocation (%)", names="Category",
                    title="Category Allocation",
                    color_discrete_sequence=px.colors.qualitative.Set2,
                    hole=0.4,
                )
                fig_cat.update_traces(textposition="inside", textinfo="label+percent")
                st.plotly_chart(fig_cat, use_container_width=True)
            else:
                st.info("Category allocation data not available in factsheet")

        st.caption(f"Factsheet data extracted on: {factsheet.get('extraction_date', 'N/A')}")
    else:
        st.info(
            "📄 Factsheet data not yet available. "
            "Run `python src/factsheet_parser.py` or wait for the monthly automation."
        )

    # ── Footer ───────────────────────────────────────────────
    st.divider()
    st.caption(
        "Data source: MFAPI (NAV) | PPFAS Mutual Fund (Factsheet) | "
        "Disclaimer: This is for informational purposes only, not investment advice."
    )


if __name__ == "__main__":
    main()
