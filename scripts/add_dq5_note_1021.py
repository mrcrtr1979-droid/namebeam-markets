#!/usr/bin/env python3
"""add_dq5_note_1021.py [FABLE-CREDIT 2026-10-21]: the record pages built 2026-10-09 count extracted business lists while the
namebeam.ai market pages count names found in the answer text. Until these pages are rebuilt from one generator, every page
stamped "Page built 2026-10-09" that carries a numbers table gets one line beside the numbers naming its rule and DQ-5.
Idempotent. Usage: python3 scripts/add_dq5_note_1021.py  (run from the repo root)"""
import glob, io, os
NOTE = '<p class="pv-note">Counted from the extracted business lists, which under-count plain-text mentions (DQ-5). See the <a href="/method/#dq-5">Method page</a>.</p>'
MARK = '<table class="pv-t">'
n_done = n_skip = 0
for p in glob.glob('record/**/index.html', recursive=True):
    t = open(p, encoding='utf-8').read()
    if 'Page built 2026-10-09' not in t or MARK not in t or NOTE in t:
        n_skip += 1; continue
    i = t.index(MARK)
    open(p, 'w', encoding='utf-8', newline='').write(t[:i] + NOTE + t[i:])
    n_done += 1
print('noted', n_done, 'skipped', n_skip)
