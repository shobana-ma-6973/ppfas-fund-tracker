"""
Batch parse ALL historical PPFAS factsheets.
Downloads each PDF, extracts sector and category allocation,
saves to data/factsheet_{year}_{month}.json.
Skips already-parsed months.
"""
import sys, os, json, time, logging, re, traceback
from pathlib import Path
from datetime import datetime
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

import requests
import pdfplumber

PPFAS_AMC_BASE = "https://amc.ppfas.com"

# --- Known AMFI industry names (used for holdings-based sector extraction) ---
KNOWN_INDUSTRIES = sorted([
    "Banks", "Power", "Consumable Fuels", "Diversified FMCG", "Finance",
    "Automobiles", "IT - Software", "Pharmaceuticals & Biotechnology",
    "Computer Software", "Catalog/Specialty Distribution", "Capital Markets",
    "Food Products", "Auto Components", "Healthcare Services",
    "Transport Services", "Telecom - Services", "Commercial Services & Supplies",
    "Industrial Products", "Realty", "Fertilizers & Agrochemicals",
    "Leisure Services", "Cement & Cement Products", "Construction",
    "Chemicals", "Media & Entertainment", "Textiles", "Retailing",
    "Minerals/Mining", "Paper & Paper Products", "Oil",
    "Consumer Durables", "Ferrous Metals", "Non-Ferrous Metals",
    "Petroleum Products", "Gas", "Insurance",
    "Aerospace & Defense", "Agricultural Food & other Products",
    "Tobacco Products", "Beverages", "IT - Hardware",
    "Telecom - Equipment & Accessories", "Diamond, Gems and Jewellery",
    "Electrical Equipment", "Electronics", "Engineering",
    "Forest Materials", "Hotels, Resorts And Other Recreational Activities",
    "Household Products", "Jute & Jute Products", "Leather",
    "Packaging", "Plantation & Plantation Products", "Printing & Publication",
    "Shipping", "Sugar", "Trading",
    "Debt and Money Market Instruments", "Cash & Cash Equivalent",
    # Allow partial matches for older factsheets
    "Software", "Pharma", "FMCG", "Financials",
], key=len, reverse=True)


def download_pdf(url):
    """Download PDF to a temp file."""
    import tempfile
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    fd, path = tempfile.mkstemp(suffix=".pdf")
    with os.fdopen(fd, 'wb') as f:
        f.write(resp.content)
    return path


def find_flexi_cap_pages(pdf):
    """Find the pages containing Flexi Cap / Long Term Equity / PPFCF data."""
    fund_names = ["flexi cap", "long term equity", "long term value", "ppfcf", "pltef", "pltvf"]
    info_page = None
    portfolio_page = None

    for i, page in enumerate(pdf.pages):
        text = (page.extract_text() or "").lower()
        is_fund_page = any(fn in text for fn in fund_names)
        if not is_fund_page:
            continue

        if "industry allocation" in text and info_page is None:
            info_page = i
        if "portfolio disclosure" in text and portfolio_page is None:
            portfolio_page = i

        # Stop if we hit another fund
        if info_page is not None:
            other_funds = ["elss", "tax saver", "liquid fund", "conservative hybrid"]
            if any(of in text for of in other_funds) and "flexi cap" not in text and "long term" not in text:
                break

    return info_page, portfolio_page


def extract_aum_from_tables(tables):
    """Extract AUM from tables."""
    for table in tables:
        for row in table:
            if not row:
                continue
            for ci, cell in enumerate(row):
                if not cell:
                    continue
                cell_str = str(cell).lower()
                if "assets under management" in cell_str or "aum" in cell_str:
                    # Check this cell and next cell for the value
                    for val_cell in [cell] + (list(row[ci+1:ci+2]) if ci+1 < len(row) else []):
                        if val_cell:
                            m = re.search(r'([\d,]+\.?\d*)\s*(Crore|crore|Cr)', str(val_cell))
                            if m:
                                return f"₹{m.group(1)} Cr"
    return "N/A"


def extract_sectors_from_text(page_text):
    """Extract sector allocation from text labels (Industry Allocation sidebar)."""
    sectors = {}
    lines = page_text.split("\n")
    for line in lines:
        line = line.strip()
        m = re.match(r"^([A-Za-z][A-Za-z &/\-,]+?)\s+(\d+\.?\d+)%$", line)
        if m:
            name = m.group(1).strip()
            pct = float(m.group(2))
            if pct <= 0 or pct > 100 or len(name) < 3:
                continue
            skip = ["ppfcf", "nifty", "cagr", "regular plan", "direct plan",
                    "beta", "standard deviation", "sharpe ratio", "portfolio turnover",
                    "since inception", "month end expense", "benchmark"]
            if any(s in name.lower() for s in skip):
                continue
            sectors[name] = pct
    return dict(sorted(sectors.items(), key=lambda x: x[1], reverse=True))


def extract_sectors_from_portfolio(portfolio_tables):
    """Compute sector allocation from individual holdings in portfolio table."""
    sectors = defaultdict(float)
    in_debt = False
    debt_total = 0
    cash_total = 0

    # Find equity table (has "Overseas Securities" or "Industry")
    equity_table = None
    debt_table = None
    for table in portfolio_tables:
        ttext = " ".join(str(r[0] or "").lower() for r in table if r and r[0])
        if "overseas securities" in ttext or "industry" in ttext:
            equity_table = table
        if "treps" in ttext and equity_table is not table:
            debt_table = table

    if not equity_table:
        return {}

    for row in equity_table:
        if not row or not row[0]:
            continue
        cell = str(row[0]).strip()
        cl = cell.lower()

        if "debt and money market" in cl:
            break
        if cl.startswith("sub total") or cl.startswith("industry") or cl.startswith("core equity"):
            continue
        if "overseas securities" in cl or "units issued by reits" in cl:
            continue
        if cl.startswith("portfolio disclosure") or cl.startswith("name"):
            continue

        # Arbitrage
        arb_m = re.match(r'^@?Arbitrage.*?(\d+\.?\d+)%$', cell)
        if arb_m:
            sectors["Arbitrage/Special Situation"] = float(arb_m.group(1))
            continue

        total_m = re.match(r'^(?:Sub )?Total\s+(\d+\.?\d+)%$', cell)
        if total_m:
            continue

        pct_m = re.search(r'(\d+\.?\d+)%\s*$', cell)
        if not pct_m:
            continue
        pct = float(pct_m.group(1))
        if pct <= 0:
            continue
        prefix = cell[:pct_m.start()].strip()

        for ind in KNOWN_INDUSTRIES:
            if prefix.endswith(ind):
                sectors[ind] = round(sectors.get(ind, 0) + pct, 2)
                break

    # Process debt table for debt/cash totals
    if debt_table:
        for row in debt_table:
            if not row or not row[0]:
                continue
            cell = str(row[0]).strip()
            cl = cell.lower()
            if "treps" in cl and "cash" in cl:
                m = re.search(r'(\d+\.?\d+)%', cell)
                if m:
                    cash_total = float(m.group(1))
            total_m = re.match(r'^Total\s+(\d+\.?\d+)%$', cell)
            if total_m:
                debt_total = float(total_m.group(1))

    if debt_total > 0:
        net_debt = round(debt_total - cash_total, 2) if cash_total else debt_total
        sectors["Debt and Money Market Instruments"] = net_debt
    if cash_total > 0:
        sectors["Cash & Cash Equivalent"] = cash_total

    return dict(sorted(sectors.items(), key=lambda x: x[1], reverse=True))


def extract_categories(portfolio_tables):
    """Extract category allocation from portfolio tables."""
    categories = {}
    cash_pct = None

    section_map = {
        "overseas securities": "Overseas Equity",
        "units issued by reits": "REITs & InvITs",
        "debt and money market": "Debt & Money Market",
    }

    equity_table = None
    debt_table = None
    for table in portfolio_tables:
        ttext = " ".join(str(r[0] or "").lower() for r in table if r and r[0])
        if "overseas securities" in ttext:
            equity_table = table
        if "treps" in ttext and equity_table is not table:
            debt_table = table

    if equity_table:
        current_section = "Indian Equity"
        for row in equity_table:
            if not row or not row[0]:
                continue
            cell = str(row[0]).strip()
            cl = cell.lower()
            for key, label in section_map.items():
                if key in cl:
                    current_section = label
                    break
            total_m = re.match(r'^Total\s+(\d+\.?\d+)%$', cell)
            if total_m:
                pct = float(total_m.group(1))
                if current_section not in categories:
                    categories[current_section] = pct

    if debt_table:
        for row in debt_table:
            if not row or not row[0]:
                continue
            cell = str(row[0]).strip()
            cl = cell.lower()
            if "treps" in cl and "cash" in cl:
                m = re.search(r'(\d+\.?\d+)%', cell)
                if m:
                    cash_pct = float(m.group(1))
            total_m = re.match(r'^Total\s+(\d+\.?\d+)%$', cell)
            if total_m:
                pct = float(total_m.group(1))
                if "Debt & Money Market" not in categories:
                    categories["Debt & Money Market"] = pct

    if cash_pct and "Debt & Money Market" in categories:
        dt = categories["Debt & Money Market"]
        categories["Debt & Money Market"] = round(dt - cash_pct, 2)
        categories["Cash & Equivalents"] = cash_pct

    if "Indian Equity" not in categories:
        other = sum(categories.values())
        if 0 < other < 100:
            categories["Indian Equity"] = round(100 - other, 2)

    return categories


def parse_one_factsheet(url, year, month):
    """Download and parse a single factsheet."""
    pdf_path = download_pdf(url)

    try:
        with pdfplumber.open(pdf_path) as pdf:
            info_idx, portfolio_idx = find_flexi_cap_pages(pdf)

            if info_idx is None:
                # Fallback for old single-page factsheets
                info_idx = 0
                portfolio_idx = 1 if len(pdf.pages) > 1 else 0

            if portfolio_idx is None:
                portfolio_idx = info_idx + 1 if info_idx + 1 < len(pdf.pages) else info_idx

            info_text = pdf.pages[info_idx].extract_text() or ""
            info_tables = pdf.pages[info_idx].extract_tables() or []
            portfolio_tables = pdf.pages[portfolio_idx].extract_tables() or []

            # Try portfolio-based sector extraction first, fallback to text-based
            sectors = extract_sectors_from_portfolio(portfolio_tables)
            if len(sectors) < 5:
                sectors = extract_sectors_from_text(info_text)

            categories = extract_categories(portfolio_tables)

            aum = extract_aum_from_tables(info_tables)

            return {
                "fund_name": "Parag Parikh Flexi Cap Fund - Direct Growth",
                "aum": aum,
                "sector_allocation": sectors,
                "category_allocation": categories,
                "extraction_date": datetime.now().strftime("%Y-%m-%d"),
                "pages_parsed": f"info={info_idx+1}, portfolio={portfolio_idx+1}",
                "source_url": url,
                "factsheet_month": datetime(year, month, 1).strftime("%B %Y"),
            }
    finally:
        os.unlink(pdf_path)


def main():
    urls_file = Path("data/factsheet_urls.json")
    if not urls_file.exists():
        print("Run scrape_all_urls.py first!")
        return

    with open(urls_file) as f:
        all_urls = json.load(f)

    print(f"Processing {len(all_urls)} factsheets...")
    success = 0
    fail = 0
    skip = 0
    errors = []

    for key, url in sorted(all_urls.items()):
        year, month = int(key[:4]), int(key[5:])
        cache_path = f"data/factsheet_{key}.json"

        # Skip if already parsed with valid data
        if Path(cache_path).exists():
            try:
                with open(cache_path) as f:
                    cached = json.load(f)
                if cached.get("sector_allocation") and len(cached["sector_allocation"]) >= 3:
                    skip += 1
                    continue
            except:
                pass

        label = datetime(year, month, 1).strftime("%b %Y")
        try:
            data = parse_one_factsheet(url, year, month)
            n_sectors = len(data.get("sector_allocation", {}))
            n_cats = len(data.get("category_allocation", {}))

            Path(cache_path).parent.mkdir(parents=True, exist_ok=True)
            with open(cache_path, "w") as f:
                json.dump(data, f, indent=2)

            status = f"✅ S={n_sectors} C={n_cats} AUM={data.get('aum','?')}"
            success += 1
        except Exception as e:
            status = f"❌ {str(e)[:80]}"
            errors.append((label, str(e)))
            fail += 1

        print(f"{label}: {status}")
        time.sleep(0.5)  # Be nice to the server

    print(f"\nDone: {success} parsed, {skip} skipped, {fail} failed")
    if errors:
        print("\nErrors:")
        for label, err in errors:
            print(f"  {label}: {err[:100]}")


if __name__ == "__main__":
    main()
