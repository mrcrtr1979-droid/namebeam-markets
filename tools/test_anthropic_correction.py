"""CPEO-1113: the dated Anthropic correction note is on exactly the affected record pages, once, ASCII, outside markers.
Run: python3 -I -B tools/test_anthropic_correction.py   (exit 0 GREEN, 1 RED)"""
import importlib.util, re, sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('aac', ROOT / 'tools' / 'add_anthropic_correction.py')
aac = importlib.util.module_from_spec(spec); spec.loader.exec_module(aac)


class Note(unittest.TestCase):
    def test_1_apply_is_idempotent_and_single(self):
        h = '<p>x</p>\n<h2>By engine</h2><div>t</div>\n'
        once = aac.apply(h)
        self.assertEqual(once.count('id="anthropic-correction"'), 1)
        self.assertEqual(aac.apply(once), once)

    def test_6_note_carries_no_date_window_the_checker_counts(self):
        # tools/check_record_consistency.py WIN: 'YYYY-MM-DD to|through YYYY-MM-DD' counts as a data window
        win = re.compile(r"(\d{4}-\d{2}-\d{2}) (?:to|through) (\d{4}-\d{2}-\d{2})")
        self.assertEqual(win.findall(aac.NOTE), [])
        self.assertIn(aac.START, aac.NOTE); self.assertIn(aac.END, aac.NOTE)

    def test_7_older_note_is_replaced_not_stacked(self):
        old = '<p class="pv-note" id="anthropic-correction">Correction 2026-11-14: from 2026-10-08 to 2026-11-12 old text.</p>\n'
        out = aac.apply('<p>x</p>\n' + old + '<h2>By engine</h2>')
        self.assertEqual(out.count('id="anthropic-correction"'), 1)
        self.assertNotIn('old text', out)
        self.assertEqual(aac.apply(out), out)

    def test_2_no_anchor_no_change(self):
        self.assertEqual(aac.apply('<p>none</p>'), '<p>none</p>')

    def test_3_note_is_ascii_and_outside_markers(self):
        self.assertTrue(all(ord(c) < 128 for c in aac.NOTE))
        self.assertNotIn('nb:', aac.NOTE)
        self.assertNotIn('—', aac.NOTE)

    def test_4_every_affected_page_carries_it_once(self):
        bad = []
        for slug in aac.affected_slugs():
            html = (ROOT / 'record' / slug / 'index.html').read_text(encoding='utf-8')
            if html.count('id="anthropic-correction"') != 1:
                bad.append(slug)
        self.assertEqual(bad, [])

    def test_5_unaffected_pages_do_not(self):
        aff = set(aac.affected_slugs())
        extra = [p.parent.name for p in (ROOT / 'record').glob('*/index.html')
                 if p.parent.name not in aff and 'id="anthropic-correction"' in p.read_text(encoding='utf-8')]
        self.assertEqual(extra, [])


if __name__ == '__main__':
    res = unittest.main(exit=False, verbosity=1).result
    bad = len(res.failures) + len(res.errors)
    print('ANTHROPIC_CORRECTION %s %d of %d' % ('GREEN' if not bad else 'RED', res.testsRun - bad, res.testsRun))
    sys.exit(1 if bad else 0)
