#!/usr/bin/env python3
"""
Auto-update 70-city housing price data.
- Reads existing compact data to find latest month
- Incrementally fetches only new data from East Money API
- Merges into compact format and re-injects into index.html
- Idempotent: safe to run multiple times; exits gracefully if no new data
"""
import json
import sys
import time
import urllib.request
import urllib.error
import os

BASE_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
PAGE_SIZE = 500

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
COMPACT_FILE = os.path.join(SCRIPT_DIR, "city_data_compact.json")
HTML_FILE = os.path.join(SCRIPT_DIR, "index.html")


def load_existing():
    """Load existing compact data file."""
    if not os.path.exists(COMPACT_FILE):
        print(f"ERROR: {COMPACT_FILE} not found! Run full fetch first.")
        sys.exit(1)
    with open(COMPACT_FILE, encoding="utf-8") as f:
        return json.load(f)


def get_latest_month(compact):
    """Return the latest month string (YYYYMM) from compact data."""
    return compact["m"][-1]


def fetch_new_data(latest_month):
    """
    Fetch records newer than latest_month from East Money API.
    Uses sort by REPORT_DATE descending + pagination.
    Stops when we hit known months.
    """
    # Convert YYYYMM to a sortable date string for the API filter
    # latest_month is like "202605", we filter for REPORT_DATE > "2026-05-31"
    year = latest_month[:4]
    month = latest_month[4:6]
    # Get the last day of latest_month as cutoff
    import calendar
    last_day = calendar.monthrange(int(year), int(month))[1]
    cutoff_date = f"{year}-{month}-{last_day}"
    
    print(f"Looking for data after: {cutoff_date}")
    
    new_records = []
    page = 1
    
    while True:
        # Use sort by REPORT_DATE descending to get newest first
        url = (f"{BASE_URL}?reportName=RPT_ECONOMY_HOUSE_PRICE"
               f"&columns=ALL&pageNumber={page}&pageSize={PAGE_SIZE}"
               f"&sortTypes=-1&sortFields=REPORT_DATE"
               f"&source=WEB&client=WEB")
        
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                d = json.loads(resp.read().decode())
        except Exception as e:
            print(f"Error on page {page}: {e}")
            time.sleep(2)
            continue
        
        if not d.get("success"):
            print(f"API error: {d.get('message')}")
            break
        
        data = d["result"]["data"]
        total = d["result"]["count"]
        pages = d["result"]["pages"]
        
        print(f"Page {page}/{pages}: fetched {len(data)} records")
        
        # Filter: only keep records with REPORT_DATE after cutoff
        added = 0
        for row in data:
            rd = row.get("REPORT_DATE", "")
            if rd > cutoff_date:
                new_records.append(row)
                added += 1
        
        print(f"  → {added} new records on this page")
        
        # Since we sort by REPORT_DATE descending, if this page has 0 new records,
        # ALL remaining pages will also be older — stop immediately
        if added == 0:
            if len(new_records) > 0:
                print("  → No more new records, stopping pagination")
            else:
                print("  → No new data at all — data is already current")
            break
        
        if page >= pages:
            break
        
        page += 1
        time.sleep(0.3)
    
    return new_records


def merge_compact(existing, new_records):
    """Merge new records into compact format."""
    if not new_records:
        return existing, 0
    
    # Find all new months
    existing_months = set(existing["m"])
    new_months = set()
    for row in new_records:
        ym = row["REPORT_DATE"][:7].replace("-", "")
        if ym not in existing_months:
            new_months.add(ym)
    
    if not new_months:
        print("No new months found in fetched data (all already exist)")
        return existing, 0
    
    new_months_sorted = sorted(new_months)
    print(f"New months to add: {new_months_sorted}")
    
    # Build full month list
    all_months = existing["m"] + new_months_sorted
    month_index = {m: i for i, m in enumerate(all_months)}
    
    # Extend existing city arrays with None for new months
    new_month_count = len(new_months_sorted)
    for city_name, city_data in existing["c"].items():
        for key in ["nm", "ny", "sm", "sy"]:
            kdata = city_data[key]
            if isinstance(kdata, dict) and "v" in kdata:
                # Extend with None values for new months
                kdata["v"].extend([None] * new_month_count)
    
    # Add new cities if any
    for row in new_records:
        city = row["CITY"]
        ym = row["REPORT_DATE"][:7].replace("-", "")
        idx = month_index[ym]
        
        if city not in existing["c"]:
            existing["c"][city] = {
                "nm": {"o": idx, "v": [None] * len(all_months)},
                "ny": {"o": idx, "v": [None] * len(all_months)},
                "sm": {"o": idx, "v": [None] * len(all_months)},
                "sy": {"o": idx, "v": [None] * len(all_months)},
            }
        
        def to_pct(val):
            if val is None:
                return None
            return round(val - 100, 1)
        
        c = existing["c"][city]
        c["nm"]["v"][idx] = to_pct(row.get("FIRST_COMHOUSE_SEQUENTIAL"))
        c["ny"]["v"][idx] = to_pct(row.get("FIRST_COMHOUSE_SAME"))
        c["sm"]["v"][idx] = to_pct(row.get("SECOND_HOUSE_SEQUENTIAL"))
        c["sy"]["v"][idx] = to_pct(row.get("SECOND_HOUSE_SAME"))
    
    # Update month list
    existing["m"] = all_months
    
    return existing, len(new_months_sorted)


def inject_html(compact):
    """Inject compact data into index.html."""
    with open(HTML_FILE, encoding="utf-8") as f:
        html = f.read()
    
    city_js = f"const CITY_DATA={json.dumps(compact, ensure_ascii=False)};"
    
    old = "// ===== CITY DATA ====="
    if old not in html:
        print("ERROR: CITY_DATA marker not found in index.html!")
        sys.exit(1)
    
    new = f"{old}\n{city_js}"
    html = html.replace(old, new)
    
    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    
    return len(html)


def main():
    print("=" * 50)
    print("70-City Housing Price Data — Auto Update")
    print("=" * 50)
    
    # 1. Load existing data
    compact = load_existing()
    latest = get_latest_month(compact)
    print(f"Current data: {len(compact['m'])} months, {len(compact['c'])} cities")
    print(f"Latest month:   {latest}")
    
    # 2. Fetch new data
    new_records = fetch_new_data(latest)
    print(f"\nFetched {len(new_records)} new records total")
    
    if not new_records:
        print("\n✓ No new data available. Dashboard is already up to date.")
        return
    
    # 3. Merge
    merged, new_months = merge_compact(compact, new_records)
    
    if new_months == 0:
        print("\n✓ No new months to add. Dashboard is already up to date.")
        return
    
    # 4. Save compact file
    with open(COMPACT_FILE, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False)
    print(f"\n✓ Saved compact data: {len(merged['m'])} months, {len(merged['c'])} cities")
    print(f"  New range: {merged['m'][0]} ~ {merged['m'][-1]}")
    
    # 5. Inject into HTML
    html_size = inject_html(merged)
    print(f"✓ Injected into index.html ({html_size/1024:.0f}KB)")
    
    print("\n" + "=" * 50)
    print(f"✓ Update complete! Added {new_months} new month(s) of data.")
    print("=" * 50)


if __name__ == "__main__":
    main()
