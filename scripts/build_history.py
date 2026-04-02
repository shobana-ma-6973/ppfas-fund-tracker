"""
Build consolidated allocation_history.json from all individual factsheet JSONs.
Groups data chronologically and normalizes category/sector data.
"""
import json
import glob
import os
from datetime import datetime

DATA_DIR = "data"
OUTPUT_FILE = os.path.join(DATA_DIR, "allocation_history.json")


def build_history():
    """Build the consolidated history JSON from all factsheet_YYYY_MM.json files."""
    records = []

    for filepath in sorted(glob.glob(os.path.join(DATA_DIR, "factsheet_*.json"))):
        basename = os.path.basename(filepath)
        # Skip non-monthly files
        if basename in ("factsheet_data.json", "factsheet_urls.json"):
            continue

        key = basename.replace("factsheet_", "").replace(".json", "")
        parts = key.split("_")
        if len(parts) != 2:
            continue

        year, month = int(parts[0]), int(parts[1])

        with open(filepath) as f:
            data = json.load(f)

        categories = data.get("category_allocation", {})
        sectors = data.get("sector_allocation", {})
        aum = data.get("aum", "N/A")

        # Skip months with no category data at all
        if not categories:
            continue

        cat_total = sum(categories.values())

        # Flag data quality
        quality = "good"
        if cat_total > 105:
            quality = "overcounted"
        elif cat_total < 90:
            quality = "incomplete"
        elif cat_total < 95:
            quality = "approximate"

        record = {
            "date": f"{year}-{month:02d}-01",
            "year": year,
            "month": month,
            "categories": categories,
            "category_total": round(cat_total, 2),
            "sectors": sectors,
            "sector_count": len(sectors),
            "aum": aum,
            "quality": quality,
        }
        records.append(record)

    # Sort chronologically
    records.sort(key=lambda r: r["date"])

    history = {
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_months": len(records),
        "date_range": {
            "start": records[0]["date"] if records else None,
            "end": records[-1]["date"] if records else None,
        },
        "quality_summary": {
            "good": sum(1 for r in records if r["quality"] == "good"),
            "approximate": sum(1 for r in records if r["quality"] == "approximate"),
            "incomplete": sum(1 for r in records if r["quality"] == "incomplete"),
            "overcounted": sum(1 for r in records if r["quality"] == "overcounted"),
        },
        "records": records,
    }

    with open(OUTPUT_FILE, "w") as f:
        json.dump(history, f, indent=2)

    print(f"Generated {OUTPUT_FILE}")
    print(f"  Total months: {history['total_months']}")
    print(f"  Date range: {history['date_range']['start']} to {history['date_range']['end']}")
    print(f"  Quality: {history['quality_summary']}")

    return history


if __name__ == "__main__":
    build_history()
