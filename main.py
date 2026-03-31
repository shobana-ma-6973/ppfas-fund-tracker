"""
PPFAS Flexi Cap Fund Tracker - Main Orchestrator
Runs the full monthly pipeline: fetch data → build email → send.
Can be triggered by GitHub Actions or run manually.
"""

import os
import sys
import yaml
import logging
from datetime import datetime
from pathlib import Path

# Ensure src is in path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from nav_fetcher import fetch_nav_history, save_nav_history, get_current_nav
from factsheet_parser import fetch_and_parse_factsheet, load_factsheet_data
from returns_calculator import (
    calculate_rolling_returns,
    get_return_summary,
    calculate_point_to_point_returns,
)
from email_builder import (
    build_html_email,
    generate_nav_chart_base64,
    generate_rolling_return_chart_base64,
    generate_sector_bar_base64,
)
from email_sender import send_email

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("main")


def load_config() -> dict:
    """Load configuration from config.yaml."""
    config_path = Path(__file__).parent / "config.yaml"
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def run_pipeline(send_mail: bool = True, dry_run: bool = False):
    """
    Execute the full monthly pipeline.

    Args:
        send_mail: Whether to send the email (False for testing)
        dry_run: If True, generate email HTML but don't send
    """
    config = load_config()
    scheme_code = config["fund"]["scheme_code"]
    data_dir = Path(__file__).parent / "data"
    data_dir.mkdir(exist_ok=True)

    # ── Step 1: Fetch NAV History ────────────────────────────
    logger.info("=" * 60)
    logger.info("STEP 1: Fetching NAV history...")
    logger.info("=" * 60)

    df_nav = fetch_nav_history(scheme_code)
    nav_file = str(data_dir / "nav_history.csv")
    save_nav_history(df_nav, nav_file)
    current_nav = {
        "nav": float(df_nav.iloc[-1]["nav"]),
        "date": df_nav.iloc[-1]["date"].strftime("%Y-%m-%d"),
    }
    logger.info(f"Latest NAV: ₹{current_nav['nav']:.4f} as of {current_nav['date']}")

    # ── Step 2: Fetch & Parse Factsheet ──────────────────────
    logger.info("=" * 60)
    logger.info("STEP 2: Fetching and parsing factsheet...")
    logger.info("=" * 60)

    factsheet = fetch_and_parse_factsheet()
    logger.info(f"AUM: {factsheet.get('aum', 'N/A')}")
    logger.info(f"Sectors found: {len(factsheet.get('sector_allocation', {}))}")
    logger.info(f"Categories found: {len(factsheet.get('category_allocation', {}))}")

    # ── Step 3: Calculate Returns ────────────────────────────
    logger.info("=" * 60)
    logger.info("STEP 3: Calculating returns...")
    logger.info("=" * 60)

    p2p_returns = calculate_point_to_point_returns(df_nav)
    logger.info(f"Point-to-point returns: {p2p_returns}")

    df_rolling = calculate_rolling_returns(df_nav, window_years=3)
    rolling_summary = get_return_summary(df_rolling)
    logger.info(f"Rolling return summary: {rolling_summary}")

    # ── Step 4: Generate Charts ──────────────────────────────
    logger.info("=" * 60)
    logger.info("STEP 4: Generating charts...")
    logger.info("=" * 60)

    nav_chart = generate_nav_chart_base64(df_nav, months=12)
    rolling_chart = generate_rolling_return_chart_base64(df_rolling, window=3)
    sector_chart = generate_sector_bar_base64(factsheet.get("sector_allocation", {}))

    logger.info(f"NAV chart: {len(nav_chart)} bytes")
    logger.info(f"Rolling chart: {len(rolling_chart)} bytes")
    logger.info(f"Sector chart: {len(sector_chart)} bytes")

    # ── Step 5: Build Email ──────────────────────────────────
    logger.info("=" * 60)
    logger.info("STEP 5: Building email...")
    logger.info("=" * 60)

    dashboard_url = os.environ.get(
        "DASHBOARD_URL",
        config.get("dashboard", {}).get("url", "https://your-app.streamlit.app"),
    )

    html_body = build_html_email(
        nav_data=current_nav,
        p2p_returns=p2p_returns,
        rolling_summary=rolling_summary,
        factsheet_data=factsheet,
        nav_chart_b64=nav_chart,
        rolling_chart_b64=rolling_chart,
        sector_chart_b64=sector_chart,
        dashboard_url=dashboard_url,
    )

    # Save email HTML for preview
    preview_path = data_dir / "email_preview.html"
    with open(preview_path, "w") as f:
        # Replace CID references with inline base64 for preview
        preview_html = html_body
        if nav_chart:
            preview_html = preview_html.replace(
                'src="cid:nav_chart"',
                f'src="data:image/png;base64,{nav_chart}"'
            )
        if rolling_chart:
            preview_html = preview_html.replace(
                'src="cid:rolling_chart"',
                f'src="data:image/png;base64,{rolling_chart}"'
            )
        if sector_chart:
            preview_html = preview_html.replace(
                'src="cid:sector_chart"',
                f'src="data:image/png;base64,{sector_chart}"'
            )
        f.write(preview_html)
    logger.info(f"Email preview saved to {preview_path}")

    # ── Step 6: Send Email ───────────────────────────────────
    if send_mail and not dry_run:
        logger.info("=" * 60)
        logger.info("STEP 6: Sending email...")
        logger.info("=" * 60)

        sender_email = os.environ.get("GMAIL_ADDRESS", config["email"]["sender"])
        sender_password = os.environ.get("GMAIL_APP_PASSWORD")
        recipients_env = os.environ.get("EMAIL_RECIPIENTS", "")

        if recipients_env:
            recipients = [r.strip() for r in recipients_env.split(",") if r.strip()]
        else:
            recipients = config["email"]["recipients"]

        if not sender_password:
            logger.error(
                "GMAIL_APP_PASSWORD not set! "
                "Set it as an environment variable or GitHub secret."
            )
            return False

        month_year = datetime.now().strftime("%B %Y")
        subject = f"{config['email']['subject_prefix']} Monthly Report — {month_year}"

        charts = {
            "nav_chart": nav_chart,
            "rolling_chart": rolling_chart,
            "sector_chart": sector_chart,
        }

        success = send_email(
            sender_email=sender_email,
            sender_password=sender_password,
            recipients=recipients,
            subject=subject,
            html_body=html_body,
            charts=charts,
        )

        if success:
            logger.info("✅ Monthly report sent successfully!")
        else:
            logger.error("❌ Failed to send monthly report")
            return False
    elif dry_run:
        logger.info("DRY RUN: Email not sent. Preview saved to data/email_preview.html")
    else:
        logger.info("Email sending disabled. Preview saved to data/email_preview.html")

    logger.info("=" * 60)
    logger.info("Pipeline completed successfully!")
    logger.info("=" * 60)
    return True


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="PPFAS Fund Tracker - Monthly Pipeline")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run pipeline without sending email (generates preview)",
    )
    parser.add_argument(
        "--no-email",
        action="store_true",
        help="Skip email sending entirely",
    )
    args = parser.parse_args()

    success = run_pipeline(
        send_mail=not args.no_email,
        dry_run=args.dry_run,
    )

    sys.exit(0 if success else 1)
