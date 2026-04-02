"""
PPFAS Flexi Cap Fund - Daily NAV Email Builder
Generates HTML email with today's NAV, day change, and rolling/monthly averages.
"""

import logging
from datetime import datetime

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

    # Build monthly averages table (last 5 years)
    monthly_rows = ""
    for _, row in monthly_df.iterrows():
        avg = row["avg_nav"]
        mn = row["min_nav"]
        mx = row["max_nav"]
        monthly_rows += f"""
        <tr>
            <td style="padding: 8px 12px; border-bottom: 1px solid #f0f0f0; font-weight: 500;">{row['month_name']}</td>
            <td style="padding: 8px 12px; border-bottom: 1px solid #f0f0f0; text-align: right;">₹{avg:.4f}</td>
            <td style="padding: 8px 12px; border-bottom: 1px solid #f0f0f0; text-align: right; color: #999;">₹{mn:.4f}</td>
            <td style="padding: 8px 12px; border-bottom: 1px solid #f0f0f0; text-align: right; color: #999;">₹{mx:.4f}</td>
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

            <!-- Monthly Averages -->
            <tr>
                <td style="padding: 16px 32px 32px 32px;">
                    <h3 style="margin: 0 0 12px 0; font-size: 16px; color: #1e3a5f;">
                        📅 Monthly Average NAV (Last 5 Years)
                    </h3>
                    <table width="100%" cellpadding="0" cellspacing="0" style="border-radius: 8px; border: 1px solid #e8eaed; overflow: hidden;">
                        <tr style="background: #f0f2f6;">
                            <th style="padding: 8px 12px; text-align: left; font-size: 12px; color: #666; text-transform: uppercase;">Month</th>
                            <th style="padding: 8px 12px; text-align: right; font-size: 12px; color: #666; text-transform: uppercase;">Avg NAV</th>
                            <th style="padding: 8px 12px; text-align: right; font-size: 12px; color: #666; text-transform: uppercase;">Min</th>
                            <th style="padding: 8px 12px; text-align: right; font-size: 12px; color: #666; text-transform: uppercase;">Max</th>
                        </tr>
                        {monthly_rows}
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
