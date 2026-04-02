"""
Batch scrape all factsheet URLs from PPFAS AMC website
and download+parse missing months.

Uses requests.Session with HTTPAdapter + exponential backoff
to handle PPFAS rate-limiting gracefully.
"""
import sys, os, json, re, time, logging, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s',
                    datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)

PPFAS_URL = "https://amc.ppfas.com/downloads/factsheet/"
DATA_DIR = Path("data")
DOWNLOAD_DELAY = 3  # seconds between downloads

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)


def make_session():
    """Create a requests session with retry + backoff."""
    session = requests.Session()
    retries = Retry(
        total=5,
        backoff_factor=3,           # 3s, 6s, 12s, 24s, 48s
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "HEAD"],
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/pdf,*/*",
        "Accept-Language": "en-US,en;q=0.9",
    })
    return session


def scrape_all_urls(session):
    """Scrape PPFAS factsheet page for ALL PDF links."""
    resp = session.get(PPFAS_URL, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    urls = []
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if ".pdf" in href.lower() and "factsheet" in href.lower():
            if not href.startswith("http"):
                href = "https://amc.ppfas.com" + href
            href = href.split("?")[0]
            urls.append(href)

    # Deduplicate preserving order
    seen = set()
    unique = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            unique.append(u)

    return unique


def url_to_year_month(url):
    """Extract year and month from a factsheet URL."""
    url_lower = url.lower()
    months = {
        'january': 1, 'february': 2, 'march': 3, 'april': 4,
        'may': 5, 'june': 6, 'july': 7, 'august': 8,
        'september': 9, 'october': 10, 'november': 11, 'december': 12
    }

    for mname, mnum in months.items():
        if mname in url_lower:
            year_match = re.search(r'20\d{2}', url)
            if year_match:
                year = int(year_match.group())
                return year, mnum
    return None, None


def download_pdf_with_session(session, url):
    """Download a PDF using our retry-enabled session."""
    resp = session.get(url, timeout=60)
    resp.raise_for_status()

    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp.write(resp.content)
    tmp.close()
    return tmp.name


def main():
    os.chdir(Path(__file__).parent.parent)

    session = make_session()

    logger.info("Scraping PPFAS factsheet page...")
    urls = scrape_all_urls(session)
    logger.info(f"Found {len(urls)} factsheet URLs")

    # Map URL to (year, month)
    url_map = {}
    for url in urls:
        y, m = url_to_year_month(url)
        if y and m:
            key = f"{y}_{m:02d}"
            if key not in url_map:
                url_map[key] = url

    logger.info(f"Mapped {len(url_map)} unique months")

    # Find which months need parsing
    need_parse = []
    for key, url in sorted(url_map.items()):
        cache_file = DATA_DIR / f"factsheet_{key}.json"
        if cache_file.exists():
            with open(cache_file) as f:
                d = json.load(f)
            if d.get("sector_allocation") and d.get("category_allocation"):
                continue  # Already good
        need_parse.append((key, url))

    logger.info(f"Need to parse: {len(need_parse)} months")

    if not need_parse:
        logger.info("All months already parsed!")
        return

    # Import parser functions
    from factsheet_parser import parse_factsheet, save_factsheet_data

    success = 0
    failed = []
    for i, (key, url) in enumerate(need_parse):
        logger.info(f"[{i+1}/{len(need_parse)}] Parsing {key} from {url}")
        try:
            # Use our session-based download with retries
            pdf_path = download_pdf_with_session(session, url)
            data = parse_factsheet(pdf_path)
            data["source_url"] = url
            y, m = key.split("_")
            data["factsheet_month"] = datetime(int(y), int(m), 1).strftime("%B %Y")
            save_factsheet_data(data, str(DATA_DIR / f"factsheet_{key}.json"))

            sects = len(data.get("sector_allocation", {}))
            cats = len(data.get("category_allocation", {}))
            logger.info(f"  -> {sects} sectors, {cats} categories, AUM={data.get('aum', 'N/A')}")
            if sects > 0:
                success += 1
            else:
                failed.append(key)

            # Clean up temp PDF
            try:
                os.unlink(pdf_path)
            except OSError:
                pass

        except Exception as e:
            logger.error(f"  -> FAILED: {e}")
            failed.append(key)
            # Save error entry so we don't retry endlessly
            save_factsheet_data({
                "fund_name": "Parag Parikh Flexi Cap Fund - Direct Growth",
                "aum": "N/A",
                "sector_allocation": {},
                "category_allocation": {},
                "extraction_date": datetime.now().strftime("%Y-%m-%d"),
                "error": str(e),
                "source_url": url,
            }, str(DATA_DIR / f"factsheet_{key}.json"))

        # Respectful delay between requests
        if i < len(need_parse) - 1:
            logger.info(f"  Waiting {DOWNLOAD_DELAY}s...")
            time.sleep(DOWNLOAD_DELAY)

    logger.info(f"\nDone! Success: {success}, Failed: {len(failed)}")
    if failed:
        logger.info(f"Failed months: {', '.join(failed)}")


if __name__ == "__main__":
    main()
