#!/usr/bin/env python3
"""test_lb107_denominators.py  LB-107 (2026-11-12) build test for the denominator sentence above the receipt table.

Red team stop point (a), CHATGPT-REDTEAM-1112: a buyer reading "0 of 17" beside "0 of 12", "0 of 19" and "0 of 24"
cannot tell what each denominator counts. tools/refresh_pages.py now writes one sentence directly above the receipt
table, inside <!--nb:rec-denominators--> markers, with every number recounted from the raw run file the page already
publishes (all.csv or rows.csv). This test grades the pages and the generator:

  1. every record page with a receipt table carries exactly one non-empty rec-denominators block, and the block sits
     directly above the table (only whitespace between the close marker and the table)
  2. every number in the sentence equals the table's own "n of N" denominator for that engine AND an independent
     recount from the raw rows over the window the sentence itself states
  3. the sentence is one ASCII sentence: no em or en dash, one full stop, under 400 characters
  4. derive_denominators on a fixture: reproduces a known table, refuses a table it cannot reproduce
  5. denominator_sentence types no number: no digit other than the literal 0 of "a 0 means" in its string literals

Usage: py -3 -I tools/test_lb107_denominators.py [--root PATH]        exit 1 on RED
RED on the pages before the generator runs (no block); GREEN after `py -3 -I -B tools/refresh_pages.py --no-fetch`.
"""
import argparse
import csv
import inspect
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..'))
sys.path.insert(0, HERE)

MARKER = re.compile(r'<!--nb:rec-denominators-->(.*?)<!--/nb:rec-denominators-->', re.DOTALL)
TABLE_OPEN = '<div class="pv-scroll"><table>'
SENTENCE = re.compile(
    r'Days behind each count differ by engine: (?P<who>Perplexity[^,]*), (?P<p>\d+) days with public answer text, '
    r'(?P<s1>\d{4}-\d{2}-\d{2}) to (?P<e1>\d{4}-\d{2}-\d{2}); (?P<later>.*?), (?P<s2>\d{4}-\d{2}-\d{2}) to '
    r'(?P<e2>\d{4}-\d{2}-\d{2}); a 0 means the business\'s name or web address was in none of that engine\'s '
    r'answers on those days\.$')
CLAUSE = re.compile(r'(?P<label>Gemini|ChatGPT|Claude) (?P<n>\d+) (?P<kind>answered|tracked) days(?: \((?P<ans>\d+) answered\))?')
ENGINE = {'Perplexity': 'perplexity', 'Gemini': 'gemini', 'ChatGPT': 'openai', 'Claude': 'anthropic'}
COLUMN = {'Perplexity': 'Perplexity named it (days)', 'Gemini': 'Gemini named it',
          'ChatGPT': 'ChatGPT named it', 'Claude': 'Claude named it'}


def receipt_pages(root):
    out = []
    rec_dir = os.path.join(root, 'record')
    for slug in sorted(os.listdir(rec_dir)):
        page = os.path.join(rec_dir, slug, 'index.html')
        if not os.path.isfile(page):
            continue
        html = open(page, encoding='utf-8').read()
        m = re.search(r'<!-- receipt:start.*?<!-- receipt:end', html, re.DOTALL)
        if m and TABLE_OPEN in m.group(0):
            out.append((slug, page, html, m.group(0)))
    return out


def table_denominators(receipt_html):
    heads = [re.sub(r'<.*?>', '', c) for c in re.findall(r'<th>(.*?)</th>', receipt_html)]
    den = {}
    for tr in re.findall(r'<tr>(.*?)</tr>', receipt_html)[1:]:
        for head, cell in zip(heads, re.findall(r'<td>(.*?)</td>', tr)):
            cm = re.match(r'(\d+) of (\d+)$', cell)
            if cm:
                den.setdefault(head, set()).add(int(cm.group(2)))
    return den


def raw_rows(root, slug):
    d = os.path.join(root, 'record', slug)
    name = 'all.csv' if os.path.exists(os.path.join(d, 'all.csv')) else 'rows.csv'
    with open(os.path.join(d, name), encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))


def days(rows, engine, start, end, answered_only):
    return len({r['date'] for r in rows if r['engine'] == engine and start <= r['date'] <= end
                and (r['status'] == 'OK' or not answered_only)})


class DenominatorSentenceOnPages(unittest.TestCase):
    root = ROOT

    def setUp(self):
        self.pages = receipt_pages(self.root)
        self.assertGreater(len(self.pages), 0, 'no record page with a receipt table under %s' % self.root)

    def test_1_every_receipt_page_has_one_block_directly_above_the_table(self):
        missing, empty, misplaced, doubled = [], [], [], []
        for slug, page, html, rec in self.pages:
            blocks = MARKER.findall(rec)
            if not blocks:
                missing.append(slug)
                continue
            if len(blocks) > 1:
                doubled.append(slug)
            if not blocks[0].strip():
                empty.append(slug)
            after = rec.split('<!--/nb:rec-denominators-->', 1)[1]
            if after.lstrip()[:len(TABLE_OPEN)] != TABLE_OPEN:
                misplaced.append(slug)
        self.assertEqual(missing, [], 'no rec-denominators block: %s' % missing)
        self.assertEqual(empty, [], 'empty rec-denominators block: %s' % empty)
        self.assertEqual(doubled, [], 'more than one block: %s' % doubled)
        self.assertEqual(misplaced, [], 'block not directly above the table: %s' % misplaced)

    def test_2_every_number_matches_the_table_and_a_recount_from_the_raw_rows(self):
        problems = []
        for slug, page, html, rec in self.pages:
            blocks = MARKER.findall(rec)
            if not blocks:
                problems.append('%s: no block' % slug)
                continue
            text = re.sub(r'<.*?>', '', blocks[0]).strip()
            m = SENTENCE.match(text)
            if not m:
                problems.append('%s: sentence shape: %s' % (slug, text[:120]))
                continue
            den = table_denominators(rec)
            rows = raw_rows(self.root, slug)
            p = int(m.group('p'))
            if den.get(COLUMN['Perplexity']) != {p}:
                problems.append('%s: Perplexity %d vs table %s' % (slug, p, sorted(den.get(COLUMN['Perplexity'], ()))))
            if days(rows, 'perplexity', m.group('s1'), m.group('e1'), True) != p:
                problems.append('%s: Perplexity %d vs recount' % (slug, p))
            if 'third-party' in m.group('who') and den.get('third-party pages carrying its name (days)') != {p}:
                problems.append('%s: third-party column vs %d' % (slug, p))
            seen = set()
            for c in CLAUSE.finditer(m.group('later')):
                label, n, kind = c.group('label'), int(c.group('n')), c.group('kind')
                seen.add(label)
                if den.get(COLUMN[label]) != {n}:
                    problems.append('%s: %s %d vs table %s' % (slug, label, n, sorted(den.get(COLUMN[label], ()))))
                if days(rows, ENGINE[label], m.group('s2'), m.group('e2'), kind == 'answered') != n:
                    problems.append('%s: %s %d %s vs recount' % (slug, label, n, kind))
                if c.group('ans') is not None and days(rows, ENGINE[label], m.group('s2'), m.group('e2'), True) != int(c.group('ans')):
                    problems.append('%s: %s answered %s vs recount' % (slug, label, c.group('ans')))
            for label in ('Gemini', 'ChatGPT', 'Claude'):
                if COLUMN[label] in den and label not in seen:
                    problems.append('%s: %s column in the table but not in the sentence' % (slug, label))
        self.assertEqual(problems, [], '\n'.join(problems))

    def test_3_one_ascii_sentence_no_dashes(self):
        problems = []
        for slug, page, html, rec in self.pages:
            blocks = MARKER.findall(rec)
            if not blocks:
                problems.append('%s: no block' % slug)
                continue
            text = re.sub(r'<.*?>', '', blocks[0]).strip()
            if any(ord(ch) > 127 for ch in text):
                problems.append('%s: non-ASCII' % slug)
            if '—' in text or '–' in text:
                problems.append('%s: em or en dash' % slug)
            if text.count('. ') or not text.endswith('.'):
                problems.append('%s: not one sentence' % slug)
            if len(text) > 400:
                problems.append('%s: %d characters' % (slug, len(text)))
        self.assertEqual(problems, [], '\n'.join(problems))


class DeriveOnFixture(unittest.TestCase):
    def rows(self):
        out = []
        for i in range(1, 11):
            d = '2026-10-%02d' % i
            out.append({'date': d, 'engine': 'perplexity', 'status': 'OK'})
            out.append({'date': d, 'engine': 'gemini', 'status': 'OK' if i % 2 else 'FAILED'})
            out.append({'date': d, 'engine': 'openai', 'status': 'OK'})
            out.append({'date': d, 'engine': 'anthropic', 'status': 'OK' if i != 4 else 'FAILED'})
        return out

    def receipt(self, p, g, o, a):
        return {'start': '2026-10-01', 'end': '2026-10-06', 'section_start': 0, 'section_end': 1,
                'denominators': {'Perplexity named it (days)': {p}, 'third-party pages carrying its name (days)': {p},
                                 'Gemini named it': {g}, 'ChatGPT named it': {o}, 'Claude named it': {a}}}

    def test_4_reproduces_a_known_table_and_refuses_an_unknown_one(self):
        import refresh_pages as rp
        got, reason = rp.derive_denominators(self.rows(), self.receipt(6, 4, 8, 8))
        self.assertIsNone(reason)
        self.assertEqual(got['public_count'], 6)
        self.assertEqual(got['cut'], '2026-10-08')
        kinds = {c['label']: (c['kind'], c['count'], c['answered']) for c in got['later']}
        self.assertEqual(kinds, {'Gemini': ('answered', 4, 4), 'ChatGPT': ('answered', 8, 8), 'Claude': ('tracked', 8, 7)})
        s = rp.denominator_sentence(got)
        self.assertIn('Perplexity and the third-party pages column, 6 days with public answer text, 2026-10-01 to 2026-10-06', s)
        self.assertIn('Gemini 4 answered days, ChatGPT 8 answered days and Claude 8 tracked days (7 answered), 2026-10-01 to 2026-10-08', s)
        self.assertTrue(s.endswith('on those days.'))
        bad, reason = rp.derive_denominators(self.rows(), self.receipt(6, 4, 9, 8))
        self.assertIsNone(bad)
        self.assertIn('no cut date', reason)
        bad, reason = rp.derive_denominators(self.rows(), self.receipt(5, 4, 8, 8))
        self.assertIsNone(bad)
        self.assertIn('Perplexity', reason)

    def test_5_the_sentence_template_types_no_number(self):
        import refresh_pages as rp
        src = inspect.getsource(rp.denominator_sentence)
        digits = set(re.findall(r'\d', ''.join(re.findall(r"'[^']*'|\"[^\"]*\"", src))))
        self.assertTrue(digits <= {'0'}, 'digits typed in the template: %s' % sorted(digits))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default=ROOT)
    ap.add_argument('-v', action='store_true')
    a = ap.parse_args()
    DenominatorSentenceOnPages.root = os.path.abspath(a.root)
    suite = unittest.TestSuite()
    loader = unittest.TestLoader()
    suite.addTests(loader.loadTestsFromTestCase(DenominatorSentenceOnPages))
    suite.addTests(loader.loadTestsFromTestCase(DeriveOnFixture))
    res = unittest.TextTestRunner(verbosity=2).run(suite)
    n = res.testsRun
    bad = len(res.failures) + len(res.errors)
    print('LB107 %s %d of %d' % ('GREEN' if bad == 0 else 'RED', n - bad, n))
    return 0 if bad == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
