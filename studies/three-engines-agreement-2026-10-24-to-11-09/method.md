# Method

## Row selection
- Corpus: github.com/mrcrtr1979-droid/namebeam-visibility-index, corpus/e1/
- Row type: research_segment (local-business questions)
- Engines: openai, gemini, anthropic ONLY. Perplexity excluded per the record's rights rule.
- Run: 1 only (no reruns)
- Status: OK for measures
- Date window: 2026-10-24 to 2026-11-09
- Model filter (headline): stable served models from 2026-10-24 onward:
  - openai: gpt-5-mini-2025-08-07
  - anthropic: anthropic.claude-haiku-4-5-20251001-v1:0
  - gemini: gemini-3.5-flash-lite

## Name extraction
- Method: orthographic (capitalisation), scripts/extract_entities_orthographic.py
- Matching: canonical form equality (scripts/extract_named_entities.canonical)
- Generic filter: names seen in >= 5 distinct niches dropped (platforms/terms)

## Exclusions
- Perplexity files: never opened (rights rule)
- Reruns: excluded
- Non-OK rows: excluded from measures
- Generic names: filtered as above

## Measures
- F1 (agreement): for each question-day with 2+ engines OK, check each engine pair for shared names
  - Reported: any-pair share with Wilson 95% CI
  - Each pair separately
  - All-three share (when all 3 engines answered OK)
  - Headline restricted to stable models and date window
  - Unrestricted count also reported
  - Denominators: engine pairs (each question-day contributes 1, 2, or 3 pairs depending on engines OK), question-days, questions, run days
- F2 (day-over-day stability): within one engine, one question, one served model, consecutive calendar days
  - Share of days where the set of names changed
  - Mean Jaccard per engine

## Formulas
- Wilson 95% CI: standard Wilson score interval, z=1.96
- Jaccard: |A intersect B| / |A union B|

## Limits
Three engines only (ChatGPT, Gemini, Claude). Stable served models. Local-business questions only.
Counts, not causes. Names extracted mechanically; errors run toward under-counting agreement, so true
agreement likely higher than reported. Generic filter may miss some platforms. Perplexity excluded
under rights rule. No ranking or outcome claims.
