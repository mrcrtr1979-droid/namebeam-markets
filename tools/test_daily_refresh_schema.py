#!/usr/bin/env python3
"""Schema tests for tools/daily_refresh.py (LB-29, 2026-11-10, on LB28_NOTE_1).

Run from the repo root:  py -3 -I -B tools/test_daily_refresh_schema.py

What is proved:
  1. The record schema (CSV_FIELDS) carries no text column, and the import-time guard refuses one.
  2. A Perplexity corpus file can never put answer text into a record row: every value of the parsed
     row is checked against a sentinel text planted in every text-bearing field of the corpus file.
  3. A legacy-schema market is rebuilt from its own corpus files in the current schema, row for row,
     with the same dates and engines; a legacy row whose corpus file is missing stops the migration.
Standard library only; writes only under a temporary directory.
"""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("daily_refresh", HERE / "daily_refresh.py")
dr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dr)

SENTINEL = "THIS TEXT MUST NEVER REACH THE PUBLIC RECORD 7f3a9c"


def corpus_file(dirpath, date, niche, market, engine, status="OK", names=None, with_text=True):
    """Write one corpus-shaped JSON file and return its path."""
    slug = "%s_%s" % (niche, market.split()[0].lower())
    prefix = "NB-CZ-SERP" if engine == "google_serp" else "NB-CZ-API"
    check_id = "%s_%s_segment_%s" % (prefix, date, slug)
    if engine != "google_serp":
        check_id += "_" + engine
    doc = {
        "check_id": check_id, "date_utc": date, "market": market, "niche": niche, "engine": engine,
        "run": 1, "run_status": status, "competitors_mentioned": names or [],
    }
    if with_text:
        for k in ("answer_text", "raw_answer", "text", "answer", "ai_overview_text", "prompt_text",
                  "sources", "citations"):
            doc[k] = SENTINEL
    p = Path(dirpath) / "corpus" / "e1" / (check_id + ".json")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc), encoding="utf-8")
    return p


class SchemaTests(unittest.TestCase):
    def test_schema_has_no_text_column(self):
        self.assertTrue(dr.assert_no_text_columns())
        for f in dr.CSV_FIELDS:
            for w in dr.TEXT_COLUMN_WORDS:
                self.assertNotIn(w, f.lower(), f)

    def test_guard_refuses_a_text_column(self):
        with self.assertRaises(ValueError):
            dr.assert_no_text_columns(dr.CSV_FIELDS + ["answer_text"])
        with self.assertRaises(ValueError):
            dr.assert_no_text_columns(["date", "engine", "text"])

    def test_legacy_header_detection(self):
        self.assertTrue(dr.is_legacy_header(dr.LEGACY_FIELDS))
        self.assertFalse(dr.is_legacy_header(list(dr.CSV_FIELDS)))
        self.assertTrue(dr.is_legacy_header(None))
        self.assertTrue(dr.is_legacy_header(list(reversed(dr.CSV_FIELDS))))

    def test_perplexity_row_never_carries_text(self):
        with tempfile.TemporaryDirectory() as td:
            p = corpus_file(td, "2026-11-09", "dentists", "Dallas TX", "perplexity",
                            names=["Example Dental"])
            row = dr.parse_corpus_file(p)
            self.assertEqual(row["engine"], "perplexity")
            self.assertEqual(set(row), set(dr.CSV_FIELDS) - {"question_slug"})
            for k, v in row.items():
                self.assertNotIn(SENTINEL, str(v), "text leaked through column %s" % k)
                self.assertNotIn("7f3a9c", str(v), k)
            self.assertEqual(row["names_count"], 1)
            self.assertEqual(row["businesses_named"], "Example Dental")

    def test_every_engine_row_never_carries_text(self):
        with tempfile.TemporaryDirectory() as td:
            for eng in ("openai", "anthropic", "gemini", "google_serp"):
                p = corpus_file(td, "2026-11-09", "dentists", "Dallas TX", eng)
                row = dr.parse_corpus_file(p)
                for k, v in row.items():
                    self.assertNotIn(SENTINEL, str(v), "%s leaked through %s" % (eng, k))

    def test_legacy_rows_rebuild_from_their_corpus_files(self):
        with tempfile.TemporaryDirectory() as td:
            legacy = []
            for date in ("2026-10-08", "2026-10-09"):
                for eng, status in (("perplexity", "OK"), ("gemini", "FAILED")):
                    p = corpus_file(td, date, "dentists", "Dallas TX", eng, status=status,
                                    names=["A Dental", "B Dental"] if status == "OK" else [])
                    legacy.append({
                        "date": date, "engine": eng, "run_status": status, "answer_sha256": "",
                        "answer_chars": "", "answer_text": "public",
                        "tracked_businesses_named_in_text": "a.com",
                        "source_file": p.relative_to(td).as_posix(),
                    })
            rebuilt = dr.migrate_legacy_rows(legacy, "dallas-dentists", td)
            self.assertEqual(len(rebuilt), len(legacy))
            for old, new in zip(legacy, rebuilt):
                self.assertEqual(set(new), set(dr.CSV_FIELDS))
                self.assertEqual(new["date"], old["date"])
                self.assertEqual(new["engine"], old["engine"])
                self.assertEqual(new["status"], old["run_status"])
                self.assertEqual(new["question_slug"], "dallas-dentists")
                self.assertEqual(new["market"], "Dallas TX")
                self.assertEqual(new["niche"], "dentists")
                self.assertEqual(len(new["raw_file_sha256"]), 64)
                for v in new.values():
                    self.assertNotIn(SENTINEL, str(v))
            ok = [r for r in rebuilt if r["status"] == "OK"]
            self.assertTrue(all(r["names_count"] == 2 for r in ok))

    def test_legacy_row_with_missing_corpus_file_stops_the_migration(self):
        with tempfile.TemporaryDirectory() as td:
            legacy = [{"date": "2026-10-08", "engine": "openai", "run_status": "OK", "answer_sha256": "",
                       "answer_chars": "", "answer_text": "public", "tracked_businesses_named_in_text": "",
                       "source_file": "corpus/e1/NB-CZ-API_2026-10-08_segment_dentists_dallas_openai.json"}]
            with self.assertRaises(ValueError):
                dr.migrate_legacy_rows(legacy, "dallas-dentists", td)

    def test_legacy_row_disagreeing_with_its_corpus_file_stops_the_migration(self):
        with tempfile.TemporaryDirectory() as td:
            p = corpus_file(td, "2026-10-08", "dentists", "Dallas TX", "openai")
            legacy = [{"date": "2026-10-09", "engine": "openai", "run_status": "OK", "answer_sha256": "",
                       "answer_chars": "", "answer_text": "public", "tracked_businesses_named_in_text": "",
                       "source_file": p.relative_to(td).as_posix()}]
            with self.assertRaises(ValueError):
                dr.migrate_legacy_rows(legacy, "dallas-dentists", td)


if __name__ == "__main__":
    unittest.main(verbosity=2)
