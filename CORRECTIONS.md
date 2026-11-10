# Corrections to the markets.namebeam.ai record

Rows are added at the bottom and never edited or removed. One row per dated change to a published
record file or to the rule that writes it: the date (UTC), which files or rows, what was wrong or what
changed, what was done, and the commit. The public corpus in namebeam-visibility-index (corpus/e1) is
never changed by a correction; a correction states a limit or changes a build rule from a stated date
forward. Format: date_utc | files or rows | what changed and why | action | commit

| date_utc | files or rows | what changed and why | action | commit |
|---|---|---|---|---|
| 2026-11-10 | record/dallas-dentists, dallas-orthodontists, atlanta-dentists, atlanta-orthodontists, phoenix-dentists, phoenix-orthodontists: rows.csv and summary.json (6 markets, 408 rows, 2026-10-08 to 2026-10-24) | These six record pages were built by a lane in an earlier CSV schema (date, engine, run_status, answer_sha256, answer_chars, answer_text, tracked_businesses_named_in_text, source_file). answer_text held only the literal placeholder "public" and answer_sha256 and answer_chars were empty in every row. The markets had no entry in roster/segment_pages.json, so tools/daily_refresh.py skipped them and their pages froze at 2026-10-24 while the corpus kept collecting daily; the first mapping attempt (nvi PR #77, 2026-11-10) failed because the refresher could not write the older header. | Each legacy row was rebuilt from the same public corpus file named in its source_file, through the same parser the daily refresh uses, into the current schema (date, question_slug, market, niche, engine, run, status, names_count, businesses_named, check_id, raw_file, raw_file_sha256). Same dates, engines and statuses; the count columns now follow the current method (competitors_mentioned) instead of the earlier tracked-domain list, so the two series are not pooled across 2026-10-24. Rows from 2026-10-25 on come from the corpus with their own dates. The refresher now reports and skips any remaining legacy market instead of stopping (tools/daily_refresh.py, tools/test_daily_refresh_schema.py). No row was invented or back-dated. | lb29/frozen-markets |
