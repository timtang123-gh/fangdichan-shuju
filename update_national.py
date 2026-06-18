#!/usr/bin/env python3
"""
Update the national D-array data in index.html with the latest NBS release.

1. Calls fetch_national.py to get the latest data
2. Checks if it's newer than what's already in index.html
3. If newer, inserts the new entry into the D array

Usage: python3 update_national.py [YYYY-MM]
Exit code 0: updated or no new data needed
Exit code 1: error
"""
import json
import os
import re
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HTML_FILE = os.path.join(SCRIPT_DIR, "index.html")


def get_latest_d_month():
    """Get the latest month from the D array in index.html."""
    with open(HTML_FILE, encoding="utf-8") as f:
        html = f.read()
    matches = re.findall(r'\{d:"(\d{4}-\d{2})"', html)
    return matches[-1] if matches else None


def insert_entry(entry):
    """Insert a new D-array entry into index.html, after the last existing entry."""
    with open(HTML_FILE, encoding="utf-8") as f:
        html = f.read()
    
    # Find the last entry in the D array
    # D array ends with: {d:"YYYY-MM",...}, followed by ]; const RD=
    latest_month = get_latest_d_month()
    if not latest_month:
        print("ERROR: Could not find D array in index.html")
        return False
    
    if entry["d"] <= latest_month:
        print(f"Data for {entry['d']} already exists (latest: {latest_month})")
        return False
    
    # Build the new entry string
    fields = []
    for key in ['d','investTotalCum','investTotalCumYoy','salesAreaCum','salesAreaCur',
                'salesAreaCumYoy','salesAreaCurYoy','salesAmtCum','salesAmtCumYoy',
                'newStartsCum','newStartsCumYoy','constrCum','constrCumYoy',
                'compCum','compCumYoy','inventory','inventoryYoy',
                'fundDepositCum','fundSelfCum','fundLoanCum','fundOtherCum','fundForeignCum']:
        val = entry.get(key)
        if val is None:
            fields.append(f'{key}:null')
        elif isinstance(val, float):
            fields.append(f'{key}:{val}')
        else:
            fields.append(f'{key}:{val}')
    
    new_line = f'    {{{",".join(fields)}}},'
    
    # Find the insertion point: right before the last '}' in the D array
    # The D array ends with: {d:"YYYY-MM",...}\n];\nconst RD=
    # We need to insert after the last entry's '}' and before the '];'
    
    # Find the last entry and replace pattern
    pattern = r'(\{d:"' + re.escape(latest_month) + r'".*?\},)\s*\];'
    
    def replace_func(m):
        return m.group(1) + '\n' + new_line + '\n];'
    
    new_html = re.sub(pattern, replace_func, html, count=1, flags=re.DOTALL)
    
    if new_html == html:
        print("ERROR: Could not find insertion point in index.html")
        return False
    
    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(new_html)
    
    print(f"✓ Inserted new entry for {entry['d']}")
    return True


def main():
    target_month = sys.argv[1] if len(sys.argv) > 1 else None
    
    # Run fetch_national.py
    fetch_script = os.path.join(SCRIPT_DIR, "fetch_national.py")
    cmd = [sys.executable, fetch_script]
    if target_month:
        cmd.append(target_month)
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"fetch_national.py failed: {result.stderr}")
        sys.exit(1)
    
    try:
        entry = json.loads(result.stdout.strip())
    except json.JSONDecodeError:
        # Try to find the last JSON line
        for line in result.stdout.strip().split('\n'):
            try:
                entry = json.loads(line)
                break
            except json.JSONDecodeError:
                continue
        else:
            print("ERROR: Could not parse fetch_national.py output")
            sys.exit(1)
    
    if "error" in entry:
        print(f"No national data available: {entry['error']}")
        print("(This is normal if NBS hasn't released the data yet)")
        sys.exit(0)
    
    # Check if we already have this data
    latest = get_latest_d_month()
    if latest and entry["d"] <= latest:
        print(f"National data already up to date (latest: {latest})")
        sys.exit(0)
    
    # Compute derived fields
    # salesAreaCur = current cumulative - previous cumulative
    # For this we need the previous month's salesAreaCum
    prev_sales = None
    with open(HTML_FILE, encoding="utf-8") as f:
        html = f.read()
    prev_match = re.search(r'\{d:"([^"]+)",.*?salesAreaCum:([\d.]+)', html)
    if prev_match:
        prev_month = prev_match.group(1)
        prev_val = float(prev_match.group(2))
        # Find the entry just before our target month
        all_entries = re.findall(r'\{d:"([^"]+)",.*?salesAreaCum:([\d.]+)', html)
        for pm, pv in all_entries:
            if pm < entry["d"]:
                prev_month = pm
                prev_val = float(pv)
        # Check if entry is cumulative month that should have salesAreaCur
        # For months 02-12 (not 01), compute current = cum - prev cum
        month_num = int(entry["d"].split("-")[1])
        if month_num != 1 and prev_val > 0:
            entry["salesAreaCur"] = round(entry.get("salesAreaCum", 0) - prev_val, 1)
    
    # Compute fundOtherCum
    fund_fields = ['fundDepositCum','fundSelfCum','fundLoanCum','fundForeignCum']
    known_sum = sum(entry.get(f, 0) or 0 for f in fund_fields)
    # The NBS table also has a "到位资金" total entry. If we had it, we could compute other.
    # For now, set fundOtherCum to None - JS will handle it
    if entry.get('fundOtherCum') is None:
        entry['fundOtherCum'] = None  # Let JS compute from fundTotal if needed
    
    # Insert into HTML
    if insert_entry(entry):
        print(f"✓ Updated national data to {entry['d']}")
    else:
        print("No update needed")
        sys.exit(0)


if __name__ == "__main__":
    main()
