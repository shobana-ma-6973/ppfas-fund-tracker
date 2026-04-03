"""
PPFAS Flexi Cap Fund - Factsheet Parser
Downloads and extracts data from PPFAS monthly factsheet PDFs.
Targets ONLY pages 1-4 (Flexi Cap Fund section).
"""

import re
import json
import tempfile
from datetime import datetime
from pathlib import Path
import logging

# Lazy imports — these may not be available on all platforms (e.g. Streamlit Cloud)
try:
    import requests
except ImportError:
    requests = None

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

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
    The factsheet lists industries clearly in the "Industry Allocation"
    or "Sectoral Allocation" section:
        Banks 20.04%
        Debt and Money Market Instruments 14.52%
        Computer Software 8.54%
        ...

    For reliability, we try to narrow to only the sector section of the text.
    """
    sectors = {}

    # Try to narrow down to sector section only
    text = page2_text
    sector_start = None
    for marker in ["Industry Allocation", "Sectoral Allocation"]:
        idx = text.find(marker)
        if idx >= 0:
            sector_start = idx
            break

    if sector_start is not None:
        # Grab text from the marker onwards (sector data follows it)
        text = text[sector_start:]

    lines = text.split("\n")
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

            # Skip non-sector lines (benchmark labels, ratio labels, holdings, etc.)
            skip_labels = [
                "ppfcf regular", "ppfcf direct", "nifty", "cagr",
                "regular plan", "direct plan", "beta", "standard deviation",
                "sharpe ratio", "portfolio turnover", "since inception",
                "month end expense", "invested total", "net assets",
                "total", "core equity", "multi cap", "open ended",
                "treps including", "cash and cash", "cash equivalent",
                "portfolio disclosure",
            ]
            if any(skip in name.lower() for skip in skip_labels):
                continue

            # Skip lines that look like individual holdings (contain Ltd, Inc, etc.)
            holding_markers = [" ltd", " inc", " limited", " corp", " plc",
                             " bank ", " nv ", " sa ", " ag "]
            if any(hm in name.lower() for hm in holding_markers):
                continue

            sectors[name] = pct

    if sectors:
        logger.info(f"Extracted {len(sectors)} sectors from page 2 sidebar")
    return dict(sorted(sectors.items(), key=lambda x: x[1], reverse=True))


def extract_category_allocation(page3_tables: list) -> dict:
    """
    Extract asset category allocation from portfolio disclosure tables.

    The page has two column areas extracted as separate tables:
    - Equity table (left column): Core Equity → Overseas → REITs, each with "Total XX.XX%"
    - Debt table  (right column): CDs, CPs, T-Bills, TREPS → "Total XX.XX%"

    pdfplumber may return tables in any order, so we process each table
    independently — tracking section headers within each table.

    For older formats (pre-2021), data may be spread across many small tables.
    We try the targeted 2-table approach first, then fall back to processing
    ALL tables as a merged stream.
    """
    categories = {}
    cash_pct = None

    section_map = {
        "overseas securities": "Overseas Equity",
        "units issued by reits": "REITs & InvITs",
        "debt and money market": "Debt & Money Market",
    }

    # --- Pass 1: Find the equity table (contains "Overseas Securities" header)
    #     and the debt table (contains "TREPS" row) ---
    equity_table = None
    debt_table = None

    for table in page3_tables:
        table_text = " ".join(
            str(row[0]).lower() for row in table if row and row[0]
        )
        if "overseas securities" in table_text:
            equity_table = table
        if "treps" in table_text or "debt and money market" in table_text:
            debt_table = table

    # If equity and debt are the same table (common in 2022 format where
    # everything is in one big table), keep both references — Pass 2 handles
    # equity sections and Pass 3 handles the debt section from the same table
    same_table = (debt_table is equity_table) and (debt_table is not None)

    # --- Pass 2: Process equity table (Indian Equity, Overseas, REITs) ---
    # Use the LAST Total per section (some PDFs have core subtotal + combined total
    # in the same section, e.g. Total 65.43% then Total 66.83% before Overseas)
    if equity_table:
        current_section = "Indian Equity"
        for row in equity_table:
            if not row or not row[0]:
                continue
            cell = str(row[0]).strip()
            cell_lower = cell.lower()

            for key, label in section_map.items():
                if key in cell_lower:
                    current_section = label
                    break

            total_match = re.match(r"^Total\s+(\d+\.?\d+)%$", cell)
            if total_match:
                pct = float(total_match.group(1))
                # Always overwrite → last Total in each section wins
                categories[current_section] = pct

    # --- Pass 3: Process debt table ---
    # Track totals relative to TREPS position to distinguish:
    #   - Grand total AFTER TREPS (Feb 2026 style): subtract cash from it
    #   - Only instruments total BEFORE TREPS (Jan 2025 style): keep separate
    # When same_table is True, only process rows after "Debt and Money Market" header
    sub_total_after_treps = None
    if debt_table:
        treps_seen = False
        debt_instrument_total = None
        grand_total = None
        individual_debt_sum = 0.0  # Sum individual instruments when no Total row exists
        in_debt_section = not same_table  # Separate table: process all; same table: wait for header

        for row in debt_table:
            if not row or not row[0]:
                continue
            cell = str(row[0]).strip()
            cell_lower = cell.lower()

            # When same table, skip all rows until "Debt and Money Market" header
            if same_table and not in_debt_section:
                if "debt and money market" in cell_lower:
                    in_debt_section = True
                continue

            # Capture TREPS/Cash value
            if "treps" in cell_lower and "cash" in cell_lower:
                m = re.search(r"(\d+\.?\d+)%", cell)
                if m:
                    cash_pct = float(m.group(1))
                    treps_seen = True
                continue

            # Match "Total XX.XX%"
            total_match = re.match(r"^Total\s+(\d+\.?\d+)%$", cell)
            if total_match:
                pct = float(total_match.group(1))
                if treps_seen:
                    grand_total = pct  # Total after TREPS = grand total
                else:
                    debt_instrument_total = pct  # Total before TREPS = instruments only
                continue

            # Match "Sub Total XX.XX%" (appears after TREPS in some formats)
            sub_match = re.match(r"^Sub\s+Total\s+(\d+\.?\d+)%$", cell)
            if sub_match and treps_seen:
                sub_total_after_treps = float(sub_match.group(1))
                continue

            # Track individual instrument percentages (for same-table with no Total row)
            if in_debt_section and not treps_seen:
                m = re.search(r"(\d+\.?\d+)%", cell)
                if m:
                    individual_debt_sum += float(m.group(1))

        # Determine Debt & Cash values
        if grand_total is not None:
            # Grand total includes both debt + cash (Feb 2026 style)
            categories["Debt & Money Market"] = grand_total
        elif debt_instrument_total is not None:
            categories["Debt & Money Market"] = debt_instrument_total
        elif individual_debt_sum > 0:
            # No Total row (common in 2022 same-table format) — sum individual instruments
            categories["Debt & Money Market"] = round(individual_debt_sum, 2)

    # --- If targeted approach found >= 2 categories, we're good ---
    if len(categories) >= 2:
        # Split Debt into Debt + Cash
        if cash_pct and "Debt & Money Market" in categories:
            debt_total = categories["Debt & Money Market"]
            if cash_pct < debt_total:
                # Grand total includes both → subtract cash
                categories["Debt & Money Market"] = round(debt_total - cash_pct, 2)
                categories["Cash & Equivalents"] = cash_pct
            else:
                # Total was instruments-only, cash is separate
                # Use Sub Total after TREPS if available (includes net current assets)
                cash_value = sub_total_after_treps if sub_total_after_treps else cash_pct
                categories["Cash & Equivalents"] = cash_value
        elif cash_pct:
            categories["Cash & Equivalents"] = cash_pct

        # Safety net: compute Indian Equity by subtraction if missing
        if "Indian Equity" not in categories:
            other_total = sum(categories.values())
            if 0 < other_total < 100:
                categories["Indian Equity"] = round(100 - other_total, 2)
                logger.info(f"Computed Indian Equity by subtraction: {categories['Indian Equity']}%")

        if categories:
            total = sum(categories.values())
            logger.info(f"Category allocation total: {total:.2f}% ({len(categories)} categories)")
        return categories

    # --- Fallback: merge ALL tables into one row stream (for old formats) ---
    logger.info("Trying merged-table category extraction...")
    categories = {}
    cash_pct = None
    current_section = "Indian Equity"
    tracking_active = False  # Only start tracking after "Core Equity" / "Portfolio Disclosure"

    # Filter out non-portfolio tables (fund info, quantitative indicators, chart tables, etc.)
    skip_table_markers = ["investment objective", "date of allotment",
                          "quantitative indicator", "riskometer",
                          "industry allocation", "sectoral allocation"]

    for table in page3_tables:
        # Check if this table is a non-portfolio table we should skip
        table_first_cells = " ".join(
            str(row[0]).lower() for row in table if row and row[0]
        )
        if any(m in table_first_cells for m in skip_table_markers):
            continue

        # Activate tracking when we see portfolio content
        if "core equity" in table_first_cells or "portfolio disclosure" in table_first_cells:
            tracking_active = True

        if not tracking_active:
            continue

        for row in table:
            if not row:
                continue
            # Check all cells in the row for content
            for cell_raw in row:
                if not cell_raw:
                    continue
                cell = str(cell_raw).strip()
                cell_lower = cell.lower()

                # Check for section transitions
                for key, label in section_map.items():
                    if key in cell_lower:
                        current_section = label
                        break

                # Check for multi-line cells: "Total 66.94%\nOverseas Securities..."
                for subline in cell.split("\n"):
                    subline = subline.strip()
                    sub_lower = subline.lower()

                    for key, label in section_map.items():
                        if key in sub_lower:
                            current_section = label
                            break

                    total_match = re.match(r"^(?:Invested\s+)?Total\s+(\d+\.?\d+)%$", subline)
                    if total_match:
                        pct = float(total_match.group(1))
                        if pct < 100 and current_section not in categories:
                            categories[current_section] = pct

                    # TREPS/Cash detection
                    if ("treps" in sub_lower or "cash and cash" in sub_lower) and "equivalent" in sub_lower:
                        m = re.search(r"(\d+\.?\d+)%", subline)
                        if m:
                            val = float(m.group(1))
                            if val < 30:
                                cash_pct = val

                    # FDR (old format for cash)
                    if sub_lower.startswith("fdr") and "%" in subline:
                        m = re.search(r"(\d+\.?\d+)%", subline)
                        if m:
                            cash_pct = float(m.group(1))

    # Split Debt into Debt + Cash
    if cash_pct and "Debt & Money Market" in categories:
        debt_total = categories["Debt & Money Market"]
        if cash_pct < debt_total:
            categories["Debt & Money Market"] = round(debt_total - cash_pct, 2)
            categories["Cash & Equivalents"] = cash_pct
    elif cash_pct and "Debt & Money Market" not in categories:
        categories["Cash & Equivalents"] = cash_pct

    # Safety net: compute Indian Equity by subtraction if missing
    if "Indian Equity" not in categories and categories:
        other_total = sum(categories.values())
        if 0 < other_total < 100:
            categories["Indian Equity"] = round(100 - other_total, 2)
            logger.info(f"Computed Indian Equity by subtraction: {categories['Indian Equity']}%")

    if categories:
        total = sum(categories.values())
        logger.info(f"Category allocation total (merged): {total:.2f}% ({len(categories)} categories)")

    return categories


def extract_category_from_text(page_text: str) -> dict:
    """
    Fallback: extract category allocation from page TEXT
    when table-based extraction fails. Works across all factsheet eras.

    Looks for patterns like:
        Total 66.94%    (after Core Equity section → Indian Equity)
        Total 27.97%    (after Overseas Securities section → Overseas Equity)
        Total 5.09%     (after Debt and Money Market section → Debt)
        Invested Total 100.00%
        Net Assets 100.00%
    """
    categories = {}
    lines = page_text.split("\n")

    current_section = "Indian Equity"
    section_map = {
        "overseas securities": "Overseas Equity",
        "units issued by reits": "REITs & InvITs",
        "debt and money market": "Debt & Money Market",
    }
    cash_pct = None

    for line in lines:
        line_stripped = line.strip()
        line_lower = line_stripped.lower()

        # Detect section changes
        for key, label in section_map.items():
            if key in line_lower:
                current_section = label
                break

        # Match "Total XX.XX%" (not "Invested Total" or "Net Assets")
        total_match = re.match(r"^Total\s+(\d+\.?\d+)%$", line_stripped)
        if total_match:
            pct = float(total_match.group(1))
            if current_section not in categories:
                categories[current_section] = pct

        # TREPS / Cash detection
        if "treps" in line_lower or ("cash" in line_lower and "equivalent" in line_lower):
            m = re.search(r"(\d+\.?\d+)%", line_stripped)
            if m:
                val = float(m.group(1))
                if val < 30:  # sanity check
                    cash_pct = val

    # Split Debt into Debt + Cash
    if cash_pct and "Debt & Money Market" in categories:
        debt_total = categories["Debt & Money Market"]
        if cash_pct < debt_total:
            categories["Debt & Money Market"] = round(debt_total - cash_pct, 2)
            categories["Cash & Equivalents"] = cash_pct

    # For very old formats: "Cash and Cash Equivalent X.XX%"  "Net Assets 100.00%"
    if not categories:
        for line in lines:
            m = re.match(r"^Cash and Cash Equivalent\s+(\d+\.?\d+)%$", line.strip())
            if m:
                cash_pct = float(m.group(1))
                categories["Cash & Equivalents"] = cash_pct

    # Safety net: compute Indian Equity by subtraction if missing
    if categories and "Indian Equity" not in categories:
        other_total = sum(categories.values())
        if 0 < other_total < 100:
            categories["Indian Equity"] = round(100 - other_total, 2)

    return categories


def _is_ppfas_fund_page(text_lower: str) -> bool:
    """Check if a page belongs to the PPFAS flagship equity fund (any era)."""
    fund_names = [
        "flexi cap",
        "long term value",
        "long term equity",
        "pltvf",
        "pltef",
        "ppfcf",
        "ppfas long term",
    ]
    return any(name in text_lower for name in fund_names)


def parse_factsheet(pdf_path: str) -> dict:
    """
    Parse a PPFAS factsheet PDF and extract fund data.
    Dynamically finds pages across ALL fund name eras:
      - 2013-2019: "PPFAS Long Term Value Fund" / "PLTVF"
      - 2019-2020: "Parag Parikh Long Term Equity Fund" / "PLTEF"
      - 2021+:     "Parag Parikh Flexi Cap Fund" / "PPFCF"
    """
    logger.info(f"Parsing factsheet: {pdf_path}")

    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        logger.info(f"PDF has {total_pages} pages. Scanning for fund pages...")

        # ── Find the fund pages dynamically ──
        # The "info" page has Industry/Sectoral Allocation + AUM
        # The "portfolio" page has Portfolio Disclosure / category tables
        fund_info_page = None
        fund_portfolio_page = None

        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            text_lower = text.lower()

            # Skip if not a PPFAS fund page
            if not _is_ppfas_fund_page(text_lower):
                continue

            # The "info" page has Industry Allocation or Sectoral Allocation
            has_sectors = ("industry allocation" in text_lower or
                          "sectoral allocation" in text_lower)
            if has_sectors and fund_info_page is None:
                fund_info_page = i
                logger.info(f"Found fund info page (sector allocation): page {i+1}")

            # The "portfolio" page has detailed holdings + category totals
            if "portfolio disclosure" in text_lower and fund_portfolio_page is None:
                fund_portfolio_page = i
                logger.info(f"Found fund portfolio page: page {i+1}")

            # Stop once we hit a different fund (e.g., ELSS, Liquid, Tax Saver)
            if fund_info_page is not None:
                other_funds = ["elss", "tax saver", "liquid fund"]
                if any(of in text_lower for of in other_funds):
                    # Only break if this page is NOT our info/portfolio page
                    if i != fund_info_page and i != fund_portfolio_page:
                        break

        # Fallback to page 2 if scan fails
        if fund_info_page is None:
            fund_info_page = min(1, total_pages - 1)
            logger.warning("Could not find fund info page; falling back to page 2")
        if fund_portfolio_page is None:
            # In many eras, info and portfolio are on the SAME page
            fund_portfolio_page = fund_info_page
            logger.info(f"Portfolio page same as info page: page {fund_portfolio_page + 1}")

        # Extract from identified pages
        info_page = pdf.pages[fund_info_page]
        info_text = info_page.extract_text() or ""
        info_tables = info_page.extract_tables() or []

        # Collect portfolio tables from all fund pages (info page + portfolio page)
        all_portfolio_tables = []
        pages_to_scan = sorted(set([fund_info_page, fund_portfolio_page]))
        for pi in pages_to_scan:
            tables = pdf.pages[pi].extract_tables() or []
            all_portfolio_tables.extend(tables)

        portfolio_text = ""
        for pi in pages_to_scan:
            portfolio_text += (pdf.pages[pi].extract_text() or "") + "\n"

        pages_desc = f"pages {fund_info_page+1}-{fund_portfolio_page+1}"

    # Extract sectors
    sector_allocation = extract_sector_allocation(info_text)

    # Extract categories: try table-based first, then text-based fallback
    category_allocation = extract_category_allocation(all_portfolio_tables)

    # If table-based is incomplete (< 2 real categories or total < 95%), try text fallback
    cat_total = sum(category_allocation.values()) if category_allocation else 0
    if not category_allocation or cat_total < 95:
        logger.info(f"Table-based categories incomplete (total={cat_total:.1f}%), trying text-based...")
        text_categories = extract_category_from_text(portfolio_text)
        text_total = sum(text_categories.values()) if text_categories else 0
        # Use whichever result is more complete
        if text_total > cat_total:
            category_allocation = text_categories
            logger.info(f"Using text-based categories (total={text_total:.1f}%)")

    result = {
        "fund_name": "Parag Parikh Flexi Cap Fund - Direct Growth",
        "aum": extract_aum(info_tables),
        "sector_allocation": sector_allocation,
        "category_allocation": category_allocation,
        "extraction_date": datetime.now().strftime("%Y-%m-%d"),
        "pages_parsed": pages_desc,
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

    # Return cached data if available AND valid (has sector data)
    if cache_file.exists():
        try:
            cached = load_factsheet_data(cache_path)
            if cached and cached.get("sector_allocation"):
                return cached
            else:
                logger.info(f"Cached data for {year}-{month:02d} has empty sectors, re-fetching...")
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
