"""
PPFAS Flexi Cap Fund - HTML Email Generator
Builds a rich HTML email with fund metrics, charts, and dashboard link.
"""

import base64
import io
from datetime import datetime
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd
import numpy as np


def generate_nav_chart_base64(df: pd.DataFrame, months: int = 6) -> str:
    """Generate a NAV trend chart and return as base64-encoded PNG."""
    cutoff = df["date"].max() - pd.Timedelta(days=months * 30)
    df_plot = df[df["date"] >= cutoff].copy()

    fig, ax = plt.subplots(figsize=(8, 3), dpi=150)
    ax.plot(df_plot["date"], df_plot["nav"], color="#1e3a5f", linewidth=1.5)
    ax.fill_between(df_plot["date"], df_plot["nav"], alpha=0.1, color="#1e3a5f")
    ax.set_title(f"NAV Trend (Last {months} Months)", fontsize=12, fontweight="bold", color="#1e3a5f")
    ax.set_xlabel("")
    ax.set_ylabel("NAV (₹)", fontsize=9)
    ax.tick_params(labelsize=8)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("₹%.0f"))
    ax.grid(axis="y", alpha=0.3)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


def generate_rolling_return_chart_base64(df_rolling: pd.DataFrame, window: int = 3) -> str:
    """Generate rolling return chart as base64-encoded PNG."""
    df_valid = df_rolling.dropna(subset=["rolling_return_pct"]).copy()

    if df_valid.empty:
        return ""

    fig, ax = plt.subplots(figsize=(8, 3), dpi=150)
    ax.plot(df_valid["date"], df_valid["rolling_return_pct"], color="#2d8a4e", linewidth=1.2)
    ax.axhline(y=df_valid["rolling_return_pct"].mean(), color="orange", linestyle="--", linewidth=1, alpha=0.7)
    ax.fill_between(
        df_valid["date"], df_valid["rolling_return_pct"],
        where=df_valid["rolling_return_pct"] >= 0,
        alpha=0.1, color="#2d8a4e"
    )
    ax.fill_between(
        df_valid["date"], df_valid["rolling_return_pct"],
        where=df_valid["rolling_return_pct"] < 0,
        alpha=0.1, color="red"
    )
    ax.set_title(f"{window}-Year Rolling Returns", fontsize=12, fontweight="bold", color="#1e3a5f")
    ax.set_xlabel("")
    ax.set_ylabel("Return (%)", fontsize=9)
    ax.tick_params(labelsize=8)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.1f%%"))
    ax.grid(axis="y", alpha=0.3)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


def generate_sector_bar_base64(sectors: dict) -> str:
    """Generate horizontal bar chart for sector allocation."""
    if not sectors:
        return ""

    # Top 10 sectors
    items = sorted(sectors.items(), key=lambda x: x[1], reverse=True)[:10]
    names = [x[0] for x in items]
    values = [x[1] for x in items]

    fig, ax = plt.subplots(figsize=(7, 4), dpi=150)
    bars = ax.barh(names[::-1], values[::-1], color="#3b82f6", edgecolor="white", height=0.6)
    for bar, val in zip(bars, values[::-1]):
        ax.text(bar.get_width() + 0.3, bar.get_y() + bar.get_height() / 2,
                f"{val:.1f}%", va="center", fontsize=8, color="#333")
    ax.set_title("Sector Allocation (Top 10)", fontsize=12, fontweight="bold", color="#1e3a5f")
    ax.set_xlabel("Allocation (%)", fontsize=9)
    ax.tick_params(labelsize=8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


def build_html_email(
    nav_data: dict,
    p2p_returns: dict,
    rolling_summary: dict,
    factsheet_data: dict,
    nav_chart_b64: str,
    rolling_chart_b64: str,
    sector_chart_b64: str,
    dashboard_url: str,
    month_year: str = None,
) -> str:
    """
    Build the full HTML email body.
    """
    if month_year is None:
        month_year = datetime.now().strftime("%B %Y")

    # ── Build returns table rows
    returns_rows = ""
    for period in ["1M", "3M", "6M", "1Y", "3Y", "5Y"]:
        val = p2p_returns.get(period)
        if val is not None:
            color = "#16a34a" if val >= 0 else "#dc2626"
            arrow = "▲" if val >= 0 else "▼"
            returns_rows += f"""
            <tr>
                <td style="padding: 8px 12px; border-bottom: 1px solid #eee; font-weight: 500;">{period}</td>
                <td style="padding: 8px 12px; border-bottom: 1px solid #eee; color: {color}; font-weight: 600;">
                    {arrow} {val:.2f}%
                </td>
            </tr>"""
        else:
            returns_rows += f"""
            <tr>
                <td style="padding: 8px 12px; border-bottom: 1px solid #eee;">{period}</td>
                <td style="padding: 8px 12px; border-bottom: 1px solid #eee; color: #999;">N/A</td>
            </tr>"""

    # ── Category allocation table
    categories = factsheet_data.get("category_allocation", {})
    cat_rows = ""
    for cat, pct in categories.items():
        cat_rows += f"""
        <tr>
            <td style="padding: 6px 12px; border-bottom: 1px solid #eee;">{cat}</td>
            <td style="padding: 6px 12px; border-bottom: 1px solid #eee; font-weight: 600;">{pct:.1f}%</td>
        </tr>"""

    # ── Rolling return summary
    rolling_html = ""
    if "error" not in rolling_summary:
        rr = rolling_summary
        color = "#16a34a" if rr["current_rolling_return"] >= 0 else "#dc2626"
        rolling_html = f"""
        <table width="100%" cellpadding="0" cellspacing="0" style="margin: 10px 0;">
            <tr>
                <td style="padding: 6px 12px; border-bottom: 1px solid #eee;">Current 3Y Rolling</td>
                <td style="padding: 6px 12px; border-bottom: 1px solid #eee; font-weight: 700; color: {color};">{rr['current_rolling_return']:.2f}%</td>
            </tr>
            <tr>
                <td style="padding: 6px 12px; border-bottom: 1px solid #eee;">Average</td>
                <td style="padding: 6px 12px; border-bottom: 1px solid #eee;">{rr['average_rolling_return']:.2f}%</td>
            </tr>
            <tr>
                <td style="padding: 6px 12px; border-bottom: 1px solid #eee;">Best</td>
                <td style="padding: 6px 12px; border-bottom: 1px solid #eee; color: #16a34a;">{rr['max_rolling_return']:.2f}% ({rr['max_date']})</td>
            </tr>
            <tr>
                <td style="padding: 6px 12px; border-bottom: 1px solid #eee;">Worst</td>
                <td style="padding: 6px 12px; border-bottom: 1px solid #eee; color: #dc2626;">{rr['min_rolling_return']:.2f}% ({rr['min_date']})</td>
            </tr>
        </table>"""

    # ── Build images (CID references for email or inline base64)
    nav_img = f'<img src="cid:nav_chart" alt="NAV Chart" style="width:100%; max-width:700px; border-radius:8px;" />' if nav_chart_b64 else ""
    rolling_img = f'<img src="cid:rolling_chart" alt="Rolling Returns" style="width:100%; max-width:700px; border-radius:8px;" />' if rolling_chart_b64 else ""
    sector_img = f'<img src="cid:sector_chart" alt="Sector Allocation" style="width:100%; max-width:600px; border-radius:8px;" />' if sector_chart_b64 else ""

    aum = factsheet_data.get("aum", "N/A")

    html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f5f5f5;">

<!-- Main Container -->
<table width="100%" cellpadding="0" cellspacing="0" style="max-width: 700px; margin: 0 auto; background-color: #ffffff;">

    <!-- Header -->
    <tr>
        <td style="background: linear-gradient(135deg, #1e3a5f 0%, #2d5a87 100%); padding: 30px; text-align: center;">
            <h1 style="color: white; margin: 0; font-size: 24px;">📊 PPFAS Flexi Cap Fund</h1>
            <p style="color: #a8c8e8; margin: 8px 0 0 0; font-size: 14px;">Monthly Report — {month_year}</p>
        </td>
    </tr>

    <!-- Key Metrics -->
    <tr>
        <td style="padding: 25px;">
            <table width="100%" cellpadding="0" cellspacing="0">
                <tr>
                    <td width="50%" style="padding: 10px;">
                        <div style="background: #f0f7ff; border-radius: 12px; padding: 20px; text-align: center; border: 1px solid #d0e3f7;">
                            <p style="margin: 0; font-size: 12px; color: #666; text-transform: uppercase; letter-spacing: 1px;">Latest NAV</p>
                            <p style="margin: 8px 0 0 0; font-size: 28px; font-weight: 700; color: #1e3a5f;">₹{nav_data.get('nav', 'N/A')}</p>
                            <p style="margin: 4px 0 0 0; font-size: 11px; color: #888;">as of {nav_data.get('date', 'N/A')}</p>
                        </div>
                    </td>
                    <td width="50%" style="padding: 10px;">
                        <div style="background: #f0f7ff; border-radius: 12px; padding: 20px; text-align: center; border: 1px solid #d0e3f7;">
                            <p style="margin: 0; font-size: 12px; color: #666; text-transform: uppercase; letter-spacing: 1px;">AUM</p>
                            <p style="margin: 8px 0 0 0; font-size: 28px; font-weight: 700; color: #1e3a5f;">{aum}</p>
                            <p style="margin: 4px 0 0 0; font-size: 11px; color: #888;">Assets Under Management</p>
                        </div>
                    </td>
                </tr>
            </table>
        </td>
    </tr>

    <!-- NAV Chart -->
    <tr>
        <td style="padding: 0 25px 20px;">
            {nav_img}
        </td>
    </tr>

    <!-- Returns Table -->
    <tr>
        <td style="padding: 0 25px 20px;">
            <h2 style="color: #1e3a5f; font-size: 18px; border-bottom: 2px solid #1e3a5f; padding-bottom: 8px;">
                📈 Returns
            </h2>
            <table width="100%" cellpadding="0" cellspacing="0" style="border: 1px solid #eee; border-radius: 8px; overflow: hidden;">
                <tr style="background: #f8f9fa;">
                    <th style="padding: 10px 12px; text-align: left; font-size: 13px; color: #666;">Period</th>
                    <th style="padding: 10px 12px; text-align: left; font-size: 13px; color: #666;">Return</th>
                </tr>
                {returns_rows}
            </table>
        </td>
    </tr>

    <!-- Rolling Returns -->
    <tr>
        <td style="padding: 0 25px 20px;">
            <h2 style="color: #1e3a5f; font-size: 18px; border-bottom: 2px solid #1e3a5f; padding-bottom: 8px;">
                🔄 3-Year Rolling Returns
            </h2>
            {rolling_html}
            {rolling_img}
        </td>
    </tr>

    <!-- Category Allocation -->
    {"" if not cat_rows else f'''
    <tr>
        <td style="padding: 0 25px 20px;">
            <h2 style="color: #1e3a5f; font-size: 18px; border-bottom: 2px solid #1e3a5f; padding-bottom: 8px;">
                📦 Category Allocation
            </h2>
            <table width="100%" cellpadding="0" cellspacing="0" style="border: 1px solid #eee; border-radius: 8px; overflow: hidden;">
                <tr style="background: #f8f9fa;">
                    <th style="padding: 8px 12px; text-align: left; font-size: 13px; color: #666;">Category</th>
                    <th style="padding: 8px 12px; text-align: left; font-size: 13px; color: #666;">Allocation</th>
                </tr>
                {cat_rows}
            </table>
        </td>
    </tr>
    '''}

    <!-- Sector Allocation Chart -->
    {"" if not sector_chart_b64 else f'''
    <tr>
        <td style="padding: 0 25px 20px;">
            <h2 style="color: #1e3a5f; font-size: 18px; border-bottom: 2px solid #1e3a5f; padding-bottom: 8px;">
                🏢 Sector Allocation
            </h2>
            {sector_img}
        </td>
    </tr>
    '''}

    <!-- Dashboard CTA -->
    <tr>
        <td style="padding: 20px 25px 30px; text-align: center;">
            <a href="{dashboard_url}" style="
                display: inline-block;
                background: linear-gradient(135deg, #1e3a5f 0%, #2d5a87 100%);
                color: white;
                text-decoration: none;
                padding: 14px 40px;
                border-radius: 8px;
                font-size: 16px;
                font-weight: 600;
                letter-spacing: 0.5px;
            ">
                🔗 View Full Dashboard →
            </a>
        </td>
    </tr>

    <!-- Footer -->
    <tr>
        <td style="background: #f8f9fa; padding: 20px 25px; text-align: center; border-top: 1px solid #eee;">
            <p style="margin: 0; font-size: 11px; color: #999; line-height: 1.6;">
                Data source: MFAPI (NAV) | PPFAS Mutual Fund (Factsheet)<br>
                This is an automated report for informational purposes only. Not investment advice.<br>
                Generated on {datetime.now().strftime('%d %b %Y at %I:%M %p')}
            </p>
        </td>
    </tr>

</table>
</body>
</html>
"""
    return html
