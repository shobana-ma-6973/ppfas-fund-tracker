"""
Batch check availability of all PPFAS factsheets from 2013 to present.
"""
import sys
sys.path.insert(0, 'src')
import requests
from datetime import datetime

PPFAS_AMC_BASE = "https://amc.ppfas.com"

def get_url(year, month):
    month_name = datetime(year, month, 1).strftime("%B")
    return f"{PPFAS_AMC_BASE}/downloads/factsheet/{year}/ppfas-mf-factsheet-for-{month_name}-{year}.pdf"

now = datetime.now()
available = []
missing = []

for year in range(2013, now.year + 1):
    start_m = 5 if year == 2013 else 1  # Fund started May 2013
    end_m = now.month - 1 if year == now.year else 12
    for month in range(start_m, end_m + 1):
        url = get_url(year, month)
        try:
            resp = requests.head(url, timeout=10, allow_redirects=True)
            if resp.status_code == 200:
                available.append((year, month, url))
                status = "OK"
            else:
                missing.append((year, month, resp.status_code))
                status = f"MISS ({resp.status_code})"
        except Exception as e:
            missing.append((year, month, str(e)))
            status = f"ERR"
        label = datetime(year, month, 1).strftime("%b %Y")
        print(f"{label}: {status}")

print(f"\nTotal: {len(available)} available, {len(missing)} missing")
if missing:
    print("Missing months:")
    for y, m, reason in missing:
        print(f"  {datetime(y, m, 1).strftime('%b %Y')}: {reason}")
