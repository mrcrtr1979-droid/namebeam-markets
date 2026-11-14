#!/usr/bin/env python3
"""
refresh_day_pages.py - Generate missing day pages for namebeam-markets

Reads all.csv for each day_pages market, generates missing date/index.html files
from the most recent existing day page as template, updates changes.csv, updates
market index.html day table, and updates sitemap.xml.

ASCII-only enforced. Idempotent. Zero network, zero model calls.
"""

import argparse
import csv
import hashlib
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path


# Markets with day pages (not rows_only)
DAY_PAGES_MARKETS = [
    'atlanta-hvac', 'atlanta-personal-injury', 'branson-short-term-rental',
    'charlotte-tanning-salons', 'chicago-personal-injury', 'columbus-tanning-salons',
    'dallas-personal-injury', 'dallas-roofing', 'denver-roofing', 'houston-hvac',
    'houston-personal-injury', 'kansas-city-health-insurance', 'miami-roofing',
    'nashville-short-term-rental', 'phoenix-hvac', 'pleasanton-dentists',
    'pleasanton-home-care', 'pleasanton-moving-companies', 'pleasanton-oil-change',
    'pleasanton-real-estate-agents', 'pleasanton-tanning-salons', 'pleasanton-tire-shops',
    'santa-cruz-short-term-rental', 'tyler-tanning-salons',
    'us-short-term-rental-booking-platforms', 'us-short-term-rental-business-model',
    'us-short-term-rental-software'
]

# Engine display order
ENGINE_ORDER = ['openai', 'anthropic', 'perplexity', 'gemini', 'google_serp']
ENGINE_DISPLAY_NAMES = {
    'openai': 'OpenAI',
    'anthropic': 'Anthropic',
    'perplexity': 'Perplexity',
    'gemini': 'Gemini',
    'google_serp': 'Google search'
}


def sanitize_ascii(text):
    """Replace non-ASCII characters with ASCII equivalents."""
    # Replace em dash and en dash with hyphen-minus
    text = text.replace('\u2014', '-')  # em dash
    text = text.replace('\u2013', '-')  # en dash
    text = text.replace('\u2018', "'")  # left single quote
    text = text.replace('\u2019', "'")  # right single quote
    text = text.replace('\u201c', '"')  # left double quote
    text = text.replace('\u201d', '"')  # right double quote
    text = text.replace('\u2026', '...')  # ellipsis
    text = text.replace('\u00b7', '-')  # middle dot
    text = text.replace('\u00d7', 'x')  # multiplication sign
    text = text.replace('\u2192', '->')  # right arrow (seen in corpus names 2026-11-10; the daily job died on it 11-11 and 11-12)
    text = text.replace('\u00a0', ' ')  # no-break space
    # Anything else above 127 becomes a numeric character reference: the file stays ASCII and the text stays true.
    text = ''.join(c if ord(c) < 128 else '&#%d;' % ord(c) for c in text)
    return text


def validate_ascii(text, context=''):
    """Check for non-ASCII and problematic dash characters in visible text."""
    # Check for non-ASCII
    try:
        text.encode('ascii')
    except UnicodeEncodeError as e:
        return f"Non-ASCII in {context}: {e}"

    # Check for em dash, en dash (but allow minus-hyphen and HTML entities)
    # We need to be careful not to flag legitimate minus signs in SHA hashes or dates
    problem_chars = []
    for i, char in enumerate(text):
        if char in ('\u2013', '\u2014', '\u00b7'):  # en dash, em dash, middle dot char
            problem_chars.append(f"pos {i}: U+{ord(char):04X} '{char}'")

    if problem_chars:
        return f"Problem dashes/chars in {context}: {', '.join(problem_chars)}"

    return None


def compute_sha256(file_path):
    """Compute SHA-256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for byte_block in iter(lambda: f.read(4096), b''):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def parse_all_csv(csv_path):
    """Parse all.csv and return data grouped by date."""
    rows_by_date = defaultdict(list)
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows_by_date[row['date']].append(row)
    return dict(rows_by_date)


def find_newest_template(market_dir):
    """Find the most recent existing day page to use as template."""
    day_pages = []
    for item in os.listdir(market_dir):
        item_path = market_dir / item
        if item_path.is_dir() and re.match(r'^\d{4}-\d{2}-\d{2}$', item):
            index_html = item_path / 'index.html'
            if index_html.exists():
                day_pages.append((item, index_html))

    if not day_pages:
        return None, None

    # Sort by date descending
    day_pages.sort(reverse=True)
    return day_pages[0][0], day_pages[0][1]


def extract_question(market_index_html):
    """Extract question text from market index.html."""
    with open(market_index_html, 'r', encoding='utf-8') as f:
        content = f.read()

    match = re.search(r'<div class="pv-q">(.*?)</div>', content, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None


def get_market_meta(market_dir):
    """Extract market metadata from index.html and all.csv."""
    index_html = market_dir / 'index.html'
    if not index_html.exists():
        return None, None, None

    with open(index_html, 'r', encoding='utf-8') as f:
        content = f.read()

    # Extract question
    question = extract_question(index_html)

    # Try to get market and niche from all.csv first
    all_csv = market_dir / 'all.csv'
    market = None
    niche = None

    if all_csv.exists():
        with open(all_csv, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            first_row = next(reader, None)
            if first_row:
                market = first_row.get('market')
                niche = first_row.get('niche')

    # Fallback: extract from title
    if not market or not niche:
        title_match = re.search(r'<title>(.*?),', content)
        if title_match:
            market = title_match.group(1).strip()

        title_full_match = re.search(r'<title>.*?,\s*(.*?),', content)
        if title_full_match:
            niche = title_full_match.group(1).strip()

    return market, niche, question


def build_engine_table_rows(day_rows):
    """Build engine table rows for a day page."""
    rows_html = []
    for engine in ENGINE_ORDER:
        engine_row = None
        for row in day_rows:
            if row['engine'] == engine:
                engine_row = row
                break

        if not engine_row:
            continue

        status = engine_row['status']
        names = engine_row['businesses_named']
        sha256 = engine_row['raw_file_sha256']
        engine_display = ENGINE_DISPLAY_NAMES[engine]

        # Build names cell
        if status == 'OK':
            if names:
                names_display = names.replace('; ', '; ')
            else:
                names_display = '<i>0 names extracted</i>'
        else:
            names_display = ''

        # Build status chip
        status_chip = f'<span class="pv-chip {status}">{status}</span>'

        row_html = f'<tr><td>{engine_display}</td><td>{status_chip}</td><td>{names_display}</td><td style="word-break:break-all;font-size:11.5px">{sha256}</td></tr>'
        rows_html.append(row_html)

    return ''.join(rows_html)


def compute_tiles(day_rows):
    """Compute tile values for a day page."""
    ok_count = sum(1 for r in day_rows if r['status'] == 'OK')
    total_count = len(day_rows)
    names_count = sum(int(r['names_count']) for r in day_rows if r['names_count'])

    return ok_count, total_count, names_count


def get_engines_with_ok_status(day_rows):
    """Get list of engines with OK status for a given day."""
    engines = []
    for engine in ENGINE_ORDER:
        for row in day_rows:
            if row['engine'] == engine and row['status'] == 'OK':
                engines.append(engine)
                break
    return engines


def compute_changes(date, prev_date, current_day_rows, prev_day_rows):
    """Compute entered and dropped names between two days."""
    # Get engines that were OK on both days
    current_engines = set(get_engines_with_ok_status(current_day_rows))
    prev_engines = set(get_engines_with_ok_status(prev_day_rows))
    compared_engines = sorted(current_engines & prev_engines, key=lambda e: ENGINE_ORDER.index(e))

    if not compared_engines:
        return [], [], []

    # Get names from businesses_named, split by "; "
    current_names = {}
    prev_names = {}

    for row in current_day_rows:
        if row['engine'] in compared_engines and row['businesses_named']:
            for name in row['businesses_named'].split('; '):
                if name not in current_names:
                    current_names[name] = []
                current_names[name].append(row['engine'])

    for row in prev_day_rows:
        if row['engine'] in compared_engines and row['businesses_named']:
            for name in row['businesses_named'].split('; '):
                if name not in prev_names:
                    prev_names[name] = []
                prev_names[name].append(row['engine'])

    entered = {name: engines for name, engines in current_names.items() if name not in prev_names}
    dropped = {name: engines for name, engines in prev_names.items() if name not in current_names}

    return compared_engines, entered, dropped


def format_engines_compared(engines):
    """Format engines_compared for changes section."""
    return ', '.join(ENGINE_DISPLAY_NAMES[e] for e in engines)


def format_name_list(names_dict):
    """Format entered/dropped names list."""
    if not names_dict:
        return 'none'
    return '; '.join(sorted(names_dict.keys()))


def generate_day_page(template_path, date, market, niche, question, day_rows,
                     prev_date, prev_day_rows, day_csv_path, first_date, today, offer_day=None):
    """Generate a day page HTML from template. offer_day (F1, CPEO-1113) is the record's latest_run_day and is what
    the offer line prints after "as of"; None keeps the old behavior (today)."""
    with open(template_path, 'r', encoding='utf-8') as f:
        html = f.read()

    slug = day_rows[0]['question_slug']

    # Replace title
    html = re.sub(
        r'<title>.*?</title>',
        f'<title>{market}, {niche}, {date} | Namebeam record</title>',
        html
    )

    # Replace meta description
    html = re.sub(
        r'<meta name="description" content=".*?">',
        f'<meta name="description" content="What each AI engine named on {date} for: {question}">',
        html
    )

    # Replace breadcrumbs date
    html = re.sub(
        r'(<div class="pv-crumbs">.*?</a> / )<span>.*?</span>',
        f'\\1<span>{date}</span>',
        html,
        flags=re.DOTALL
    )

    # Replace H1
    html = re.sub(
        r'<h1>.*?</h1>',
        f'<h1>{market}, {niche}: {date}</h1>',
        html
    )

    # Replace lb19:offer date
    html = re.sub(
        r'(<!-- lb19:offer -->.*?as of )\d{4}-\d{2}-\d{2}',
        f'\\g<1>{offer_day or today}',
        html,
        flags=re.DOTALL
    )
    html = re.sub(
        r'(<!-- lb19:offer -->.*?on )\d{4}-\d{2}-\d{2}',
        f'\\g<1>{date}',
        html,
        flags=re.DOTALL
    )
    html = re.sub(
        r'(<!-- lb19:offer -->.*?utm_content=)[^#]+#',
        f'\\g<1>{slug}/{date}#',
        html,
        flags=re.DOTALL
    )

    # Replace tiles
    ok_count, total_count, names_count = compute_tiles(day_rows)
    html = re.sub(
        r'<div class="pv-tile"><div class="v">\d+ of \d+</div><div class="l">sources answered OK</div><div class="d">run day \d{4}-\d{2}-\d{2}</div></div>',
        f'<div class="pv-tile"><div class="v">{ok_count} of {total_count}</div><div class="l">sources answered OK</div><div class="d">run day {date}</div></div>',
        html
    )
    html = re.sub(
        r'<div class="pv-tile"><div class="v">\d+</div><div class="l">name entries logged</div>',
        f'<div class="pv-tile"><div class="v">{names_count}</div><div class="l">name entries logged</div>',
        html
    )

    # Replace engine table
    engine_table_rows = build_engine_table_rows(day_rows)
    html = re.sub(
        r'(<table class="pv-t"><tr><th>Engine</th>.*?</tr>)(.*?)(</table>)',
        f'\\g<1>{engine_table_rows}\\g<3>',
        html,
        flags=re.DOTALL
    )

    # Replace Changes section
    if prev_day_rows:
        compared_engines, entered, dropped = compute_changes(date, prev_date, day_rows, prev_day_rows)
        engines_compared_str = format_engines_compared(compared_engines)
        entered_str = format_name_list(entered)
        dropped_str = format_name_list(dropped)

        changes_section = f'<h2>Changes since {prev_date}</h2><p>Compared engines: {engines_compared_str}.</p><p><b>Entered:</b> {entered_str}</p><p><b>Dropped:</b> {dropped_str}</p>'
    else:
        changes_section = f'<h2>Changes since {prev_date}</h2><p>First day in window.</p>'

    html = re.sub(
        r'<h2>Changes since \d{4}-\d{2}-\d{2}</h2>.*?(?=<p class="pv-note">Names are shown)',
        changes_section,
        html,
        flags=re.DOTALL
    )

    # Replace CSV link and SHA
    csv_sha = compute_sha256(day_csv_path)
    html = re.sub(
        r'<p>This day as a file: <a href=".*?">\d{4}-\d{2}-\d{2}\.csv</a> \(SHA-256 [0-9a-f]+\)\.',
        f'<p>This day as a file: <a href="/record/{slug}/{date}.csv">{date}.csv</a> (SHA-256 {csv_sha}).',
        html
    )

    # Replace prev/next links
    prev_link = f'<a href="/record/{slug}/{prev_date}/">&larr; {prev_date}</a>' if prev_date else ''
    html = re.sub(
        r'<div class="pv-pn"><span>.*?</span><span><a href="/record/[^/]+/">All run days</a></span><span>.*?</span></div>',
        f'<div class="pv-pn"><span>{prev_link}</span><span><a href="/record/{slug}/">All run days</a></span><span></span></div>',
        html,
        flags=re.DOTALL
    )

    # Replace footer dates
    html = re.sub(
        r'Data window \d{4}-\d{2}-\d{2} to \d{4}-\d{2}-\d{2}\.',
        f'Data window {first_date} to {date}.',
        html
    )
    html = re.sub(
        r'Source files generated \d{4}-\d{2}-\d{2}\.',
        f'Source files generated {date}.',
        html
    )
    html = re.sub(
        r'Page built \d{4}-\d{2}-\d{2}\.',
        f'Page built {today}.',
        html
    )

    return html


def update_market_index(index_path, new_dates_data, first_date, latest_date, today):
    """Update market index.html with new day table rows."""
    with open(index_path, 'r', encoding='utf-8') as f:
        html = f.read()

    slug = index_path.parent.name

    # Build new rows
    new_rows_html = []
    for date in sorted(new_dates_data.keys(), reverse=True):
        day_rows = new_dates_data[date]
        cells = []
        for engine in ENGINE_ORDER:
            engine_row = None
            for row in day_rows:
                if row['engine'] == engine:
                    engine_row = row
                    break

            if engine_row:
                status = engine_row['status']
                names_count = int(engine_row['names_count']) if engine_row['names_count'] else 0
                if status == 'OK':
                    cell = f'<span class="pv-chip OK">OK</span> <span class="pv-note">{names_count} names</span>'
                else:
                    cell = f'<span class="pv-chip {status}">{status}</span>'
            else:
                cell = ''
            cells.append(cell)

        row_html = f'<tr><td><a href="/record/{slug}/{date}/">{date}</a></td>'
        for cell in cells:
            row_html += f'<td>{cell}</td>'
        row_html += '</tr>'
        new_rows_html.append(row_html)

    # Insert after the header row of the day table
    table_pattern = r'(<h2>Every run day</h2>.*?<table class="pv-t"><tr><th>Date</th>.*?</tr>)'
    html = re.sub(
        table_pattern,
        '\\g<0>' + ''.join(new_rows_html),
        html,
        flags=re.DOTALL
    )

    # Update window line
    html = re.sub(
        r'window \d{4}-\d{2}-\d{2} to \d{4}-\d{2}-\d{2}',
        f'window {first_date} to {latest_date}',
        html
    )

    # Update built date in footer
    html = re.sub(
        r'(Data window \d{4}-\d{2}-\d{2} to \d{4}-\d{2}-\d{2}\. Source files generated \d{4}-\d{2}-\d{2}\. )Page built \d{4}-\d{2}-\d{2}\.',
        f'\\g<1>Page built {today}.',
        html
    )

    return html


def update_sitemap(sitemap_path, new_entries, today, hub_lastmods=None):
    """Add new day page entries to sitemap.xml with lastmod, and update hub lastmods.

    Args:
        sitemap_path: Path to sitemap.xml
        new_entries: Set of URLs to add (day pages)
        today: YYYY-MM-DD string for lastmod on new entries
        hub_lastmods: Dict of {hub_url: lastmod_date} to update existing hub entries
    """
    with open(sitemap_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Parse existing entries (full url blocks)
    url_block_pattern = r'<url>\s*<loc>(.*?)</loc>(?:\s*<lastmod>(.*?)</lastmod>)?\s*</url>'
    matches = list(re.finditer(url_block_pattern, content, re.DOTALL))

    existing_urls = {m.group(1): (m.group(2) or None) for m in matches}

    # Build new entries for day pages (not already in sitemap)
    new_entries_xml = []
    for url in sorted(new_entries):
        if url not in existing_urls:
            entry = f'  <url>\n    <loc>{url}</loc>\n    <lastmod>{today}</lastmod>\n  </url>'
            new_entries_xml.append(entry)

    # Update hub lastmods if provided
    if hub_lastmods:
        for url, lastmod in hub_lastmods.items():
            if url in existing_urls:
                # Find and replace the url block
                old_block_pattern = r'<url>\s*<loc>' + re.escape(url) + r'</loc>(?:\s*<lastmod>.*?</lastmod>)?\s*</url>'
                new_block = f'<url>\n    <loc>{url}</loc>\n    <lastmod>{lastmod}</lastmod>\n  </url>'
                content = re.sub(old_block_pattern, new_block, content, count=1, flags=re.DOTALL)

    # Insert new entries before </urlset>
    if new_entries_xml:
        content = content.replace('</urlset>', '\n'.join(new_entries_xml) + '\n</urlset>')

    return content


def process_market(market_slug, root_dir, today, stats):
    """Process one market: generate missing day pages."""
    # F1 (CPEO-1113): the day pages' offer date is the record's latest_run_day (data/latest.json), not the run day.
    offer_day = None
    latest_json = root_dir / 'data' / 'latest.json'
    if latest_json.exists():
        with open(latest_json, 'r', encoding='utf-8') as lf:
            offer_day = json.load(lf).get('latest_run_day')
    market_dir = root_dir / 'record' / market_slug
    all_csv = market_dir / 'all.csv'
    changes_csv = market_dir / 'changes.csv'
    index_html = market_dir / 'index.html'

    if not all_csv.exists():
        return

    # Parse all.csv
    rows_by_date = parse_all_csv(all_csv)

    # Find newest existing template
    template_date, template_path = find_newest_template(market_dir)
    if not template_path:
        print(f"Warning: No existing day page template found for {market_slug}")
        return

    # Get market metadata
    market, niche, question = get_market_meta(market_dir)
    if not market or not niche or not question:
        print(f"Warning: Could not extract market metadata for {market_slug}")
        return

    # Find all dates in all.csv
    all_dates = sorted(rows_by_date.keys())
    first_date = all_dates[0]

    # Find dates missing day pages
    missing_dates = []
    for date in all_dates:
        day_dir = market_dir / date
        index_path = day_dir / 'index.html'
        if not index_path.exists():
            missing_dates.append(date)

    if not missing_dates:
        return

    # Generate day pages
    new_dates_data = {}
    new_changes_rows = []
    new_sitemap_entries = set()

    for date in missing_dates:
        day_rows = rows_by_date[date]
        day_dir = market_dir / date
        day_csv = market_dir / f'{date}.csv'

        if not day_csv.exists():
            print(f"Warning: CSV not found for {market_slug} {date}")
            continue

        # Find previous date
        date_index = all_dates.index(date)
        prev_date = all_dates[date_index - 1] if date_index > 0 else None
        prev_day_rows = rows_by_date[prev_date] if prev_date else None

        # Generate page
        day_html = generate_day_page(
            template_path, date, market, niche, question, day_rows,
            prev_date, prev_day_rows, day_csv, first_date, today, offer_day=offer_day
        )

        # Sanitize to ASCII
        day_html = sanitize_ascii(day_html)

        # Validate ASCII
        err = validate_ascii(day_html, f'{market_slug}/{date}/index.html')
        if err:
            print(f"ERROR: {err}")
            sys.exit(3)

        # Ensure directory exists
        day_dir.mkdir(parents=True, exist_ok=True)

        # Write file
        index_path = day_dir / 'index.html'
        with open(index_path, 'w', encoding='utf-8') as f:
            f.write(day_html)

        stats['days_written'][market_slug] = stats['days_written'].get(market_slug, 0) + 1
        new_dates_data[date] = day_rows

        # Add to sitemap
        sitemap_url = f'https://markets.namebeam.ai/record/{market_slug}/{date}/'
        new_sitemap_entries.add(sitemap_url)

        # Generate changes rows
        if prev_day_rows:
            compared_engines, entered, dropped = compute_changes(date, prev_date, day_rows, prev_day_rows)

            engines_compared_str = ' '.join(compared_engines)
            days_apart = (datetime.strptime(date, '%Y-%m-%d') - datetime.strptime(prev_date, '%Y-%m-%d')).days

            for name, engines in entered.items():
                engines_naming_str = ' '.join(engines)
                new_changes_rows.append({
                    'date': date,
                    'previous_run_day': prev_date,
                    'days_apart': days_apart,
                    'engines_compared': engines_compared_str,
                    'change': 'entered',
                    'name': name,
                    'engines_naming': engines_naming_str
                })

            for name, engines in dropped.items():
                engines_naming_str = ' '.join(engines)
                new_changes_rows.append({
                    'date': date,
                    'previous_run_day': prev_date,
                    'days_apart': days_apart,
                    'engines_compared': engines_compared_str,
                    'change': 'dropped',
                    'name': name,
                    'engines_naming': engines_naming_str
                })

    # Update forward links to chain all pages
    if missing_dates:
        sorted_missing = sorted(missing_dates)

        # Update forward link of the previous newest day page (template)
        if template_date:
            future_missing_dates = [d for d in sorted_missing if d > template_date]
            if future_missing_dates:
                first_new_date = min(future_missing_dates)
                template_index_path = market_dir / template_date / 'index.html'
                with open(template_index_path, 'r', encoding='utf-8') as f:
                    template_html = f.read()

                # Update the next link (third span in pv-pn)
                next_link = f'<a href="/record/{market_slug}/{first_new_date}/">{first_new_date} &rarr;</a>'
                template_html = re.sub(
                    r'(<div class="pv-pn">.*?<span><a href="/record/[^/]+/">All run days</a></span><span>).*?(</span>)',
                    f'\\g<1>{next_link}\\g<2>',
                    template_html,
                    flags=re.DOTALL
                )

                with open(template_index_path, 'w', encoding='utf-8') as f:
                    f.write(template_html)

        # Update forward links between newly generated pages
        for i, date in enumerate(sorted_missing[:-1]):  # All except last
            current_page = market_dir / date / 'index.html'
            next_date = sorted_missing[i + 1]

            if current_page.exists():
                with open(current_page, 'r', encoding='utf-8') as f:
                    page_html = f.read()

                next_link = f'<a href="/record/{market_slug}/{next_date}/">{next_date} &rarr;</a>'
                page_html = re.sub(
                    r'(<div class="pv-pn">.*?<span><a href="/record/[^/]+/">All run days</a></span><span>).*?(</span>)',
                    f'\\g<1>{next_link}\\g<2>',
                    page_html,
                    flags=re.DOTALL
                )

                with open(current_page, 'w', encoding='utf-8') as f:
                    f.write(page_html)

    # Append to changes.csv
    if new_changes_rows:
        with open(changes_csv, 'a', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['date', 'previous_run_day', 'days_apart',
                                                   'engines_compared', 'change', 'name', 'engines_naming'])
            for row in new_changes_rows:
                writer.writerow(row)

        stats['changes_rows'][market_slug] = len(new_changes_rows)

    # Update market index.html
    if new_dates_data and index_html.exists():
        latest_date = max(all_dates)
        updated_index_html = update_market_index(index_html, new_dates_data, first_date, latest_date, today)

        # Sanitize to ASCII
        updated_index_html = sanitize_ascii(updated_index_html)

        err = validate_ascii(updated_index_html, f'{market_slug}/index.html')
        if err:
            print(f"ERROR: {err}")
            sys.exit(3)

        with open(index_html, 'w', encoding='utf-8') as f:
            f.write(updated_index_html)

    # Store sitemap entries
    stats['sitemap_entries'].update(new_sitemap_entries)


def selftest():
    """Run self-test with a fixture."""
    import tempfile
    import shutil

    print("Running selftest...")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        market_dir = tmpdir / 'record' / 'test-market'
        market_dir.mkdir(parents=True)

        # Create all.csv with 3 days
        all_csv = market_dir / 'all.csv'
        with open(all_csv, 'w', encoding='utf-8') as f:
            f.write('date,question_slug,market,niche,engine,run,status,names_count,businesses_named,check_id,raw_file,raw_file_sha256\n')
            f.write('2026-10-01,test-market,Test Market,test niche,openai,1,OK,0,,check1,file1.json,abc123\n')
            f.write('2026-10-01,test-market,Test Market,test niche,perplexity,1,OK,2,Name A; Name B,check2,file2.json,def456\n')
            f.write('2026-10-02,test-market,Test Market,test niche,openai,1,OK,1,Name C,check3,file3.json,ghi789\n')
            f.write('2026-10-02,test-market,Test Market,test niche,perplexity,1,OK,2,Name B; Name D,check4,file4.json,jkl012\n')
            f.write('2026-10-03,test-market,Test Market,test niche,openai,1,OK,0,,check5,file5.json,mno345\n')
            f.write('2026-10-03,test-market,Test Market,test niche,perplexity,1,OK,1,Name D,check6,file6.json,pqr678\n')

        # Create changes.csv
        changes_csv = market_dir / 'changes.csv'
        with open(changes_csv, 'w', encoding='utf-8') as f:
            f.write('date,previous_run_day,days_apart,engines_compared,change,name,engines_naming\n')
            f.write('2026-10-02,2026-10-01,1,openai perplexity,entered,Name C,openai\n')
            f.write('2026-10-02,2026-10-01,1,openai perplexity,entered,Name D,perplexity\n')
            f.write('2026-10-02,2026-10-01,1,openai perplexity,dropped,Name A,perplexity\n')

        # Create CSV files for each day
        for date in ['2026-10-01', '2026-10-02', '2026-10-03']:
            csv_path = market_dir / f'{date}.csv'
            with open(csv_path, 'w', encoding='utf-8') as f:
                f.write('date,question_slug,market,niche,engine,run,status,names_count,businesses_named,check_id,raw_file,raw_file_sha256\n')

        # Create index.html
        index_html = market_dir / 'index.html'
        with open(index_html, 'w', encoding='utf-8') as f:
            f.write('''<!DOCTYPE html>
<html lang="en">
<head>
<title>Test Market, test niche, daily record | Namebeam</title>
</head>
<body>
<div class="pv-q">What is the test question?</div>
<h2>Every run day</h2>
<p class="pv-note">Newest at the top.</p>
<div class="pv-scroll"><table class="pv-t"><tr><th>Date</th><th>OpenAI</th><th>Perplexity</th></tr></table></div>
<p class="pv-note">Data window 2026-10-01 to 2026-10-02. Source files generated 2026-10-02. Page built 2026-10-03.</p>
</body>
</html>''')

        # Create template day page (2026-10-02)
        day1_dir = market_dir / '2026-10-02'
        day1_dir.mkdir()
        day1_html = day1_dir / 'index.html'
        with open(day1_html, 'w', encoding='utf-8') as f:
            f.write('''<!DOCTYPE html>
<html lang="en">
<head>
<title>Test Market, test niche, 2026-10-02 | Namebeam record</title>
<meta name="description" content="What each AI engine named on 2026-10-02 for: What is the test question?">
</head>
<body>
<div class="pv-crumbs"><a href="/">Namebeam</a> / <a href="/record/">The record</a> / <a href="/record/test-market/">Test Market, test niche</a> / <span>2026-10-02</span></div>
<h1>Test Market, test niche: 2026-10-02</h1>
<p class="nb-offer"><!-- lb19:offer --> This page is one day of the Namebeam dated record: the business names each AI answer engine returned on 2026-10-02 for one Test Market test niche question. It is for agencies that want the dated record. It is a count of names on a date, not a ranking and not a promise of any outcome. The Test Market test niche Market Record is $49 a month as of 2026-11-09: <a href="/buy/?utm_source=site&amp;utm_medium=day&amp;utm_content=test-market/2026-10-02#market-record">see the scope and buy</a>.</p>
<div class="pv-q">What is the test question?</div>
<div class="pv-tiles">
<div class="pv-tile"><div class="v">2 of 2</div><div class="l">sources answered OK</div><div class="d">run day 2026-10-02</div></div>
<div class="pv-tile"><div class="v">3</div><div class="l">name entries logged</div><div class="d">all engines, with repeats across engines</div></div>
</div>
<div class="pv-scroll"><p class="pv-note">Counted from the extracted business lists.</p><table class="pv-t"><tr><th>Engine</th><th>Status</th><th>Names as extracted</th><th>Raw answer SHA-256</th></tr><tr><td>OpenAI</td><td><span class="pv-chip OK">OK</span></td><td>Name C</td><td style="word-break:break-all;font-size:11.5px">ghi789</td></tr><tr><td>Perplexity</td><td><span class="pv-chip OK">OK</span></td><td>Name B; Name D</td><td style="word-break:break-all;font-size:11.5px">jkl012</td></tr></table></div>
<h2>Changes since 2026-10-01</h2><p>Compared engines: OpenAI, Perplexity.</p><p><b>Entered:</b> Name C; Name D</p><p><b>Dropped:</b> Name A</p>
<p class="pv-note">Names are shown as extracted from each answer.</p>
<p>This day as a file: <a href="/record/test-market/2026-10-02.csv">2026-10-02.csv</a> (SHA-256 ''' + compute_sha256(market_dir / '2026-10-02.csv') + ''').</p>
<div class="pv-pn"><span><a href="/record/test-market/2026-10-01/">&larr; 2026-10-01</a></span><span><a href="/record/test-market/">All run days</a></span><span></span></div>
<p class="pv-note">Data window 2026-10-01 to 2026-10-02. Source files generated 2026-10-02. Page built 2026-10-03.</p>
</body>
</html>''')

        # Create sitemap.xml
        sitemap_xml = tmpdir / 'sitemap.xml'
        with open(sitemap_xml, 'w', encoding='utf-8') as f:
            f.write('''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://markets.namebeam.ai/record/test-market/</loc>
  </url>
</urlset>
''')

        # Run the script
        stats = {
            'days_written': {},
            'changes_rows': {},
            'sitemap_entries': set()
        }

        # F1 (CPEO-1113): the offer date on a new day page is latest_run_day (2026-11-08 here, distinct from the
        # template's 2026-11-09 and the run day 2026-11-10), not the run day.
        (tmpdir / 'data').mkdir()
        with open(tmpdir / 'data' / 'latest.json', 'w', encoding='utf-8') as f:
            f.write('{"latest_run_day": "2026-11-08"}')

        process_market('test-market', tmpdir, '2026-11-10', stats)

        # Update sitemap
        updated_sitemap = update_sitemap(sitemap_xml, stats['sitemap_entries'], '2026-11-10')
        with open(sitemap_xml, 'w', encoding='utf-8') as f:
            f.write(updated_sitemap)

        # Verify day 3 page exists
        day3_html = market_dir / '2026-10-03' / 'index.html'
        assert day3_html.exists(), "Day 3 page not created"

        # Verify tiles
        with open(day3_html, 'r', encoding='utf-8') as f:
            content = f.read()
            assert '2 of 2' in content, "Tiles: OK count wrong"
            assert 'Market Record is $49 a month as of 2026-11-08:' in content, "Offer date is not latest_run_day"
            assert '1</div><div class="l">name entries logged</div>' in content, "Tiles: names count wrong"

        # Verify changes rows
        with open(changes_csv, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            assert len(lines) == 6, f"Expected 6 lines in changes.csv, got {len(lines)}"  # header + 3 old + 2 new (dropped Name B, Name C)

        # Verify sitemap
        with open(sitemap_xml, 'r', encoding='utf-8') as f:
            sitemap_content = f.read()
            assert 'record/test-market/2026-10-03/' in sitemap_content, "Sitemap not updated"

        # Verify prev/next links
        assert '2026-10-03 &rarr;</a>' in open(day1_html).read(), "Forward link not updated"

        print("Selftest PASSED")


def repair_links(market_dir, market_slug):
    """Idempotent pass over every day page of one market: the pv-pn block must point back to the previous run day
    and forward to the next one (forward link empty only on the newest day). Returns the number of pages rewritten."""
    dates = sorted(p.name for p in market_dir.iterdir()
                   if p.is_dir() and re.match(r'^\d{4}-\d{2}-\d{2}$', p.name) and (p / 'index.html').exists())
    fixed = 0
    for i, d in enumerate(dates):
        prev_d = dates[i - 1] if i > 0 else None
        next_d = dates[i + 1] if i + 1 < len(dates) else None
        prev_html = f'<a href="/record/{market_slug}/{prev_d}/">&larr; {prev_d}</a>' if prev_d else ''
        next_html = f'<a href="/record/{market_slug}/{next_d}/">{next_d} &rarr;</a>' if next_d else ''
        want = (f'<div class="pv-pn"><span>{prev_html}</span><span><a href="/record/{market_slug}/">All run days</a></span>'
                f'<span>{next_html}</span></div>')
        path = market_dir / d / 'index.html'
        with open(path, 'r', encoding='utf-8') as f:
            html = f.read()
        new_html, n = re.subn(r'<div class="pv-pn">.*?</div>', lambda m: want, html, count=1, flags=re.DOTALL)
        if n == 1 and new_html != html:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(new_html)
            fixed += 1
    return fixed


def main():
    parser = argparse.ArgumentParser(description='Generate missing day pages for namebeam-markets')
    parser.add_argument('--root', type=str, help='Root directory (default: current directory)')
    parser.add_argument('--today', type=str, help='Today date in YYYY-MM-DD format (default: current date)')
    parser.add_argument('--selftest', action='store_true', help='Run self-test')

    args = parser.parse_args()

    if args.selftest:
        selftest()
        return 0

    root_dir = Path(args.root) if args.root else Path.cwd()
    today = args.today if args.today else datetime.now().strftime('%Y-%m-%d')

    stats = {
        'days_written': {},
        'changes_rows': {},
        'sitemap_entries': set(),
        'hub_lastmods': {}  # {hub_url: lastmod_date}
    }

    # Process each market
    for market_slug in DAY_PAGES_MARKETS:
        # Skip kansas-city-health-insurance if it has no new rows
        if market_slug == 'kansas-city-health-insurance':
            all_csv = root_dir / 'record' / market_slug / 'all.csv'
            if all_csv.exists():
                with open(all_csv, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    if lines:
                        last_date = lines[-1].split(',')[0]
                        if last_date <= '2026-10-07':
                            continue

        process_market(market_slug, root_dir, today, stats)

    # Prev and next links on every day page, repaired idempotently (LB-24: the first build left forward links empty)
    repaired = 0
    for market_slug in DAY_PAGES_MARKETS:
        market_dir = root_dir / 'record' / market_slug
        if market_dir.exists():
            repaired += repair_links(market_dir, market_slug)
    print(f"day page links repaired: {repaired}")

    # Collect hub lastmods from summary.json for markets that had pages updated
    for market_slug in stats['days_written'].keys():
        summary_path = root_dir / 'record' / market_slug / 'summary.json'
        if summary_path.exists():
            with open(summary_path, 'r', encoding='utf-8') as f:
                summary = json.load(f)
            hub_url = f'https://markets.namebeam.ai/record/{market_slug}/'
            stats['hub_lastmods'][hub_url] = summary['window_last']

    # Update sitemap
    sitemap_path = root_dir / 'sitemap.xml'
    if sitemap_path.exists():
        updated_sitemap = update_sitemap(sitemap_path, stats['sitemap_entries'], today, stats['hub_lastmods'])
        with open(sitemap_path, 'w', encoding='utf-8') as f:
            f.write(updated_sitemap)

    # Remove empty directories
    for market_slug in DAY_PAGES_MARKETS:
        market_dir = root_dir / 'record' / market_slug
        if market_dir.exists():
            for item in market_dir.iterdir():
                if item.is_dir() and re.match(r'^\d{4}-\d{2}-\d{2}$', item.name):
                    if not (item / 'index.html').exists():
                        item.rmdir()

    # Print summary
    print("\n=== Summary ===")
    print(f"{'Market':<45} {'Days Written':<15} {'Changes Rows':<15} {'Sitemap Entries'}")
    print("-" * 90)

    for market_slug in sorted(stats['days_written'].keys()):
        days = stats['days_written'].get(market_slug, 0)
        changes = stats['changes_rows'].get(market_slug, 0)
        # Count sitemap entries for this market
        sitemap_count = sum(1 for url in stats['sitemap_entries'] if f'/record/{market_slug}/' in url)
        print(f"{market_slug:<45} {days:<15} {changes:<15} {sitemap_count}")

    total_days = sum(stats['days_written'].values())
    total_changes = sum(stats['changes_rows'].values())
    total_sitemap = len(stats['sitemap_entries'])

    print("-" * 90)
    print(f"{'TOTAL':<45} {total_days:<15} {total_changes:<15} {total_sitemap}")

    return 0


if __name__ == '__main__':
    sys.exit(main())
