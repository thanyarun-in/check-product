#!/usr/bin/env python3
"""
Daily refresh of the SRM Stock data embedded in index.html, run by
.github/workflows/refresh-stock.yml.

This script ONLY refreshes the ART_INFO table (article -> name/status/stock).
The store list (STORES) and barcode map (BC2ART) are left untouched -- they
come from internal Excel files that don't change often and aren't published
anywhere this workflow can reach, so they're only refreshed manually
(rebuild locally and re-upload index.html) when the store list or barcode
list itself changes.

Data source: the "SRM Stock" Google Sheet, "Master" tab, shared as "Anyone
with the link can view". Fetched via the public gviz/tq CSV export endpoint,
which (unlike the plain /export?format=csv endpoint) works for an anonymous,
unauthenticated request -- exactly what a GitHub Actions runner is.
"""
import csv
import io
import json
import sys
import urllib.request

SHEET_ID = "1GOUzzDPuS2l5T-Dk5RecNcKJrgvHmJ17b6KjExtTnoQ"
SHEET_TAB = "Master"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={SHEET_TAB}"
INDEX_PATH = "index.html"

PREFIX = "const ART_INFO = "
MARKER = ";  /* article -> [name, status] */"

MIN_EXPECTED_ARTICLES = 10000  # sanity guard -- see main()


def s(v):
    return (v or '').strip()


def num_str(v):
    if not v:
        return 0
    try:
        return int(round(float(str(v).replace(',', ''))))
    except Exception:
        return 0


def date_str(v):
    """Google's CSV export gives ISO dates (yyyy-mm-dd); reformat to
    dd/mm/yyyy to match what the app (and the original build pipeline) uses."""
    v = s(v)
    if not v:
        return ''
    parts = v.split('-')
    if len(parts) == 3 and len(parts[0]) == 4:
        y, m, d = parts
        return f'{d}/{m}/{y}'
    return v


def fetch_art_info():
    req = urllib.request.Request(CSV_URL, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read().decode('utf-8-sig')

    reader = csv.reader(io.StringIO(raw))
    header = next(reader)
    idx = {h: i for i, h in enumerate(header) if h}
    required = ['article_no', 'product_name', 'product_status',
                'kk_available_stock', 'kk_intransit_date',
                'bw_available_stock', 'bw_intransit_date']
    missing = [c for c in required if c not in idx]
    if missing:
        raise SystemExit(f"SRM Stock CSV is missing column(s): {missing}. Found: {list(idx.keys())}")

    art_info = {}
    for r in reader:
        if not r or idx['article_no'] >= len(r):
            continue
        art = r[idx['article_no']]
        if not art:
            continue
        art = s(art)
        name = s(r[idx['product_name']]) if idx['product_name'] < len(r) else ''
        status = s(r[idx['product_status']]) if idx['product_status'] < len(r) else ''
        kk_stock = num_str(r[idx['kk_available_stock']]) if idx['kk_available_stock'] < len(r) else 0
        kk_date = date_str(r[idx['kk_intransit_date']]) if idx['kk_intransit_date'] < len(r) else ''
        kk_qty = num_str(r[idx['kk_intransit_qty']]) if 'kk_intransit_qty' in idx and idx['kk_intransit_qty'] < len(r) else 0
        bw_stock = num_str(r[idx['bw_available_stock']]) if idx['bw_available_stock'] < len(r) else 0
        bw_date = date_str(r[idx['bw_intransit_date']]) if idx['bw_intransit_date'] < len(r) else ''
        bw_qty = num_str(r[idx['bw_intransit_qty']]) if 'bw_intransit_qty' in idx and idx['bw_intransit_qty'] < len(r) else 0
        art_info[art] = [name, status, kk_stock, kk_date, kk_qty, bw_stock, bw_date, bw_qty]
    return art_info


def safe_json_text(raw_json_text):
    """Guard against '</' breaking out of the <script> tag when embedded
    verbatim as a JS literal (same escaping build_app.py uses)."""
    return raw_json_text.replace('</script', '<\\/script').replace('</', '<\\/')


def main():
    print(f'Fetching {CSV_URL} ...', file=sys.stderr)
    art_info = fetch_art_info()
    print(f'  {len(art_info)} articles fetched', file=sys.stderr)

    if len(art_info) < MIN_EXPECTED_ARTICLES:
        # If the sheet is ever unshared, moved, or the export briefly
        # returns something truncated/broken, refuse to overwrite the live
        # site with bad data -- better to serve yesterday's real data than
        # today's broken data.
        print(
            f'Refusing to update: only {len(art_info)} articles fetched '
            f'(expected at least {MIN_EXPECTED_ARTICLES}). Leaving index.html untouched.',
            file=sys.stderr,
        )
        sys.exit(1)

    art_info_json = safe_json_text(json.dumps(art_info, ensure_ascii=False, separators=(',', ':')))

    with open(INDEX_PATH, encoding='utf-8') as f:
        html = f.read()

    start = html.find(PREFIX)
    if start == -1:
        raise SystemExit(f'Could not find "{PREFIX}" in {INDEX_PATH} -- has the template changed?')
    end = html.find(MARKER, start)
    if end == -1:
        raise SystemExit(f'Could not find the trailing marker in {INDEX_PATH} -- has the template changed?')

    new_html = html[:start] + PREFIX + art_info_json + html[end:]

    if new_html == html:
        print('No change (data identical to what is already embedded).', file=sys.stderr)
        return

    with open(INDEX_PATH, 'w', encoding='utf-8') as f:
        f.write(new_html)

    print(f'Updated {INDEX_PATH} with {len(art_info)} articles.', file=sys.stderr)


if __name__ == '__main__':
    main()
