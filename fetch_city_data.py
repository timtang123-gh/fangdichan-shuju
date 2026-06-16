#!/usr/bin/env python3
"""Fetch all 70-city housing price index data from East Money datacenter API."""
import json
import time
import urllib.request
import urllib.error

BASE_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
PAGE_SIZE = 500
OUTPUT_FILE = "city_data.json"

all_data = []
page = 1

while True:
    url = (f"{BASE_URL}?reportName=RPT_ECONOMY_HOUSE_PRICE"
           f"&columns=ALL&pageNumber={page}&pageSize={PAGE_SIZE}"
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
        print(f"API error on page {page}: {d.get('message')}")
        break
    
    data = d["result"]["data"]
    total = d["result"]["count"]
    pages = d["result"]["pages"]
    
    all_data.extend(data)
    print(f"Page {page}/{pages}: fetched {len(data)} records, total so far: {len(all_data)}/{total}")
    
    if len(all_data) >= total:
        break
    
    page += 1
    time.sleep(0.3)  # Be nice to the server

print(f"\nDone! Total records: {len(all_data)}")

# Save as JSON
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(all_data, f, ensure_ascii=False)

print(f"Saved to {OUTPUT_FILE}")

# Print summary
dates = set()
cities = set()
for row in all_data:
    dates.add(row["REPORT_DATE"][:7])
    cities.add(row["CITY"])
dates_sorted = sorted(dates)
print(f"Date range: {dates_sorted[0]} - {dates_sorted[-1]}")
print(f"Months: {len(dates_sorted)}")
print(f"Cities: {len(cities)}")
