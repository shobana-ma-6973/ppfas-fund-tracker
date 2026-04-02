"""Check alternative URL patterns for older PPFAS factsheets."""
import requests

BASE = "https://amc.ppfas.com"

# Try various URL patterns for a sample older month (Jun 2020)
patterns = [
    "/downloads/factsheet/2020/ppfas-mf-factsheet-for-June-2020.pdf",
    "/downloads/factsheet/2020/ppfas-mf-factsheet-june-2020.pdf",
    "/downloads/factsheet/2020/factsheet-june-2020.pdf", 
    "/downloads/factsheet/2020/ppfas-factsheet-june-2020.pdf",
    "/downloads/factsheet/2020/Factsheet-June-2020.pdf",
    "/downloads/factsheet/ppfas-mf-factsheet-for-June-2020.pdf",
    "/downloads/factsheet/Factsheet-for-June-2020.pdf",
    "/downloads/factsheet/2020/PPFAS-MF-Factsheet-for-June-2020.pdf",
    "/downloads/factsheet/2020/ppfas-mutual-fund-factsheet-june-2020.pdf",
]

for p in patterns:
    url = BASE + p
    try:
        r = requests.head(url, timeout=10, allow_redirects=True)
        print(f"{r.status_code} {url}")
    except:
        print(f"ERR {url}")

# Also try scraping the factsheet page to find historical links
print("\n--- Scraping factsheet archive page ---")
from bs4 import BeautifulSoup
resp = requests.get(BASE + "/downloads/factsheet/", timeout=30)
soup = BeautifulSoup(resp.text, "html.parser")
links = soup.find_all("a", href=True)
pdf_links = [l["href"] for l in links if ".pdf" in l["href"].lower() and "factsheet" in l["href"].lower()]
print(f"Found {len(pdf_links)} factsheet PDF links")
# Show oldest and newest
for link in sorted(pdf_links)[:5]:
    print(f"  {link}")
print("  ...")
for link in sorted(pdf_links)[-5:]:
    print(f"  {link}")
