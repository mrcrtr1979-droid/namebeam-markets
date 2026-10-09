#!/usr/bin/env python3
"""S5b-2 revamp preview generator. Reads namebeam-site chrome + Edition 1 data, writes preview/ tree.
Run: python3 gen_preview.py   (idempotent: wipes OUT first)"""
import json, glob, os, re, csv, io, hashlib, html, collections, datetime, shutil, sys

SITE = '/home/claude/namebeam-site'
OUT = '/home/claude/namebeam-markets/preview'
BUILD = '2026-10-09'
STRIPE_PACK = 'https://buy.stripe.com/28EaEX8Bm0SB5eE4hadIA0T'
PENDING = '#PAYMENT_LINK_PENDING'
P = '/preview'
# Corpus link stays hidden until the Edition 1 release on 2026-10-15 (D3 audit, COS STRATEGIC_PLAN_1009B move 2). Flip to True at go-live.
CORPUS_PUBLIC = False
CORPUS_HIDDEN_TXT = 'The raw answer files are released with Edition 1 on 2026-10-15.'
MAKERS_URL = 'https://shop.namebeam.ai/'
FLAGSHIPS_URL = 'https://terryjcarter7.gumroad.com/'

ENG = ['openai', 'anthropic', 'perplexity', 'gemini', 'google_serp']
ENGL = {'openai': 'OpenAI', 'anthropic': 'Anthropic', 'perplexity': 'Perplexity', 'gemini': 'Gemini', 'google_serp': 'Google search'}
STATUSES = ['OK', 'EXTRACTION_FAILED', 'QUOTA_BLOCKED', 'FAILED']

# ---------- text helpers ----------
DASH = {0x2013: '-', 0x2014: '-', 0x2012: '-', 0x2015: '-', 0x2212: '-'}
def clean(s):
    s = str(s).translate(DASH)
    for a, b in (('‘', "'"), ('’', "'"), ('“', '"'), ('”', '"'), (' ', ' ')):
        s = s.replace(a, b)
    return s.strip()
def esc(s):
    return html.escape(clean(s), quote=True).encode('ascii', 'xmlcharrefreplace').decode()

def w(path, text, binary=False):
    full = os.path.join(OUT, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    if binary:
        open(full, 'wb').write(text)
    else:
        open(full, 'w', encoding='utf-8', newline='\n').write(text)

# ---------- chrome from the live home (verbatim) ----------
src = open(SITE + '/index.html', encoding='utf-8').read()
STYLE = re.search(r'<style>(.*?)</style>', src, re.S).group(1)
FOOTER = re.search(r'<footer class="ce-foot">.*?</footer>', src, re.S).group(0)
FOOTER = FOOTER.replace('href="/company"', 'href="https://namebeam.ai/company"')
# R63 / NAV AND LEG RULES: the parked legs stay one footer link away.
_tl = re.search(r'<a href="https://api.receiptsindex.com"[^>]*>RECEIPTS API</a>', FOOTER)
assert _tl, 'footer RECEIPTS API link not found'
if "MAKER'S RECEIPT" not in FOOTER:
    FOOTER = FOOTER.replace(_tl.group(0), _tl.group(0) + '\n      <a href="%s" target="_blank" rel="noopener">MAKER\'S RECEIPT TEES</a>\n      <a href="%s" target="_blank" rel="noopener">CARTER FLAGSHIPS</a>' % (MAKERS_URL, FLAGSHIPS_URL), 1)
LOGO = 'https://namebeam.ai/logo_namebeam_avatar.png'

EXTRA_CSS = """
/* S5b-2 preview components */
.pv-banner{background:#0e2140;border-bottom:1px solid #E3B341;color:#F6F8FC;text-align:center;font-size:13px;padding:7px 12px}
.pv-wrap{max-width:1040px;margin:0 auto;padding:22px 20px 40px}
.pv-crumbs{font-size:13px;color:var(--muted);margin-bottom:14px}
.pv-crumbs a{margin-right:4px}
.pv-wrap h1{font-size:clamp(1.5rem,4vw,2.2rem);line-height:1.2;color:#F6F8FC;margin:6px 0 10px;text-wrap:balance}
.pv-wrap h2{font-size:21px;color:#F6F8FC;margin:30px 0 8px}
.pv-wrap h3{font-size:17px;color:#F6F8FC;margin:0 0 4px}
.pv-wrap p,.pv-wrap li{color:#dbe6f7;max-width:780px}
.pv-wrap p{margin-bottom:10px}
.pv-wrap p,.pv-wrap li{overflow-wrap:anywhere}
.pv-wrap ul{margin:6px 0 12px 20px}
.pv-q{border-left:3px solid #E3B341;padding:6px 14px;color:#F6F8FC;font-style:italic;margin:8px 0 14px;max-width:780px}
.pv-tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin:14px 0 6px}
.pv-tile{background:#0e2140;border:1px solid var(--line);border-radius:12px;padding:14px 16px}
.pv-tile .v{font-size:clamp(1.5rem,4vw,2rem);font-weight:800;color:#E3B341;line-height:1.1}
.pv-tile .l{font-size:13px;color:#F6F8FC;margin-top:4px}
.pv-tile .d{font-size:11.5px;color:var(--muted);margin-top:2px}
.pv-scroll{overflow-x:auto;margin:8px 0 14px;-webkit-overflow-scrolling:touch}
.pv-t{border-collapse:collapse;width:100%;font-size:13.5px;min-width:560px}
.pv-t th,.pv-t td{border:1px solid var(--line);padding:6px 9px;text-align:left;vertical-align:top;color:#dbe6f7}
.pv-t th{background:#0e2140;color:#F6F8FC;font-weight:700;position:sticky;top:0}
.pv-t td.n{text-align:right;white-space:nowrap}
.pv-chip{display:inline-block;border-radius:6px;padding:1px 7px;font-size:11.5px;font-weight:700;letter-spacing:.02em;border:1px solid var(--line);white-space:nowrap}
.pv-chip.OK{background:#12385a;color:#F6F8FC;border-color:#2c6aa0}
.pv-chip.EXTRACTION_FAILED,.pv-chip.QUOTA_BLOCKED,.pv-chip.FAILED{background:#3a1f26;color:#F6F8FC;border-color:#8a3a4a}
.pv-chip.none{background:transparent;color:var(--muted)}
.pv-note{font-size:12.5px;color:var(--muted);max-width:780px}
.pv-cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:14px;margin:12px 0}
.pv-card{background:#0e2140;border:1px solid var(--line);border-radius:12px;padding:16px 18px}
.pv-card.gold{border-color:#E3B341}
.pv-card .p{font-size:24px;font-weight:800;color:#E3B341;margin:2px 0 6px}
.pv-prod{background:#0e2140;border:1px solid #E3B341;border-radius:12px;padding:20px;margin:18px 0}
.pv-prod .top{display:flex;flex-wrap:wrap;gap:8px 24px;align-items:baseline;justify-content:space-between}
.pv-prod .price{font-size:28px;font-weight:800;color:#E3B341}
.pv-prod .per{font-size:13px;color:var(--muted)}
.pv-cols{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:12px 0}
@media(max-width:700px){.pv-cols{grid-template-columns:1fr}}
.pv-cols h4{font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:#E3B341;margin-bottom:4px}
.pv-facts{font-size:14px;color:#dbe6f7;margin:6px 0 12px}
.pv-facts b{color:#F6F8FC}
.pv-grid td a{display:block}
.pv-grid td.e{background:transparent}
.pv-rel{display:flex;flex-wrap:wrap;gap:8px 16px}
.pv-ent{color:#F6F8FC}
.pv-pn{display:flex;justify-content:space-between;gap:12px;margin:16px 0;font-size:14px}
"""

NAV = ('<a href="%s/record/">The record</a><a href="%s/agencies/">Agencies</a><a href="%s/data/">Data and API</a>'
       '<a class="btn" href="%s/check/" style="padding:8px 14px;margin-left:18px">Free check</a>') % (P, P, P, P)

HEADER = ('<header>\n  <a class="brand" href="%s/" style="text-decoration:none">\n'
          '    <img src="%s" alt="Namebeam emblem" style="height:46px;width:auto;display:block;border-radius:10px">\n'
          '    <div><div class="name">Name<span>beam</span></div><div class="tag">The dated record of who AI names</div></div>\n'
          '  </a>\n  <nav>\n    %s\n  </nav>\n</header>') % (P, LOGO, NAV)

BANNER = '<div class="pv-banner">Preview build %s. Not the live site. Prices are the approved prices; buy buttons go live when the payment links exist.</div>' % BUILD

def page(path, title, desc, body, hero=False):
    doc = ('<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="UTF-8">\n'
           '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
           '<title>%s</title>\n<meta name="description" content="%s">\n'
           '<meta name="robots" content="noindex, nofollow">\n'
           '<link rel="stylesheet" href="/preview/site.css">\n</head>\n<body>\n%s\n%s\n<main>\n%s\n</main>\n\n%s\n</body>\n</html>\n'
           ) % (esc(title), esc(desc), BANNER, HEADER, body, FOOTER)
    w(path, doc)

if os.path.isdir(OUT): shutil.rmtree(OUT)
# ---------- load data ----------
Q = {}
# Record data pinned to namebeam-site af1e9b7e1f (2026-10-08T16:04Z), the data the COS-verified Miami recount used; repoint to the Edition 1 build on 2026-10-14.
E1_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pinned', 'e1_af1e9b7e1f')
for f in sorted(glob.glob(E1_DIR + '/*.json')):
    d = json.load(open(f, encoding='utf-8'))
    Q[d['slug']] = d

def canon_map(d):
    inv = {}
    for c, forms in d.get('name_forms', {}).items():
        for v in forms:
            inv.setdefault(v, c)
    return inv

def day_range(a, b):
    x = datetime.date.fromisoformat(a); y = datetime.date.fromisoformat(b)
    while x <= y:
        yield x.isoformat(); x += datetime.timedelta(days=1)

def enames(rs):
    out = []
    for r in rs:
        if r['status'] == 'OK':
            for n in r['_names']:
                if n not in out: out.append(n)
    return out

for slug, d in Q.items():
    inv = canon_map(d)
    byd = collections.defaultdict(dict)
    for r in d['rows']:
        names = []
        seen = set()
        for n in (r.get('businesses_named') or []):
            c = clean(inv.get(n, n))
            if c and c not in seen:
                seen.add(c); names.append(c)
        r['_names'] = names
        byd[r['date']].setdefault(r['engine'], []).append(r)
        m_ = re.search(r'_r(\d+)$', r['check_id']); r['_run'] = int(m_.group(1)) if m_ else 1
    for dd_ in byd:
        for ee_ in byd[dd_]: byd[dd_][ee_].sort(key=lambda r: r['_run'])
    d['_byd'] = byd
    d['_dates'] = sorted(byd)
    ws, we = d['window']
    d['_missing'] = [x for x in day_range(ws, we) if x not in byd]
    d['_outside'] = [x for x in d['_dates'] if x < ws or x > we]
    # changes
    ch = []
    prev = None
    for dt in d['_dates']:
        ok = {e for e, rs in byd[dt].items() if any(r['status'] == 'OK' for r in rs)}
        if prev is not None:
            pdt, pok = prev
            comp = [e for e in ENG if e in ok and e in pok]
            if comp:
                A = {}; B = {}
                for e in comp:
                    for n in enames(byd[dt][e]): A.setdefault(n, []).append(e)
                    for n in enames(byd[pdt][e]): B.setdefault(n, []).append(e)
                ent = sorted(set(A) - set(B)); drp = sorted(set(B) - set(A))
                ch.append({'date': dt, 'prev': pdt, 'engines': comp, 'entered': [(n, A[n]) for n in ent], 'dropped': [(n, B[n]) for n in drp], 'gap': (datetime.date.fromisoformat(dt) - datetime.date.fromisoformat(pdt)).days})
            else:
                ch.append({'date': dt, 'prev': pdt, 'engines': [], 'entered': [], 'dropped': [], 'gap': (datetime.date.fromisoformat(dt) - datetime.date.fromisoformat(pdt)).days})
        prev = (dt, ok)
    d['_changes'] = {c['date']: c for c in ch}

def title_of(d):
    return '%s, %s' % (clean(d['market']), clean(d['niche']))

def short(d):
    return clean(d['market']) + ' ' + clean(d['niche'])

def counts(d):
    c = collections.Counter(r['status'] for r in d['rows'])
    return c

def fmt(n):
    return '{:,}'.format(n)

# ---------- CSVs ----------
CSV_COLS = ['date', 'question_slug', 'market', 'niche', 'engine', 'run', 'status', 'names_count', 'businesses_named', 'check_id', 'raw_file', 'raw_file_sha256']
def rows_csv(d, rows):
    buf = io.StringIO()
    cw = csv.writer(buf, lineterminator='\n')
    cw.writerow(CSV_COLS)
    for r in rows:
        cw.writerow([r['date'], d['slug'], clean(d['market']), clean(d['niche']), r['engine'], r['_run'], r['status'], len(r['_names']),
                     '; '.join(r['_names']), r['check_id'], r['file'], r['sha256']])
    return buf.getvalue().encode('utf-8')

MANIFEST = []
def write_csv(rel, data):
    w(rel, data, binary=True)
    MANIFEST.append((hashlib.sha256(data).hexdigest(), P + '/' + rel))
    return hashlib.sha256(data).hexdigest()

for slug, d in Q.items():
    base = 'record/%s/' % slug
    allrows = sorted(d['rows'], key=lambda r: (r['date'], ENG.index(r['engine']), r['_run']))
    d['_all_sha'] = write_csv(base + 'all.csv', rows_csv(d, allrows))
    d['_day_sha'] = {}
    for dt in d['_dates']:
        rs = [r for e in ENG for r in d['_byd'][dt].get(e, [])]
        d['_day_sha'][dt] = write_csv(base + dt + '.csv', rows_csv(d, rs))
    # changes csv
    buf = io.StringIO(); cw = csv.writer(buf, lineterminator='\n')
    cw.writerow(['date', 'previous_run_day', 'days_apart', 'engines_compared', 'change', 'name', 'engines_naming'])
    for dt in d['_dates']:
        c = d['_changes'].get(dt)
        if not c: continue
        for n, es in c['entered']: cw.writerow([dt, c['prev'], c['gap'], ' '.join(c['engines']), 'entered', n, ' '.join(es)])
        for n, es in c['dropped']: cw.writerow([dt, c['prev'], c['gap'], ' '.join(c['engines']), 'dropped', n, ' '.join(es)])
    d['_chg_sha'] = write_csv(base + 'changes.csv', buf.getvalue().encode('utf-8'))

# ---------- shared bits ----------
def chip(status):
    if status is None:
        return '<span class="pv-chip none">no row</span>'
    return '<span class="pv-chip %s">%s</span>' % (status, esc(status))

def tile(v, l, dd=''):
    return '<div class="pv-tile"><div class="v">%s</div><div class="l">%s</div>%s</div>' % (v, l, ('<div class="d">%s</div>' % dd) if dd else '')

def crumbs(items):
    out = []
    for h, t in items:
        out.append('<a href="%s">%s</a>' % (h, esc(t)) if h else '<span>%s</span>' % esc(t))
    return '<div class="pv-crumbs">%s</div>' % ' / '.join(out)

AUTHOR = ('<p class="pv-note">Compiled by Terry J Carter, Carter Enterprise LLC. Data window %s to %s. Source files generated %s. '
          'Page built %s. <a href="%s/method/">Method</a> &middot; <a href="%s/corrections/">Corrections</a></p>')

def author_line(d):
    return AUTHOR % (d['window'][0], d['window'][1], d['generated'], BUILD, P, P)

STATUS_DEF = ('<p class="pv-note">Status words: OK means an answer was logged. QUOTA_BLOCKED means the engine refused the call over its quota. '
              'FAILED means the call did not complete. EXTRACTION_FAILED means the response came back without readable results '
              '(in the logged rows this is Google search pages blocked by a consent wall or captcha). Every status is printed at the same size as the wins.</p>')

NAMES_NOTE = ('<p class="pv-note">Names are shown as extracted from each answer. Some entries are headings or terms, not businesses. '
              'That is a known issue in the Edition 1 files and it is logged on the <a href="%s/corrections/">corrections page</a>. '
              'A count is not a ranking.</p>') % P

# ---------- question pages ----------
def eng_status_table(d):
    c = {e: collections.Counter() for e in ENG}
    zero = collections.Counter()
    for r in d['rows']:
        c[r['engine']][r['status']] += 1
        if r['status'] == 'OK' and not r['_names']: zero[r['engine']] += 1
    h = '<div class="pv-scroll"><table class="pv-t"><tr><th>Engine</th>' + ''.join('<th>%s</th>' % s for s in STATUSES) + '<th>OK, 0 names</th><th>Rows</th></tr>'
    for e in ENG:
        tot = sum(c[e].values())
        h += '<tr><td>%s</td>' % ENGL[e] + ''.join('<td class="n">%d</td>' % c[e][s] for s in STATUSES) + '<td class="n">%d</td><td class="n">%d</td></tr>' % (zero[e], tot)
    return h + '</table></div>'

def names_table(d, limit=15):
    okn = collections.Counter()
    cnt = collections.defaultdict(collections.Counter)
    for r in d['rows']:
        if r['status'] != 'OK': continue
        okn[r['engine']] += 1
        for n in r['_names']: cnt[n][r['engine']] += 1
    tot = {n: sum(v.values()) for n, v in cnt.items()}
    top = sorted(tot, key=lambda n: (-tot[n], n))[:limit]
    h = '<div class="pv-scroll"><table class="pv-t"><tr><th>Name as extracted</th>' + ''.join('<th>%s</th>' % ENGL[e] for e in ENG) + '</tr>'
    h += '<tr><td><i>OK answers in window</i></td>' + ''.join('<td class="n">%d</td>' % okn[e] for e in ENG) + '</tr>'
    for n in top:
        h += '<tr><td>%s</td>' % esc(n) + ''.join('<td class="n">%d</td>' % cnt[n][e] for e in ENG) + '</tr>'
    return h + '</table></div>', cnt, okn

def history_matrix(d):
    h = '<div class="pv-scroll"><table class="pv-t"><tr><th>Date</th>' + ''.join('<th>%s</th>' % ENGL[e] for e in ENG) + '</tr>'
    alld = sorted(set(d['_dates']) | set(d['_missing']), reverse=True)
    for dt in alld:
        if dt in d['_byd']:
            cells = ''
            for e in ENG:
                rs = d['_byd'][dt].get(e, [])
                if not rs: cells += '<td>%s</td>' % chip(None)
                else:
                    cells += '<td>' + '<br>'.join(('%s <span class="pv-note">%d names</span>' % (chip('OK'), len(r['_names']))) if r['status'] == 'OK' else chip(r['status']) for r in rs) + '</td>'
            h += '<tr><td><a href="%s/record/%s/%s/">%s</a></td>%s</tr>' % (P, d['slug'], dt, dt, cells)
        else:
            h += '<tr><td>%s</td><td colspan="5"><span class="pv-chip none">no rows logged for this day</span></td></tr>' % dt
    return h + '</table></div>'

def change_log_html(d, limit=14):
    h = ''
    shown = 0
    for dt in sorted(d['_changes'], reverse=True):
        c = d['_changes'][dt]
        if shown >= limit: break
        shown += 1
        eng = ', '.join(ENGL[e] for e in c['engines']) if c['engines'] else 'none'
        if not c['engines']:
            h += '<tr><td><a href="%s/record/%s/%s/">%s</a></td><td>%s</td><td colspan="3">Not comparable: no engine answered OK on both days.</td></tr>' % (P, d['slug'], dt, dt, c['prev'])
            continue
        ent = '; '.join(esc(n) for n, _ in c['entered']) or 'none'
        drp = '; '.join(esc(n) for n, _ in c['dropped']) or 'none'
        h += '<tr><td><a href="%s/record/%s/%s/">%s</a></td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>' % (P, d['slug'], dt, dt, c['prev'], esc(eng), ent, drp)
    return ('<div class="pv-scroll"><table class="pv-t"><tr><th>Run day</th><th>Compared with</th><th>Engines compared</th><th>Entered</th><th>Dropped</th></tr>%s</table></div>' % h)

def related(d):
    same_m = [s for s, x in Q.items() if x['market'] == d['market'] and s != d['slug']]
    same_n = [s for s, x in Q.items() if x['niche'] == d['niche'] and s != d['slug']]
    items = same_m + same_n
    if not items: return ''
    li = ''.join('<a href="%s/record/%s/">%s</a>' % (P, s, esc(title_of(Q[s]))) for s in items[:8])
    return '<h2>Related records</h2><div class="pv-rel">%s</div>' % li

for slug, d in Q.items():
    c = counts(d)
    nd = len(d['_dates'])
    cal = len(list(day_range(*d['window'])))
    ntab, cnt, okn = names_table(d)
    last = d['_dates'][-1]
    body = ['<div class="pv-wrap">', crumbs([(P + '/', 'Namebeam'), (P + '/record/', 'The record'), (None, title_of(d))]),
            '<h1>%s</h1>' % esc(title_of(d)),
            '<p>Asked every run day, word for word:</p><div class="pv-q">%s</div>' % esc(d['prompt_verbatim']),
            '<div class="pv-tiles">',
            tile(fmt(len(d['rows'])), 'rows logged', 'window %s to %s' % (d['window'][0], d['window'][1])),
            tile('%d of %d' % (nd, cal), 'calendar days with rows', 'last row %s' % last)]
    for s in STATUSES:
        body.append(tile(fmt(c[s]), s, 'rows, same window'))
    body.append('</div>')
    body.append(STATUS_DEF)
    if d['_missing']:
        body.append('<p class="pv-note">Days in the window with no rows: %s.</p>' % ', '.join(d['_missing']))
    body.append('<h2>Downloads (ungated)</h2><ul>'
                '<li><a href="%s/record/%s/all.csv">all.csv</a>, every row in the window. SHA-256 %s</li>'
                '<li><a href="%s/record/%s/changes.csv">changes.csv</a>, who entered and who dropped, every run day. SHA-256 %s</li>'
                '<li>One CSV per day is linked from each day in the table below.</li></ul>'
                '<p>License: CC BY 4.0. Credit: Namebeam (namebeam.ai). Use without credit needs the <a href="%s/buy/#edition-license">Commercial License</a>.</p>'
                '<p>How to cite: "Namebeam record, %s, window %s to %s, retrieved from namebeam.ai on [date]". Read the <a href="%s/method/">method</a>. '
                'Pull the same rows by API: <a href="https://api.receiptsindex.com/datasets/">api.receiptsindex.com/datasets</a>.</p>' %
                (P, slug, d['_all_sha'], P, slug, d['_chg_sha'], P, esc(title_of(d)), d['window'][0], d['window'][1], P))
    body.append('<h2>By engine</h2>' + eng_status_table(d))
    body.append('<h2>Names by engine, whole window</h2><p class="pv-note">Each cell counts OK answers from that engine that named the entry. The top row is how many OK answers that engine gave.</p>' + ntab + NAMES_NOTE)
    body.append('<h2>Who entered and who dropped</h2><p class="pv-note">Each run day is compared with the previous run day, using the engines that answered OK on both days. One engine skipping a day cannot show up as a drop. The full list is in changes.csv.</p>' + change_log_html(d))
    body.append('<h2>Every run day</h2><p class="pv-note">Newest at the top. Each date opens the day page with the names, the answer hash and a CSV.</p>' + history_matrix(d))
    body.append(related(d))
    body.append(author_line(d))
    body.append('</div>')
    page('record/%s/index.html' % slug, '%s, daily record | Namebeam' % title_of(d),
         'Daily record of the businesses AI engines named for: %s. Window %s to %s, per-engine split, CSV per day.' % (d['prompt_verbatim'], d['window'][0], d['window'][1]),
         '\n'.join(body))

    # ---- day pages ----
    for i, dt in enumerate(d['_dates']):
        prv = d['_dates'][i - 1] if i > 0 else None
        nxt = d['_dates'][i + 1] if i + 1 < len(d['_dates']) else None
        rows = d['_byd'][dt]
        okc = sum(1 for rs in rows.values() if any(r['status'] == 'OK' for r in rs))
        b = ['<div class="pv-wrap">', crumbs([(P + '/', 'Namebeam'), (P + '/record/', 'The record'), ('%s/record/%s/' % (P, slug), title_of(d)), (None, dt)]),
             '<h1>%s: %s</h1>' % (esc(title_of(d)), dt),
             '<div class="pv-q">%s</div>' % esc(d['prompt_verbatim']),
             '<div class="pv-tiles">', tile('%d of 5' % okc, 'sources answered OK', 'run day %s' % dt),
             tile(fmt(sum(len(enames(rs)) for rs in rows.values())), 'name entries logged', 'all engines, with repeats across engines'), '</div>']
        t = '<div class="pv-scroll"><table class="pv-t"><tr><th>Engine</th><th>Status</th><th>Names as extracted</th><th>Raw answer SHA-256</th></tr>'
        for e in ENG:
            rs = rows.get(e, [])
            if not rs:
                t += '<tr><td>%s</td><td>%s</td><td></td><td></td></tr>' % (ENGL[e], chip(None)); continue
            for r in rs:
                nm = '; '.join(esc(n) for n in r['_names']) if r['status'] == 'OK' else ''
                if r['status'] == 'OK' and not r['_names']: nm = '<i>0 names extracted</i>'
                lab = ENGL[e] + (' (rerun %d)' % (r['_run'] - 1) if r['_run'] > 1 else '')
                t += '<tr><td>%s</td><td>%s</td><td>%s</td><td style="word-break:break-all;font-size:11.5px">%s</td></tr>' % (lab, chip(r['status']), nm, esc(r['sha256']))
        b.append(t + '</table></div>')
        c = d['_changes'].get(dt)
        if c:
            if c['engines']:
                b.append('<h2>Changes since %s</h2><p>Compared engines: %s.</p><p><b>Entered:</b> %s</p><p><b>Dropped:</b> %s</p>' % (
                    c['prev'], esc(', '.join(ENGL[e] for e in c['engines'])), '; '.join(esc(n) for n, _ in c['entered']) or 'none', '; '.join(esc(n) for n, _ in c['dropped']) or 'none'))
            else:
                b.append('<h2>Changes since %s</h2><p>Not comparable: no engine answered OK on both days.</p>' % c['prev'])
        else:
            b.append('<h2>Changes</h2><p>Earliest run day in the window. Nothing to compare.</p>')
        b.append(NAMES_NOTE)
        b.append('<p>This day as a file: <a href="%s/record/%s/%s.csv">%s.csv</a> (SHA-256 %s). Whole window: <a href="%s/record/%s/all.csv">all.csv</a>. '
                 '%s</p>' % (P, slug, dt, dt, d['_day_sha'][dt], P, slug, ('Raw answers sit in the <a href="%s">public corpus</a> under the file names in the CSV.' % esc(d['repo'])) if CORPUS_PUBLIC else CORPUS_HIDDEN_TXT))
        b.append('<div class="pv-pn"><span>%s</span><span><a href="%s/record/%s/">All run days</a></span><span>%s</span></div>' % (
            ('<a href="%s/record/%s/%s/">&larr; %s</a>' % (P, slug, prv, prv)) if prv else '', P, slug,
            ('<a href="%s/record/%s/%s/">%s &rarr;</a>' % (P, slug, nxt, nxt)) if nxt else ''))
        b.append(author_line(d)); b.append('</div>')
        page('record/%s/%s/index.html' % (slug, dt), '%s, %s | Namebeam record' % (title_of(d), dt),
             'What each AI engine named on %s for: %s' % (dt, d['prompt_verbatim']), '\n'.join(b))

# ---------- record index (grid) ----------
markets = sorted({clean(d['market']) for d in Q.values()})
niches = sorted({clean(d['niche']) for d in Q.values()})
cell = {(clean(d['market']), clean(d['niche'])): s for s, d in Q.items()}
g = '<div class="pv-scroll"><table class="pv-t pv-grid"><tr><th>Market</th>' + ''.join('<th>%s</th>' % esc(n) for n in niches) + '</tr>'
for m in markets:
    g += '<tr><td>%s</td>' % esc(m)
    for n in niches:
        s = cell.get((m, n))
        g += ('<td><a href="%s/record/%s/">Open</a><span class="pv-note">%d rows</span></td>' % (P, s, len(Q[s]['rows']))) if s else '<td class="e"></td>'
    g += '</tr>'
g += '</table></div>'
lst = '<div class="pv-scroll"><table class="pv-t"><tr><th>Question</th><th>Window</th><th>Rows</th><th>OK</th><th>Not OK</th><th>Last row</th></tr>'
for s, d in sorted(Q.items(), key=lambda kv: title_of(kv[1])):
    c = counts(d)
    lst += '<tr><td><a href="%s/record/%s/">%s</a></td><td>%s to %s</td><td class="n">%d</td><td class="n">%d</td><td class="n">%d</td><td>%s</td></tr>' % (
        P, s, esc(title_of(d)), d['window'][0], d['window'][1], len(d['rows']), c['OK'], len(d['rows']) - c['OK'], d['_dates'][-1])
lst += '</table></div>'
body = ('<div class="pv-wrap">' + crumbs([(P + '/', 'Namebeam'), (None, 'The record')]) +
        '<h1>The record: every question, every run day</h1>'
        '<p>Each cell below is a page. Open it to see the daily history, the split by engine, who entered and who dropped, and a free CSV for each day.</p>' +
        g + '<h2>All questions</h2>' + lst +
        '<p class="pv-note">Rows and statuses are counted from the Edition 1 files, source files generated 2026-10-08. A count is not a ranking. <a href="%s/method/">Method</a> &middot; <a href="%s/corrections/">Corrections</a>.</p>' % (P, P) +
        '<h2>Data for every question</h2><p><a href="%s/record/manifest.sha256">manifest.sha256</a> lists the SHA-256 of every CSV on these pages.</p></div>' % P)
page('record/index.html', 'The record: every question, every run day | Namebeam', 'Market and category grid of the dated record of which businesses AI engines name.', body)

# ---------- home ----------
def latest_ok(d):
    for dt in reversed(d['_dates']):
        if any(r['status'] == 'OK' for rs in d['_byd'][dt].values() for r in rs): return dt
    return d['_dates'][-1]

def feat_card(slug):
    d = Q[slug]; dt = latest_ok(d)
    h = '<div class="pv-card"><h3>%s</h3><p class="pv-note">Run day %s</p>' % (esc(title_of(d)), dt)
    h += '<div class="pv-scroll"><table class="pv-t" style="min-width:0"><tr><th>Engine</th><th>Status</th><th>Names</th></tr>'
    for e in ENG:
        rs = d['_byd'][dt].get(e, [])
        if not rs: h += '<tr><td>%s</td><td>%s</td><td></td></tr>' % (ENGL[e], chip(None)); continue
        okr = [r for r in rs if r['status'] == 'OK']
        allnm = enames(rs)
        if okr:
            nm = allnm[:3]; more = len(allnm) - len(nm)
            txt = ('; '.join(esc(n) for n in nm) + (' (+%d more)' % more if more > 0 else '')) if nm else '<i>0 names</i>'
            stt = 'OK'
        else: txt = ''; stt = rs[0]['status']
        h += '<tr><td>%s</td><td>%s</td><td>%s</td></tr>' % (ENGL[e], chip(stt), txt)
    h += '</table></div><p><a href="%s/record/%s/%s/">Open this day</a> &middot; <a href="%s/record/%s/">Full history</a></p></div>' % (P, slug, dt, P, slug)
    return h

# Miami receipt, recomputed from the data
mi = Q['miami-roofing']
okp = [r for r in mi['rows'] if r['engine'] == 'perplexity' and r['status'] == 'OK']
cn = collections.Counter(n for r in okp for n in r['_names'])
top, topn = sorted(cn.items(), key=lambda kv: (-kv[1], kv[0]))[0]
oth = [r for r in mi['rows'] if r['engine'] in ('openai', 'anthropic', 'gemini') and r['status'] == 'OK']
othn = sum(1 for r in oth if top in r['_names'])
MIAMI = {'top': top, 'perp_named': topn, 'perp_ok': len(okp), 'oth_named': othn, 'oth_ok': len(oth)}

# Pinned to the 2026-10-08 run (namebeam-site 69d03dfafc) because only VERIFIED NUMBERS may print; repoint on build day after the COS re-pull.
ci = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pinned', 'citation_index_2026-10-08.json')))
CI_TOTAL = ci['gate']['businesses_total']; CI_CORR = ci['gate']['businesses_corroborated']; CI_DATE = ci['generated_utc'][:10]
assert (CI_TOTAL, CI_CORR) == (3208, 1476), (CI_TOTAL, CI_CORR)

home = f'''
<section class="ce-hero">
  <div class="ce-rays"></div>
  <h1 class="nb-h1">The dated record of which businesses AI names.</h1>
  <p class="nb-sub">Every run day we ask four AI engines and Google search the same buyer questions and log what comes back, including the days an engine refuses. Every page shows its dates, its method and a free CSV.</p>
  <p class="nb-slogan">Every claim owes the future a receipt.</p>
  <div class="nb-receipt">
    <div class="nb-rlabel">FROM THE RECORD &middot; {esc(clean(mi['market']).upper())} &middot; {mi['window'][0]} TO {mi['window'][1]}</div>
    <p class="nb-rq">Asked every run day: "{esc(mi['prompt_verbatim'])}"</p>
    <p class="nb-rbig">Perplexity named {esc(MIAMI['top'])} in {MIAMI['perp_named']} of {MIAMI['perp_ok']} answers. OpenAI, Anthropic and Gemini named it in {MIAMI['oth_named']} of {MIAMI['oth_ok']}.</p>
    <p class="nb-rnote">Window {mi['window'][0]} to {mi['window'][1]}, counted from the daily record on {BUILD}. A count, not a ranking. Every name, engine and answer hash is on the Miami page.</p>
    <a href="{P}/record/miami-roofing/">Read the Miami record</a>
  </div>
</section>
<div class="pv-wrap">
  <h2>What AI named on the latest run day</h2>
  <p>Three questions, five sources each, the newest day with an answer. Open any day for the full list, the answer hashes and a CSV.</p>
  <div class="pv-cards">{feat_card('miami-roofing')}{feat_card('kansas-city-health-insurance')}{feat_card('atlanta-hvac')}</div>
  {NAMES_NOTE}
  <div class="pv-tiles">
    {tile(fmt(CI_TOTAL), 'businesses in the citation index', 'as of ' + CI_DATE)}
    {tile(fmt(CI_CORR), 'of them corroborated', 'as of ' + CI_DATE)}
  </div>
  <p class="pv-note">Citation index read from <a href="https://namebeam.ai/data/citation_index.json">namebeam.ai/data/citation_index.json</a>, generated {esc(ci['generated_utc'])}. Corroborated means Perplexity or Google search cited the business, or two or more engines named it. <a href="{P}/method/">Method</a>.</p>

  <h2>Edition 1</h2>
  <div class="pv-prod">
    <div class="top"><h3>Edition 1: the dated record as files, free</h3><div><span class="price">CC BY 4.0</span> <span class="per">free, with credit</span></div></div>
    <p>Raw CSV files for every question and run day in the window 2026-08-05 to 2026-10-07, a SHA-256 manifest, a method note and a verify script, so you can check every file yourself. Planned release: 2026-10-15. Use it with credit to Namebeam at no cost.</p>
    <p>Need to use it without credit, or white-label it in client reports? The Commercial License is $540, paid once. <a href="{P}/buy/#edition-license">See the scope and the price</a>.</p>
  </div>

  <h2>Three paths</h2>
  <div class="pv-cards">
    <div class="pv-card gold"><h3>Agencies</h3><p>Show clients which businesses AI names in their market. The daily record for one market is $49 a month.</p><p><a class="btn" href="{P}/agencies/">For agencies</a></p></div>
    <div class="pv-card gold"><h3>Data buyers and API</h3><p>The free record, a Commercial License, a founding-partner feed and per-call API rows.</p><p><a class="btn" href="{P}/data/">Data and API</a></p></div>
    <div class="pv-card gold"><h3>Business owners</h3><p>See your own record. Free, no card. We do not sell to the businesses we measure.</p><p><a class="btn" href="{P}/check/">Free check</a></p></div>
  </div>
  <p class="pv-note">Browse by market and category: <a href="{P}/record/">the record grid</a>. Corrections are logged in public: <a href="{P}/corrections/">corrections</a>.</p>
</div>
'''
page('index.html', 'The dated record of which businesses AI names | Namebeam', 'Namebeam logs the businesses AI engines name for local buyer questions every run day, with the split by engine, a change log and free CSVs.', home)

# ---------- product data ----------
PRODUCTS = [
 dict(id='market-record', name='Market Record, 1 market', price='$49', per='per market, per month', link='https://buy.stripe.com/7sY28rbNy58RbD25ledIA0V',
      scope='The daily dated record of which businesses AI engines name for one market and one category: who is named, how often, which websites the answers read. A monthly CSV and PDF of the month.',
      notin=['Ranking, traffic or booking promises', 'Changes to any business listing', 'Custom segments (sold separately)', 'Resale of the files'],
      keep='The CSV and PDF files you download. They stay yours after you cancel.', ends='Renews monthly until you cancel.'),
 dict(id='market-record-5', name='Market Record, 5 markets', price='$199', per='per month, founding rate for the first 10 agencies', link='https://buy.stripe.com/14A5kDg3OcBj8qQ3d6dIA0W',
      scope='The same daily dated record as the one-market plan, for five markets of your choice, with a monthly CSV and PDF for each.',
      notin=['Ranking, traffic or booking promises', 'Changes to any business listing', 'Custom segments (sold separately)', 'Resale of the files', 'A sixth market'],
      keep='The CSV and PDF files you download. They stay yours after you cancel.', ends='Renews monthly until you cancel. The founding rate is open to the first 10 agencies.'),
 dict(id='custom-segment', name='Custom segment setup', price='$99', per='one-time setup, plus the monthly Market Record price ($49 a month per segment)', link='https://buy.stripe.com/14AfZheZK9p7dLa3d6dIA0X',
      scope='We set up one segment you name (a market and category pair not already in the record) and add it to the daily record.',
      notin=['The monthly Market Record fee (billed separately)', 'Ranking, traffic or booking promises', 'More than one segment per setup'],
      keep='The setup itself and the files you download from the segment.', ends='The $99 is paid once. Monthly record fees renew until you cancel.'),
 dict(id='data-feed', name='Market Record feed, founding partner', price='$200', per='per month', link='https://buy.stripe.com/fZu3cv8BmatbfTi8xqdIA0U',
      scope='A service level for data teams: an API key to the current daily rows, delivered the same day, with the change log of who entered and who dropped. The record itself stays free under CC BY 4.0; the feed is the delivery, not exclusive data.',
      notin=['Use without credit (see the Commercial License)', 'Custom segments (sold separately)', 'Ranking, traffic or booking promises'],
      keep='The rows and files you download while subscribed.', ends='Renews monthly until you cancel.'),
 dict(id='edition-license', name='Commercial License, Edition 1', price='$540', per='one license, paid once', link='https://buy.stripe.com/cNi3cv3h20SBdLaaFydIA0Y',
      scope='The right to use and republish Edition 1 data without credit, including white-label inside your client reports, plus a signed statement of the SHA-256 manifest and named support. The Edition 1 files themselves are free for everyone under CC BY 4.0 with credit. The final file list is confirmed on 2026-10-14, before release on 2026-10-15.',
      notin=['The data files (free under CC BY 4.0, with credit)', 'Edition 2 or later', 'The daily feed (sold separately)', 'Custom segments (sold separately)', 'Ranking, traffic or booking promises'],
      keep='The signed manifest statement and the right to use Edition 1 data without credit. Full license wording is published with the final Edition 1 build.', ends='One payment. No renewal.'),
 dict(id='agency-evidence-pack', name='Agency Evidence Pack', price='$397', per='one-time, white-label license', link=STRIPE_PACK,
      scope='We run the dated AI-visibility check on your prospects and hand you white-label audit pages with dated transcripts, plus the agency data pack and resell rights. You deliver them under your brand. The audit count is stated in the checkout description.',
      notin=['Ongoing monitoring', 'Prospect list building', 'Outreach for you'],
      keep='The audits and files, to resell under your brand at your prices.', ends='One-time license, no renewal. See the <a href="https://markets.namebeam.ai/agency/">agency page</a> for turnaround dates and terms.'),
]

def prod_card(p, detail=True):
    nb = ''.join('<li>%s</li>' % x for x in p['notin'])
    btn = '<a class="btn" href="%s" data-link="%s">Buy %s</a>' % (p['link'], 'live' if p['link'].startswith('http') else 'pending', esc(p['name']))
    return (f'<div class="pv-prod" id="{p["id"]}"><div class="top"><h3>{esc(p["name"])}</h3><div><span class="price">{p["price"]}</span> <span class="per">{p["per"]}</span></div></div>'
            f'<div class="pv-cols"><div><h4>Fixed scope</h4><p>{p["scope"]}</p><h4>You keep</h4><p>{p["keep"]}</p></div>'
            f'<div><h4>Not included</h4><ul>{nb}</ul><h4>Ends or renews</h4><p>{p["ends"]}</p></div></div>{btn}</div>')

buy = ('<div class="pv-wrap">' + crumbs([(P + '/', 'Namebeam'), (None, 'Buy')]) + '<h1>Buy the record</h1>'
       '<p>Six products. Each one states what is in it, what is not, what you keep and when it ends or renews, beside the price.</p>' +
       ''.join(prod_card(p) for p in PRODUCTS) +
       '<p class="pv-note">Questions: <a href="mailto:hello@namebeam.ai">hello@namebeam.ai</a>. Payments run on Stripe. Prices as of %s.</p></div>' % BUILD)
page('buy/index.html', 'Buy the record | Namebeam', 'Namebeam products with fixed scope, what is not included, what you keep and the renewal date.', buy)

ag = ('<div class="pv-wrap">' + crumbs([(P + '/', 'Namebeam'), (None, 'Agencies')]) + '<h1>For agencies: show clients which businesses AI names</h1>'
      '<p>The record is built for people who study local search. Pick a market and put a dated page in front of a client: who each engine named, on which days, and where the engines disagree.</p>'
      '<div class="pv-cards">'
      f'<div class="pv-card gold"><h3>Market Record, 1 market</h3><div class="p">$49</div><p>per month. The daily record for one market and category, with a monthly CSV and PDF.</p><p><a class="btn" href="{P}/buy/#market-record">Scope and price</a></p></div>'
      f'<div class="pv-card gold"><h3>Market Record, 5 markets</h3><div class="p">$199</div><p>per month, founding rate for the first 10 agencies.</p><p><a class="btn" href="{P}/buy/#market-record-5">Scope and price</a></p></div>'
      f'<div class="pv-card gold"><h3>Agency Evidence Pack</h3><div class="p">$397</div><p>one-time. White-label audits of your prospects, yours to resell.</p><p><a class="btn" href="{P}/buy/#agency-evidence-pack">Scope and price</a></p></div>'
      '</div>'
      f'<h2>Start with a record page</h2><p>Every page below is free and ungated, with a CSV for each day.</p><div class="pv-rel"><a href="{P}/record/miami-roofing/">Miami roofing</a><a href="{P}/record/atlanta-hvac/">Atlanta HVAC</a><a href="{P}/record/kansas-city-health-insurance/">Kansas City health insurance</a><a href="{P}/record/">All questions</a></div>'
      '<p class="pv-note">Sample audits and pack terms: <a href="https://markets.namebeam.ai/agency/">markets.namebeam.ai/agency</a>. Need a segment that is not in the record? <a href="%s/buy/#custom-segment">Custom segment, $99 setup</a>.</p></div>' % P)
page('agencies/index.html', 'For agencies | Namebeam', 'Market Record plans and the Agency Evidence Pack for agencies that report on AI search.', ag)

dt = ('<div class="pv-wrap">' + crumbs([(P + '/', 'Namebeam'), (None, 'Data and API')]) + '<h1>Data and API</h1>'
      '<p>Free to start, paid when you want the whole set, the feed, or per-call rows.</p>'
      f'<div class="pv-cards"><div class="pv-card"><h3>Free, CC BY 4.0</h3><p>A CSV for every question and run day, the change log, the manifest and the method. No form, no gate. Credit Namebeam (namebeam.ai).</p><p><a href="{P}/record/">Browse the record</a> &middot; <a href="{P}/method/">Method</a> &middot; <a href="https://api.receiptsindex.com/datasets/">Public datasets</a></p></div>'
      f'<div class="pv-card gold"><h3>Commercial License, Edition 1</h3><div class="p">$540</div><p>One payment. Use without credit, white-label rights, a signed manifest statement and named support.</p><p><a class="btn" href="{P}/buy/#edition-license">Scope and price</a></p></div>'
      f'<div class="pv-card gold"><h3>Founding-partner feed</h3><div class="p">$200</div><p>per month. A key to the current daily rows, same-day delivery and the change log.</p><p><a class="btn" href="{P}/buy/#data-feed">Scope and price</a></p></div></div>'
      '<h2>Pay per call</h2><p>Rows are priced for machine buyers over x402: <b>0.27 USDC</b> per call, <b>1.81 USDC</b> for a day. The discovery file is at <a href="https://api.receiptsindex.com/.well-known/x402">api.receiptsindex.com/.well-known/x402</a>. Payment settlement is still being tested; write to <a href="mailto:hello@namebeam.ai">hello@namebeam.ai</a> before you build on it.</p>'
      '<p class="pv-note">Not included in any plan: ranking, traffic or booking promises. The record is free for everyone under CC BY 4.0; paid items sell delivery, derived cuts and the right to use without credit, not exclusive data.</p></div>')
page('data/index.html', 'Data and API | Namebeam', 'Free CSVs, the Edition 1 license, the founding-partner feed and per-call rows.', dt)

ck = ('<div class="pv-wrap">' + crumbs([(P + '/', 'Namebeam'), (None, 'Free check')]) + '<h1>Free check: see your own record</h1>'
      '<p>Tell us your business name and city. You get a page showing which AI engines named you for your market, and which websites their answers read. Free, no card.</p>'
      '<h2>What it is for</h2><ul><li>Trust and data. You see your own record.</li><li>We do not send a sales sequence to businesses that run the check.</li><li>Your result is a snapshot of one run day, dated. The record page for your market shows the rest.</li></ul>'
      '<p><a class="btn" href="https://bit.ly/cs-aicheck">Run my free check</a></p>'
      f'<p class="pv-note">Prefer the data first? <a href="{P}/record/">Browse the record</a>. Questions: <a href="mailto:hello@namebeam.ai">hello@namebeam.ai</a>.</p></div>')
page('check/index.html', 'Free check | Namebeam', 'See which AI engines name your business. Free, no card, no sales sequence.', ck)

mt = ('<div class="pv-wrap">' + crumbs([(P + '/', 'Namebeam'), (None, 'Method')]) + '<h1>Method</h1>'
      '<h2>What a row is</h2><p>For each question, on each run day, we send the same words to each source and log one row per source: the status, the names found in the answer, and the SHA-256 of the raw answer file. The sources are OpenAI, Anthropic, Perplexity and Gemini (by API) and Google search.</p>'
      '<h2>What the status words mean</h2>' + STATUS_DEF +
      '<h2>Names and merging</h2><p>Names are extracted from each answer. Spelling variants that the Edition 1 files group together are shown as one name. Dashes and curly quotes are normalized to plain characters in names. Extraction is automatic, so some entries are headings or terms and not businesses. We log that on the corrections page.</p>'
      '<h2>Who entered and who dropped</h2><p>Each run day is compared with the previous run day that has rows. The engines that answered OK on both days are the ones compared, so an engine skipping a day cannot look like a business dropping out.</p>'
      '<h2>What the counts are not</h2><p>A count is not a ranking, not a score and not a promise about traffic or bookings. AI answers vary from run to run.</p>'
      '<h2>Check it yourself</h2><p>Each CSV lists the raw file name and its SHA-256. %s <a href="%s/record/manifest.sha256">manifest.sha256</a> lists the hash of every CSV on these pages.</p>' % (('The raw files are in the <a href="https://github.com/mrcrtr1979-droid/namebeam-visibility-index/tree/main/corpus/e1">public corpus</a>.' if CORPUS_PUBLIC else CORPUS_HIDDEN_TXT), P) +
      '<p class="pv-note">Compiled by Terry J Carter, Carter Enterprise LLC. Page built %s.</p></div>' % BUILD)
page('method/index.html', 'Method | Namebeam', 'How the daily record is built: rows, statuses, names, change log and how to verify.', mt)

cr = ('<div class="pv-wrap">' + crumbs([(P + '/', 'Namebeam'), (None, 'Corrections')]) + '<h1>Corrections</h1>'
      '<p>When we find an error we log it here with its date and what changed. The old figure stays visible and is marked as superseded. To report one, write to <a href="mailto:hello@namebeam.ai">hello@namebeam.ai</a> with the page link.</p>'
      '<h2>Log</h2><ul>'
      '<li><b>%s.</b> Known issue: the name lists in the Edition 1 files include some headings and terms that are not businesses (for example "Certifications", "Overview"). The counts on these pages are of entries as extracted. The fix is made at the source and its date will be added to this line.</li>'
      '<li><b>2026-10-06.</b> The agency page at markets.namebeam.ai/agency removed non-business phrases from its counts and shows the corrected figures.</li>'
      '<li><b>%s.</b> Days with no rows are listed on each question page and are not filled in.</li></ul></div>') % (BUILD, BUILD)
page('corrections/index.html', 'Corrections | Namebeam', 'Dated log of corrections to the Namebeam record.', cr)

# ---------- manifest + headers ----------
w('site.css', STYLE + EXTRA_CSS)
w('../_headers', '/preview/*\n  X-Robots-Tag: noindex, nofollow\n')
MANIFEST.sort(key=lambda x: x[1])
w('record/manifest.sha256', ''.join('%s  %s\n' % m for m in MANIFEST))

summary = {'questions': len(Q), 'csvs': len(MANIFEST), 'miami': MIAMI, 'ci': (CI_TOTAL, CI_CORR, CI_DATE)}
print(json.dumps(summary))
