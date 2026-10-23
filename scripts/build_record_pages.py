#!/usr/bin/env python3
"""build_record_pages.py  rebuild the record pages (markets.namebeam.ai/record/) on the namebeam.ai market-page counting rule. Zero model calls.

The pages built 2026-10-09 had no generator in any repository (searched 2026-10-21 and 2026-10-23: namebeam-markets, carter-brain,
namebeam-visibility-index, namebeam-site). This script is that generator. It keeps the page layout and prose of the 2026-10-09 pages
and changes the numbers:

  Counting rule  the text-mention rule of the namebeam.ai market pages (namebeam-site scripts/segment_pages/gen_pages.py, S2_COUNT_RULE=text,
                 PR #62): a business counts for an engine on every OK answer whose saved text names it, full name, with the per-word
                 capital-letter check. The names and per-answer hits are read from gen_pages.py itself (S2_EXPLORER_CELLS and S2_CELLS_OUT),
                 so a record page and its market page cannot disagree.
  Window         per question, from its first to its last row date, up to --end (the same window as the market pages).
  Extracted list beside the numbers: the counts on the extracted business lists (gen_pages.py S2_COUNT_RULE=extracted) and the DQ-5 line.

CSV files: rows on or before 2026-10-07 keep every published column unchanged (businesses_named is the 2026-10-08 source list).
Rows after that date carry the extracted list of the market-page generator. Two columns are appended to every row: names_in_text_count,
names_in_text (the counting rule above). changes.csv is recomputed on the counting rule.

Usage (run from the namebeam-markets root):
  python3 -I -B scripts/build_record_pages.py --site <namebeam-site checkout> --corpus <namebeam-visibility-index>/corpus/e1 --end 2026-10-21 \
      --built 2026-10-23 --generated 2026-10-22
Deterministic: a second run with the same inputs changes nothing. Stdlib only."""
import argparse, ast, collections, csv, datetime, glob, hashlib, html, io, json, os, re, shutil, subprocess, sys, tempfile

ap = argparse.ArgumentParser()
ap.add_argument('--site', required=True); ap.add_argument('--corpus', required=True)
ap.add_argument('--end', required=True); ap.add_argument('--built', required=True); ap.add_argument('--generated', required=True)
ap.add_argument('--root', default='.')
A = ap.parse_args()
ROOT = os.path.abspath(A.root); REC = os.path.join(ROOT, 'record')
SEG = os.path.join(os.path.abspath(A.site), 'scripts', 'segment_pages')
CORPUS = os.path.abspath(A.corpus)
OLD_END = '2026-10-07'   # last row date of the 2026-10-09 build; rows on or before it keep their published columns
ENGS = ['openai', 'anthropic', 'perplexity', 'gemini', 'google_serp']
TEXT_ENGS = ['openai', 'anthropic', 'perplexity', 'gemini']
LBL = {'openai': 'OpenAI', 'anthropic': 'Anthropic', 'perplexity': 'Perplexity', 'gemini': 'Gemini', 'google_serp': 'Google search'}
STATUSES = ['OK', 'EXTRACTION_FAILED', 'QUOTA_BLOCKED', 'FAILED']
DASH = re.compile('[\u2013\u2014\u2012\u2015\u2212]')

def esc(s):
    return html.escape(DASH.sub('-', s), quote=True).replace('&#x27;', '&#x27;')
def sha_b(b): return hashlib.sha256(b).hexdigest()
def sha_f(p): return sha_b(open(p, 'rb').read())
def write(p, s):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, 'w', encoding='utf-8', newline='').write(s)
def csv_text(rows):
    s = io.StringIO(); csv.writer(s, lineterminator='\n').writerows(rows); return s.getvalue()

# ---------------------------------------------------------------- 1. the market-page generator, both rules
SEGS = ast.literal_eval(re.search(r'^SEGS = (\[.*?^\])', open(os.path.join(SEG, 'gen_pages.py'), encoding='utf-8').read(), re.S | re.M).group(1))
tmp = tempfile.mkdtemp(prefix='recb_')
def run_gen(rule):
    env = dict(os.environ, S2_COUNT_RULE=rule, S2_CORPUS=CORPUS, S2_END=A.end, S2_TODAY=A.built, PYTHONDONTWRITEBYTECODE='1',
               S2_SITE=os.path.join(tmp, 'no_site'),   # no site checkout: gen_pages.patch_site writes nothing
               S2_EXPLORER_CELLS=os.path.join(tmp, 'cells_' + rule), S2_CELLS_OUT=os.path.join(tmp, 'dump_' + rule))
    subprocess.check_call([sys.executable, '-B', os.path.join(SEG, 'gen_pages.py'), os.path.join(tmp, 'out_' + rule)], env=env,
                          stdout=subprocess.DEVNULL)
    return {os.path.basename(p)[:-5]: json.load(open(p)) for p in glob.glob(os.path.join(tmp, 'cells_' + rule, '*.json'))}
CELLS = run_gen('text')
XCELLS = run_gen('extracted')
DUMP = {os.path.basename(p)[:-5]: json.load(open(p)) for p in glob.glob(os.path.join(tmp, 'dump_text', '*.json'))}

# extracted lists per answer, the market-page generator's extracted rule (names.names_for + the frozen label pass)
sys.path.insert(0, SEG)
os.environ['S2_CORPUS'] = CORPUS; os.environ['S2_END'] = A.end
sys.dont_write_bytecode = True
from names import names_for
from load2 import load_all, urls_of, sk
LABELS = json.load(open(os.path.join(SEG, 'final_labels.json'), encoding='utf-8'))
QUOTE = re.compile('[\u2018\u2019]')
BY = collections.defaultdict(list)
for r in load_all():
    if r.get('row_type') == 'research_segment': BY[sk(r)].append(r)
def extracted_lists(key, rows):
    lab = LABELS.get('|'.join(key), {})
    ok = [r for r in rows if r['run_status'] == 'OK' and r['engine'] in TEXT_ENGS]
    cnt = collections.Counter(t for r in ok for t in set(names_for(r, urls_of(r))) if t not in lab)
    out = {}
    for r in ok:
        s = set()
        for t in names_for(r, urls_of(r)):
            l = lab.get(t)
            if l is None:
                if cnt[t] >= 2: s.add(QUOTE.sub("'", DASH.sub('-', t)))
            elif l[0] == 'B': s.add(QUOTE.sub("'", DASH.sub('-', l[1])))
        out[r['check_id']] = sorted(s)
    return out

# ---------------------------------------------------------------- 2. per question
HDR = ['date', 'question_slug', 'market', 'niche', 'engine', 'run', 'status', 'names_count', 'businesses_named', 'check_id', 'raw_file', 'raw_file_sha256']
NEWCOLS = ['names_in_text_count', 'names_in_text']
def drange(a, b):
    d0, d1 = datetime.date.fromisoformat(a), datetime.date.fromisoformat(b)
    return [str(d0 + datetime.timedelta(i)) for i in range((d1 - d0).days + 1)]
def body(t, a, b): i = t.index(a); return t[i:t.index(b, i)]
def chip(st): return '<span class="pv-chip %s">%s</span>' % (st, st)
def eng_list(es): return ', '.join(LBL[e] for e in es)

SUMMARY = {}
MANIFEST = []
SITEMAP_NEW = []
for spec in SEGS:
    slug, market, niche, prefix = spec[:4]
    d = os.path.join(REC, slug)
    old_index = open(os.path.join(d, 'index.html'), encoding='utf-8').read()
    old_day = open(os.path.join(d, OLD_END, 'index.html'), encoding='utf-8').read()
    keys = [k for k in BY if k[0] == market and k[1] == niche and k[2].startswith(prefix)]
    assert len(keys) == 1, (slug, keys)
    key = keys[0]; prompt = key[2]
    rows = sorted(BY[key], key=lambda r: (r['date_utc'], ENGS.index(r['engine'])))
    cell, xcell, dump = CELLS[slug], XCELLS[slug], DUMP[slug]
    first, last = rows[0]['date_utc'], rows[-1]['date_utc']
    assert (first, last) == (cell['first'], cell['last']), (slug, first, last, cell['first'], cell['last'])
    assert all(r['run_status'] in STATUSES for r in rows), slug
    # names in the answer text, per answer: the names of the market page's table (classified names only), from its own hit list
    text = collections.defaultdict(list)
    for name in sorted(cell['names']):
        for cid in dump[name]['text']: text[cid].append(name)
    for cid in text: text[cid].sort()
    xl = extracted_lists(key, rows)
    # self-checks against the market-page generator
    st = {e: collections.Counter(r['run_status'] for r in rows if r['engine'] == e) for e in ENGS}
    assert {e: st[e]['OK'] for e in TEXT_ENGS} == cell['n_ok'], slug
    rc = collections.defaultdict(collections.Counter)
    for r in rows:
        for n in text.get(r['check_id'], []): rc[n][r['engine']] += 1
    for n, v in cell['names'].items():
        assert {e: rc[n][e] for e in TEXT_ENGS} == v['eng'], (slug, n)
    xc = collections.defaultdict(collections.Counter)
    for r in rows:
        for n in xl.get(r['check_id'], []): xc[n][r['engine']] += 1
    for n, v in xcell['names'].items():
        assert {e: xc[n][e] for e in TEXT_ENGS} == v['eng'], (slug, n, 'extracted')

    # CSV rows
    oldrows = {r['check_id']: r for r in csv.DictReader(open(os.path.join(d, 'all.csv'), encoding='utf-8', newline=''))}
    out = []
    for r in rows:
        cid = r['check_id']
        if r['date_utc'] <= OLD_END:
            o = oldrows[cid]; base = [o[h] for h in HDR]
        else:
            nm = xl.get(cid, []) if r['run_status'] == 'OK' and r['engine'] in TEXT_ENGS else []
            base = [r['date_utc'], slug, market, niche, r['engine'], str(r.get('run') or '1'), r['run_status'], str(len(nm)), '; '.join(nm),
                    cid, r['_file'], sha_f(os.path.join(CORPUS, r['_file']))]
        tn = text.get(cid, []) if r['run_status'] == 'OK' else []
        out.append(base + [str(len(tn)), '; '.join(tn)])
    byday = collections.defaultdict(dict)
    for o in out: byday[o[0]][o[4]] = o
    days = sorted(byday)
    missing = [x for x in drange(first, last) if x not in byday]
    csvs = {}
    csvs['all.csv'] = csv_text([HDR + NEWCOLS] + out)
    for day in days:
        csvs[day + '.csv'] = csv_text([HDR + NEWCOLS] + [byday[day][e] for e in ENGS if e in byday[day]])
    # changes on the counting rule
    def day_names(day, engs):
        m = collections.defaultdict(set)
        for e in engs:
            for n in byday[day][e][13].split('; '):
                if n: m[n].add(e)
        return m
    changes, perday = [], {}
    for p, q in zip(days, days[1:]):
        engs = [e for e in ENGS if byday[p].get(e, [None] * 7)[6] == 'OK' and byday[q].get(e, [None] * 7)[6] == 'OK']
        a, b = day_names(p, engs), day_names(q, engs)
        ent = sorted(set(b) - set(a), key=str.lower); drp = sorted(set(a) - set(b), key=str.lower)
        perday[q] = (p, engs, ent, drp)
        gap = (datetime.date.fromisoformat(q) - datetime.date.fromisoformat(p)).days
        for n in ent: changes.append([q, p, str(gap), ' '.join(engs), 'entered', n, ' '.join(e for e in engs if e in b[n])])
        for n in drp: changes.append([q, p, str(gap), ' '.join(engs), 'dropped', n, ' '.join(e for e in engs if e in a[n])])
    csvs['changes.csv'] = csv_text([['date', 'previous_run_day', 'days_apart', 'engines_compared', 'change', 'name', 'engines_naming']] + changes)
    for fn, s in csvs.items():
        write(os.path.join(d, fn), s)
    H = {fn: sha_b(s.encode('utf-8')) for fn, s in csvs.items()}
    MANIFEST += ['%s  /record/%s/%s' % (H[fn], slug, fn) for fn in csvs]

    # ------------------------------------------------ shared fragments
    head_top = old_index[:old_index.index('<title>')]
    hdr_block = old_index[old_index.index('</head>'):old_index.index('<main>')]
    foot = old_index[old_index.index('</main>'):]
    label = '%s, %s' % (market, niche)
    built = ('<p class="pv-note">Compiled by Terry J Carter, Carter Enterprise LLC. Data window %s to %s. Source files generated %s. Page built %s. '
             '<a href="/method/">Method</a> &middot; <a href="/corrections/">Corrections</a></p>' % (first, last, A.generated, A.built))
    names_note = body(old_index, '<p class="pv-note">Names are shown as extracted', '</p>') + '</p>'
    n_ok = cell['n_ok']
    top = sorted(cell['names'].items(), key=lambda kv: (-sum(kv[1]['eng'].values()), kv[0].lower()))
    def per_eng(eng):
        return ', '.join('%s %d of %d' % (LBL[e], eng.get(e, 0), n_ok[e]) for e in ['perplexity', 'openai', 'anthropic', 'gemini'] if n_ok[e])
    RULE = ('Counting rule: a business counts for an engine when its full name, written with the same capital letters, appears in that '
            'engine\'s saved answer text, the same rule as the market pages on namebeam.ai. Google search rows are results pages and are not '
            'counted by this rule.')
    if top:
        tn = top[0][0]
        xe = xcell['names'].get(tn, {}).get('eng', {})
        XLINE = ('On the extracted business lists, which under-count plain-text mentions (DQ-5), %s reads %s; under the counting rule it reads %s. '
                 'See the <a href="/method/#dq-5">Method page</a>.' % (esc(tn), per_eng(xe), per_eng(top[0][1]['eng'])))
    else:
        XLINE = 'The extracted business lists under-count plain-text mentions (DQ-5). See the <a href="/method/#dq-5">Method page</a>.'
    NOTE = '<p class="pv-note">%s %s</p>' % (RULE, XLINE)
    DAYNOTE = ('<p class="pv-note">%s Names in the answer text are counted on that rule. Names as extracted are the extracted business list, '
               'which under-counts plain-text mentions (DQ-5). See the <a href="/method/#dq-5">Method page</a>.</p>' % RULE)

    # ------------------------------------------------ question page
    tot = collections.Counter(o[6] for o in out)
    L = [head_top, '<title>%s, daily record | Namebeam</title>\n' % esc(label),
         '<meta name="description" content="Daily record of the businesses AI engines named for: %s. Window %s to %s, per-engine split, CSV per day.">\n' % (esc(prompt), first, last),
         '<link rel="stylesheet" href="/site.css">\n', hdr_block, '<main>\n<div class="pv-wrap">\n']
    L.append('<div class="pv-crumbs"><a href="/">Namebeam</a> / <a href="/record/">The record</a> / <span>%s</span></div>\n' % esc(label))
    L.append('<h1>%s</h1>\n' % esc(label))
    L.append('<p>Asked every run day, word for word:</p><div class="pv-q">%s</div>\n' % esc(prompt))
    L.append('<div class="pv-tiles">\n')
    L.append('<div class="pv-tile"><div class="v">%d</div><div class="l">rows logged</div><div class="d">window %s to %s</div></div>\n' % (len(out), first, last))
    L.append('<div class="pv-tile"><div class="v">%d of %d</div><div class="l">calendar days with rows</div><div class="d">last row %s</div></div>\n' % (len(days), len(drange(first, last)), last))
    for s in STATUSES:
        L.append('<div class="pv-tile"><div class="v">%d</div><div class="l">%s</div><div class="d">rows, same window</div></div>\n' % (tot[s], s))
    L.append('</div>\n')
    L.append(body(old_index, '<p class="pv-note">Status words:', '</p>') + '</p>\n')
    L.append('<p class="pv-note">Days in the window with no rows: %s.</p>\n' % (', '.join(missing) if missing else 'none'))
    L.append('<h2>Downloads (ungated)</h2><ul><li><a href="/record/%s/all.csv">all.csv</a>, every row in the window. SHA-256 %s</li>'
             '<li><a href="/record/%s/changes.csv">changes.csv</a>, who entered and who dropped, every run day. SHA-256 %s</li>'
             '<li>One CSV per day is linked from each day in the table below.</li></ul>' % (slug, H['all.csv'], slug, H['changes.csv']))
    L.append(body(old_index, '<p>License: CC BY 4.0.', '</p>') + '</p>')
    cite = body(old_index, '<p>How to cite:', '</p>') + '</p>'
    L.append(re.sub(r'window \d{4}-\d\d-\d\d to \d{4}-\d\d-\d\d', 'window %s to %s' % (first, last), cite) + '\n')
    L.append('<h2>By engine</h2><div class="pv-scroll">' + NOTE + '<table class="pv-t"><tr><th>Engine</th>' + ''.join('<th>%s</th>' % s for s in STATUSES) +
             '<th>OK, 0 names</th><th>Rows</th></tr>')
    for e in ENGS:
        z = sum(1 for o in out if o[4] == e and o[6] == 'OK' and o[12] == '0')
        L.append('<tr><td>%s</td>%s<td class="n">%d</td><td class="n">%d</td></tr>' % (LBL[e], ''.join('<td class="n">%d</td>' % st[e][s] for s in STATUSES), z, sum(st[e].values())))
    L.append('</table></div>\n')
    L.append('<h2>Names by engine, whole window</h2><p class="pv-note">Each cell counts OK answers from that engine that named the entry. The top row is how many OK answers that engine gave.</p>'
             '<div class="pv-scroll"><table class="pv-t"><tr><th>Name as written</th>' + ''.join('<th>%s</th>' % LBL[e] for e in ENGS) + '</tr>')
    L.append('<tr><td><i>OK answers in window</i></td>' + ''.join('<td class="n">%d</td>' % st[e]['OK'] for e in ENGS) + '</tr>')
    for n, v in top[:15]:
        L.append('<tr><td>%s</td>%s<td class="n">0</td></tr>' % (esc(n), ''.join('<td class="n">%d</td>' % v['eng'].get(e, 0) for e in TEXT_ENGS)))
    L.append('</table></div>' + names_note + '\n')
    L.append('<h2>Who entered and who dropped</h2>' + body(old_index, '<p class="pv-note">Each run day is compared', '</p>') + '</p>' +
             '<div class="pv-scroll"><table class="pv-t"><tr><th>Run day</th><th>Compared with</th><th>Engines compared</th><th>Entered</th><th>Dropped</th></tr>')
    for q in [x for x in reversed(days) if x in perday][:14]:
        p, engs, ent, drp = perday[q]
        L.append('<tr><td><a href="/record/%s/%s/">%s</a></td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>' % (
            slug, q, q, p, eng_list(engs), esc('; '.join(ent)) if ent else 'none', esc('; '.join(drp)) if drp else 'none'))
    L.append('</table></div>\n')
    L.append('<h2>Every run day</h2><p class="pv-note">Newest at the top. Each date opens the day page with the names, the answer hash and a CSV.</p>'
             '<div class="pv-scroll"><table class="pv-t"><tr><th>Date</th>' + ''.join('<th>%s</th>' % LBL[e] for e in ENGS) + '</tr>')
    for day in reversed(days):
        cells_ = []
        for e in ENGS:
            o = byday[day].get(e)
            if o is None: cells_.append('<td></td>')
            elif o[6] == 'OK': cells_.append('<td>%s <span class="pv-note">%s names</span></td>' % (chip('OK'), o[12]))
            else: cells_.append('<td>%s</td>' % chip(o[6]))
        L.append('<tr><td><a href="/record/%s/%s/">%s</a></td>%s</tr>' % (slug, day, day, ''.join(cells_)))
    L.append('</table></div>\n')
    if '<h2>Related records</h2>' in old_index:
        L.append(body(old_index, '<h2>Related records</h2>', '\n<p class="pv-note">Compiled') + '\n')
    L.append(built + '\n</div>\n')
    L.append(foot)
    write(os.path.join(d, 'index.html'), ''.join(L))

    # ------------------------------------------------ day pages
    dhead_top = old_day[:old_day.index('<title>')]
    dhdr = old_day[old_day.index('</head>'):old_day.index('<main>')]
    dfoot = old_day[old_day.index('</main>'):]
    file_tail = body(old_day, ' Whole window:', '</p>') + '</p>'
    for i, day in enumerate(days):
        new = not os.path.exists(os.path.join(d, day, 'index.html'))
        if new: SITEMAP_NEW.append('https://markets.namebeam.ai/record/%s/%s/' % (slug, day))
        dr = [byday[day][e] for e in ENGS if e in byday[day]]
        L = [dhead_top, '<title>%s, %s | Namebeam record</title>\n' % (esc(label), day),
             '<meta name="description" content="What each AI engine named on %s for: %s">\n' % (day, esc(prompt)),
             '<link rel="stylesheet" href="/site.css">\n', dhdr, '<main>\n<div class="pv-wrap">\n']
        L.append('<div class="pv-crumbs"><a href="/">Namebeam</a> / <a href="/record/">The record</a> / <a href="/record/%s/">%s</a> / <span>%s</span></div>\n' % (slug, esc(label), day))
        L.append('<h1>%s: %s</h1>\n<div class="pv-q">%s</div>\n' % (esc(label), day, esc(prompt)))
        L.append('<div class="pv-tiles">\n<div class="pv-tile"><div class="v">%d of %d</div><div class="l">sources answered OK</div><div class="d">run day %s</div></div>\n' % (
            sum(1 for o in dr if o[6] == 'OK'), len(dr), day))
        L.append('<div class="pv-tile"><div class="v">%d</div><div class="l">name entries logged</div><div class="d">all engines, with repeats across engines</div></div>\n</div>\n' % sum(int(o[12]) for o in dr))
        L.append('<div class="pv-scroll">' + DAYNOTE + '<table class="pv-t"><tr><th>Engine</th><th>Status</th><th>Names in the answer text</th><th>Names as extracted</th><th>Raw answer SHA-256</th></tr>')
        for o in dr:
            if o[6] == 'OK':
                tcell = esc(o[13]) if o[13] else '<i>0 names in the answer text</i>' if o[4] != 'google_serp' else '<i>not counted, results page</i>'
                xcell_ = esc(o[8]) if o[8] else '<i>0 names extracted</i>'
            else:
                tcell = xcell_ = ''
            L.append('<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td style="word-break:break-all;font-size:11.5px">%s</td></tr>' % (LBL[o[4]], chip(o[6]), tcell, xcell_, o[11]))
        L.append('</table></div>\n')
        if day in perday:
            p, engs, ent, drp = perday[day]
            L.append('<h2>Changes since %s</h2><p>Compared engines: %s.</p><p><b>Entered:</b> %s</p><p><b>Dropped:</b> %s</p>\n' % (
                p, eng_list(engs), esc('; '.join(ent)) if ent else 'none', esc('; '.join(drp)) if drp else 'none'))
        else:
            L.append('<h2>Changes</h2><p>Earliest run day in the window. Nothing to compare.</p>\n')
        L.append(names_note + '\n')
        L.append('<p>This day as a file: <a href="/record/%s/%s.csv">%s.csv</a> (SHA-256 %s).%s\n' % (slug, day, day, H[day + '.csv'], file_tail))
        prv = '<a href="/record/%s/%s/">&larr; %s</a>' % (slug, days[i - 1], days[i - 1]) if i else ''
        nxt = '<a href="/record/%s/%s/">%s &rarr;</a>' % (slug, days[i + 1], days[i + 1]) if i + 1 < len(days) else ''
        L.append('<div class="pv-pn"><span>%s</span><span><a href="/record/%s/">All run days</a></span><span>%s</span></div>\n' % (prv, slug, nxt))
        L.append(built + '\n</div>\n' + dfoot)
        write(os.path.join(d, day, 'index.html'), ''.join(L))
    SUMMARY[slug] = {'first': first, 'last': last, 'rows': len(out), 'ok': tot['OK'], 'top': top[0][0] if top else None,
                     'text': top[0][1]['eng'] if top else {}, 'extracted': xcell['names'].get(top[0][0], {}).get('eng', {}) if top else {}, 'n_ok': n_ok}

# ---------------------------------------------------------------- 3. hub, manifest, sitemap
hub_p = os.path.join(REC, 'index.html'); hub = open(hub_p, encoding='utf-8').read()
for slug, s in SUMMARY.items():
    hub, k = re.subn(r'(<a href="/record/%s/">Open</a><span class="pv-note">)\d+( rows</span>)' % re.escape(slug), r'\g<1>%d\g<2>' % s['rows'], hub); assert k == 1, slug
    hub, k = re.subn(r'(<td><a href="/record/%s/">[^<]*</a></td><td>)[^<]*(</td><td class="n">)\d+(</td><td class="n">)\d+(</td><td class="n">)\d+(</td><td>)[^<]*(</td>)' % re.escape(slug),
                     lambda m: '%s%s to %s%s%d%s%d%s%d%s%s%s' % (m.group(1), s['first'], s['last'], m.group(2), s['rows'], m.group(3), s['ok'], m.group(4), s['rows'] - s['ok'], m.group(5), s['last'], m.group(6)), hub)
    assert k == 1, slug
hub = re.sub(r'source files generated \d{4}-\d\d-\d\d', 'source files generated %s' % A.generated, hub)
write(hub_p, hub)
write(os.path.join(REC, 'manifest.sha256'), '\n'.join(sorted(MANIFEST, key=lambda l: l.split('  ')[1])) + '\n')
sm_p = os.path.join(ROOT, 'sitemap.xml'); sm = open(sm_p, encoding='utf-8').read()
have = set(re.findall(r'<loc>([^<]+)</loc>', sm))
add = [u for u in sorted(SITEMAP_NEW) if u not in have]
# every record URL was rebuilt: its lastmod becomes the build date; new day pages are added in the same entry format
sm = re.sub(r'(<loc>https://markets\.namebeam\.ai/record/[^<]*</loc>\s*<lastmod>)\d{4}-\d\d-\d\d(</lastmod>)', r'\g<1>%s\g<2>' % A.built, sm)
if add:
    i = sm.rindex('</urlset>')
    block = ''.join('  <url>\n    <loc>%s</loc>\n    <lastmod>%s</lastmod>\n  </url>\n' % (u, A.built) for u in add)
    sm = sm[:i] + block + sm[i:]
write(sm_p, sm)
json.dump(SUMMARY, open(os.path.join(tmp, 'summary.json'), 'w'), indent=1, sort_keys=True)
print('rebuilt %d questions, window end %s, %d new day pages, summary %s' % (len(SUMMARY), A.end, len(SITEMAP_NEW), os.path.join(tmp, 'summary.json')))
c = SUMMARY.get('chicago-personal-injury')
if c: print('chicago-personal-injury', c['first'], c['last'], c['top'], 'text', c['text'], 'extracted', c['extracted'], 'n_ok', c['n_ok'])
