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
from nav_averages import calculate_monthly_averages, calculate_rolling_averages as calc_rolling_avg
import numpy as np

# ── Page Config ──────────────────────────────────────────────
st.set_page_config(
    page_title="PPFAS Flexi Cap Fund Tracker",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
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
    /* Uniform height for stat metric cards */
    [data-testid="stMetric"] {
        min-height: 120px;
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    /* Screener-style inline pill buttons for radio */
    div[data-testid="stHorizontalBlock"] .stRadio > div {
        flex-direction: row !important;
        gap: 0px !important;
    }
    div[data-testid="stHorizontalBlock"] .stRadio > div > label {
        background: #f0f2f6;
        border: 1px solid #ddd;
        border-radius: 6px;
        padding: 4px 14px;
        margin: 0 2px;
        font-size: 14px;
        cursor: pointer;
    }
    div[data-testid="stHorizontalBlock"] .stRadio > div > label[data-checked="true"] {
        background: #5b5ea6;
        color: white;
        border-color: #5b5ea6;
    }
    /* Return card styling */
    .return-card {
        text-align: center;
        padding: 16px 12px;
        border-radius: 10px;
        background: #f8f9fb;
        border: 1px solid #e8eaed;
        min-height: 110px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
    }
    .return-card .period { font-size: 13px; color: #666; margin-bottom: 4px; }
    .return-card .value { font-size: 22px; font-weight: 700; }
    .return-card .type { font-size: 11px; color: #999; margin-top: 2px; }
    .return-positive .value { color: #0d9d5c; }
    .return-negative .value { color: #e23636; }
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


    # ── Key Metrics Row ──────────────────────────────────────
    p2p = calculate_point_to_point_returns(df)

    # Row 1: NAV and AUM
    col1, col2 = st.columns(2)
    with col1:
        st.metric(
            "Latest NAV",
            f"₹{p2p['latest_nav']:.2f}",
            f"As of {p2p['as_of_date']}",
        )
    with col2:
        aum = factsheet.get("aum", "N/A") if factsheet else "N/A"
        st.metric("AUM", aum)

    # Row 2: Returns
    col3, col4 = st.columns(2)
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

    # ── Daily NAV Movements ──────────────────────────────────
    st.subheader("📈 Daily NAV Movements")

    # Build list of available year-month combos from data
    df_nav_months = df.copy()
    df_nav_months["ym"] = df_nav_months["date"].dt.to_period("M")
    available_periods = sorted(df_nav_months["ym"].unique(), reverse=True)
    month_labels = [p.strftime("%B %Y") for p in available_periods]

    # Inline month selector
    hdr_col, sel_col = st.columns([2, 1])
    with hdr_col:
        st.markdown("View daily NAV values for any month — bars are colored "
                     "**green** (up from previous day) or **red** (down).")
    with sel_col:
        selected_label = st.selectbox(
            "Select Month", month_labels, index=0, label_visibility="collapsed"
        )
    selected_period = available_periods[month_labels.index(selected_label)]

    # Filter data for that month
    df_month = df_nav_months[df_nav_months["ym"] == selected_period].sort_values("date").copy()

    if not df_month.empty:
        # Compute daily change; first day uses previous available NAV
        prev_row = df_nav_months[df_nav_months["date"] < df_month["date"].min()].sort_values("date").tail(1)
        if not prev_row.empty:
            prev_nav = prev_row["nav"].iloc[0]
        else:
            prev_nav = df_month["nav"].iloc[0]

        df_month["prev_nav"] = df_month["nav"].shift(1)
        df_month.iloc[0, df_month.columns.get_loc("prev_nav")] = prev_nav
        df_month["change"] = df_month["nav"] - df_month["prev_nav"]
        df_month["pct_change"] = (df_month["change"] / df_month["prev_nav"]) * 100
        df_month["color"] = df_month["change"].apply(lambda c: "#2d8a4e" if c >= 0 else "#d9534f")
        df_month["day_label"] = df_month["date"].dt.strftime("%d %b")

        # Plotly bar chart
        fig_daily = go.Figure()
        fig_daily.add_trace(go.Bar(
            x=df_month["day_label"],
            y=df_month["nav"],
            marker_color=df_month["color"],
            text=df_month["nav"].apply(lambda v: f"₹{v:,.2f}"),
            textposition="outside",
            hovertemplate=(
                "<b>%{x}</b><br>"
                "NAV: ₹%{y:,.2f}<br>"
                "Change: %{customdata[0]:+.2f} (%{customdata[1]:+.2f}%)"
                "<extra></extra>"
            ),
            customdata=list(zip(df_month["change"], df_month["pct_change"])),
        ))

        nav_min = df_month["nav"].min()
        nav_max = df_month["nav"].max()
        y_pad = (nav_max - nav_min) * 0.15 if nav_max != nav_min else nav_max * 0.01
        fig_daily.update_layout(
            title=f"Daily NAV — {selected_label}",
            xaxis_title="Date",
            yaxis_title="NAV (₹)",
            plot_bgcolor="white",
            yaxis=dict(
                range=[nav_min - y_pad * 3, nav_max + y_pad * 3],
                gridcolor="#eee",
            ),
            xaxis=dict(gridcolor="#eee", tickangle=-45),
            height=450,
            showlegend=False,
        )
        st.plotly_chart(fig_daily, use_container_width=True)

        # Summary stats row
        open_nav = df_month["nav"].iloc[0]
        close_nav = df_month["nav"].iloc[-1]
        high_nav = df_month["nav"].max()
        low_nav = df_month["nav"].min()
        avg_nav = df_month["nav"].mean()
        total_chg = close_nav - open_nav
        total_pct = (total_chg / open_nav) * 100

        s1, s2, s3, s4, s5, s6 = st.columns(6)
        s1.metric("Open", f"₹{open_nav:,.2f}")
        s2.metric("Close", f"₹{close_nav:,.2f}")
        s3.metric("High", f"₹{high_nav:,.2f}")
        s4.metric("Low", f"₹{low_nav:,.2f}")
        s5.metric("Average", f"₹{avg_nav:,.2f}")
        s6.metric("Month Change", f"{total_pct:+.2f}%", delta=f"₹{total_chg:+.2f}")
    else:
        st.info("No NAV data available for the selected month.")

    st.divider()

    # ── NAV Chart ────────────────────────────────────────────
    st.subheader("📈 NAV History")
    date_range = st.radio(
        "Period",
        ["1M", "6M", "1Y", "3Y", "5Y", "Max"],
        index=2,
        horizontal=True,
        label_visibility="collapsed",
    )

    range_days = {
        "1M": 30, "6M": 182,
        "1Y": 365, "3Y": 1095, "5Y": 1825, "Max": None,
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
    fig_nav.update_traces(line_color="#5b5ea6", line_width=2)
    st.plotly_chart(fig_nav, use_container_width=True)

    # ── Returns Section (Screener-style cards) ───────────────
    st.subheader("📊 Returns")

    periods = ["1M", "3M", "6M", "1Y", "3Y", "5Y"]
    ret_cols = st.columns(len(periods))
    for col, period in zip(ret_cols, periods):
        val = p2p.get(period)
        ret_type = "Absolute" if period in ["1M", "3M", "6M"] else "CAGR"
        if val is not None:
            css_class = "return-positive" if val >= 0 else "return-negative"
            display_val = f"{val:+.2f}%"
        else:
            css_class = ""
            display_val = "N/A"
        with col:
            st.markdown(
                f'<div class="return-card {css_class}">'
                f'<div class="period">{period}</div>'
                f'<div class="value">{display_val}</div>'
                f'<div class="type">{ret_type}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    st.write("")

    # ── Rolling Returns ──────────────────────────────────────
    st.subheader("📉 Rolling Returns")
    rolling_window = st.radio(
        "Window",
        ["1Y", "2Y", "3Y", "5Y"],
        index=2,
        horizontal=True,
        label_visibility="collapsed",
    )
    rolling_window_years = int(rolling_window.replace("Y", ""))

    df_rolling = calculate_rolling_returns(df, window_years=rolling_window_years)
    summary = get_return_summary(df_rolling)

    if "error" not in summary:
        roll_cols = st.columns(4)
        roll_items = [
            ("Current", summary['current_rolling_return'], None),
            ("Average", summary['average_rolling_return'], None),
            ("Min", summary['min_rolling_return'], summary['min_date']),
            ("Max", summary['max_rolling_return'], summary['max_date']),
        ]
        for col, (label, val, date) in zip(roll_cols, roll_items):
            css_class = "return-positive" if val >= 0 else "return-negative"
            date_str = f'<div class="type">{date}</div>' if date else ''
            with col:
                st.markdown(
                    f'<div class="return-card {css_class}">'
                    f'<div class="period">{label}</div>'
                    f'<div class="value">{val:+.2f}%</div>'
                    f'{date_str}'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    # Rolling Returns Chart
    df_rolling_valid = df_rolling.dropna(subset=["rolling_return_pct"])
    if not df_rolling_valid.empty:
        fig_rolling = px.line(
            df_rolling_valid, x="date", y="rolling_return_pct",
            title=f"{rolling_window_years}-Year Rolling Returns (%)",
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

    # ── NAV Analytics ────────────────────────────────────────
    st.subheader("📊 NAV Analytics")

    # --- Rolling Averages (1M - 5Y) ---
    rolling_avgs = calc_rolling_avg(df)
    st.markdown("**Average NAV (Rolling Windows)**")
    st.caption("Average NAV over each period and how today's NAV compares.")

    ra_cols = st.columns(7)
    for col, period in zip(ra_cols, ["1M", "3M", "6M", "1Y", "2Y", "3Y", "5Y"]):
        data = rolling_avgs.get(period, {})
        avg = data.get("avg_nav")
        chg = data.get("change_pct")
        with col:
            if avg is not None:
                css_class = "return-positive" if chg >= 0 else "return-negative"
                sign = "+" if chg >= 0 else ""
                st.markdown(
                    f'<div class="return-card {css_class}">'
                    f'<div class="period">{period}</div>'
                    f'<div class="value" style="font-size:18px;">₹{avg:,.2f}</div>'
                    f'<div class="type">{sign}{chg:.2f}% vs current</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    '<div class="return-card"><div class="period">' + period + '</div>'
                    '<div class="value">N/A</div></div>',
                    unsafe_allow_html=True,
                )

    st.write("")

    # --- Monthly NAV Heatmap ---
    monthly_df = calculate_monthly_averages(df, years=5)
    if not monthly_df.empty:
        st.markdown("**Monthly Average NAV Heatmap** (Last 5 Years)")
        st.caption("Each cell shows the monthly average NAV. Color intensity: red (lower) → green (higher).")

        # Pivot for heatmap: rows=year, cols=month
        hm = monthly_df.copy()
        hm["month_short"] = hm["month"].apply(lambda m: ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"][m-1])
        hm_pivot = hm.pivot(index="year", columns="month", values="avg_nav").sort_index(ascending=True)
        hm_pivot.columns = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"][:len(hm_pivot.columns)] if len(hm_pivot.columns) == 12 else [f"{c}" for c in hm_pivot.columns]

        # Proper column names
        month_map = {1:"Jan",2:"Feb",3:"Mar",4:"Apr",5:"May",6:"Jun",7:"Jul",8:"Aug",9:"Sep",10:"Oct",11:"Nov",12:"Dec"}
        hm_pivot_full = hm.pivot(index="year", columns="month", values="avg_nav").sort_index(ascending=True)
        hm_pivot_full = hm_pivot_full.reindex(columns=range(1,13))
        hm_pivot_full.columns = [month_map[c] for c in hm_pivot_full.columns]

        # Text annotations (₹ formatted) + adaptive font color
        text_vals = hm_pivot_full.map(lambda v: f"₹{v:,.1f}" if pd.notna(v) else "—")

        # Compute per-cell font color: white for top 10% NAVs, dark for rest
        nav_vals = hm_pivot_full.values.flatten()
        valid_vals = [v for v in nav_vals if pd.notna(v)]
        if valid_vals:
            threshold_90 = np.percentile(valid_vals, 90)
        else:
            threshold_90 = float("inf")
        font_colors = hm_pivot_full.map(
            lambda v: "#ffffff" if pd.notna(v) and v >= threshold_90 else "#333333"
        ).values

        fig_hm = go.Figure(data=go.Heatmap(
            z=hm_pivot_full.values,
            x=hm_pivot_full.columns.tolist(),
            y=[str(int(y)) for y in hm_pivot_full.index],
            text=text_vals.values,
            texttemplate="%{text}",
            textfont={"size": 11, "color": font_colors.flatten().tolist()},
            colorscale=[
                [0, "#f5a0a0"],
                [0.4, "#f0f0b0"],
                [0.85, "#8cdc8c"],
                [1, "#1a7a3a"],
            ],
            hovertemplate="<b>%{y} %{x}</b><br>Avg NAV: %{text}<extra></extra>",
            showscale=True,
            colorbar=dict(title="NAV (₹)", thickness=15),
        ))
        fig_hm.update_layout(
            title="Monthly Average NAV Heatmap",
            height=max(300, len(hm_pivot_full) * 50 + 100),
            plot_bgcolor="white",
            xaxis=dict(side="top", dtick=1),
            yaxis=dict(autorange="reversed", dtick=1),
            margin=dict(l=60, r=40, t=80, b=40),
        )
        st.plotly_chart(fig_hm, use_container_width=True)

    # --- Side-by-side: Monthly Momentum + Yearly Summary ---
    col_mom, col_yr = st.columns(2)

    # Monthly Momentum (last 12 months)
    with col_mom:
        st.markdown("**Monthly Momentum** (Last 12 Months)")
        if not monthly_df.empty:
            mom = monthly_df.copy().sort_values(["year", "month"]).reset_index(drop=True)
            mom["mom_pct"] = mom["avg_nav"].pct_change() * 100
            mom_recent = mom.tail(12).dropna(subset=["mom_pct"])

            if not mom_recent.empty:
                mom_recent = mom_recent.copy()
                mom_recent["color"] = mom_recent["mom_pct"].apply(lambda v: "#0d9d5c" if v >= 0 else "#e23636")
                mom_recent["label"] = mom_recent["mom_pct"].apply(lambda v: f"{v:+.1f}%")

                fig_mom = go.Figure()
                fig_mom.add_trace(go.Bar(
                    y=mom_recent["month_name"],
                    x=mom_recent["mom_pct"],
                    orientation="h",
                    marker_color=mom_recent["color"],
                    text=mom_recent["label"],
                    textposition="outside",
                    hovertemplate="<b>%{y}</b><br>MoM: %{x:+.2f}%<extra></extra>",
                ))
                fig_mom.update_layout(
                    height=400,
                    plot_bgcolor="white",
                    xaxis=dict(title="MoM Change (%)", gridcolor="#eee", zeroline=True, zerolinecolor="#ccc"),
                    yaxis=dict(autorange="reversed"),
                    margin=dict(l=80, r=60, t=20, b=40),
                    showlegend=False,
                )
                st.plotly_chart(fig_mom, use_container_width=True)
            else:
                st.info("Not enough data for momentum calculation.")

    # Yearly Summary
    with col_yr:
        st.markdown("**Yearly Summary**")
        if not monthly_df.empty:
            ym = monthly_df.copy()
            years = sorted(ym["year"].unique())
            yearly_data = []
            prev_avg = None
            for yr in years:
                yr_data = ym[ym["year"] == yr]
                avg = yr_data["avg_nav"].mean()
                high = yr_data["max_nav"].max()
                low = yr_data["min_nav"].min()
                spread = high - low
                yoy = ((avg - prev_avg) / prev_avg * 100) if prev_avg else None
                prev_avg = avg
                yearly_data.append({
                    "year": int(yr), "avg": avg, "high": high,
                    "low": low, "spread": spread, "yoy": yoy,
                })

            yearly_data = yearly_data[::-1]  # newest first

            # Build styled HTML table
            table_rows = ""
            for d in yearly_data:
                # YoY cell with color + pill badge
                if d["yoy"] is not None:
                    yoy_val = d["yoy"]
                    yoy_color = "#0d9d5c" if yoy_val >= 0 else "#e23636"
                    yoy_bg = "rgba(13,157,92,0.1)" if yoy_val >= 0 else "rgba(226,54,54,0.1)"
                    yoy_arrow = "▲" if yoy_val >= 0 else "▼"
                    yoy_html = (
                        f'<span style="background:{yoy_bg}; color:{yoy_color}; '
                        f'padding:3px 10px; border-radius:12px; font-weight:600; font-size:13px;">'
                        f'{yoy_arrow} {yoy_val:+.1f}%</span>'
                    )
                else:
                    yoy_html = '<span style="color:#bbb;">—</span>'

                table_rows += (
                    f'<tr>'
                    f'<td style="padding:10px 12px; font-weight:700; color:#1e3a5f; border-bottom:1px solid #f0f0f0;">{d["year"]}</td>'
                    f'<td style="padding:10px 12px; text-align:right; font-weight:600; border-bottom:1px solid #f0f0f0;">₹{d["avg"]:,.2f}</td>'
                    f'<td style="padding:10px 12px; text-align:right; color:#0d9d5c; font-weight:500; border-bottom:1px solid #f0f0f0;">₹{d["high"]:,.2f}</td>'
                    f'<td style="padding:10px 12px; text-align:right; color:#e23636; font-weight:500; border-bottom:1px solid #f0f0f0;">₹{d["low"]:,.2f}</td>'
                    f'<td style="padding:10px 12px; text-align:right; color:#666; border-bottom:1px solid #f0f0f0;">₹{d["spread"]:,.2f}</td>'
                    f'<td style="padding:10px 14px; text-align:center; border-bottom:1px solid #f0f0f0;">{yoy_html}</td>'
                    f'</tr>'
                )

            th_style = 'padding:10px 12px; font-size:12px; color:#888; text-transform:uppercase; letter-spacing:0.5px; border-bottom:2px solid #e8eaed;'
            yearly_html = (
                '<div style="border:1px solid #e8eaed; border-radius:10px; overflow:hidden; background:white;">'
                '<style>table.ysummary tr:last-child td{border-bottom:none !important;}</style>'
                '<table class="ysummary" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse; font-size:14px;">'
                '<thead><tr style="background:#f8f9fb;">'
                f'<th style="{th_style} text-align:left;">Year</th>'
                f'<th style="{th_style} text-align:right;">Avg NAV</th>'
                f'<th style="{th_style} text-align:right;">High</th>'
                f'<th style="{th_style} text-align:right;">Low</th>'
                f'<th style="{th_style} text-align:right;">Spread</th>'
                f'<th style="{th_style} text-align:center;">YoY</th>'
                '</tr></thead>'
                f'<tbody>{table_rows}</tbody>'
                '</table></div>'
            )
            st.markdown(yearly_html, unsafe_allow_html=True)

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
                    text=df_sectors["Allocation (%)"].apply(lambda v: f"{v:.2f}%"),
                )
                fig_sector.update_traces(
                    textposition="outside",
                    textfont_size=12,
                    cliponaxis=False,
                )
                fig_sector.update_layout(
                    showlegend=False, plot_bgcolor="white",
                    yaxis=dict(autorange="reversed"),
                    height=max(400, len(sectors) * 35),
                    xaxis=dict(range=[0, df_sectors["Allocation (%)"].max() * 1.3]),
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
    foot_col1, foot_col2 = st.columns([3, 1])
    with foot_col1:
        st.caption(
            f"Data: {df['date'].min().strftime('%d %b %Y')} — {df['date'].max().strftime('%d %b %Y')} "
            f"({len(df):,} records) | Source: MFAPI (NAV), PPFAS Mutual Fund (Factsheet) | "
            "Disclaimer: For informational purposes only, not investment advice."
        )
    with foot_col2:
        if st.button("🔄 Refresh Data"):
            st.cache_data.clear()
            st.rerun()


if __name__ == "__main__":
    main()
