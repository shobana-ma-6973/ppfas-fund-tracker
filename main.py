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
from factsheet_parser import fetch_and_parse_factsheet, load_factsheet_data, check_factsheet_available
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
from sent_tracker import get_target_month, is_already_sent, mark_as_sent
from nav_averages import get_nav_summary
from daily_nav_email import build_daily_nav_email

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

    nav_chart = generate_nav_chart_base64(df_nav, months=6)
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


def check_and_send():
    """
    Smart daily check mode:
    1. Determine target month (previous month from today)
    2. If report already sent for that month → skip
    3. Check if factsheet is available → if not → exit (retry tomorrow)
    4. If available → run full pipeline → mark as sent
    
    Returns exit code: 0=success/skip, 1=error
    """
    target_year, target_month = get_target_month()
    month_label = datetime(target_year, target_month, 1).strftime("%B %Y")
    
    logger.info("=" * 60)
    logger.info(f"SMART CHECK: Looking for {month_label} factsheet")
    logger.info("=" * 60)
    
    # Step 1: Check if already sent
    if is_already_sent(target_year, target_month):
        logger.info(f"⏭️  Report for {month_label} already sent. Nothing to do.")
        return 0
    
    # Step 2: Check factsheet availability
    available, factsheet_url = check_factsheet_available(target_year, target_month)
    
    if not available:
        logger.info(f"⏳ Factsheet for {month_label} not yet released. Will retry tomorrow.")
        return 0
    
    # Step 3: Factsheet is available! Run the full pipeline
    logger.info(f"🎯 Factsheet for {month_label} is available! Running full pipeline...")
    
    success = run_pipeline(send_mail=True, dry_run=False)
    
    if success:
        # Step 4: Mark as sent so we don't send again
        mark_as_sent(target_year, target_month, factsheet_url)
        logger.info(f"✅ Report for {month_label} sent and marked as done!")
        return 0
    else:
        logger.error(f"❌ Pipeline failed for {month_label}. Will retry tomorrow.")
        return 1


def run_daily_nav(send_mail: bool = True, dry_run: bool = False):
    """
    Daily NAV email pipeline:
    1. Fetch latest NAV data
    2. Calculate rolling & monthly averages
    3. Build daily NAV email
    4. Send email
    """
    config = load_config()
    scheme_code = config["fund"]["scheme_code"]
    data_dir = Path(__file__).parent / "data"
    data_dir.mkdir(exist_ok=True)

    logger.info("=" * 60)
    logger.info("DAILY NAV EMAIL PIPELINE")
    logger.info("=" * 60)

    # Step 1: Fetch NAV
    logger.info("Step 1: Fetching NAV data...")
    df_nav = fetch_nav_history(scheme_code)
    current_nav = float(df_nav.iloc[-1]["nav"])
    nav_date = df_nav.iloc[-1]["date"].strftime("%d %b %Y")
    logger.info(f"Latest NAV: ₹{current_nav:.4f} as of {nav_date}")

    # Step 2: Calculate averages
    logger.info("Step 2: Calculating NAV averages...")
    nav_summary = get_nav_summary(df_nav)
    rolling = nav_summary["rolling_averages"]
    for period in ["1M", "3M", "6M", "1Y", "3Y", "5Y"]:
        avg = rolling.get(period, {}).get("avg_nav")
        if avg:
            logger.info(f"  {period} avg: ₹{avg:.4f}")

    # Step 3: Build email
    logger.info("Step 3: Building daily NAV email...")
    html_body = build_daily_nav_email(nav_summary)

    # Save preview
    preview_path = data_dir / "daily_nav_preview.html"
    with open(preview_path, "w") as f:
        f.write(html_body)
    logger.info(f"Preview saved to {preview_path}")

    # Step 4: Send email
    if send_mail and not dry_run:
        logger.info("Step 4: Sending daily NAV email...")

        sender_email = os.environ.get("GMAIL_ADDRESS", config["email"]["sender"])
        sender_password = os.environ.get("GMAIL_APP_PASSWORD")
        recipients_env = os.environ.get("EMAIL_RECIPIENTS", "")

        if recipients_env:
            recipients = [r.strip() for r in recipients_env.split(",") if r.strip()]
        else:
            recipients = config["email"]["recipients"]

        if not sender_password:
            logger.error("GMAIL_APP_PASSWORD not set!")
            return False

        today_str = datetime.now().strftime("%d %b %Y")
        subject = f"PPFAS Flexi Cap — Daily NAV ₹{current_nav:.4f} — {today_str}"

        success = send_email(
            sender_email=sender_email,
            sender_password=sender_password,
            recipients=recipients,
            subject=subject,
            html_body=html_body,
        )

        if success:
            logger.info("✅ Daily NAV email sent!")
        else:
            logger.error("❌ Failed to send daily NAV email")
            return False
    else:
        logger.info("Email not sent (dry-run or disabled). Preview saved.")

    logger.info("Daily NAV pipeline completed!")
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
    parser.add_argument(
        "--check-and-send",
        action="store_true",
        help="Smart mode: check factsheet availability, send if available, skip if already sent",
    )
    parser.add_argument(
        "--daily-nav",
        action="store_true",
        help="Send daily NAV email with rolling and monthly averages",
    )
    args = parser.parse_args()

    if args.check_and_send:
        exit_code = check_and_send()
    elif args.daily_nav:
        success = run_daily_nav(
            send_mail=not args.no_email,
            dry_run=args.dry_run,
        )
        exit_code = 0 if success else 1
    else:
        success = run_pipeline(
            send_mail=not args.no_email,
            dry_run=args.dry_run,
        )
        exit_code = 0 if success else 1

    sys.exit(exit_code)
