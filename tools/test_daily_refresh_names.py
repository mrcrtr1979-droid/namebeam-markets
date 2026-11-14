"""CPEO-1113: the Anthropic names filter in tools/daily_refresh.py.
Run: python3 -I -B tools/test_daily_refresh_names.py   (stdlib only; exit 0 GREEN, 1 RED)
Headings and advice that the Anthropic extractor lists (seen on every Anthropic run 2026-10-08 to 2026-10-12) must not
count as businesses; real business names that carry a trade or law word must; other engines must be unchanged."""
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('dr', ROOT / 'tools' / 'daily_refresh.py')
dr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dr)

HEADINGS = ['Red flags to avoid', 'Get multiple quotes', 'Ways to find options', 'Research methods', 'Tips for choosing',
            'Check these sources', 'Ask about warranties', 'Popular Houston HVAC companies', 'Where to check',
            'Certifications', 'Hurricane ratings', 'Questions to ask', 'Next steps', 'Local bar associations',
            'State bar referral', 'Initial consultation', 'Look for', 'Key qualifications to verify']
NAMES_HVAC = ['Cunningham Associates Heating & AC', 'Aire Serv Heating & Air Conditioning', 'Smith Brothers Heating and Air']
NAMES_LAW = ['Morgan & Morgan Attorneys', 'Jones Law Firm', 'GJEL Accident Attorneys']


def raw(engine, names, day='2026-10-10'):
    return {'check_id': 'NB-CZ-API_%s_segment_hvac_atlanta_%s' % (day, engine), 'date_utc': day, 'market': 'Atlanta GA',
            'niche': 'hvac repair and replacement', 'run': 1, 'run_status': 'OK', 'competitors_mentioned': names,
            'answer_verbatim': 'text'}


class AnthropicNames(unittest.TestCase):
    def test_1_headings_never_count_in_any_niche(self):
        for market, niche in (('Atlanta GA', 'hvac repair and replacement'), ('Dallas TX', 'personal injury attorneys'),
                              ('Denver CO', 'residential roofing')):
            self.assertEqual(dr.filter_anthropic_names(HEADINGS, market, niche), [], (market, niche))

    def test_2_real_names_with_a_trade_word_are_kept(self):
        self.assertEqual(dr.filter_anthropic_names(NAMES_HVAC, 'Atlanta GA', 'hvac repair and replacement'), NAMES_HVAC)

    def test_3_real_law_names_are_kept_in_a_law_niche(self):
        self.assertEqual(dr.filter_anthropic_names(NAMES_LAW, 'Houston TX', 'personal injury attorneys'), NAMES_LAW)

    def test_4_mixed_list_keeps_only_the_names(self):
        got = dr.filter_anthropic_names(HEADINGS[:4] + NAMES_HVAC, 'Atlanta GA', 'hvac repair and replacement')
        self.assertEqual(got, NAMES_HVAC)

    def test_5_parse_corpus_file_filters_anthropic_only(self):
        mixed = HEADINGS[:3] + NAMES_HVAC[:1]
        with tempfile.TemporaryDirectory() as d:
            out = {}
            for eng in ('anthropic', 'openai', 'perplexity', 'gemini'):
                p = Path(d) / ('NB-CZ-API_2026-10-10_segment_hvac_atlanta_%s.json' % eng)
                p.write_text(json.dumps(raw(eng, mixed)), encoding='utf-8')
                out[eng] = dr.parse_corpus_file(p)
        self.assertEqual(out['anthropic']['names_count'], 1)
        self.assertEqual(out['anthropic']['businesses_named'], NAMES_HVAC[0])
        for eng in ('openai', 'perplexity', 'gemini'):
            self.assertEqual(out[eng]['names_count'], len(mixed), eng)
            self.assertEqual(out[eng]['businesses_named'], '; '.join(mixed), eng)

    def test_6_empty_and_missing_lists_stay_zero(self):
        self.assertEqual(dr.filter_anthropic_names([], 'Atlanta GA', 'hvac repair and replacement'), [])
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'NB-CZ-API_2026-10-10_segment_hvac_atlanta_anthropic.json'
            r = raw('anthropic', [])
            del r['competitors_mentioned']
            p.write_text(json.dumps(r), encoding='utf-8')
            row = dr.parse_corpus_file(p)
        self.assertEqual((row['names_count'], row['businesses_named']), (0, ''))


if __name__ == '__main__':
    res = unittest.main(exit=False, verbosity=1).result
    bad = len(res.failures) + len(res.errors)
    print('DAILY_REFRESH_NAMES %s %d of %d' % ('GREEN' if not bad else 'RED', res.testsRun - bad, res.testsRun))
    sys.exit(1 if bad else 0)
