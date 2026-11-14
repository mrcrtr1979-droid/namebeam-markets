"""F3 (CPEO-1113): llms.txt must list every record page in data/latest.json once, by its public URL.
Run: python3 -I -B tools/test_llms_records.py   (stdlib only; exit 0 GREEN, 1 RED)"""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = 'https://markets.namebeam.ai/record/'


class LlmsRecordPages(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = (ROOT / 'llms.txt').read_text(encoding='utf-8')
        cls.slugs = sorted(json.loads((ROOT / 'data' / 'latest.json').read_text(encoding='utf-8'))['markets'])
        cls.listed = re.findall(re.escape(BASE) + r'([a-z0-9-]+)/', cls.text)

    def test_1_every_record_page_is_listed_once(self):
        slugs = [s for s in self.listed]
        missing = [s for s in self.slugs if slugs.count(s) != 1]
        self.assertEqual(missing, [], 'record pages not listed exactly once: %s' % missing)

    def test_2_no_listed_page_is_missing_on_disk(self):
        gone = [s for s in set(self.listed) if not (ROOT / 'record' / s / 'index.html').exists()]
        self.assertEqual(gone, [], 'listed but no page: %s' % gone)

    def test_3_ascii_and_no_dashes(self):
        self.assertTrue(all(ord(c) < 128 for c in self.text), 'non-ASCII in llms.txt')
        self.assertNotIn('—', self.text)
        self.assertNotIn('–', self.text)

    def test_4_hub_is_listed(self):
        self.assertIn(BASE + '\n', self.text + '\n')

    def test_5_selfcheck_catches_a_missing_page(self):
        if not self.slugs:
            self.skipTest('no markets')
        broken = self.text.replace(BASE + self.slugs[0] + '/', BASE + 'x-removed/')
        found = re.findall(re.escape(BASE) + r'([a-z0-9-]+)/', broken)
        self.assertNotEqual(found.count(self.slugs[0]), 1)


if __name__ == '__main__':
    r = unittest.main(exit=False, verbosity=1).result
    n = r.testsRun
    ok = r.wasSuccessful()
    print('LLMS_RECORDS %s %d of %d' % ('GREEN' if ok else 'RED', n - len(r.failures) - len(r.errors), n))
    sys.exit(0 if ok else 1)
