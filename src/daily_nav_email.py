"""
PPFAS Flexi Cap Fund - Daily NAV Email Builder
Generates HTML email with today's NAV, day change, and rolling/monthly averages.
Uses pure HTML/CSS heatmap grid for monthly averages (no images needed).
"""

import logging
from datetime import datetime
import pandas as pd

logger = logging.getLogger(__name__)


def _color(val):
    """Return green/red color based on positive/negative."""
    if val is None:
        return "#666"
    return "#0d9d5c" if val >= 0 else "#e23636"


def _arrow(val):
    """Return up/down arrow."""
    if val is None:
        return ""
    return "▲" if val >= 0 else "▼"


def _sign(val):
    """Return +/- prefix."""
    if val is None:
        return "N/A"
    return f"+{val:.2f}" if val >= 0 else f"{val:.2f}"


def _nav_heatmap_color(nav_val, nav_min, nav_max):
    """
    Return a background color for heatmap cell based on NAV value.
    Low NAV → warm red, High NAV → cool green/blue.
    """
    if nav_max == nav_min:
        ratio = 0.5
    else:
        ratio = (nav_val - nav_min) / (nav_max - nav_min)

    # Interpolate from red (low) through yellow (mid) to green (high)
    if ratio < 0.5:
        # Red → Yellow
        r = 245
        g = int(160 + (ratio * 2) * 80)  # 160 → 240
        b = int(140 + (ratio * 2) * 40)  # 140 → 180
    else:
        # Yellow → Green
        r = int(240 - ((ratio - 0.5) * 2) * 100)  # 240 → 140
        g = int(240 - ((ratio - 0.5) * 2) * 20)   # 240 → 220
        b = int(180 - ((ratio - 0.5) * 2) * 30)   # 180 → 150

    return f"rgb({r},{g},{b})"


def _build_heatmap_grid(monthly_df: pd.DataFrame) -> str:
    """
    Build a pure HTML/CSS heatmap grid: Years (rows) × Months (columns).
    Each cell shows avg NAV with color intensity based on value.
    """
    df = monthly_df.copy()
    years = sorted(df["year"].unique())
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    # Global min/max for color scaling
    nav_min = df["avg_nav"].min()
    nav_max = df["avg_nav"].max()

    # Header row
    header_cells = '<th style="padding:6px 4px; font-size:11px; color:#555; text-align:center; border-bottom:2px solid #ddd; background:#f8f9fb; min-width:48px;">Year</th>'
    for m in month_names:
        header_cells += f'<th style="padding:6px 2px; font-size:10px; color:#666; text-align:center; border-bottom:2px solid #ddd; background:#f8f9fb; min-width:44px;">{m}</th>'

    # Data rows
    data_rows = ""
    for yr in years:
        yr_data = df[df["year"] == yr]
        row_cells = f'<td style="padding:6px 4px; font-weight:700; font-size:12px; color:#1e3a5f; text-align:center; border-bottom:1px solid #eee; background:#fafbfc;">{int(yr)}</td>'

        for m in range(1, 13):
            cell_data = yr_data[yr_data["month"] == m]
            if not cell_data.empty:
                avg = cell_data.iloc[0]["avg_nav"]
                bg = _nav_heatmap_color(avg, nav_min, nav_max)
                # Determine text color for contrast
                row_cells += f'''<td style="padding:5px 2px; text-align:center; font-size:10px; font-weight:600; color:#333; background:{bg}; border-bottom:1px solid #eee; border-right:1px solid rgba(255,255,255,0.5);">₹{avg:.1f}</td>'''
            else:
                row_cells += '<td style="padding:5px 2px; text-align:center; font-size:10px; color:#ccc; background:#fafafa; border-bottom:1px solid #eee;">—</td>'

        data_rows += f"<tr>{row_cells}</tr>\n"

    return f"""
    <table width="100%" cellpadding="0" cellspacing="0" style="border-radius:8px; border:1px solid #e0e0e0; overflow:hidden; border-collapse:collapse;">
        <tr>{header_cells}</tr>
        {data_rows}
    </table>
    """


def _build_mom_bars(monthly_df: pd.DataFrame) -> str:
    """
    Build HTML rows showing month-over-month % change with visual bars.
    Shows last 12 months only for readability.
    """
    df = monthly_df.copy().sort_values(["year", "month"]).reset_index(drop=True)
    df["mom_pct"] = df["avg_nav"].pct_change() * 100

    # Last 12 months
    df_recent = df.tail(12).dropna(subset=["mom_pct"])
    if df_recent.empty:
        return ""

    max_abs = max(abs(df_recent["mom_pct"].max()), abs(df_recent["mom_pct"].min()), 1)

    rows = ""
    for _, row in df_recent.iterrows():
        pct = row["mom_pct"]
        bar_color = "#0d9d5c" if pct >= 0 else "#e23636"
        bar_width = min(abs(pct) / max_abs * 100, 100)
        arrow = "▲" if pct >= 0 else "▼"
        sign = "+" if pct >= 0 else ""

        rows += f"""
        <tr>
            <td style="padding:6px 10px; border-bottom:1px solid #f0f0f0; font-weight:500; font-size:12px; color:#333; white-space:nowrap; width:70px;">{row['month_name']}</td>
            <td style="padding:6px 10px; border-bottom:1px solid #f0f0f0; font-size:12px; color:{bar_color}; font-weight:600; text-align:right; white-space:nowrap; width:65px;">
                {arrow} {sign}{pct:.1f}%
            </td>
            <td style="padding:6px 10px; border-bottom:1px solid #f0f0f0;">
                <div style="background:#f0f0f0; border-radius:4px; height:14px; width:100%; overflow:hidden;">
                    <div style="background:{bar_color}; height:100%; width:{bar_width:.0f}%; border-radius:4px; opacity:0.75;"></div>
                </div>
            </td>
        </tr>"""

    return rows


def _build_yearly_summary_rows(monthly_df: pd.DataFrame) -> str:
    """Build HTML table rows with yearly NAV summary."""
    df = monthly_df.copy()
    years = sorted(df["year"].unique())  # ascending: 2021, 2022, ...
    rows = ""
    prev_year_avg = None
    for yr in years:
        yr_data = df[df["year"] == yr]
        avg = yr_data["avg_nav"].mean()
        mn = yr_data["min_nav"].min()
        mx = yr_data["max_nav"].max()
        volatility = mx - mn

        if prev_year_avg is not None:
            yoy = ((avg - prev_year_avg) / prev_year_avg) * 100
            yoy_color = "#0d9d5c" if yoy >= 0 else "#e23636"
            yoy_str = f'<span style="color:{yoy_color}; font-weight:600;">{yoy:+.1f}%</span>'
        else:
            yoy_str = '<span style="color:#999;">—</span>'
        prev_year_avg = avg

        rows += f"""
        <tr>
            <td style="padding: 8px 12px; border-bottom: 1px solid #f0f0f0; font-weight: 600;">{int(yr)}</td>
            <td style="padding: 8px 12px; border-bottom: 1px solid #f0f0f0; text-align: right;">₹{avg:.2f}</td>
            <td style="padding: 8px 12px; border-bottom: 1px solid #f0f0f0; text-align: right; color: #0d9d5c;">₹{mx:.2f}</td>
            <td style="padding: 8px 12px; border-bottom: 1px solid #f0f0f0; text-align: right; color: #e23636;">₹{mn:.2f}</td>
            <td style="padding: 8px 12px; border-bottom: 1px solid #f0f0f0; text-align: right; color: #666;">₹{volatility:.2f}</td>
            <td style="padding: 8px 12px; border-bottom: 1px solid #f0f0f0; text-align: right;">{yoy_str}</td>
        </tr>"""
    # Rows are already in ascending order; reverse so latest year is on top
    return rows[::-1] if False else _reverse_rows(rows)


def _reverse_rows(rows_html: str) -> str:
    """Reverse the order of <tr>...</tr> blocks so newest year appears first."""
    import re
    trs = re.findall(r'<tr>.*?</tr>', rows_html, re.DOTALL)
    return "\n".join(reversed(trs))


def build_daily_nav_email(nav_summary: dict) -> str:
    """
    Build HTML email for daily NAV update.

    Args:
        nav_summary: Output from nav_averages.get_nav_summary()

    Returns:
        HTML string
    """
    nav = nav_summary["latest_nav"]
    date = nav_summary["latest_date"]
    day_change = nav_summary.get("day_change")
    day_change_pct = nav_summary.get("day_change_pct")
    rolling = nav_summary["rolling_averages"]
    monthly_df = nav_summary["monthly_averages"]

    # Generate HTML components
    heatmap_html = _build_heatmap_grid(monthly_df)
    mom_bars_html = _build_mom_bars(monthly_df)
    yearly_rows = _build_yearly_summary_rows(monthly_df)

    # Day change display
    if day_change is not None:
        change_color = _color(day_change)
        change_arrow = _arrow(day_change)
        change_text = f"{change_arrow} {_sign(day_change)} ({_sign(day_change_pct)}%)"
    else:
        change_color = "#666"
        change_text = "N/A"

    # Build rolling averages table rows
    rolling_rows = ""
    for period in ["1M", "3M", "6M", "1Y", "2Y", "3Y", "5Y"]:
        data = rolling.get(period, {})
        avg = data.get("avg_nav")
        chg = data.get("change_pct")
        if avg is not None:
            chg_color = _color(chg)
            rolling_rows += f"""
            <tr>
                <td style="padding: 10px 16px; border-bottom: 1px solid #f0f0f0; font-weight: 600; color: #333;">{period}</td>
                <td style="padding: 10px 16px; border-bottom: 1px solid #f0f0f0; text-align: right;">₹{avg:.4f}</td>
                <td style="padding: 10px 16px; border-bottom: 1px solid #f0f0f0; text-align: right; color: {chg_color}; font-weight: 600;">
                    {_sign(chg)}%
                </td>
            </tr>"""
        else:
            rolling_rows += f"""
            <tr>
                <td style="padding: 10px 16px; border-bottom: 1px solid #f0f0f0; font-weight: 600; color: #333;">{period}</td>
                <td style="padding: 10px 16px; border-bottom: 1px solid #f0f0f0; text-align: right; color: #999;">N/A</td>
                <td style="padding: 10px 16px; border-bottom: 1px solid #f0f0f0; text-align: right; color: #999;">N/A</td>
            </tr>"""

    today = datetime.now().strftime("%d %b %Y")

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin: 0; padding: 0; background-color: #f5f6fa; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
        <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f5f6fa; padding: 20px 0;">
        <tr><td align="center">
        <table width="640" cellpadding="0" cellspacing="0" style="background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.06);">

            <!-- Header -->
            <tr>
                <td style="background: linear-gradient(135deg, #1e3a5f 0%, #2d5a87 100%); padding: 28px 32px; text-align: center;">
                    <h1 style="margin: 0; color: white; font-size: 22px; font-weight: 600;">
                        📊 PPFAS Flexi Cap Fund — Daily NAV
                    </h1>
                    <p style="margin: 6px 0 0 0; color: rgba(255,255,255,0.75); font-size: 13px;">
                        {today}
                    </p>
                </td>
            </tr>

            <!-- NAV Hero Card -->
            <tr>
                <td style="padding: 32px 32px 16px 32px;">
                    <table width="100%" cellpadding="0" cellspacing="0" style="background: #f8f9fb; border-radius: 10px; border: 1px solid #e8eaed;">
                    <tr>
                        <td style="padding: 24px; text-align: center;">
                            <p style="margin: 0; font-size: 13px; color: #666; text-transform: uppercase; letter-spacing: 1px;">Latest NAV</p>
                            <h2 style="margin: 8px 0; font-size: 42px; color: #1e3a5f; font-weight: 700;">₹{nav:.4f}</h2>
                            <p style="margin: 0; font-size: 14px; color: #999;">As of {date}</p>
                            <p style="margin: 8px 0 0 0; font-size: 16px; color: {change_color}; font-weight: 600;">
                                {change_text}
                            </p>
                        </td>
                    </tr>
                    </table>
                </td>
            </tr>

            <!-- Rolling Averages -->
            <tr>
                <td style="padding: 16px 32px;">
                    <h3 style="margin: 0 0 12px 0; font-size: 16px; color: #1e3a5f;">
                        📈 Average NAV (Rolling)
                    </h3>
                    <table width="100%" cellpadding="0" cellspacing="0" style="border-radius: 8px; border: 1px solid #e8eaed; overflow: hidden;">
                        <tr style="background: #f0f2f6;">
                            <th style="padding: 10px 16px; text-align: left; font-size: 12px; color: #666; text-transform: uppercase;">Period</th>
                            <th style="padding: 10px 16px; text-align: right; font-size: 12px; color: #666; text-transform: uppercase;">Avg NAV</th>
                            <th style="padding: 10px 16px; text-align: right; font-size: 12px; color: #666; text-transform: uppercase;">vs Current</th>
                        </tr>
                        {rolling_rows}
                    </table>
                    <p style="margin: 6px 0 0 0; font-size: 11px; color: #aaa;">
                        "vs Current" shows how today's NAV compares to the average for that period.
                    </p>
                </td>
            </tr>

            <!-- Monthly NAV Heatmap Grid -->
            <tr>
                <td style="padding: 16px 32px 8px 32px;">
                    <h3 style="margin: 0 0 4px 0; font-size: 16px; color: #1e3a5f;">
                        📅 Monthly Average NAV (Last 5 Years)
                    </h3>
                    <p style="margin: 0 0 10px 0; font-size: 11px; color: #999;">
                        Each cell shows monthly avg NAV. Color: <span style="color:#e23636;">red = lower</span> → <span style="color:#0d9d5c;">green = higher</span>
                    </p>
                    {heatmap_html}
                </td>
            </tr>

            <!-- Month-over-Month Momentum (last 12 months) -->
            <tr>
                <td style="padding: 12px 32px 8px 32px;">
                    <h3 style="margin: 0 0 10px 0; font-size: 14px; color: #1e3a5f;">
                        📊 Monthly Momentum (Last 12 Months)
                    </h3>
                    <table width="100%" cellpadding="0" cellspacing="0" style="border-radius: 8px; border: 1px solid #e8eaed; overflow: hidden;">
                        {mom_bars_html}
                    </table>
                </td>
            </tr>

            <!-- Yearly Summary Table -->
            <tr>
                <td style="padding: 8px 32px 32px 32px;">
                    <h3 style="margin: 0 0 10px 0; font-size: 14px; color: #1e3a5f;">
                        📋 Yearly Summary
                    </h3>
                    <table width="100%" cellpadding="0" cellspacing="0" style="border-radius: 8px; border: 1px solid #e8eaed; overflow: hidden; font-size: 13px;">
                        <tr style="background: #f0f2f6;">
                            <th style="padding: 8px 12px; text-align: left; font-size: 11px; color: #666; text-transform: uppercase;">Year</th>
                            <th style="padding: 8px 12px; text-align: right; font-size: 11px; color: #666; text-transform: uppercase;">Avg NAV</th>
                            <th style="padding: 8px 12px; text-align: right; font-size: 11px; color: #666; text-transform: uppercase;">High</th>
                            <th style="padding: 8px 12px; text-align: right; font-size: 11px; color: #666; text-transform: uppercase;">Low</th>
                            <th style="padding: 8px 12px; text-align: right; font-size: 11px; color: #666; text-transform: uppercase;">Spread</th>
                            <th style="padding: 8px 12px; text-align: right; font-size: 11px; color: #666; text-transform: uppercase;">YoY</th>
                        </tr>
                        {yearly_rows}
                    </table>
                </td>
            </tr>

            <!-- Footer -->
            <tr>
                <td style="background: #f8f9fb; padding: 16px 32px; text-align: center; border-top: 1px solid #e8eaed;">
                    <p style="margin: 0; font-size: 11px; color: #999;">
                        Data source: MFAPI | Parag Parikh Flexi Cap Fund — Direct Growth (122639)<br>
                        This is an automated email for informational purposes only, not investment advice.
                    </p>
                </td>
            </tr>

        </table>
        </td></tr>
        </table>
    </body>
    </html>
    """
    return html
