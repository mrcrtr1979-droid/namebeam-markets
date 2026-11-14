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
NOTE = ('<p class="pv-note" id="%s">Correction 2026-11-14: from %s to %s the Anthropic names on this page and its day pages '
        'include section headings and advice lines that the extractor listed as names, so the Anthropic named-business counts '
        'for those days overstate. Those days are not restated. From 2026-11-14 new Anthropic rows keep only names that pass '
        'a strict business-name rule, which can leave out a real business.</p>\n') % (NOTE_ID, START, END)
ANCHOR = '<h2>By engine</h2>'


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
    """Pure: returns html with exactly one note before the By engine heading; unchanged when already present or no anchor."""
    if 'id="%s"' % NOTE_ID in html or ANCHOR not in html:
        return html
    return html.replace(ANCHOR, NOTE + ANCHOR, 1)


def main(argv):
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
