#!/usr/bin/env python3
"""Selftests for name counting. Usage: selftest.py --method old|new [--corpus corpus/e1]
RED means the fixture fails under that method; GREEN means it passes. The old method is the
extractor-field count with exact strings and calendar-day denominators. The new method reads
answer text, merges spelling variants and divides by answered days."""
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import namecount as nc


def mkrow(day, text, field, status='OK'):
    return {'date_utc': day, 'answer_verbatim': text if status == 'OK' else '', 'competitors_mentioned': field,
            'run_status': status, 'engine': 'fixture', 'prompt_text': 'fixture question'}


def days(lo, n):
    return list(nc.daterange(lo, '2026-09-30'))[:n]


# ---- counting under each method; both return (named_days, denominator)
def count_old(rows, name, lo, hi):
    named = {r['date_utc'] for r in rows if lo <= r['date_utc'] <= hi and name in (r['competitors_mentioned'] or [])}
    den = len(list(nc.daterange(lo, hi)))          # calendar days, failed runs counted as misses
    return len(named), den


def count_new(rows, name, lo, hi, variants=None):
    table = nc.build_alias_table({v: 1 for v in (variants or [name])}, seeds=[name], lawish_niche=True)
    ans, failed = nc.day_status(rows, lo, hi)
    by = {}
    for r in rows:
        if nc.is_answered(r) and lo <= r['date_utc'] <= hi:
            by.setdefault(r['date_utc'], set()).update(nc.text_hits(r['answer_verbatim'], table))
    cl = nc.build_alias_table({v: 1 for v in (variants or [name])}, seeds=[name], lawish_niche=True)[0]['name']
    return sum(1 for d, h in by.items() if cl in h), len(ans)


def fixtures():
    out = []
    ds = days('2026-09-01', 14)
    # 1. extractor field misses a name that is present in the answer text (13 of 14 days; field carries 6)
    rows = []
    for i, d in enumerate(ds):
        has = i < 13
        text = ('Top firms:\n#### 2. **GJEL Accident Attorneys (Gillin, Jacobson, Ellis, Larsen & Lucey)**\n* Pleasanton office\n' if has
                else 'Top firms:\n#### 2. **Some Other Firm**\n')
        rows.append(mkrow(d, text, ['GJEL Accident Attorneys'] if i < 6 else ['Some Other Firm']))
    out.append(('F1 field misses a name present in the text', rows, 'GJEL Accident Attorneys', ds[0], ds[-1], None, (13, 14)))
    # 2. spelling variants of one firm across three days
    rows = [mkrow('2026-09-01', 'Consider John Michael Hosterman, a trial lawyer.', ['John Michael Hosterman']),
            mkrow('2026-09-02', 'Consider J. Michael Hosterman, a trial lawyer.', ['J. Michael Hosterman']),
            mkrow('2026-09-03', 'The Law Offices of J. Michael Hosterman handle injury cases.', ['Law Offices of J. Michael Hosterman'])]
    out.append(('F2 spelling variants merge into one business', rows, 'J. Michael Hosterman', '2026-09-01', '2026-09-03',
                ['J. Michael Hosterman', 'John Michael Hosterman', 'Law Offices of J. Michael Hosterman'], (3, 3)))
    # 3. failed days leave the denominator: 21 named of 24 answered, 3 failed (stated rule: failed runs are failures, not misses)
    rows = []
    for d in nc.daterange('2026-09-01', '2026-09-27'):
        failed = d in ('2026-09-02', '2026-09-03', '2026-09-04')
        n_named = len([r for r in rows if r['answer_verbatim']])
        named = (not failed) and n_named < 21
        rows.append(mkrow(d, 'GJEL Accident Attorneys is one option.' if named else 'Some other advice.',
                          ['GJEL Accident Attorneys'] if named else [], 'FAILED' if failed else 'OK'))
    out.append(('F3 failed days excluded from the denominator', rows, 'GJEL Accident Attorneys', '2026-09-01', '2026-09-27', None, (21, 24)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--method', choices=['old', 'new'], required=True)
    ap.add_argument('--corpus')
    a = ap.parse_args()
    bad = 0
    print('METHOD', a.method)
    for title, rows, name, lo, hi, variants, expect in fixtures():
        got = count_old(rows, name, lo, hi) if a.method == 'old' else count_new(rows, name, lo, hi, variants)
        ok = got == expect
        bad += not ok
        print('%s  %s: expected %d of %d, got %d of %d' % ('GREEN' if ok else 'RED  ', title, expect[0], expect[1], got[0], got[1]))
    if a.corpus and a.method == 'new':
        rows = nc.load_rows(a.corpus, '2026-09-01', '2026-09-27')
        cell = [r for r in rows if r['engine'] == 'gemini' and r['market'] == 'Pleasanton CA'
                and r['prompt_text'] == 'Who is the best personal injury lawyer in Pleasanton California?']
        ans, _ = nc.day_status(cell, '2026-09-01', '2026-09-27')
        t = nc.build_alias_table({'GJEL Accident Attorneys': 6}, lawish_niche=True)
        txt = len({r['date_utc'] for r in cell if nc.is_answered(r) and nc.text_hits(r['answer_verbatim'], t)})
        fld = len({r['date_utc'] for r in cell if nc.is_answered(r) and nc.field_hits(r.get('competitors_mentioned'), t)})
        ok = (txt, fld, len(ans)) == (13, 6, 14)
        bad += not ok
        print('%s  RAW Gemini prompt A GJEL: text %d, field %d, answered days %d (expected 13, 6, 14)' % ('GREEN' if ok else 'RED  ', txt, fld, len(ans)))
    print('RESULT', 'ALL GREEN' if not bad else '%d RED' % bad)
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
