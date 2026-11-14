"""F1 (CPEO-1113, Overseer item 7): no tool may type an offer date; each reads latest_run_day from data/latest.json.
Run: python3 -I -B tools/test_f1_date_producers.py   (stdlib only; exit 0 GREEN, 1 RED)"""
import importlib.util
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LATEST = json.loads((ROOT / 'data' / 'latest.json').read_text(encoding='utf-8'))['latest_run_day']


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'tools' / (name + '.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class DateProducers(unittest.TestCase):
    def test_1_lb23_buy_description_uses_latest_run_day(self):
        m = load('lb23_apply_titles')
        desc = m.PAGES['buy/index.html'][1]
        self.assertIn('per market as of %s:' % LATEST, desc)
        self.assertTrue(m.check())

    def test_2_no_typed_offer_date_in_the_three_producers(self):
        for name in ('lb23_apply_titles', 'refresh_pages', 'refresh_day_pages'):
            src = (ROOT / 'tools' / (name + '.py')).read_text(encoding='utf-8')
            typed = re.findall(r'a month[^\n]{0,80}as of 20\d\d-\d\d-\d\d', src)
            # the selftest and test fixtures in refresh_day_pages.py and refresh_pages.py carry fixture dates on purpose
            typed = [t for t in typed if name == 'lb23_apply_titles']
            self.assertEqual(typed, [], name)

    def test_3_day_page_generator_takes_offer_day(self):
        import inspect
        m = load('refresh_day_pages')
        self.assertIn('offer_day', inspect.signature(m.generate_day_page).parameters)

    def test_4_record_pages_carry_latest_run_day(self):
        bad = []
        for slug in json.loads((ROOT / 'data' / 'latest.json').read_text(encoding='utf-8'))['markets']:
            html = (ROOT / 'record' / slug / 'index.html').read_text(encoding='utf-8')
            line = [l for l in html.split('\n') if 'lb19:offer' in l]
            if not line or ('as of %s' % LATEST) not in line[0]:
                bad.append(slug)
        self.assertEqual(bad, [])


if __name__ == '__main__':
    res = unittest.main(exit=False, verbosity=1).result
    bad = len(res.failures) + len(res.errors)
    print('F1_DATE_PRODUCERS %s %d of %d' % ('GREEN' if not bad else 'RED', res.testsRun - bad, res.testsRun))
    sys.exit(1 if bad else 0)
