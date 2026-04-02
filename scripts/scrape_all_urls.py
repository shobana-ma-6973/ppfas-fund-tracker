"""
Scrape all factsheet PDF links from the PPFAS archive page
and save to a JSON mapping file.
"""
import sys
sys.path.insert(0, 'src')
import requests
from bs4 import BeautifulSoup
import json
import re
from pathlib import Path

PPFAS_AMC_BASE = "https://amc.ppfas.com"
PPFAS_FACTSHEET_PAGE = PPFAS_AMC_BASE + "/downloads/factsheet/"

resp = requests.get(PPFAS_FACTSHEET_PAGE, timeout=30)
soup = BeautifulSoup(resp.text, "html.parser")
links = soup.find_all("a", href=True)

factsheets = {}
month_names = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}

for link in links:
    href = link["href"]
    if ".pdf" not in href.lower():
        continue
    if "factsheet" not in href.lower():
        continue
    
    # Normalize URL
    url = href if href.startswith("http") else PPFAS_AMC_BASE + href
    url = url.split("?")[0]
    
    # Extract year and month from URL
    url_lower = url.lower()
    year_m = re.search(r"/(\d{4})/", url_lower)
    if not year_m:
        continue
    year = int(year_m.group(1))
    
    month = None
    for mname, mnum in month_names.items():
        if mname in url_lower:
            month = mnum
            break
    
    if not month:
        continue
    
    key = f"{year}_{month:02d}"
    factsheets[key] = url

# Sort by key
factsheets = dict(sorted(factsheets.items()))

print(f"Found {len(factsheets)} factsheet URLs")
print(f"Range: {list(factsheets.keys())[0]} to {list(factsheets.keys())[-1]}")

# Save to file
outpath = Path("data/factsheet_urls.json")
outpath.parent.mkdir(parents=True, exist_ok=True)
with open(outpath, "w") as f:
    json.dump(factsheets, f, indent=2)
print(f"Saved to {outpath}")

# Show all
for key, url in factsheets.items():
    print(f"  {key}: {url}")
