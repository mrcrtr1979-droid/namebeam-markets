#!/usr/bin/env python3
"""gen_record.py  the generator for the record pages (markets.namebeam.ai/record/). Zero model calls. Stdlib only.

History: the record pages were built 2026-10-09 by scripts/gen_preview.py on branch s5b-2-revamp-preview (commit 721f02bc, not on
main), from pinned Edition 1 JSON, counting the extracted business lists. On 2026-10-22 the namebeam.ai market pages moved to the
text-mention rule (namebeam-site PR #62: the explorer's name matching plus the per-word capital check, window per pair from its
first to its last row date). This script rebuilds only record/ on that same rule and window, from the same generator run:

  1. copies the namebeam-site checkout to a temp dir (gen_pages.patch_site writes into its site dir) and runs
     scripts/segment_pages/gen_pages.py there with S2_END / S2_TODAY pinned, S2_EXPLORER_CELLS (the per-name, per-engine counts
     each market page prints) and S2_CELLS_OUT (for every name, the answers the text rule counts and the answers the extracted
     lists counted);
  2. checks that the 27 regenerated market pages are byte-identical to the committed namebeam-site pages (same rule, same
     window, same corpus; exits 1 if not, unless NB_ALLOW_SITE_DIFF=1);
  3. writes record/<slug>/index.html, record/<slug>/<date>/index.html, the CSVs, record/index.html and record/manifest.sha256.
     The text-rule count is the headline number; the extracted-list count is printed beside it with the DQ-5 line.

Usage (from the namebeam-markets root):
  NB_SITE=<namebeam-site checkout> NB_CORPUS=<namebeam-visibility-index>/corpus/e1 NB_END=2026-10-21 NB_TODAY=2026-10-22 \
  NB_BUILD=2026-10-22 python3 -I -B scripts/gen_record.py
The chrome (head, header, footer) is read verbatim from the committed record/index.html, so header and footer edits made by
other PRs are kept. Files are overwritten in place; nothing is deleted (day pages outside the new data are reported, not removed).
"""
import os, sys, re, csv, io, json, html, hashlib, shutil, subprocess, tempfile, datetime, collections

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
SITE = os.environ.get('NB_SITE', '/home/claude/namebeam-site')
CORPUS = os.environ.get('NB_CORPUS', '/home/claude/namebeam-visibility-index/corpus/e1')
END = os.environ.get('NB_END', '')
TODAY = os.environ.get('NB_TODAY', '')
BUILD = os.environ.get('NB_BUILD') or datetime.date.today().isoformat()
if not (END and TODAY):
    sys.exit('set NB_END and NB_TODAY (the S2_END and S2_TODAY of the market-page run being matched)')

ENG = ['openai', 'anthropic', 'perplexity', 'gemini', 'google_serp']
NE = ['openai', 'anthropic', 'perplexity', 'gemini']          # engines the text rule counts (Google search rows are result pages)
ENGL = {'openai': 'OpenAI', 'anthropic': 'Anthropic', 'perplexity': 'Perplexity', 'gemini': 'Gemini', 'google_serp': 'Google search'}
STATUSES = ['OK', 'EXTRACTION_FAILED', 'QUOTA_BLOCKED', 'FAILED']

# ---------- 1. one gen_pages.py run, the same one the market pages come from ----------
tmp = tempfile.mkdtemp(prefix='nb_record_')
site_copy = os.path.join(tmp, 'site')
shutil.copytree(SITE, site_copy, ignore=shutil.ignore_patterns('.git'))
gp, cells_dir, xcells_dir = os.path.join(tmp, 'gp'), os.path.join(tmp, 'cells'), os.path.join(tmp, 'xcells')
env = dict(os.environ, S2_SITE=site_copy, S2_CORPUS=CORPUS, S2_END=END, S2_TODAY=TODAY, S2_CELLS_OUT=cells_dir,
           S2_EXPLORER_CELLS=xcells_dir)
env.pop('S2_COUNT_RULE', None)
env.pop('S2_PATCH_DEVELOPERS', None)
subprocess.check_call([sys.executable, '-I', '-B', os.path.join(SITE, 'scripts', 'segment_pages', 'gen_pages.py'), gp], env=env,
                      stdout=subprocess.DEVNULL)

# ---------- 2. same rule and window as the committed market pages ----------
slugs = sorted(os.path.basename(p)[:-5] for p in os.listdir(os.path.join(gp, 'data', 'e1')) if p.endswith('.json'))
diff = [s for s in slugs if open(os.path.join(gp, s + '.html'), 'rb').read() != open(os.path.join(SITE, s + '.html'), 'rb').read()]
print('market pages byte-identical to namebeam-site:', len(slugs) - len(diff), 'of', len(slugs), ('differ: ' + ', '.join(diff)) if diff else '')
if diff and os.environ.get('NB_ALLOW_SITE_DIFF') != '1':
    sys.exit('the regenerated market pages differ from the committed namebeam-site pages; pin NB_END/NB_TODAY/NB_CORPUS to the run they were built from')

# ---------- text helpers ----------
DASH = {0x2013: '-', 0x2014: '-', 0x2012: '-', 0x2015: '-', 0x2212: '-'}
def clean(s):
    s = str(s).translate(DASH)
    for a, b in (('‘', "'"), ('’', "'"), ('“', '"'), ('”', '"'), (' ', ' ')):
        s = s.replace(a, b)
    return s.strip()
def esc(s):
    return html.escape(clean(s), quote=True).encode('ascii', 'xmlcharrefreplace').decode()
def fmt(n):
    return '{:,}'.format(n)
def day_range(a, b):
    x, y = datetime.date.fromisoformat(a), datetime.date.fromisoformat(b)
    while x <= y:
        yield x.isoformat(); x += datetime.timedelta(days=1)

def w(rel, data):
    full = os.path.join(ROOT, rel)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    if isinstance(data, str):
        data = data.encode('utf-8')
    open(full, 'wb').write(data)
    return data

# ---------- chrome, verbatim from the committed record index ----------
_idx = open(os.path.join(ROOT, 'record', 'index.html'), encoding='utf-8').read()
HEAD = _idx[:_idx.index('<body>')]
BODY_TOP = _idx[_idx.index('<body>'):_idx.index('<main>')]
BODY_END = _idx[_idx.index('</main>'):]
BRAND = 'Namebeam, a Carter Enterprise property. This is the first leg.'
assert BRAND in BODY_END, 'brand line missing from the footer chrome'

def page(rel, title, desc, body):
    h = re.sub(r'<title>.*?</title>', lambda m: '<title>%s</title>' % esc(title), HEAD, count=1, flags=re.S)
    h = re.sub(r'<meta name="description" content="[^"]*">', lambda m: '<meta name="description" content="%s">' % esc(desc), h, count=1)
    w(rel, h + BODY_TOP + '<main>\n' + body + '\n' + BODY_END)

# ---------- load the run ----------
Q = {}
for s in slugs:
    d = json.load(open(os.path.join(gp, 'data', 'e1', s + '.json'), encoding='utf-8'))
    x = json.load(open(os.path.join(xcells_dir, s + '.json'), encoding='utf-8'))
    cl = json.load(open(os.path.join(cells_dir, s + '.json'), encoding='utf-8'))
    assert d['window'] == [x['first'], x['last']], (s, d['window'], x['first'], x['last'])
    eng_of = {r['check_id']: r['engine'] for r in d['rows']}
    text_of = collections.defaultdict(list)       # check_id -> page names whose text the rule finds in that answer
    ext_eng = {}                                   # page name -> extracted-list count per engine
    for c in sorted(x['names'], key=str.lower):
        for cid in cl[c]['text']:
            text_of[cid].append(clean(c))
        ext_eng[clean(c)] = collections.Counter(eng_of[cid] for cid in cl[c]['extracted'])
        tc = collections.Counter(eng_of[cid] for cid in cl[c]['text'])
        assert all(tc[e] == x['names'][c]['eng'][e] for e in NE), (s, c)   # the per-row lists add up to the page's counts
    byd = collections.defaultdict(dict)
    for r in d['rows']:
        m_ = re.search(r'_r(\d+)$', r['check_id'])
        r['_run'] = int(m_.group(1)) if m_ else 1
        r['_names'] = text_of.get(r['check_id'], []) if (r['status'] == 'OK' and r['engine'] in NE) else []
        ex = []
        for n in (r.get('businesses_named') or []):
            n = clean(n)
            if n and n not in ex: ex.append(n)
        r['_ext'] = ex if r['status'] == 'OK' else []
        byd[r['date']].setdefault(r['engine'], []).append(r)
    for dt in byd:
        for e in byd[dt]: byd[dt][e].sort(key=lambda r: r['_run'])
    d['_x'], d['_ext_eng'], d['_byd'], d['_dates'] = x, ext_eng, byd, sorted(byd)
    d['_missing'] = [t for t in day_range(*d['window']) if t not in byd]
    Q[s] = d

def ok_names(rs, key='_names'):
    out = []
    for r in rs:
        if r['status'] == 'OK':
            for n in r[key]:
                if n not in out: out.append(n)
    return out

for s, d in Q.items():
    byd, ch, prev = d['_byd'], {}, None
    for dt in d['_dates']:
        ok = {e for e, rs in byd[dt].items() if e in NE and any(r['status'] == 'OK' for r in rs)}
        if prev is not None:
            pdt, pok = prev
            comp = [e for e in NE if e in ok and e in pok]
            A, B = {}, {}
            for e in comp:
                for n in ok_names(byd[dt][e]): A.setdefault(n, []).append(e)
                for n in ok_names(byd[pdt][e]): B.setdefault(n, []).append(e)
            ch[dt] = {'date': dt, 'prev': pdt, 'engines': comp, 'gap': (datetime.date.fromisoformat(dt) - datetime.date.fromisoformat(pdt)).days,
                      'entered': [(n, A[n]) for n in sorted(set(A) - set(B))], 'dropped': [(n, B[n]) for n in sorted(set(B) - set(A))]}
        prev = (dt, ok)
    d['_changes'] = ch

def title_of(d):
    return '%s, %s' % (clean(d['market']), clean(d['niche']))

# ---------- CSVs ----------
CSV_COLS = ['date', 'question_slug', 'market', 'niche', 'engine', 'run', 'status', 'names_count', 'businesses_named', 'check_id', 'raw_file',
            'raw_file_sha256', 'names_count_extracted_list', 'businesses_named_extracted_list']
MANIFEST = []
def write_csv(rel, data):
    w(rel, data)
    h = hashlib.sha256(data).hexdigest()
    MANIFEST.append((h, '/' + rel))
    return h
def rows_csv(d, rows):
    buf = io.StringIO(); cw = csv.writer(buf, lineterminator='\n'); cw.writerow(CSV_COLS)
    for r in rows:
        cw.writerow([r['date'], d['slug'], clean(d['market']), clean(d['niche']), r['engine'], r['_run'], r['status'], len(r['_names']),
                     '; '.join(r['_names']), r['check_id'], r['file'], r['sha256'], len(r['_ext']), '; '.join(r['_ext'])])
    return buf.getvalue().encode('utf-8')

for s, d in Q.items():
    base = 'record/%s/' % s
    allrows = sorted(d['rows'], key=lambda r: (r['date'], ENG.index(r['engine']), r['_run']))
    d['_all_sha'] = write_csv(base + 'all.csv', rows_csv(d, allrows))
    d['_day_sha'] = {}
    for dt in d['_dates']:
        d['_day_sha'][dt] = write_csv(base + dt + '.csv', rows_csv(d, [r for e in ENG for r in d['_byd'][dt].get(e, [])]))
    buf = io.StringIO(); cw = csv.writer(buf, lineterminator='\n')
    cw.writerow(['date', 'previous_run_day', 'days_apart', 'engines_compared', 'change', 'name', 'engines_naming'])
    for dt in d['_dates']:
        c = d['_changes'].get(dt)
        if not c: continue
        for n, es in c['entered']: cw.writerow([dt, c['prev'], c['gap'], ' '.join(c['engines']), 'entered', n, ' '.join(es)])
        for n, es in c['dropped']: cw.writerow([dt, c['prev'], c['gap'], ' '.join(c['engines']), 'dropped', n, ' '.join(es)])
    d['_chg_sha'] = write_csv(base + 'changes.csv', buf.getvalue().encode('utf-8'))

# ---------- shared bits (prose kept from the 2026-10-09 build) ----------
def chip(status):
    if status is None: return '<span class="pv-chip none">no row</span>'
    return '<span class="pv-chip %s">%s</span>' % (status, esc(status))
def tile(v, l, dd=''):
    return '<div class="pv-tile"><div class="v">%s</div><div class="l">%s</div>%s</div>' % (v, l, ('<div class="d">%s</div>' % dd) if dd else '')
def crumbs(items):
    return '<div class="pv-crumbs">%s</div>' % ' / '.join(('<a href="%s">%s</a>' % (h, esc(t))) if h else '<span>%s</span>' % esc(t) for h, t in items)

AUTHOR = ('<p class="pv-note">Compiled by Terry J Carter, Carter Enterprise LLC. Data window %s to %s. Source files generated %s. '
          'Page built %s. <a href="/method/">Method</a> &middot; <a href="/corrections/">Corrections</a></p>')
def author_line(d):
    return AUTHOR % (d['window'][0], d['window'][1], d['generated'], BUILD)

STATUS_DEF = ('<p class="pv-note">Status words: OK means an answer was logged. QUOTA_BLOCKED means the engine refused the call over its quota. '
              'FAILED means the call did not complete. EXTRACTION_FAILED means the response came back without readable results '
              '(in the logged rows this is Google search pages blocked by a consent wall or captcha). Every status is printed at the same size as the wins.</p>')
NAMES_NOTE = ('<p class="pv-note">Names are shown as extracted from each answer. Some entries are headings or terms, not businesses. '
              'That is a known issue in the Edition 1 files and it is logged on the <a href="/corrections/">corrections page</a>. '
              'A count is not a ranking.</p>')
# the DQ-5 line, beside every table of numbers: the headline rule, then the extracted-list figure printed next to it
RULE_NOTE = ('<p class="pv-note">Counted as named in the answer text, with the homepage explorer\'s name matching plus a capital-letter check, '
             'the rule the namebeam.ai market pages use since 2026-10-22 (window per question: its first to its last row date). '
             'The count from the extracted business lists is printed beside each number; the extracted lists under-count plain-text mentions (DQ-5). '
             'Google search rows are result pages and are not counted for names. See the <a href="/method/#dq-5">Method page</a>.</p>')

def eng_status_table(d):
    c = {e: collections.Counter() for e in ENG}
    zt, zx = collections.Counter(), collections.Counter()
    for r in d['rows']:
        c[r['engine']][r['status']] += 1
        if r['status'] == 'OK' and r['engine'] in NE:
            if not r['_names']: zt[r['engine']] += 1
            if not r['_ext']: zx[r['engine']] += 1
    h = ('<div class="pv-scroll">' + RULE_NOTE + '<table class="pv-t"><tr><th>Engine</th>' + ''.join('<th>%s</th>' % s for s in STATUSES) +
         '<th>OK, 0 names</th><th>OK, 0 names, extracted list</th><th>Rows</th></tr>')
    for e in ENG:
        z = ('<td class="n">%d</td><td class="n">%d</td>' % (zt[e], zx[e])) if e in NE else '<td class="n">n/a</td><td class="n">n/a</td>'
        h += '<tr><td>%s</td>' % ENGL[e] + ''.join('<td class="n">%d</td>' % c[e][s] for s in STATUSES) + z + '<td class="n">%d</td></tr>' % sum(c[e].values())
    return h + '</table></div>'

def top_names(d, limit=15):
    x = d['_x']
    tot = {clean(c): sum(v['eng'][e] for e in NE) for c, v in x['names'].items()}
    eng = {clean(c): v['eng'] for c, v in x['names'].items()}
    top = sorted([n for n in tot if tot[n] >= 2], key=lambda n: (-tot[n], n.lower()))[:limit]
    return top, eng

def names_table(d):
    x = d['_x']; n_ok = x['n_ok']
    top, eng = top_names(d)
    h = '<div class="pv-scroll">' + RULE_NOTE + '<table class="pv-t"><tr><th>Name as written</th>' + ''.join('<th>%s</th>' % ENGL[e] for e in NE) + '</tr>'
    h += '<tr><td><i>OK answers in window</i></td>' + ''.join('<td class="n">%d</td>' % n_ok[e] for e in NE) + '</tr>'
    for n in top:
        h += '<tr><td>%s</td>' % esc(n) + ''.join('<td class="n">%d of %d<br><span class="pv-note">extracted list %d</span></td>' % (eng[n][e], n_ok[e], d['_ext_eng'][n][e]) for e in NE) + '</tr>'
    if not top:
        h += '<tr><td colspan="5">No business was named in at least two answers.</td></tr>'
    return h + '</table></div>'

def history_matrix(d):
    h = '<div class="pv-scroll"><table class="pv-t"><tr><th>Date</th>' + ''.join('<th>%s</th>' % ENGL[e] for e in ENG) + '</tr>'
    for dt in sorted(set(d['_dates']) | set(d['_missing']), reverse=True):
        if dt not in d['_byd']:
            h += '<tr><td>%s</td><td colspan="5"><span class="pv-chip none">no rows logged for this day</span></td></tr>' % dt; continue
        cells = ''
        for e in ENG:
            rs = d['_byd'][dt].get(e, [])
            if not rs: cells += '<td>%s</td>' % chip(None); continue
            def one(r):
                if r['status'] != 'OK': return chip(r['status'])
                if e not in NE: return chip('OK')
                return '%s <span class="pv-note">%d names, extracted list %d</span>' % (chip('OK'), len(r['_names']), len(r['_ext']))
            cells += '<td>' + '<br>'.join(one(r) for r in rs) + '</td>'
        h += '<tr><td><a href="/record/%s/%s/">%s</a></td>%s</tr>' % (d['slug'], dt, dt, cells)
    return h + '</table></div>'

def change_log_html(d, limit=14):
    h = ''
    for dt in sorted(d['_changes'], reverse=True)[:limit]:
        c = d['_changes'][dt]
        if not c['engines']:
            h += '<tr><td><a href="/record/%s/%s/">%s</a></td><td>%s</td><td colspan="3">Not comparable: no engine answered OK on both days.</td></tr>' % (d['slug'], dt, dt, c['prev'])
            continue
        h += '<tr><td><a href="/record/%s/%s/">%s</a></td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>' % (
            d['slug'], dt, dt, c['prev'], esc(', '.join(ENGL[e] for e in c['engines'])),
            '; '.join(esc(n) for n, _ in c['entered']) or 'none', '; '.join(esc(n) for n, _ in c['dropped']) or 'none')
    return '<div class="pv-scroll"><table class="pv-t"><tr><th>Run day</th><th>Compared with</th><th>Engines compared</th><th>Entered</th><th>Dropped</th></tr>%s</table></div>' % h

def related(d):
    items = [s for s, x in Q.items() if x['market'] == d['market'] and s != d['slug']] + [s for s, x in Q.items() if x['niche'] == d['niche'] and s != d['slug']]
    if not items: return ''
    return '<h2>Related records</h2><div class="pv-rel">%s</div>' % ''.join('<a href="/record/%s/">%s</a>' % (s, esc(title_of(Q[s]))) for s in items[:8])

# ---------- question pages and day pages ----------
for s, d in Q.items():
    c = collections.Counter(r['status'] for r in d['rows'])
    cal = len(list(day_range(*d['window'])))
    last = d['_dates'][-1]
    ws, we = d['window']
    body = ['<div class="pv-wrap">', crumbs([('/', 'Namebeam'), ('/record/', 'The record'), (None, title_of(d))]),
            '<h1>%s</h1>' % esc(title_of(d)),
            '<p>Asked every run day, word for word:</p><div class="pv-q">%s</div>' % esc(d['prompt_verbatim']),
            '<div class="pv-tiles">', tile(fmt(len(d['rows'])), 'rows logged', 'window %s to %s' % (ws, we)),
            tile('%d of %d' % (len(d['_dates']), cal), 'calendar days with rows', 'last row %s' % last)]
    body += [tile(fmt(c[st]), st, 'rows, same window') for st in STATUSES]
    body.append('</div>')
    body.append(STATUS_DEF)
    if d['_missing']:
        body.append('<p class="pv-note">Days in the window with no rows: %s.</p>' % ', '.join(d['_missing']))
    body.append('<h2>Downloads (ungated)</h2><ul>'
                '<li><a href="/record/%s/all.csv">all.csv</a>, every row in the window. SHA-256 %s</li>'
                '<li><a href="/record/%s/changes.csv">changes.csv</a>, who entered and who dropped, every run day. SHA-256 %s</li>'
                '<li>One CSV per day is linked from each day in the table below.</li></ul>'
                '<p>License: CC BY 4.0. Credit: Namebeam (namebeam.ai). Use without credit needs the <a href="/buy/#edition-license">Commercial License</a>.</p>'
                '<p>How to cite: "Namebeam record, %s, window %s to %s, retrieved from namebeam.ai on [date]". Read the <a href="/method/">method</a>. '
                'Pull the same rows by API: <a href="https://api.receiptsindex.com/datasets/">api.receiptsindex.com/datasets</a>.</p>' %
                (s, d['_all_sha'], s, d['_chg_sha'], esc(title_of(d)), ws, we))
    body.append('<h2>By engine</h2>' + eng_status_table(d))
    body.append('<h2>Names by engine, whole window</h2><p class="pv-note">Each cell counts OK answers from that engine that named the entry. The top row is how many OK answers that engine gave.</p>' + names_table(d) + NAMES_NOTE)
    body.append('<h2>Who entered and who dropped</h2><p class="pv-note">Each run day is compared with the previous run day, using the engines that answered OK on both days. One engine skipping a day cannot show up as a drop. The full list is in changes.csv.</p>' + change_log_html(d))
    body.append('<h2>Every run day</h2><p class="pv-note">Newest at the top. Each date opens the day page with the names, the answer hash and a CSV.</p>' + history_matrix(d))
    body.append(related(d))
    body.append(author_line(d))
    body.append('</div>')
    page('record/%s/index.html' % s, '%s, daily record | Namebeam' % title_of(d),
         'Daily record of the businesses AI engines named for: %s. Window %s to %s, per-engine split, CSV per day.' % (d['prompt_verbatim'], ws, we), '\n'.join(body))

    for i, dt in enumerate(d['_dates']):
        prv = d['_dates'][i - 1] if i > 0 else None
        nxt = d['_dates'][i + 1] if i + 1 < len(d['_dates']) else None
        rows = d['_byd'][dt]
        okc = sum(1 for rs in rows.values() if any(r['status'] == 'OK' for r in rs))
        b = ['<div class="pv-wrap">', crumbs([('/', 'Namebeam'), ('/record/', 'The record'), ('/record/%s/' % s, title_of(d)), (None, dt)]),
             '<h1>%s: %s</h1>' % (esc(title_of(d)), dt), '<div class="pv-q">%s</div>' % esc(d['prompt_verbatim']),
             '<div class="pv-tiles">', tile('%d of 5' % okc, 'sources answered OK', 'run day %s' % dt),
             tile(fmt(sum(len(ok_names(rs)) for rs in rows.values())), 'name entries logged', 'all engines, with repeats across engines'),
             tile(fmt(sum(len(ok_names(rs, '_ext')) for rs in rows.values())), 'name entries, extracted list', 'same answers, DQ-5'), '</div>']
        t = ('<div class="pv-scroll">' + RULE_NOTE + '<table class="pv-t"><tr><th>Engine</th><th>Status</th><th>Named in the answer text</th>'
             '<th>Names as extracted</th><th>Raw answer SHA-256</th></tr>')
        for e in ENG:
            rs = rows.get(e, [])
            if not rs:
                t += '<tr><td>%s</td><td>%s</td><td></td><td></td><td></td></tr>' % (ENGL[e], chip(None)); continue
            for r in rs:
                if r['status'] != 'OK': nm = nx = ''
                else:
                    nm = ('; '.join(esc(n) for n in r['_names']) or '<i>0 names</i>') if e in NE else 'n/a'
                    nx = '; '.join(esc(n) for n in r['_ext']) or '<i>0 names extracted</i>'
                lab = ENGL[e] + (' (rerun %d)' % (r['_run'] - 1) if r['_run'] > 1 else '')
                t += '<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td style="word-break:break-all;font-size:11.5px">%s</td></tr>' % (lab, chip(r['status']), nm, nx, esc(r['sha256']))
        b.append(t + '</table></div>')
        c = d['_changes'].get(dt)
        if c and c['engines']:
            b.append('<h2>Changes since %s</h2><p>Compared engines: %s.</p><p><b>Entered:</b> %s</p><p><b>Dropped:</b> %s</p>' % (
                c['prev'], esc(', '.join(ENGL[e] for e in c['engines'])), '; '.join(esc(n) for n, _ in c['entered']) or 'none', '; '.join(esc(n) for n, _ in c['dropped']) or 'none'))
        elif c:
            b.append('<h2>Changes since %s</h2><p>Not comparable: no engine answered OK on both days.</p>' % c['prev'])
        else:
            b.append('<h2>Changes</h2><p>Earliest run day in the window. Nothing to compare.</p>')
        b.append(NAMES_NOTE)
        b.append('<p>This day as a file: <a href="/record/%s/%s.csv">%s.csv</a> (SHA-256 %s). Whole window: <a href="/record/%s/all.csv">all.csv</a>. '
                 'Raw answers sit in the <a href="%s">public corpus</a> under the file names in the CSV.</p>' % (s, dt, dt, d['_day_sha'][dt], s, esc(d['repo'])))
        b.append('<div class="pv-pn"><span>%s</span><span><a href="/record/%s/">All run days</a></span><span>%s</span></div>' % (
            ('<a href="/record/%s/%s/">&larr; %s</a>' % (s, prv, prv)) if prv else '', s, ('<a href="/record/%s/%s/">%s &rarr;</a>' % (s, nxt, nxt)) if nxt else ''))
        b.append(author_line(d)); b.append('</div>')
        page('record/%s/%s/index.html' % (s, dt), '%s, %s | Namebeam record' % (title_of(d), dt),
             'What each AI engine named on %s for: %s' % (dt, d['prompt_verbatim']), '\n'.join(b))

# ---------- record index ----------
markets = sorted({clean(d['market']) for d in Q.values()}); niches = sorted({clean(d['niche']) for d in Q.values()})
cell = {(clean(d['market']), clean(d['niche'])): s for s, d in Q.items()}
g = '<div class="pv-scroll"><table class="pv-t pv-grid"><tr><th>Market</th>' + ''.join('<th>%s</th>' % esc(n) for n in niches) + '</tr>'
for m in markets:
    g += '<tr><td>%s</td>' % esc(m)
    for n in niches:
        s = cell.get((m, n))
        g += ('<td><a href="/record/%s/">Open</a><span class="pv-note">%d rows</span></td>' % (s, len(Q[s]['rows']))) if s else '<td class="e"></td>'
    g += '</tr>'
g += '</table></div>'
lst = '<div class="pv-scroll"><table class="pv-t"><tr><th>Question</th><th>Window</th><th>Rows</th><th>OK</th><th>Not OK</th><th>Last row</th></tr>'
for s, d in sorted(Q.items(), key=lambda kv: title_of(kv[1])):
    c = collections.Counter(r['status'] for r in d['rows'])
    lst += '<tr><td><a href="/record/%s/">%s</a></td><td>%s to %s</td><td class="n">%d</td><td class="n">%d</td><td class="n">%d</td><td>%s</td></tr>' % (
        s, esc(title_of(d)), d['window'][0], d['window'][1], len(d['rows']), c['OK'], len(d['rows']) - c['OK'], d['_dates'][-1])
lst += '</table></div>'
gen = sorted({d['generated'] for d in Q.values()})
body = ('<div class="pv-wrap">' + crumbs([('/', 'Namebeam'), (None, 'The record')]) +
        '<h1>The record: every question, every run day</h1>'
        '<p>Each cell below is a page. Open it to see the daily history, the split by engine, who entered and who dropped, and a free CSV for each day.</p>' +
        g + '<h2>All questions</h2>' + lst +
        '<p class="pv-note">Rows and statuses are counted from the raw answer files in the public corpus, source files generated %s. '
        'Names are counted as named in the answer text, the rule the namebeam.ai market pages use since 2026-10-22, with the extracted-list count beside each number (DQ-5). '
        'A count is not a ranking. <a href="/method/">Method</a> &middot; <a href="/corrections/">Corrections</a>.</p>' % ', '.join(gen) +
        '<h2>Data for every question</h2><p><a href="/record/manifest.sha256">manifest.sha256</a> lists the SHA-256 of every CSV on these pages.</p></div>')
page('record/index.html', 'The record: every question, every run day | Namebeam', 'Market and category grid of the dated record of which businesses AI engines name.', body)

MANIFEST.sort(key=lambda m: m[1])
w('record/manifest.sha256', ''.join('%s  %s\n' % m for m in MANIFEST))

# ---------- sitemap: every regenerated record page listed, lastmod = the build date ----------
SM = os.path.join(ROOT, 'sitemap.xml')
sm = open(SM, encoding='utf-8').read()
want = ['https://markets.namebeam.ai/record/'] + ['https://markets.namebeam.ai/record/%s/' % s for s in Q] + \
       ['https://markets.namebeam.ai/record/%s/%s/' % (s, dt) for s, d in Q.items() for dt in d['_dates']]
wantset = set(want)
def _bump(m):
    return m.group(0) if m.group(1) not in wantset else '<url>\n    <loc>%s</loc>\n    <lastmod>%s</lastmod>\n  </url>' % (m.group(1), BUILD)
sm = re.sub(r'<url>\s*<loc>([^<]+)</loc>\s*<lastmod>[^<]*</lastmod>\s*</url>', _bump, sm)
have = set(re.findall(r'<loc>([^<]+)</loc>', sm))
added = 0
for s, d in Q.items():
    new = ['https://markets.namebeam.ai/record/%s/%s/' % (s, dt) for dt in d['_dates'] if 'https://markets.namebeam.ai/record/%s/%s/' % (s, dt) not in have]
    if not new: continue
    block = ''.join('\n  <url>\n    <loc>%s</loc>\n    <lastmod>%s</lastmod>\n  </url>' % (u, BUILD) for u in new)
    locs = [m for m in re.finditer(r'<loc>https://markets\.namebeam\.ai/record/%s/[^<]*</loc>\s*<lastmod>[^<]*</lastmod>\s*</url>' % re.escape(s), sm)]
    at = locs[-1].end() if locs else sm.rindex('</urlset>')
    sm = sm[:at] + block + sm[at:]
    added += len(new)
open(SM, 'w', encoding='utf-8', newline='\n').write(sm)
print('sitemap: added', added, 'record URLs')

# ---------- report ----------
stale = []
for s, d in Q.items():
    for p in sorted(os.listdir(os.path.join(ROOT, 'record', s))):
        dt = p[:-4] if p.endswith('.csv') else p
        if re.match(r'^\d{4}-\d{2}-\d{2}$', dt) and dt not in d['_byd']:
            stale.append('record/%s/%s' % (s, p))
summary = {'questions': len(Q), 'csvs': len(MANIFEST), 'day_pages': sum(len(d['_dates']) for d in Q.values()), 'stale_not_regenerated': stale,
           'top': {s: (lambda t, e: [t[0], {k: '%d/%d' % (e[t[0]][k], Q[s]['_x']['n_ok'][k]) for k in NE}] if t else None)(*top_names(Q[s])) for s in Q}}
print(json.dumps(summary, indent=1))
shutil.rmtree(tmp, ignore_errors=True)
