#!/usr/bin/env python3
"""CPEO-1113 (2026-11-14): one dated correction note on every record page whose Anthropic rows carry names in the
heading window. Idempotent; the note sits outside every nb: marker, so the daily refresh never rewrites it.
Usage: python3 -I tools/add_anthropic_correction.py [--check]   (run from the repo root; --check only reports)
The note says what is true on the day it ships: the days are NOT restated (the record keeps its history), and the
filter in tools/daily_refresh.py applies to new rows only."""
import csv, glob, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
START, END = '2026-10-08', '2026-11-12'
NOTE_ID = 'anthropic-correction'
NOTE = ('<p class="pv-note" id="%s">Correction 2026-11-14: for the days between %s and %s the Anthropic names on this page and its day pages '
        'include section headings and advice lines that the extractor listed as names, so the Anthropic named-business counts '
        'for those days overstate. Those days are not restated. From 2026-11-14 new Anthropic rows keep only names that pass '
        'a strict business-name rule, which can leave out a real business.</p>\n') % (NOTE_ID, START, END)
ANCHOR = '<h2>By engine</h2>'
DAY_ID = 'anthropic-correction-day'
DAY_NOTE = ('<p class="pv-note" id="%s">Correction 2026-11-14: on this day the Anthropic names include section headings and advice lines '
            'that the extractor listed as names, so this day\'s Anthropic named-business count overstates. This day is not restated. '
            'From 2026-11-14 new Anthropic rows keep only names that pass a strict business-name rule, which can leave out a real business.</p>\n') % DAY_ID
H1_RE = re.compile(r'(<h1>[^\n]*</h1>\n)')
OLD = re.compile(r'<p class="pv-note" id="%s">.*?</p>\n' % NOTE_ID, re.S)


def affected_slugs():
    out = []
    for f in sorted(glob.glob(str(ROOT / 'record' / '*' / 'all.csv'))):
        with open(f, encoding='utf-8', newline='') as fh:
            for r in csv.DictReader(fh):
                if (r['engine'].lower().startswith('anthropic') and r['status'] == 'OK' and START <= r['date'] <= END
                        and int(r['names_count'] or 0) > 0):
                    out.append(Path(f).parent.name)
                    break
    return out


def apply(html):
    """Pure: returns html with exactly one current note before the By engine heading (an older note is replaced in place); unchanged when no anchor."""
    if ANCHOR not in html:
        return html
    if 'id="%s"' % NOTE_ID in html:
        return OLD.sub(lambda m: NOTE, html, count=1)
    return html.replace(ANCHOR, NOTE + ANCHOR, 1)


def affected_days():
    out = []
    for f in sorted(glob.glob(str(ROOT / 'record' / '*' / 'all.csv'))):
        days = set()
        with open(f, encoding='utf-8', newline='') as fh:
            for r in csv.DictReader(fh):
                if (r['engine'].lower().startswith('anthropic') and r['status'] == 'OK' and START <= r['date'] <= END
                        and int(r['names_count'] or 0) > 0):
                    days.add(r['date'])
        for d in sorted(days):
            out.append((Path(f).parent.name, d))
    return out


def apply_day(html):
    """Pure: one day note straight after the h1 line; unchanged when present or no h1 line."""
    if 'id="%s"' % DAY_ID in html or not H1_RE.search(html):
        return html
    return H1_RE.sub(lambda m: m.group(1) + DAY_NOTE, html, count=1)


def main_days(check):
    days = affected_days()
    changed = missing = 0
    for slug, d in days:
        p = ROOT / 'record' / slug / d / 'index.html'
        if not p.exists():
            missing += 1
            continue
        html = p.read_text(encoding='utf-8')
        new = apply_day(html)
        if new != html:
            changed += 1
            if not check:
                p.write_text(new, encoding='utf-8', newline='\n')
    print('affected market-days %d, day pages changed %d, day pages missing %d%s' % (len(days), changed, missing, ' (check only)' if check else ''))
    return 0


def main(argv):
    if '--days' in argv:
        return main_days('--check' in argv)
    check = '--check' in argv
    slugs = affected_slugs()
    changed = 0
    for slug in slugs:
        p = ROOT / 'record' / slug / 'index.html'
        html = p.read_text(encoding='utf-8')
        new = apply(html)
        if new != html:
            changed += 1
            if not check:
                p.write_text(new, encoding='utf-8', newline='\n')
    print('affected pages %d, changed %d%s' % (len(slugs), changed, ' (check only)' if check else ''))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
