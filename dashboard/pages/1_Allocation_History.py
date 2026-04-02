"""
PPFAS Flexi Cap Fund - Allocation History Dashboard
Shows historical sector and category allocation from 2013 to present.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import os
from pathlib import Path
from datetime import datetime

# ── Page config ──
st.set_page_config(
    page_title="PPFAS Allocation History",
    page_icon="📊",
    layout="wide",
)

# ── Resolve project root ──
_project_root = Path(__file__).parent.parent.parent.resolve()
os.chdir(_project_root)

# ── Load allocation history ──
@st.cache_data(ttl=3600)
def load_history():
    history_path = Path("data/allocation_history.json")
    if not history_path.exists():
        return None
    with open(history_path) as f:
        return json.load(f)


def main():
    st.title("📊 Allocation History")
    st.markdown("**Parag Parikh Flexi Cap Fund** — Category & sector allocation from 2013 to present")

    history = load_history()
    if not history or not history.get("records"):
        st.error("No allocation history data found. Run `python scripts/build_history.py` first.")
        return

    records = history["records"]
    total = history["total_months"]
    quality = history["quality_summary"]

    # ── Summary metrics ──
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Months", total)
    col2.metric("Date Range", f"{records[0]['year']} – {records[-1]['year']}")
    col3.metric("Good Quality", quality["good"])
    col4.metric("Approximate", quality["approximate"] + quality["incomplete"])

    st.divider()

    # ── Build DataFrame ──
    rows = []
    for r in records:
        date = pd.to_datetime(r["date"])
        cats = r["categories"]
        row = {
            "Date": date,
            "Year": r["year"],
            "Month": r["month"],
            "Indian Equity": cats.get("Indian Equity", 0),
            "Overseas Equity": cats.get("Overseas Equity", 0),
            "REITs & InvITs": cats.get("REITs & InvITs", 0),
            "Debt & Money Market": cats.get("Debt & Money Market", 0),
            "Cash & Equivalents": cats.get("Cash & Equivalents", 0),
            "AUM": r["aum"],
            "Quality": r["quality"],
            "Category Total": r["category_total"],
            "Sector Count": r["sector_count"],
        }
        rows.append(row)

    df = pd.DataFrame(rows)

    # ── Normalize categories to 100% for visualization ──
    cat_cols = ["Indian Equity", "Overseas Equity", "REITs & InvITs",
                "Debt & Money Market", "Cash & Equivalents"]

    df_norm = df.copy()
    row_totals = df_norm[cat_cols].sum(axis=1)
    for col in cat_cols:
        df_norm[col] = (df_norm[col] / row_totals * 100).round(2)
    df_norm[cat_cols] = df_norm[cat_cols].fillna(0)

    # ── Quality filter ──
    with st.expander("⚙️ Data Quality Filter", expanded=False):
        st.caption("Filter months by data extraction quality")
        quality_options = ["good", "approximate", "incomplete", "overcounted"]
        selected_quality = st.multiselect(
            "Include quality levels:",
            quality_options,
            default=["good", "approximate", "incomplete"],
        )
        use_normalized = st.toggle("Normalize to 100%", value=True,
                                    help="Scale categories so they sum to 100% for each month")

    df_filtered = df_norm if use_normalized else df
    df_filtered = df_filtered[df_filtered["Quality"].isin(selected_quality)]

    if df_filtered.empty:
        st.warning("No data matches the selected quality filters.")
        return

    # ═══════════════════════════════════════════════════════════
    # 1. CATEGORY ALLOCATION — STACKED AREA CHART
    # ═══════════════════════════════════════════════════════════
    st.subheader("Category Allocation Over Time")

    color_map = {
        "Indian Equity": "#2E86AB",
        "Overseas Equity": "#A23B72",
        "REITs & InvITs": "#F18F01",
        "Debt & Money Market": "#C73E1D",
        "Cash & Equivalents": "#3B1F2B",
    }

    # Melt for plotly
    df_melt = df_filtered[["Date"] + cat_cols].melt(
        id_vars="Date", var_name="Category", value_name="Allocation %"
    )

    fig_area = px.area(
        df_melt,
        x="Date",
        y="Allocation %",
        color="Category",
        color_discrete_map=color_map,
        title="Asset Category Allocation (% of Portfolio)",
        labels={"Allocation %": "Allocation (%)"},
    )
    fig_area.update_layout(
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5),
        height=500,
        margin=dict(l=20, r=20, t=50, b=20),
    )
    fig_area.update_xaxes(dtick="M12", tickformat="%Y")
    st.plotly_chart(fig_area, use_container_width=True)

    # ═══════════════════════════════════════════════════════════
    # 2. INDIVIDUAL CATEGORY TRENDS — LINE CHARTS
    # ═══════════════════════════════════════════════════════════
    st.subheader("Individual Category Trends")

    col_left, col_right = st.columns(2)

    with col_left:
        fig_ie = go.Figure()
        fig_ie.add_trace(go.Scatter(
            x=df_filtered["Date"],
            y=df_filtered["Indian Equity"],
            mode="lines+markers",
            name="Indian Equity",
            line=dict(color="#2E86AB", width=2),
            marker=dict(size=3),
        ))
        fig_ie.update_layout(
            title="Indian Equity %",
            height=300,
            margin=dict(l=20, r=20, t=40, b=20),
            yaxis_title="%",
        )
        st.plotly_chart(fig_ie, use_container_width=True)

    with col_right:
        fig_oe = go.Figure()
        fig_oe.add_trace(go.Scatter(
            x=df_filtered["Date"],
            y=df_filtered["Overseas Equity"],
            mode="lines+markers",
            name="Overseas Equity",
            line=dict(color="#A23B72", width=2),
            marker=dict(size=3),
        ))
        fig_oe.update_layout(
            title="Overseas Equity %",
            height=300,
            margin=dict(l=20, r=20, t=40, b=20),
            yaxis_title="%",
        )
        st.plotly_chart(fig_oe, use_container_width=True)

    col_left2, col_right2 = st.columns(2)

    with col_left2:
        fig_debt = go.Figure()
        fig_debt.add_trace(go.Scatter(
            x=df_filtered["Date"],
            y=df_filtered["Debt & Money Market"],
            mode="lines+markers",
            name="Debt & Money Market",
            line=dict(color="#C73E1D", width=2),
            marker=dict(size=3),
        ))
        fig_debt.update_layout(
            title="Debt & Money Market %",
            height=300,
            margin=dict(l=20, r=20, t=40, b=20),
            yaxis_title="%",
        )
        st.plotly_chart(fig_debt, use_container_width=True)

    with col_right2:
        fig_cash = go.Figure()
        fig_cash.add_trace(go.Scatter(
            x=df_filtered["Date"],
            y=df_filtered["Cash & Equivalents"],
            mode="lines+markers",
            name="Cash & Equivalents",
            line=dict(color="#3B1F2B", width=2),
            marker=dict(size=3),
        ))
        fig_cash.update_layout(
            title="Cash & Equivalents %",
            height=300,
            margin=dict(l=20, r=20, t=40, b=20),
            yaxis_title="%",
        )
        st.plotly_chart(fig_cash, use_container_width=True)

    st.divider()

    # ═══════════════════════════════════════════════════════════
    # 3. SECTOR ALLOCATION HEATMAP (months with sector data)
    # ═══════════════════════════════════════════════════════════
    st.subheader("Sector Allocation Heatmap")

    # Build sector DataFrame from records with sector data
    sector_rows = []
    for r in records:
        if r["sector_count"] > 3 and r["quality"] in selected_quality:
            date = pd.to_datetime(r["date"])
            for sector, pct in r["sectors"].items():
                sector_rows.append({
                    "Date": date,
                    "Label": date.strftime("%b %Y"),
                    "Sector": sector,
                    "Allocation": pct,
                })

    if sector_rows:
        df_sectors = pd.DataFrame(sector_rows)

        # Get top N sectors by average allocation
        top_n = st.slider("Top N sectors to show", 5, 25, 12, key="sector_slider")
        avg_alloc = df_sectors.groupby("Sector")["Allocation"].mean().nlargest(top_n)
        top_sectors = avg_alloc.index.tolist()

        df_sectors_top = df_sectors[df_sectors["Sector"].isin(top_sectors)]

        # Pivot for heatmap
        pivot = df_sectors_top.pivot_table(
            index="Sector", columns="Date", values="Allocation", aggfunc="first"
        )
        # Sort sectors by average allocation
        pivot = pivot.reindex(top_sectors)

        # Format column labels
        col_labels = [d.strftime("%b\n%Y") for d in pivot.columns]

        fig_heatmap = go.Figure(data=go.Heatmap(
            z=pivot.values,
            x=col_labels,
            y=pivot.index,
            colorscale="YlOrRd",
            colorbar=dict(title="%"),
            hoverongaps=False,
            text=pivot.values.round(1),
            texttemplate="%{text}",
            textfont={"size": 8},
        ))
        fig_heatmap.update_layout(
            height=max(400, top_n * 35),
            margin=dict(l=20, r=20, t=20, b=20),
            xaxis=dict(tickangle=-45, nticks=min(30, len(pivot.columns))),
        )
        st.plotly_chart(fig_heatmap, use_container_width=True)
    else:
        st.info("No sector data available for the selected quality filters.")

    st.divider()

    # ═══════════════════════════════════════════════════════════
    # 4. AUM GROWTH OVER TIME
    # ═══════════════════════════════════════════════════════════
    st.subheader("AUM Growth Over Time")

    aum_rows = []
    for r in records:
        aum_str = r.get("aum", "N/A")
        if aum_str and aum_str != "N/A":
            # Parse AUM like "₹1,34,253.17 Cr" or "₹451.86 Cr"
            import re
            nums = re.findall(r"[\d,]+\.?\d*", aum_str.replace(",", "", 1))
            # Handle Indian numbering: remove all commas and parse
            clean = aum_str.replace("₹", "").replace(" Cr", "").replace("Crores", "").replace("`", "").strip()
            clean = clean.replace(",", "")
            try:
                aum_val = float(clean)
                aum_rows.append({
                    "Date": pd.to_datetime(r["date"]),
                    "AUM (Cr)": aum_val,
                })
            except ValueError:
                pass

    if aum_rows:
        df_aum = pd.DataFrame(aum_rows)
        fig_aum = px.area(
            df_aum, x="Date", y="AUM (Cr)",
            title="Assets Under Management",
            labels={"AUM (Cr)": "AUM (₹ Crores)"},
        )
        fig_aum.update_traces(line_color="#2E86AB", fillcolor="rgba(46,134,171,0.2)")
        fig_aum.update_layout(
            height=350,
            margin=dict(l=20, r=20, t=50, b=20),
        )
        st.plotly_chart(fig_aum, use_container_width=True)
    else:
        st.info("No AUM data available.")

    st.divider()

    # ═══════════════════════════════════════════════════════════
    # 5. DETAILED DATA TABLE
    # ═══════════════════════════════════════════════════════════
    st.subheader("Detailed Monthly Data")

    display_df = df_filtered[["Date", "AUM"] + cat_cols + ["Category Total", "Quality", "Sector Count"]].copy()
    display_df["Date"] = display_df["Date"].dt.strftime("%b %Y")

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        height=400,
        column_config={
            "Indian Equity": st.column_config.NumberColumn(format="%.1f%%"),
            "Overseas Equity": st.column_config.NumberColumn(format="%.1f%%"),
            "REITs & InvITs": st.column_config.NumberColumn(format="%.1f%%"),
            "Debt & Money Market": st.column_config.NumberColumn(format="%.1f%%"),
            "Cash & Equivalents": st.column_config.NumberColumn(format="%.1f%%"),
            "Category Total": st.column_config.NumberColumn(format="%.1f%%"),
        },
    )

    # ── Footer ──
    st.divider()
    st.caption(
        f"Data from {history['total_months']} monthly PPFAS factsheets "
        f"({history['date_range']['start'][:7]} to {history['date_range']['end'][:7]}). "
        f"Generated: {history['generated']}. "
        "Quality: 'good' = categories sum to ~100%, 'approximate' = 90-95%, "
        "'incomplete' = <90%. Older factsheets (2013-2018) may have limited data."
    )


if __name__ == "__main__":
    main()
else:
    main()
