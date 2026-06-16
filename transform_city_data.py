#!/usr/bin/env python3
"""Transform to ultra-compact array format for HTML embedding."""
import json

with open("city_data.json", encoding="utf-8") as f:
    raw = json.load(f)

# Get all months
all_months_set = set()
for row in raw:
    ym = row["REPORT_DATE"][:7].replace("-", "")
    all_months_set.add(ym)
all_months = sorted(all_months_set)
month_index = {m: i for i, m in enumerate(all_months)}

cities = {}
for row in raw:
    city = row["CITY"]
    ym = row["REPORT_DATE"][:7].replace("-", "")
    idx = month_index[ym]
    
    if city not in cities:
        cities[city] = {
            "nm": [None] * len(all_months),  # new_mom
            "ny": [None] * len(all_months),  # new_yoy
            "sm": [None] * len(all_months),  # second_mom
            "sy": [None] * len(all_months),  # second_yoy
        }
    
    def to_pct(val):
        if val is None:
            return None
        return round(val - 100, 1)
    
    cities[city]["nm"][idx] = to_pct(row.get("FIRST_COMHOUSE_SEQUENTIAL"))
    cities[city]["ny"][idx] = to_pct(row.get("FIRST_COMHOUSE_SAME"))
    cities[city]["sm"][idx] = to_pct(row.get("SECOND_HOUSE_SEQUENTIAL"))
    cities[city]["sy"][idx] = to_pct(row.get("SECOND_HOUSE_SAME"))

# Compactify: remove trailing/leading nulls, convert to compact array
for c in cities:
    for k in ["nm", "ny", "sm", "sy"]:
        arr = cities[c][k]
        # Find first and last non-null
        first = next((i for i, v in enumerate(arr) if v is not None), None)
        last = next((i for i, v in enumerate(reversed(arr)) if v is not None), None)
        if first is None:
            cities[c][k] = []
        else:
            last = len(arr) - 1 - last
            compact = arr[first:last+1]
            # Replace nulls with null (JSON null) but strip trailing nulls
            while compact and compact[-1] is None:
                compact.pop()
            cities[c][k] = {"o": first, "v": compact}  # offset + values

# Output structure
output = {
    "m": all_months,  # shared month list
    "c": cities,      # {city: {nm: {o:offset, v:[...]}, ny:..., sm:..., sy:...}}
}

with open("city_data_compact.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False)

size = len(json.dumps(output, ensure_ascii=False))
print(f"Compact size: {size} chars ({size/1024:.0f}KB)")
print(f"Cities: {len(cities)}, Months: {len(all_months)}")
print(f"Range: {all_months[0]} - {all_months[-1]}")
