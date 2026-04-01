"""
Sent Status Tracker
Tracks which monthly reports have been sent to avoid duplicate emails.
Uses a JSON file (data/sent_status.json) that gets committed to the repo.
"""

import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

STATUS_FILE = Path(__file__).parent.parent / "data" / "sent_status.json"


def _load_status() -> dict:
    """Load the sent status file."""
    if STATUS_FILE.exists():
        try:
            with open(STATUS_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Error reading status file: {e}")
    return {"sent_months": {}}


def _save_status(status: dict):
    """Save the sent status file."""
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATUS_FILE, "w") as f:
        json.dump(status, f, indent=2)
    logger.info(f"Status saved to {STATUS_FILE}")


def get_target_month() -> tuple:
    """
    Determine which month's factsheet we should look for.
    Factsheet for previous month is released in the current month.

    Returns:
        (year: int, month: int) — the target factsheet month
    """
    now = datetime.now()
    if now.month == 1:
        return now.year - 1, 12
    return now.year, now.month - 1


def is_already_sent(year: int, month: int) -> bool:
    """Check if the report for the given month was already sent."""
    key = f"{year}-{month:02d}"
    status = _load_status()
    sent = key in status.get("sent_months", {})
    if sent:
        sent_on = status["sent_months"][key].get("sent_on", "unknown")
        logger.info(f"Report for {key} was already sent on {sent_on}")
    return sent


def mark_as_sent(year: int, month: int, factsheet_url: str = None):
    """Mark a month's report as sent."""
    key = f"{year}-{month:02d}"
    status = _load_status()
    status["sent_months"][key] = {
        "sent_on": datetime.now().isoformat(),
        "factsheet_url": factsheet_url,
    }
    _save_status(status)
    logger.info(f"✅ Marked {key} as sent")


def get_all_sent_months() -> dict:
    """Return all months that have been marked as sent."""
    return _load_status().get("sent_months", {})
