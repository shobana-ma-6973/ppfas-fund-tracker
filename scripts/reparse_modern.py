#!/usr/bin/env python3
"""Re-parse 2022-2025 months using fixed parser. Uses source URLs from existing cached JSONs."""
import sys, os, json, time, tempfile, logging
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from factsheet_parser import parse_factsheet

logging.basicConfig(level=logging.INFO, format="%(message)s")

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

# Months to re-parse (2022_03 through 2025_03)
MONTHS_TO_REPARSE = []
for y in range(2022, 2026):
    for m in range(1, 13):
        if (y == 2022 and m < 3): continue
        if (y == 2025 and m > 3): continue
        MONTHS_TO_REPARSE.append((y, m))

# Setup session with retry
session = requests.Session()
retry = Retry(total=5, backoff_factor=2, status_forcelist=[429, 500, 502, 503, 504])
session.mount("https://", HTTPAdapter(max_retries=retry))
session.headers.update({"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"})

success = 0
failed = 0
skipped = 0

for year, month in MONTHS_TO_REPARSE:
    cache_path = os.path.join(DATA_DIR, f"factsheet_{year}_{month:02d}.json")

    # Read existing JSON for source URL
    if not os.path.exists(cache_path):
        print(f"  {year}_{month:02d}: No cached file, skipping")
        skipped += 1
        continue

    with open(cache_path) as f:
        cached = json.load(f)

    url = cached.get("source_url")
    if not url:
        print(f"  {year}_{month:02d}: No source_url in cache, skipping")
        skipped += 1
        continue

    # Check current data quality
    cats = cached.get("category_allocation", {})
    total = sum(cats.values())
    if total >= 95:
        print(f"  {year}_{month:02d}: Already good ({total:.1f}%), skipping")
        skipped += 1
        continue

    print(f"  {year}_{month:02d}: Re-parsing ({total:.1f}% -> ?) from {url}")

    try:
        time.sleep(2)  # Rate limiting
        resp = session.get(url, timeout=60)
        resp.raise_for_status()

        tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        tmp.write(resp.content)
        tmp.close()

        result = parse_factsheet(tmp.name)
        os.unlink(tmp.name)

        # Preserve existing metadata
        result["source_url"] = url
        result["factsheet_month"] = cached.get("factsheet_month", "")
        result["extraction_date"] = cached.get("extraction_date", "")

        new_cats = result.get("category_allocation", {})
        new_total = sum(new_cats.values())

        # Save updated JSON
        with open(cache_path, "w") as f:
            json.dump(result, f, indent=2)

        print(f"    -> {new_total:.2f}% ({', '.join(f'{k}: {v}' for k, v in new_cats.items())})")
        success += 1

    except Exception as e:
        print(f"    FAILED: {e}")
        failed += 1

print(f"\nDone: {success} re-parsed, {failed} failed, {skipped} skipped")
