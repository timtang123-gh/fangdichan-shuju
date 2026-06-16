#!/usr/bin/env python3
"""Inject compact city data into index.html."""
import json

# Read city data
with open("city_data_compact.json", encoding="utf-8") as f:
    city_data = json.load(f)

# Read index.html
with open("index.html", encoding="utf-8") as f:
    html = f.read()

# Build JS string
city_js = f"const CITY_DATA={json.dumps(city_data, ensure_ascii=False)};"

# Replace the marker
old = "// ===== CITY DATA ====="
new = f"{old}\n{city_js}"
html = html.replace(old, new)

with open("index.html", "w", encoding="utf-8") as f:
    f.write(html)

print(f"Injected CITY_DATA ({len(city_js)} chars)")
print(f"Final HTML size: {len(html)} chars ({len(html)/1024:.0f}KB)")
