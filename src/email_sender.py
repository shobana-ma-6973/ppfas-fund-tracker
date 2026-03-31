"""
PPFAS Flexi Cap Fund - Email Sender (Gmail SMTP)
Sends HTML email with embedded chart images via Gmail.
"""

import smtplib
import base64
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def send_email(
    sender_email: str,
    sender_password: str,
    recipients: list[str],
    subject: str,
    html_body: str,
    charts: dict = None,
) -> bool:
    """
    Send HTML email via Gmail SMTP with embedded chart images.

    Args:
        sender_email: Gmail address
        sender_password: Gmail App Password (NOT regular password)
        recipients: List of recipient email addresses
        subject: Email subject line
        html_body: HTML content of the email
        charts: Dict of {cid_name: base64_png_data} for embedded images

    Returns:
        True if sent successfully, False otherwise
    """
    if charts is None:
        charts = {}

    msg = MIMEMultipart("related")
    msg["From"] = f"PPFAS Fund Tracker <{sender_email}>"
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject

    # Attach HTML body
    html_part = MIMEText(html_body, "html")
    msg_alt = MIMEMultipart("alternative")
    msg_alt.attach(html_part)
    msg.attach(msg_alt)

    # Attach chart images with Content-ID for inline display
    for cid, b64_data in charts.items():
        if b64_data:
            img_data = base64.b64decode(b64_data)
            img = MIMEImage(img_data, _subtype="png")
            img.add_header("Content-ID", f"<{cid}>")
            img.add_header("Content-Disposition", "inline", filename=f"{cid}.png")
            msg.attach(img)

    # Send via Gmail SMTP
    try:
        logger.info(f"Connecting to Gmail SMTP...")
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, recipients, msg.as_string())

        logger.info(f"Email sent successfully to {len(recipients)} recipients: {recipients}")
        return True

    except smtplib.SMTPAuthenticationError:
        logger.error(
            "Gmail authentication failed. Make sure you're using an App Password, "
            "not your regular password. Generate one at: https://myaccount.google.com/apppasswords"
        )
        return False
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return False


def send_monthly_report(
    sender_email: str = None,
    sender_password: str = None,
    recipients: list[str] = None,
    html_body: str = "",
    charts: dict = None,
    dashboard_url: str = "",
):
    """
    Convenience function for the monthly automation.
    Reads credentials from environment variables if not provided.
    """
    sender_email = sender_email or os.environ.get("GMAIL_ADDRESS")
    sender_password = sender_password or os.environ.get("GMAIL_APP_PASSWORD")
    recipients_str = os.environ.get("EMAIL_RECIPIENTS", "")
    recipients = recipients or [r.strip() for r in recipients_str.split(",") if r.strip()]

    if not sender_email or not sender_password:
        raise ValueError(
            "Gmail credentials not provided. Set GMAIL_ADDRESS and GMAIL_APP_PASSWORD "
            "environment variables, or pass them as arguments."
        )

    if not recipients:
        raise ValueError(
            "No recipients specified. Set EMAIL_RECIPIENTS environment variable "
            "(comma-separated) or pass them as arguments."
        )

    month_year = datetime.now().strftime("%B %Y")
    subject = f"[PPFAS Tracker] Monthly Report — {month_year}"

    success = send_email(
        sender_email=sender_email,
        sender_password=sender_password,
        recipients=recipients,
        subject=subject,
        html_body=html_body,
        charts=charts or {},
    )

    if success:
        logger.info(f"Monthly report for {month_year} sent successfully!")
    else:
        logger.error(f"Failed to send monthly report for {month_year}")

    return success
