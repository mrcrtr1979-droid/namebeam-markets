#!/usr/bin/env python3
"""
refresh_pages.py - Update dated content on namebeam markets pages from data/latest.json

Usage:
    py -3.13 -I -B tools/refresh_pages.py [--root PATH] [--today YYYY-MM-DD] [--no-fetch] [--selftest]

Updates five HTML pages with current dates and data from the daily record.
"""

import argparse
import json
import re
import sys
import tempfile
import hashlib
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError
import csv


class RefreshError(Exception):
    """Raised when refresh fails"""
    pass


def main():
    parser = argparse.ArgumentParser(description='Refresh dated content in HTML pages')
    parser.add_argument('--root', type=Path, default=Path.cwd(),
                        help='Repository root path')
    parser.add_argument('--today', type=str,
                        help='Override today date (YYYY-MM-DD)')
    parser.add_argument('--no-fetch', action='store_true',
                        help='Skip citation index fetch')
    parser.add_argument('--selftest', action='store_true',
                        help='Run self-test')

    args = parser.parse_args()

    if args.selftest:
        return run_selftest()

    root = args.root.resolve()
    today = args.today if args.today else datetime.utcnow().strftime('%Y-%m-%d')

    print(f"Root: {root}")
    print(f"Today: {today}")

    # Load data
    latest = load_json(root / 'data' / 'latest.json')
    latest_run_day = latest['latest_run_day']

    # Load summary data for markets
    markets_data = {}
    for slug in latest['markets'].keys():
        summary_path = root / 'record' / slug / 'summary.json'
        if summary_path.exists():
            markets_data[slug] = load_json(summary_path)

    # Prepare refresher
    refresher = PageRefresher(root, latest, markets_data, today, not args.no_fetch)

    # Track changes
    changes = []

    # Refresh each page
    print("\nRefreshing pages...")
    changes.extend(refresher.refresh_index())
    changes.extend(refresher.refresh_record_index())
    changes.extend(refresher.refresh_buy())
    changes.extend(refresher.refresh_agency())
    changes.extend(refresher.refresh_check())
    changes.extend(refresher.refresh_record_pages())

    # Print change table
    print("\nChanges made:")
    print(f"{'Marker':<30} {'Page':<25} {'Old (60 chars)':<60} {'New (60 chars)':<60}")
    print("-" * 175)
    for change in changes:
        old_short = (change['old'][:57] + '...') if len(change['old']) > 60 else change['old']
        new_short = (change['new'][:57] + '...') if len(change['new']) > 60 else change['new']
        print(f"{change['marker']:<30} {change['page']:<25} {old_short:<60} {new_short:<60}")

    print(f"\nTotal changes: {len(changes)}")
    return 0


def load_json(path):
    """Load JSON file"""
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def compute_sha256(file_path):
    """Compute SHA-256 hash of a file"""
    sha = hashlib.sha256()
    with open(file_path, 'rb') as f:
        while chunk := f.read(8192):
            sha.update(chunk)
    return sha.hexdigest()


def sanitize_text(text):
    """Sanitize text to ASCII-only, replacing curly quotes and other common chars"""
    # Replace curly quotes with straight quotes
    text = text.replace(''', "'")  # Left single quote
    text = text.replace(''', "'")  # Right single quote
    text = text.replace('"', '"')  # Left double quote
    text = text.replace('"', '"')  # Right double quote
    # Replace em and en dashes
    text = text.replace('–', '-')  # En dash
    text = text.replace('—', '--')  # Em dash
    # Remove any remaining non-ASCII
    text = ''.join(c if ord(c) < 128 else '?' for c in text)
    return text


def check_ascii(text):
    """Check if text contains only ASCII and no em/en dashes"""
    for char in text:
        code = ord(char)
        # Check for non-ASCII
        if code > 127:
            return False, f"Non-ASCII character found: {char} (U+{code:04X})"
        # Check for em dash (U+2014) and en dash (U+2013) - should not reach here if > 127
    # Also check for UTF-8 encoded em/en dashes in the string
    if '–' in text or '—' in text:
        return False, "Em or en dash found"
    return True, None


class PageRefresher:
    def __init__(self, root, latest, markets_data, today, fetch_citation):
        self.root = root
        self.latest = latest
        self.markets_data = markets_data
        self.today = today
        self.fetch_citation = fetch_citation
        self.changes = []
        self.citation_data = None

        if fetch_citation:
            self.citation_data = self.fetch_citation_index()

    def fetch_citation_index(self):
        """Fetch citation index from namebeam.ai"""
        try:
            req = Request('https://namebeam.ai/data/citation_index.json',
                          headers={'User-Agent': 'namebeam-markets-daily-refresh/1.0 (tools/refresh_pages.py)'})
            with urlopen(req, timeout=20) as response:
                data = json.loads(response.read())
                print("Citation index fetched successfully")
                return data
        except (URLError, Exception) as e:
            print(f"Citation index fetch failed (continuing): {e}")
            return None

    def replace_marker(self, page_name, html, marker, new_content):
        """Replace content between HTML comment markers"""
        pattern = f'<!--nb:{marker}-->(.*?)<!--/nb:{marker}-->'
        match = re.search(pattern, html, re.DOTALL)

        if not match:
            print(f"WARNING: Marker {marker} not found in {page_name}")
            return html

        old_content = match.group(1)

        # ASCII guard
        is_ascii, error = check_ascii(new_content)
        if not is_ascii:
            print(f"ERROR: ASCII guard failed for marker {marker} in {page_name}: {error}")
            sys.exit(3)

        # Record change
        self.changes.append({
            'marker': marker,
            'page': page_name,
            'old': old_content.strip(),
            'new': new_content.strip()
        })

        # Replace
        new_html = re.sub(pattern, f'<!--nb:{marker}-->{new_content}<!--/nb:{marker}-->', html, flags=re.DOTALL)
        return new_html

    def add_marker_if_missing(self, html, marker, search_text, replacement_with_marker):
        """Add marker around existing text if marker not present"""
        pattern = f'<!--nb:{marker}-->'
        if pattern in html:
            return html  # Marker already exists

        # Find and wrap the text
        if search_text not in html:
            print(f"WARNING: Could not find text to add marker {marker}")
            return html

        html = html.replace(search_text, replacement_with_marker)
        return html

    def read_page(self, page_path):
        """Read HTML page"""
        with open(self.root / page_path, 'r', encoding='utf-8') as f:
            return f.read()

    def write_page(self, page_path, html):
        """Write HTML page"""
        with open(self.root / page_path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(html)

    def get_csv_rows_for_date(self, slug, date):
        """Get CSV rows for a specific date"""
        csv_path = self.root / 'record' / slug / 'all.csv'
        rows = []
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['date'] == date:
                    rows.append(row)
        return rows

    def format_engine_table_rows(self, rows):
        """Format engine table rows for pv-cards"""
        # Group by engine
        engines_order = ['openai', 'anthropic', 'perplexity', 'gemini', 'google_serp']
        engine_labels = {
            'openai': 'OpenAI',
            'anthropic': 'Anthropic',
            'perplexity': 'Perplexity',
            'gemini': 'Gemini',
            'google_serp': 'Google search'
        }

        html_rows = []
        for engine_key in engines_order:
            row_data = next((r for r in rows if r['engine'] == engine_key), None)
            if not row_data:
                continue

            label = engine_labels[engine_key]
            status = sanitize_text(row_data['status'])
            names_count = int(row_data['names_count']) if row_data['names_count'] else 0
            businesses = sanitize_text(row_data['businesses_named'])

            # Status chip
            if status == 'OK':
                chip = '<span class="pv-chip OK">OK</span>'
            else:
                chip = f'<span class="pv-chip {status}">{status}</span>'

            # Names
            if names_count == 0:
                names_text = '<i>0 names</i>'
            else:
                names_text = businesses

            html_rows.append(f'<tr><td>{label}</td><td>{chip}</td><td>{names_text}</td></tr>')

        return ''.join(html_rows)

    def refresh_index(self):
        """Refresh index.html"""
        page_name = 'index.html'
        html = self.read_page(page_name)
        changes_before = len(self.changes)

        latest_run_day = self.latest['latest_run_day']

        # Offer as-of
        html = self.replace_marker(page_name, html, 'offer-asof',
                                   f'as of {latest_run_day}')

        # Label window for Miami
        miami = self.latest['markets']['miami-roofing']
        label_window = f"MIAMI FL &middot; {miami['window_first'].upper()} TO {miami['window_last'].upper()}"
        html = self.replace_marker(page_name, html, 'label-window', sanitize_text(label_window))

        # rnote
        first = miami['window_first']
        last = miami['window_last']
        html = self.replace_marker(page_name, html, 'rnote',
                                   f"Window {first} to {last}, counted from the daily record on {self.today}. A count, not a ranking. Every name, engine and answer hash is on the Miami page.")

        # Three pv-cards
        cards = [
            ('miami-roofing', 'miami-card'),
            ('kansas-city-health-insurance', 'kc-card'),
            ('atlanta-hvac', 'atlanta-card')
        ]

        for slug, marker_prefix in cards:
            market_info = self.latest['markets'][slug]
            window_last = market_info['window_last']

            # Get CSV rows for that date
            rows = self.get_csv_rows_for_date(slug, window_last)

            # Run day
            html = self.replace_marker(page_name, html, f'{marker_prefix}-runday',
                                       f'Run day {window_last}')

            # Engine table
            table_html = self.format_engine_table_rows(rows)
            html = self.replace_marker(page_name, html, f'{marker_prefix}-table',
                                       table_html)

            # Link
            html = self.replace_marker(page_name, html, f'{marker_prefix}-link',
                                       f'/record/{slug}/{window_last}/')

        # Citation tiles
        # The live file (citation_index_daily.yml in carter-brain, rebuilt every day) carries generated_utc at the top
        # level and the two counts under gate: businesses_total and businesses_corroborated.
        gate = (self.citation_data or {}).get('gate') or {}
        gen_ts = (self.citation_data or {}).get('generated_utc') or (self.citation_data or {}).get('generated')
        if gen_ts and 'businesses_total' in gate and 'businesses_corroborated' in gate:
            gen_date = gen_ts.split('T')[0]
            html = self.replace_marker(page_name, html, 'cite-n-1', f"{int(gate['businesses_total']):,}")
            html = self.replace_marker(page_name, html, 'cite-n-2', f"{int(gate['businesses_corroborated']):,}")
            html = self.replace_marker(page_name, html, 'cite-asof-1',
                                       f'as of {gen_date}')
            html = self.replace_marker(page_name, html, 'cite-asof-2',
                                       f'as of {gen_date}')
            html = self.replace_marker(page_name, html, 'cite-generated',
                                       f'generated {gen_ts}')
        else:
            print("Citation data not available, skipping citation tile updates")

        self.write_page(page_name, html)
        return self.changes[changes_before:]

    def refresh_record_index(self):
        """Refresh record/index.html"""
        page_name = 'record/index.html'
        html = self.read_page(page_name)
        changes_before = len(self.changes)

        # Hub window
        first = self.latest['window_first']
        last = self.latest['window_end']
        html = self.replace_marker(page_name, html, 'hub-window',
                                   f'window {first} to {last}')

        # Hub rows - build table rows for all markets
        rows_html = []
        # Need to maintain order from existing table - read it from latest.json markets order
        for slug in self.latest['markets'].keys():
            if slug not in self.markets_data:
                continue

            summary = self.markets_data[slug]
            market = summary['market']
            niche = summary['niche']
            window_first = summary['window_first']
            window_last = summary['window_last']
            rows_total = summary['rows_total']

            # Calculate ok_rows from by_engine
            ok_rows = sum(engine_data['ok'] for engine_data in summary['by_engine'].values())
            errors = rows_total - ok_rows

            link_text = f"{market}, {niche}"
            link_href = f"/record/{slug}/"

            rows_html.append(
                f'<tr>'
                f'<td><a href="{link_href}">{link_text}</a></td>'
                f'<td>{window_first} to {window_last}</td>'
                f'<td class="n">{rows_total}</td>'
                f'<td class="n">{ok_rows}</td>'
                f'<td class="n">{errors}</td>'
                f'<td>{window_last}</td>'
                f'</tr>'
            )

        html = self.replace_marker(page_name, html, 'hub-rows', '\n'.join(rows_html))

        self.write_page(page_name, html)
        return self.changes[changes_before:]

    def refresh_buy(self):
        """Refresh buy/index.html"""
        page_name = 'buy/index.html'
        html = self.read_page(page_name)
        changes_before = len(self.changes)

        # Both as-of markers
        html = self.replace_marker(page_name, html, 'buy-asof-meta', f'as of {self.today}')
        html = self.replace_marker(page_name, html, 'buy-asof', f'Prices as of {self.today}')

        self.write_page(page_name, html)
        return self.changes[changes_before:]

    def refresh_agency(self):
        """Refresh agency/index.html"""
        page_name = 'agency/index.html'
        html = self.read_page(page_name)
        changes_before = len(self.changes)

        latest_run_day = self.latest['latest_run_day']

        # Update og:title (plain edit, not marker-based)
        og_title_old = 'AI Visibility Audit Pack, White-Label for Agencies, NameBeam'
        og_title_new = 'Agency Evidence Pack, white-label market files | Namebeam'
        html = html.replace(
            f'<meta property="og:title" content="{og_title_old}">',
            f'<meta property="og:title" content="{og_title_new}">'
        )

        # Five daily-through markers
        for i in range(1, 6):
            html = self.replace_marker(page_name, html, f'daily-through-{i}',
                                       f', with daily files through {latest_run_day}')

        self.write_page(page_name, html)
        return self.changes[changes_before:]

    def refresh_check(self):
        """Refresh check/index.html"""
        page_name = 'check/index.html'
        html = self.read_page(page_name)
        changes_before = len(self.changes)

        # Update meta description
        old_desc = 'See which AI engines name your business. Free, no card, no sales sequence.'
        new_desc = 'A free dated sample from the record for one market. A trust step, no result promised.'
        html = html.replace(
            f'<meta name="description" content="{old_desc}">',
            f'<meta name="description" content="{new_desc}">'
        )

        # Update H1
        old_h1 = 'Free check: see your own record'
        new_h1 = 'Free sample: see one market\'s record'
        if old_h1 in html:
            html = html.replace(f'<h1>{old_h1}</h1>', f'<h1>{new_h1}</h1>')
            print(f"check/index.html H1: Changed from '{old_h1}' to '{new_h1}'")
        else:
            # Check if already updated
            if new_h1 in html:
                print(f"check/index.html H1: Already set to '{new_h1}'")
            else:
                print(f"check/index.html H1: Could not find '{old_h1}', searching for actual H1...")
                h1_match = re.search(r'<h1>(.*?)</h1>', html)
                if h1_match:
                    actual_h1 = h1_match.group(1)
                    print(f"check/index.html H1: Found '{actual_h1}' - not changing")

        self.write_page(page_name, html)
        return self.changes[changes_before:]

    def refresh_record_pages(self):
        """Refresh all record/<slug>/index.html pages"""
        changes_before = len(self.changes)

        for slug, market_data in self.latest['markets'].items():
            page_path = self.root / 'record' / slug / 'index.html'
            if not page_path.exists():
                continue

            page_name = f'record/{slug}/index.html'
            html = self.read_page(page_path.relative_to(self.root).as_posix())

            # Get data for this market
            summary = self.markets_data.get(slug, {})
            window_first = market_data.get('window_first')
            window_last = market_data.get('window_last')
            question = market_data.get('question', '')
            market_name = market_data.get('market', '')
            niche = market_data.get('niche', '')
            shape = market_data.get('shape', 'rows_only')
            collection_active = market_data.get('collection_active', False)
            by_engine = market_data.get('by_engine', {})
            latest_day = market_data.get('latest_day', {})
            run_days = market_data.get('run_days', 0)
            ok_rows = market_data.get('ok_rows', 0)
            rows_total = market_data.get('rows_total', 0)

            # a. Meta description
            meta_desc = f'Asked word for word: {question} The names each AI engine returned, counted by day, {window_first} to {window_last}, free CSV. A count, not a ranking.'
            if not collection_active and window_last:
                meta_desc += f' Collection ended {window_last}.'

            # Add marker if not present
            if '<!--nb:rec-meta-->' not in html:
                html = re.sub(
                    r'(<meta name="description" content="[^"]*">)',
                    r'<!--nb:rec-meta-->\1<!--/nb:rec-meta-->',
                    html
                )

            html = self.replace_marker(page_name, html, 'rec-meta',
                                      f'<meta name="description" content="{sanitize_text(meta_desc)}">')

            # b. Tiles (pv-tiles)
            engine_order = ['perplexity', 'openai', 'gemini', 'anthropic']
            engine_labels = {
                'perplexity': 'Perplexity',
                'openai': 'ChatGPT (OpenAI)',
                'gemini': 'Gemini',
                'anthropic': 'Claude (Anthropic)'
            }

            tiles_html = '<div class="pv-tiles">'
            for eng in engine_order:
                if eng in by_engine:
                    days_with_ok = by_engine[eng].get('days_with_ok', 0)
                    label = engine_labels[eng]
                    tiles_html += f'<div class="pv-tile"><div class="v">{days_with_ok}</div><div class="l">{label} answer days</div><div class="d">OK answers, {window_first} to {window_last}</div></div>'

            tiles_html += '</div>'

            # Add marker if not present
            if '<!--nb:rec-tiles-->' not in html:
                html = re.sub(
                    r'(<div class="pv-tiles">.*?</div>)',
                    r'<!--nb:rec-tiles-->\1<!--/nb:rec-tiles-->',
                    html,
                    flags=re.DOTALL
                )

            html = self.replace_marker(page_name, html, 'rec-tiles', tiles_html)

            # c. Agency block (NEW)
            agency_html = ''

            # P1: Latest day receipts
            latest_date = latest_day.get('date')
            engines_data = latest_day.get('engines', {})

            if latest_date:
                p1_start = f'On {latest_date}, asked this question word for word: '
                p1_parts = []

                for eng in ['openai', 'gemini', 'anthropic', 'perplexity']:
                    eng_label = {'openai': 'ChatGPT', 'gemini': 'Gemini', 'anthropic': 'Claude', 'perplexity': 'Perplexity'}[eng]

                    if eng in engines_data and engines_data[eng]['status'] == 'OK':
                        names_count = engines_data[eng].get('names_count', 0)
                        if shape == 'day_pages':
                            if p1_parts:  # Not the first engine
                                p1_parts.append(f'{eng_label} {names_count}')
                            else:  # First engine, full format
                                p1_parts.append(f'{eng_label} answered with {names_count} names')
                        else:  # rows_only
                            p1_parts.append(f'{eng_label} answered, {names_count} tracked names')
                    else:
                        p1_parts.append(f'{eng_label}: no OK answer that day')

                if shape == 'day_pages':
                    p1_text = p1_start + ', '.join(p1_parts) + '. The table below counts, by day, which tracked businesses each engine named.'
                else:  # rows_only
                    p1_text = p1_start + '; '.join(p1_parts) + '. The table below counts, by day, which tracked businesses each engine named.'

                p1 = '<p class="pv-note">' + sanitize_text(p1_text) + '</p>'
            else:
                p1 = '<p class="pv-note">No latest day data available.</p>'

            # P2: Window summary
            if collection_active:
                p2 = f'<p>Dated window {window_first} to {window_last}, {run_days} run days, {ok_rows} OK answers of {rows_total} rows. <a class="btn" href="#nb-sample">Get the free sample for this market</a></p>'
            else:
                p2 = f'<p>Collection for this market ended {window_last}; the record stands as published, {run_days} run days, {ok_rows} OK answers of {rows_total} rows.</p>'

            agency_html = p1 + p2

            # Add marker if not present (insert after pv-q div, before nb-offer)
            if '<!--nb:rec-agency-->' not in html:
                html = re.sub(
                    r'(<div class="pv-q">.*?</div>)\s*(<p class="nb-offer">)',
                    r'\1\n<!--nb:rec-agency--><!--/nb:rec-agency-->\n\2',
                    html,
                    flags=re.DOTALL
                )

            html = self.replace_marker(page_name, html, 'rec-agency', agency_html)

            # d. Downloads
            if shape == 'day_pages':
                csv_file = 'all.csv'
            else:
                csv_file = 'rows.csv'

            csv_path = self.root / 'record' / slug / csv_file
            csv_sha = compute_sha256(csv_path)

            # Count rows in CSV
            with open(csv_path, 'r', encoding='utf-8') as f:
                csv_rows = sum(1 for _ in f) - 1  # subtract header

            downloads_html = f'<a href="/record/{slug}/{csv_file}">{csv_file}</a>, one row per engine per day, {window_first} to {window_last}: status, answer SHA-256, characters, whether the answer text is public, and the tracked businesses named in the text. {csv_rows} rows. SHA-256 {csv_sha}'

            # Add marker if not present
            if '<!--nb:rec-downloads-->' not in html:
                html = re.sub(
                    r'(<h2>Downloads \(ungated\)</h2><ul><li>)([^<]*)(</li></ul>)',
                    r'\1<!--nb:rec-downloads-->\2<!--/nb:rec-downloads-->\3',
                    html,
                    flags=re.DOTALL
                )

            html = self.replace_marker(page_name, html, 'rec-downloads', downloads_html)

            # e. JSON-LD
            dataset_json = {
                "@context": "https://schema.org",
                "@type": "Dataset",
                "name": f"{market_name} {niche}: dated AI answer record",
                "description": sanitize_text(meta_desc),
                "url": f"https://markets.namebeam.ai/record/{slug}/",
                "sameAs": "https://github.com/mrcrtr1979-droid/namebeam-visibility-index",
                "temporalCoverage": f"{window_first}/{window_last}",
                "dateModified": self.today,
                "license": "https://creativecommons.org/licenses/by/4.0/",
                "isAccessibleForFree": True,
                "creator": {
                    "@type": "Organization",
                    "name": "Carter Enterprise LLC",
                    "url": "https://namebeam.ai/"
                },
                "publisher": {
                    "@type": "Organization",
                    "name": "Namebeam",
                    "url": "https://namebeam.ai/"
                },
                "keywords": [market_name, niche, "AI visibility", "business names", "AI answer engines"],
                "variableMeasured": "business names returned by AI answer engines, counted by day",
                "distribution": [
                    {
                        "@type": "DataDownload",
                        "encodingFormat": "text/csv",
                        "contentUrl": f"https://markets.namebeam.ai/record/{slug}/{csv_file}"
                    }
                ]
            }

            jsonld_str = json.dumps(dataset_json, ensure_ascii=True, indent=None)
            # Escape </ for script tag
            jsonld_str = jsonld_str.replace('</', '<\\/')

            jsonld_html = f'<script type="application/ld+json">{jsonld_str}</script>'

            # Add marker if not present (in head, after other meta tags)
            if '<!--nb:rec-jsonld-->' not in html:
                html = re.sub(
                    r'(</head>)',
                    r'<!--nb:rec-jsonld--><!--/nb:rec-jsonld-->\n\1',
                    html
                )

            html = self.replace_marker(page_name, html, 'rec-jsonld', jsonld_html)

            # Write back
            self.write_page(page_path.relative_to(self.root).as_posix(), html)

        return self.changes[changes_before:]


def run_selftest():
    """Run self-test with fixtures"""
    print("Running self-test...")

    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        # Create fixture structure
        (root / 'data').mkdir()
        (root / 'record' / 'test-market').mkdir(parents=True)

        # Fixture latest.json
        latest = {
            "generated_utc": "2026-11-10T05:24:14Z",
            "latest_run_day": "2026-11-09",
            "window_first": "2026-08-05",
            "window_end": "2026-11-09",
            "markets": {
                "test-market": {
                    "window_first": "2026-08-09",
                    "window_last": "2026-11-09",
                    "run_days": 10,
                    "rows_total": 50,
                    "ok_rows": 40
                }
            },
            "totals": {"rows": 50, "ok_rows": 40, "markets": 1, "engines": 5}
        }
        (root / 'data' / 'latest.json').write_text(json.dumps(latest))

        # Fixture summary.json
        summary = {
            "slug": "test-market",
            "market": "Test City",
            "niche": "test niche",
            "window_first": "2026-08-09",
            "window_last": "2026-11-09",
            "rows_total": 50,
            "by_engine": {
                "openai": {"rows": 10, "ok": 8},
                "anthropic": {"rows": 10, "ok": 8}
            }
        }
        (root / 'record' / 'test-market' / 'summary.json').write_text(json.dumps(summary))

        # Fixture all.csv
        csv_content = """date,question_slug,market,niche,engine,run,status,names_count,businesses_named,check_id,raw_file,raw_file_sha256
2026-11-09,test-market,Test City,test niche,openai,1,OK,0,,check1,file1.json,abc123
2026-11-09,test-market,Test City,test niche,anthropic,1,OK,2,Business A; Business B,check2,file2.json,def456
"""
        (root / 'record' / 'test-market' / 'all.csv').write_text(csv_content)

        # Fixture HTML page with markers
        test_html = """<!DOCTYPE html>
<html><head><title>Test</title></head><body>
<p>Offer: <!--nb:offer-asof-->as of 2026-01-01<!--/nb:offer-asof--></p>
<p>Window: <!--nb:hub-window-->window 2026-01-01 to 2026-01-31<!--/nb:hub-window--></p>
</body></html>"""
        (root / 'index.html').write_text(test_html)

        # Test 1: Marker replacement
        refresher = PageRefresher(root, latest, {"test-market": summary}, "2026-11-10", False)
        html = test_html
        html = refresher.replace_marker('test.html', html, 'offer-asof', 'as of 2026-11-09')
        assert '<!--nb:offer-asof-->as of 2026-11-09<!--/nb:offer-asof-->' in html
        print("  PASS: Marker replacement")

        # Test 2: Missing marker warning
        html2 = "<p>no markers here</p>"
        html2 = refresher.replace_marker('test.html', html2, 'missing-marker', 'new content')
        # Should print warning but not crash
        print("  PASS: Missing marker handling")

        # Test 3: ASCII guard with em dash
        try:
            is_ascii, error = check_ascii('text with em dash—here')
            assert not is_ascii
            print("  PASS: ASCII guard detects em dash")
        except:
            print("  FAIL: ASCII guard")
            return 1

        # Test 4: ASCII guard with valid text
        is_ascii, error = check_ascii('valid ASCII text 123')
        assert is_ascii
        print("  PASS: ASCII guard allows valid text")

        print("\nSelf-test PASSED")
        return 0


if __name__ == '__main__':
    sys.exit(main())
