#!/usr/bin/env python3
"""
Fetch national real estate data from NBS for a given month.
Tries multiple strategies to find the NBS communique page URL.

Usage: python3 fetch_national.py [YYYY-MM]

Output: JSON with D-array entry fields. Exit code 0 on success, non-zero on failure.
"""
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
URL_BANK_FILE = os.path.join(SCRIPT_DIR, "nbs_urls.json")
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


def load_url_bank():
    if os.path.exists(URL_BANK_FILE):
        with open(URL_BANK_FILE) as f:
            return json.load(f)
    return {}


def save_url_bank(bank):
    with open(URL_BANK_FILE, "w") as f:
        json.dump(bank, f, indent=2)


def find_nbs_url(target_month):
    """Find the NBS communique URL for a given month."""
    # Check URL bank first
    bank = load_url_bank()
    if target_month in bank:
        url = bank[target_month]
        print(f"Using cached URL: {url}", file=sys.stderr)
        return url
    
    # Compute release month (data for month M is released in month M+1, ~16th)
    target_dt = datetime.strptime(target_month, "%Y-%m")
    release_dt = datetime(target_dt.year, target_dt.month, 1) + timedelta(days=45)
    release_dt = release_dt.replace(day=1)
    release_ym = release_dt.strftime("%Y%m")
    
    # Try URLs with dates 14-18 of release month
    for day in range(14, 19):
        url = f"https://www.stats.gov.cn/sj/zxfb/{release_ym}/t{release_ym}{day:02d}_1963950.html"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    html = resp.read().decode("utf-8", errors="ignore")
                    if "房地产市场" in html:
                        print(f"Found: {url}", file=sys.stderr)
                        bank[target_month] = url
                        save_url_bank(bank)
                        return url
        except Exception:
            continue
    
    # Fallback: try without ID suffix (just the date)
    for day in range(14, 19):
        # Try next sequential IDs
        last_id = max([int(v.split("_")[-1].replace(".html", "")) for v in bank.values()] + [1963900])
        for offset in range(10):
            cid = last_id + offset
            url = f"https://www.stats.gov.cn/sj/zxfb/{release_ym}/t{release_ym}{day:02d}_{cid}.html"
            try:
                req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(req, timeout=8) as resp:
                    if resp.status == 200:
                        html = resp.read().decode("utf-8", errors="ignore")
                        if "房地产市场" in html or "房地产开发投资" in html:
                            print(f"Found (with ID guess): {url}", file=sys.stderr)
                            bank[target_month] = url
                            save_url_bank(bank)
                            return url
            except Exception:
                continue
    
    return None


def parse_nbs_html(html):
    """Parse NBS communique HTML and extract all real estate indicators."""
    indicators = {}
    
    # Define indicator patterns: (label_keywords, field_prefix)
    indicator_specs = [
        # Main indicators with 2 values (absolute + yoy)
        ("房地产开发投资", "invest", True),
        ("房屋施工面积", "constr", True),
        ("房屋新开工面积", "newStarts", True),
        ("房屋竣工面积", "comp", True),
        ("新建商品房销售面积", "salesArea", True),
        ("新建商品房销售额", "salesAmt", True),
        ("商品房待售面积", "inventory", True),
        # Funding breakdown (with yoy)
        ("国内贷款", "fundLoan", True),
        ("自筹资金", "fundSelf", True),
        ("定金及预收款", "fundDeposit", True),
        ("利用外资", "fundForeign", False),  # often very small/zero
        ("个人按揭贷款", "fundPMort", True),
    ]
    
    # Strip HTML tags for text extraction
    text = re.sub(r'<[^>]+>', ' ', html)
    text = re.sub(r'\s+', ' ', text)
    
    # Parse the table more precisely
    # Look for table rows with indicators
    table_patterns = [
        r'<table[^>]*>(.*?)</table>',
    ]
    
    # Try to find the main data table
    # The NBS table has rows like:
    # <tr><td>房地产开发投资（亿元）</td><td>30356</td><td>-16.2</td></tr>
    # Or: <tr><td>房地产开发投资</td><td>30356</td><td>-16.2</td></tr>
    
    # Strategy 1: Parse table rows directly
    # Clean HTML first
    clean = re.sub(r'<!--.*?-->', '', html, flags=re.DOTALL)
    
    # Find all table rows that have at least 3 cells with numeric content
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', clean, re.DOTALL)
    
    table_data = []
    for row in rows:
        cells = re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', row, re.DOTALL)
        if len(cells) < 2:
            continue
        # Clean cell content
        clean_cells = [re.sub(r'<[^>]+>', '', c).strip() for c in cells]
        # Remove empty/nbsp cells
        clean_cells = [c for c in clean_cells if c and c != '\xa0' and c != '&nbsp;']
        if len(clean_cells) >= 2:
            table_data.append(clean_cells)
    
    # Extract values from parsed table rows
    for cells in table_data:
        label = cells[0].replace('\u3000', '').replace('　', '').strip()
        
        # Try to match against our indicator specs
        for keywords, prefix, has_yoy in indicator_specs:
            if keywords in label:
                # Try to find numeric values in remaining cells
                for cell in cells[1:]:
                    m = re.search(r'(-?\d+\.?\d*)', cell)
                    if m:
                        val = float(m.group(1))
                        if f'{prefix}Val' not in indicators:
                            indicators[f'{prefix}Val'] = val
                        elif has_yoy and f'{prefix}Yoy' not in indicators:
                            indicators[f'{prefix}Yoy'] = val
                break
    
    # Strategy 2: fallback to text-based extraction for any missing fields
    def text_val(keyword):
        m = re.search(rf'{keyword}[^0-9]*?(\d+\.?\d*)\s*(?:亿元|万平方米|%)?', text)
        return float(m.group(1)) if m else None
    
    def text_pct(keyword):
        m = re.search(rf'{keyword}[^0-9]*?(-?\d+\.?\d*)%', text)
        if not m:
            m = re.search(rf'{keyword}[\s\S]*?(-?\d+\.?\d*)%', text)
        return float(m.group(1)) if m else None
    
    # Fill missing values from text
    fill_map = {
        ('investVal','investYoy'): '房地产开发投资',
        ('constrVal','constrYoy'): '房屋施工面积',
        ('newStartsVal','newStartsYoy'): '房屋新开工面积',
        ('compVal','compYoy'): '房屋竣工面积',
        ('salesAreaVal','salesAreaYoy'): '新建商品房销售面积',
        ('salesAmtVal','salesAmtYoy'): '新建商品房销售额',
        ('inventoryVal','inventoryYoy'): '商品房待售面积',
    }
    
    for (val_key, yoy_key), keyword in fill_map.items():
        if val_key not in indicators:
            v = text_val(keyword)
            if v is not None:
                indicators[val_key] = v
        if yoy_key not in indicators:
            p = text_pct(keyword)
            if p is not None:
                indicators[yoy_key] = p
    
    # Funding breakdown
    fund_keywords = {
        'fundLoan': '国内贷款',
        'fundSelf': '自筹资金',
        'fundDeposit': '定金及预收款',
        'fundForeign': '利用外资',
    }
    for key, kw in fund_keywords.items():
        val_key = f'{key}Val'
        if val_key not in indicators:
            v = text_val(kw)
            if v is not None:
                indicators[val_key] = v
    
    # Print debug info
    print(f"Parsed {len(indicators)} indicator values:", file=sys.stderr)
    for k in sorted(indicators.keys()):
        print(f"  {k}: {indicators[k]}", file=sys.stderr)
    
    return indicators


def build_entry(indicators, target_month):
    """Build D-array entry from parsed indicators."""
    entry = {"d": target_month}
    
    # Direct mappings
    val_to_field = {
        'investVal': 'investTotalCum', 'investYoy': 'investTotalCumYoy',
        'constrVal': 'constrCum', 'constrYoy': 'constrCumYoy',
        'newStartsVal': 'newStartsCum', 'newStartsYoy': 'newStartsCumYoy',
        'compVal': 'compCum', 'compYoy': 'compCumYoy',
        'salesAreaVal': 'salesAreaCum', 'salesAreaYoy': 'salesAreaCumYoy',
        'salesAmtVal': 'salesAmtCum', 'salesAmtYoy': 'salesAmtCumYoy',
        'inventoryVal': 'inventory', 'inventoryYoy': 'inventoryYoy',
        'fundLoanVal': 'fundLoanCum',
        'fundSelfVal': 'fundSelfCum',
        'fundDepositVal': 'fundDepositCum',
        'fundForeignVal': 'fundForeignCum',
    }
    
    for src, dst in val_to_field.items():
        if src in indicators:
            entry[dst] = indicators[src]
    
    # Compute salesAreaCur (当月 = 累计期 - 累前期)
    # This requires the previous month's data, which the caller handles
    entry['salesAreaCur'] = None
    entry['salesAreaCurYoy'] = None
    
    # fundForeignCum defaults to 0 if not found
    if 'fundForeignCum' not in entry:
        entry['fundForeignCum'] = 0
    
    # Compute fundOtherCum from total if available
    # Or leave as null - it will be computed by the JS in the page
    # We'll set null and let the JS side compute it
    entry['fundOtherCum'] = None
    
    # Ensure all expected fields exist
    expected = ['investTotalCum','investTotalCumYoy','salesAreaCum','salesAreaCur',
                'salesAreaCumYoy','salesAreaCurYoy','salesAmtCum','salesAmtCumYoy',
                'newStartsCum','newStartsCumYoy','constrCum','constrCumYoy',
                'compCum','compCumYoy','inventory','inventoryYoy',
                'fundDepositCum','fundSelfCum','fundLoanCum','fundOtherCum','fundForeignCum']
    for f in expected:
        if f not in entry:
            entry[f] = None
    
    return entry


def main():
    if len(sys.argv) > 1:
        target_month = sys.argv[1]
    else:
        now = datetime.now()
        prev = now.replace(day=1) - timedelta(days=1)
        target_month = prev.strftime("%Y-%m")
    
    print(f"Target: {target_month}", file=sys.stderr)
    
    url = find_nbs_url(target_month)
    if not url:
        print(json.dumps({"error": f"Could not find NBS page for {target_month}"}))
        sys.exit(1)
    
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        html = resp.read().decode("utf-8", errors="ignore")
    
    indicators = parse_nbs_html(html)
    
    if not indicators:
        print(json.dumps({"error": "Failed to parse any indicators"}))
        sys.exit(1)
    
    entry = build_entry(indicators, target_month)
    print(json.dumps(entry, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
