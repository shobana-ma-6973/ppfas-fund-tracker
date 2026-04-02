"""
PPFAS Flexi Cap Fund - Factsheet Parser
Downloads and extracts data from PPFAS monthly factsheet PDFs.
Targets ONLY pages 1-4 (Flexi Cap Fund section).
"""

import requests
import pdfplumber
import re
import json
import tempfile
from datetime import datetime
from pathlib import Path
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)

# The actual PPFAS AMC website (not www.ppfas.com which is the PMS/advisory arm)
PPFAS_FACTSHEET_PAGE = "https://amc.ppfas.com/downloads/factsheet/"
PPFAS_AMC_BASE = "https://amc.ppfas.com"

# Pages in factsheet that contain Flexi Cap Fund data (0-indexed)
FLEXI_CAP_PAGES = [0, 1, 2, 3]  # Pages 1-4


def find_latest_factsheet_url() -> str:
    """
    Scrape the PPFAS AMC website to find the latest monthly factsheet PDF URL.
    Factsheets are listed at https://amc.ppfas.com/downloads/factsheet/
    PDF pattern: /downloads/factsheet/{year}/ppfas-mf-factsheet-for-{Month}-{Year}.pdf
    """
    logger.info("Searching for latest factsheet URL...")

    try:
        response = requests.get(PPFAS_FACTSHEET_PAGE, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        pdf_links = []
        for link in soup.find_all("a", href=True):
            href = link["href"]
            if ".pdf" in href.lower() and "factsheet" in href.lower():
                if not href.startswith("http"):
                    href = PPFAS_AMC_BASE + href
                pdf_links.append(href)

        if pdf_links:
            url = pdf_links[0].split("?")[0]
            logger.info(f"Found factsheet: {url}")
            return url

    except Exception as e:
        logger.warning(f"Error fetching {PPFAS_FACTSHEET_PAGE}: {e}")

    # Fallback: construct URL based on previous month
    now = datetime.now()
    if now.month == 1:
        prev_month_name = "December"
        prev_year = now.year - 1
    else:
        prev_month_name = datetime(now.year, now.month - 1, 1).strftime("%B")
        prev_year = now.year

    fallback_url = (
        f"{PPFAS_AMC_BASE}/downloads/factsheet/{prev_year}/"
        f"ppfas-mf-factsheet-for-{prev_month_name}-{prev_year}.pdf"
    )
    logger.info(f"Trying fallback factsheet URL: {fallback_url}")

    try:
        resp = requests.head(fallback_url, timeout=15, allow_redirects=True)
        if resp.status_code == 200:
            return fallback_url
    except Exception:
        pass

    raise ValueError("Could not find factsheet PDF URL on PPFAS website")


def get_target_month_url(year: int, month: int) -> str:
    """
    Build the expected factsheet URL for a specific month/year.
    PPFAS pattern: ppfas-mf-factsheet-for-{Month}-{Year}.pdf
    """
    month_name = datetime(year, month, 1).strftime("%B")
    return (
        f"{PPFAS_AMC_BASE}/downloads/factsheet/{year}/"
        f"ppfas-mf-factsheet-for-{month_name}-{year}.pdf"
    )


def check_factsheet_available(target_year: int = None, target_month: int = None) -> tuple:
    """
    Lightweight check: is the factsheet for the target month available?
    Defaults to previous month from today.

    Returns:
        (available: bool, url: str or None)
    """
    now = datetime.now()
    if target_year is None or target_month is None:
        if now.month == 1:
            target_month = 12
            target_year = now.year - 1
        else:
            target_month = now.month - 1
            target_year = now.year

    target_url = get_target_month_url(target_year, target_month)
    month_name = datetime(target_year, target_month, 1).strftime("%B %Y")
    logger.info(f"Checking factsheet availability for {month_name}...")
    logger.info(f"URL: {target_url}")

    # Method 1: Try HEAD request on the constructed URL
    try:
        resp = requests.head(target_url, timeout=15, allow_redirects=True)
        if resp.status_code == 200:
            logger.info(f"✅ Factsheet for {month_name} is AVAILABLE")
            return True, target_url
    except Exception as e:
        logger.debug(f"HEAD request failed: {e}")

    # Method 2: Scrape the factsheet page to see if it's listed
    try:
        response = requests.get(PPFAS_FACTSHEET_PAGE, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        month_str = datetime(target_year, target_month, 1).strftime("%B").lower()
        for link in soup.find_all("a", href=True):
            href = link["href"].lower()
            if ".pdf" in href and "factsheet" in href:
                if month_str in href and str(target_year) in href:
                    full_url = link["href"]
                    if not full_url.startswith("http"):
                        full_url = PPFAS_AMC_BASE + full_url
                    full_url = full_url.split("?")[0]
                    logger.info(f"✅ Factsheet for {month_name} found via scrape: {full_url}")
                    return True, full_url
    except Exception as e:
        logger.debug(f"Scrape check failed: {e}")

    logger.info(f"❌ Factsheet for {month_name} is NOT yet available")
    return False, None


def download_pdf(url: str) -> str:
    """Download PDF to a temp file and return the path."""
    logger.info(f"Downloading factsheet PDF: {url}")
    response = requests.get(url, timeout=60)
    response.raise_for_status()

    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp.write(response.content)
    tmp.close()
    logger.info(f"Downloaded to {tmp.name}")
    return tmp.name


def extract_aum(page2_tables: list) -> str:
    """
    Extract AUM from page 2 table.
    Row format: ['Assets Under Management\\n(AUM) as on ...', '` 1,34,253.17 Crores']
    PPFAS uses backtick ` as rupee symbol in PDFs.
    """
    for table in page2_tables:
        for row in table:
            if not row or not row[0]:
                continue
            cell = str(row[0]).lower()
            if "assets under management" in cell or "aum" in cell:
                if len(row) > 1 and row[1]:
                    val = str(row[1]).strip()
                    match = re.search(r"([\d,]+\.?\d*)\s*(Crore|crore|Cr)", val)
                    if match:
                        return f"₹{match.group(1)} Cr"
    return "N/A"


def extract_sector_allocation(page2_text: str) -> dict:
    """
    Extract industry/sector allocation from the sidebar on page 2.
    The factsheet lists industries clearly at the bottom of page 2:
        Banks 20.04%
        Debt and Money Market Instruments 14.52%
        Computer Software 8.54%
        Power 6.92%
        IT - Software 6.91%
        Automobiles 6.71%
        ...
    """
    sectors = {}

    lines = page2_text.split("\n")
    for line in lines:
        line = line.strip()
        # Match: "Sector Name XX.XX%" — name starts with a letter, ends with percentage
        match = re.match(r"^([A-Za-z][A-Za-z &/\-,]+?)\s+(\d+\.?\d+)%$", line)
        if match:
            name = match.group(1).strip()
            pct = float(match.group(2))

            if pct <= 0 or pct > 100:
                continue
            if len(name) < 3:
                continue

            # Skip non-sector lines (benchmark labels, ratio labels, etc.)
            skip_labels = [
                "ppfcf regular", "ppfcf direct", "nifty", "cagr",
                "regular plan", "direct plan", "beta", "standard deviation",
                "sharpe ratio", "portfolio turnover", "since inception",
                "month end expense",
            ]
            if any(skip in name.lower() for skip in skip_labels):
                continue

            sectors[name] = pct

    if sectors:
        logger.info(f"Extracted {len(sectors)} sectors from page 2 sidebar")
    return dict(sorted(sectors.items(), key=lambda x: x[1], reverse=True))


def extract_category_allocation(page3_tables: list) -> dict:
    """
    Extract asset category allocation from page 3 portfolio disclosure.

    Page 3 has clear section totals in the tables:
      Core Equity section → 'Total 67.88%'
      Overseas Securities → 'Total 10.51%'
      REITs & InvITs      → 'Total 3.52%'
      Debt & Money Market → 'Total 18.09%'
      Net Assets           → 100.00%
    """
    categories = {}

    # Section headers that appear in the table rows, mapped to display names
    section_map = {
        "overseas securities": "Overseas Equity",
        "units issued by reits": "REITs & InvITs",
        "debt and money market": "Debt & Money Market",
    }

    current_section = "Indian Equity"  # First section in the table is Core Equity

    for table in page3_tables:
        for row in table:
            if not row or not row[0]:
                continue
            cell = str(row[0]).strip()
            cell_lower = cell.lower()

            # Detect section transitions
            for key, label in section_map.items():
                if key in cell_lower:
                    current_section = label
                    break

            # Capture "Total XX.XX%" lines — these are section totals
            total_match = re.match(r"^Total\s+(\d+\.?\d+)%$", cell)
            if total_match:
                pct = float(total_match.group(1))
                # Only store the first "Total" per section (avoid double-counting)
                if current_section not in categories:
                    categories[current_section] = pct

    # Split "Debt & Money Market" into Debt instruments vs Cash if possible.
    # The TREPS/Cash line (3.57%) is a subset of Debt & Money Market total (18.09%).
    # We separate them for a cleaner breakdown that sums to 100%.
    # Look for TREPS/Cash line to split
    for table in page3_tables:
        for row in table:
            if not row or not row[0]:
                continue
            cell_lower = str(row[0]).strip().lower()
            if "treps" in cell_lower and "cash" in cell_lower:
                treps_match = re.search(r"(\d+\.?\d+)%", str(row[0]))
                if treps_match and "Debt & Money Market" in categories:
                    cash_pct = float(treps_match.group(1))
                    debt_total = categories["Debt & Money Market"]
                    categories["Debt & Money Market"] = round(debt_total - cash_pct, 2)
                    categories["Cash & Equivalents"] = cash_pct
                break

    if categories:
        total = sum(categories.values())
        logger.info(f"Category allocation total: {total:.2f}% ({len(categories)} categories)")

    return categories


def parse_factsheet(pdf_path: str) -> dict:
    """
    Parse a PPFAS factsheet PDF and extract Flexi Cap Fund data only (pages 1-4).
    """
    logger.info(f"Parsing factsheet: {pdf_path}")

    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        logger.info(f"PDF has {total_pages} pages. Parsing pages 1-4 (Flexi Cap Fund).")

        # Page 2 (index 1): Fund details, AUM, Industry Allocation sidebar
        page2_text = pdf.pages[1].extract_text() or ""
        page2_tables = pdf.pages[1].extract_tables() or []

        # Page 3 (index 2): Portfolio disclosure with category totals
        page3_tables = pdf.pages[2].extract_tables() or []

    result = {
        "fund_name": "Parag Parikh Flexi Cap Fund - Direct Growth",
        "aum": extract_aum(page2_tables),
        "sector_allocation": extract_sector_allocation(page2_text),
        "category_allocation": extract_category_allocation(page3_tables),
        "extraction_date": datetime.now().strftime("%Y-%m-%d"),
        "pages_parsed": "1-4 (Flexi Cap Fund only)",
    }

    logger.info(
        f"Extracted: AUM={result['aum']}, "
        f"Sectors={len(result['sector_allocation'])}, "
        f"Categories={len(result['category_allocation'])}"
    )

    return result


def save_factsheet_data(data: dict, filepath: str = "data/factsheet_data.json"):
    """Save parsed factsheet data to JSON."""
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)
    logger.info(f"Saved factsheet data to {filepath}")


def load_factsheet_data(filepath: str = "data/factsheet_data.json") -> dict:
    """Load saved factsheet data."""
    with open(filepath, "r") as f:
        return json.load(f)


def fetch_and_parse_factsheet() -> dict:
    """Full pipeline: find, download, parse, save."""
    try:
        url = find_latest_factsheet_url()
        pdf_path = download_pdf(url)
        data = parse_factsheet(pdf_path)
        data["source_url"] = url
        save_factsheet_data(data)
        return data
    except Exception as e:
        logger.error(f"Factsheet extraction failed: {e}")
        return {
            "aum": "N/A",
            "sector_allocation": {},
            "category_allocation": {},
            "extraction_date": datetime.now().strftime("%Y-%m-%d"),
            "error": str(e),
        }


def fetch_factsheet_for_month(year: int, month: int) -> dict:
    """
    Fetch and parse the factsheet for a specific month/year.
    Saves to data/factsheet_{year}_{month:02d}.json for caching.
    Returns parsed data dict or None if not available.
    """
    cache_path = f"data/factsheet_{year}_{month:02d}.json"
    cache_file = Path(cache_path)

    # Return cached data if available
    if cache_file.exists():
        try:
            return load_factsheet_data(cache_path)
        except Exception:
            pass

    month_name = datetime(year, month, 1).strftime("%B %Y")
    logger.info(f"Fetching factsheet for {month_name}...")

    # Check availability
    available, url = check_factsheet_available(year, month)
    if not available or not url:
        logger.info(f"Factsheet for {month_name} not available")
        return None

    try:
        pdf_path = download_pdf(url)
        data = parse_factsheet(pdf_path)
        data["source_url"] = url
        data["factsheet_month"] = month_name
        save_factsheet_data(data, cache_path)
        return data
    except Exception as e:
        logger.error(f"Failed to parse factsheet for {month_name}: {e}")
        return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    data = fetch_and_parse_factsheet()
    print(json.dumps(data, indent=2))
