"""
PPFAS Flexi Cap Fund - Factsheet Parser
Downloads and extracts data from PPFAS monthly factsheet PDFs.
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

PPFAS_FACTSHEET_PAGE = "https://www.ppfas.com/mutual-fund/schemes/ppfas-flexi-cap-fund/"
PPFAS_DOWNLOADS_PAGE = "https://www.ppfas.com/downloads/factsheets/"


def find_latest_factsheet_url() -> str:
    """
    Scrape the PPFAS website to find the latest monthly factsheet PDF URL.
    """
    logger.info("Searching for latest factsheet URL...")

    # Try the downloads/factsheets page first
    for base_url in [PPFAS_DOWNLOADS_PAGE, PPFAS_FACTSHEET_PAGE]:
        try:
            response = requests.get(base_url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            # Look for PDF links containing 'factsheet'
            pdf_links = []
            for link in soup.find_all("a", href=True):
                href = link["href"]
                if ".pdf" in href.lower() and "factsheet" in href.lower():
                    if not href.startswith("http"):
                        href = "https://www.ppfas.com" + href
                    pdf_links.append(href)

            if pdf_links:
                # Return the first (most recent) factsheet
                logger.info(f"Found factsheet: {pdf_links[0]}")
                return pdf_links[0]
        except Exception as e:
            logger.warning(f"Error fetching {base_url}: {e}")
            continue

    raise ValueError("Could not find factsheet PDF URL on PPFAS website")


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


def extract_aum(text: str) -> str:
    """Extract AUM from factsheet text."""
    patterns = [
        r"AUM[:\s]*(?:Rs\.?|₹|INR)?\s*([\d,]+\.?\d*)\s*(Cr|Crore|crore)",
        r"Assets Under Management[:\s]*(?:Rs\.?|₹|INR)?\s*([\d,]+\.?\d*)\s*(Cr|Crore|crore)",
        r"Fund Size[:\s]*(?:Rs\.?|₹|INR)?\s*([\d,]+\.?\d*)\s*(Cr|Crore|crore)",
        r"Net Assets[:\s]*(?:Rs\.?|₹|INR)?\s*([\d,]+\.?\d*)\s*(Cr|Crore|crore)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return f"₹{match.group(1)} Cr"
    return "N/A"


def extract_sector_allocation(text: str) -> dict:
    """
    Extract sector-wise allocation from factsheet.
    Returns dict like: {"Financial Services": 25.5, "Technology": 18.2, ...}
    """
    sectors = {}

    # Common sector patterns in PPFAS factsheets
    sector_keywords = [
        "Financial", "Technology", "Information Technology", "Healthcare",
        "Consumer", "Automobile", "Auto", "Energy", "Power", "Materials",
        "Pharma", "FMCG", "Metals", "Cement", "Telecom", "Real Estate",
        "Capital Goods", "Oil & Gas", "Banking", "Insurance", "Retail",
        "Chemicals", "Textiles", "Media", "Services", "Others"
    ]

    # Pattern: Sector Name followed by percentage
    for line in text.split("\n"):
        line = line.strip()
        for keyword in sector_keywords:
            if keyword.lower() in line.lower():
                # Look for a percentage value
                pct_match = re.search(r"(\d+\.?\d*)\s*%", line)
                if pct_match:
                    pct = float(pct_match.group(1))
                    if 0 < pct < 100:
                        sectors[line.split(str(pct))[0].strip().rstrip("%").strip()] = pct
                        break

    # Also try table-like extraction
    if not sectors:
        rows = re.findall(
            r"([A-Za-z\s&/]+?)\s+(\d+\.?\d*)\s*%",
            text
        )
        for name, pct in rows:
            name = name.strip()
            pct = float(pct)
            if len(name) > 2 and 0 < pct < 100:
                sectors[name] = pct

    return dict(sorted(sectors.items(), key=lambda x: x[1], reverse=True))


def extract_category_allocation(text: str) -> dict:
    """
    Extract asset category allocation (Equity/Debt/Cash/Foreign Equity).
    Returns dict like: {"Equity": 65.5, "Foreign Equity": 20.2, ...}
    """
    categories = {}

    cat_patterns = [
        (r"(?:Domestic|Indian)\s*Equity[:\s]*(\d+\.?\d*)\s*%", "Domestic Equity"),
        (r"Foreign\s*(?:Equity|Securities)[:\s]*(\d+\.?\d*)\s*%", "Foreign Equity"),
        (r"(?:Total\s*)?Equity[:\s]*(\d+\.?\d*)\s*%", "Equity"),
        (r"Debt[:\s]*(\d+\.?\d*)\s*%", "Debt"),
        (r"Cash\s*(?:&|and)?\s*(?:Cash\s*)?Equivalents?[:\s]*(\d+\.?\d*)\s*%", "Cash & Equivalents"),
        (r"Cash[:\s]*(\d+\.?\d*)\s*%", "Cash"),
        (r"Gold[:\s]*(\d+\.?\d*)\s*%", "Gold"),
        (r"REITs?[:\s]*(\d+\.?\d*)\s*%", "REITs"),
        (r"Others?[:\s]*(\d+\.?\d*)\s*%", "Others"),
    ]

    for pattern, label in cat_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            pct = float(match.group(1))
            if 0 < pct <= 100:
                categories[label] = pct

    return categories


def parse_factsheet(pdf_path: str) -> dict:
    """
    Parse a PPFAS factsheet PDF and extract key data.
    """
    logger.info(f"Parsing factsheet: {pdf_path}")

    full_text = ""
    tables = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            full_text += page_text + "\n"

            page_tables = page.extract_tables()
            if page_tables:
                tables.extend(page_tables)

    result = {
        "aum": extract_aum(full_text),
        "sector_allocation": extract_sector_allocation(full_text),
        "category_allocation": extract_category_allocation(full_text),
        "extraction_date": datetime.now().strftime("%Y-%m-%d"),
        "raw_text_length": len(full_text),
        "tables_found": len(tables),
    }

    logger.info(f"Extracted: AUM={result['aum']}, "
                f"Sectors={len(result['sector_allocation'])}, "
                f"Categories={len(result['category_allocation'])}")

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
        # Return placeholder data so the pipeline doesn't break
        return {
            "aum": "N/A",
            "sector_allocation": {},
            "category_allocation": {},
            "extraction_date": datetime.now().strftime("%Y-%m-%d"),
            "error": str(e),
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    data = fetch_and_parse_factsheet()
    print(json.dumps(data, indent=2))
