#!/usr/bin/env python3
"""rebuild_market_pages.py [2026-10-22]: regenerate the figures on market_*.html on the 10-22 counting rule.
Source: data/explorer_data_2026-10-22.json, a copy of namebeam-site data/explorer_data.json as rebuilt in namebeam-site PR #62
(scripts/explorer/rebuild_explorer.py). Rule: a business counts for an engine on every answer day whose saved answer text names it
(full name, same capital letters per word); each engine is divided by its own answer days; window per pair runs from the pair's
first to its last row date. The older generator (carter-brain gen_market_pages.py, run 2026-09-08) counted extracted business lists.
Kept as written: page head, style, heading, disclosure, footer, brand line. Replaced: the numbers blocks (meta, engine coverage,
businesses table, niche list) and the two footer lines that named the old file and generator.
Pages whose market is not in the data file are left unchanged and listed. Zero model calls, stdlib only.
Usage (repo root): python3 -I -B scripts/rebuild_market_pages.py [data/explorer_data_2026-10-22.json]"""
import json, re, sys, html
DATA = sys.argv[1] if len(sys.argv) > 1 else 'data/explorer_data_2026-10-22.json'
BUILT = '2026-10-22'
PAGES = {'Atlanta GA': 'market_atlanta.html', 'Charlotte NC': 'market_charlotte.html', 'Chicago IL': 'market_chicago.html',
         'Dallas TX': 'market_dallas.html', 'Denver CO': 'market_denver.html', 'Houston TX': 'market_houston.html',
         'Kansas City MO': 'market_kansas-city.html', 'Miami FL': 'market_miami.html', 'Phoenix AZ': 'market_phoenix.html',
         'US nationwide': 'market_us-nationwide.html'}
ENG = [('perplexity', 'Perplexity'), ('openai', 'OpenAI'), ('anthropic', 'Anthropic'), ('gemini', 'Gemini')]
E = html.escape
P13 = '<p style="font-size:13px;color:#666;">'
RULE = ('Counts read "answers naming it / answers that returned text", per engine. Counting rule: a business counts for an engine when its '
        'full name, written with the same capital letters, appears in that engine\'s saved answer text, so a count means named in the answer '
        'text. The matching is the homepage explorer\'s name matching with an added capital-letter check on each word of the name, run over '
        'each niche\'s own window and counted per answer. A business listed as an example counts, and a count does not mean the engine picked '
        'it. Rows overlap (a chain and its locations are separate rows), so rows are not added together.')
DQ5 = ('Until 2026-10-21 this page counted from the extracted business lists, which under-counted plain-text mentions by different amounts per '
       'engine (DQ-5). Details: <a href="https://markets.namebeam.ai/method/#dq-5">Method, DQ-5</a>.')
OLD_F1 = 'Data source: NameBeam AI Visibility Index corpus (citation_corpus.csv), collection rows read for this run.'
NEW_F1 = 'Data source: Namebeam public record, data/explorer_data_2026-10-22.json (window ends 2026-10-21), saved answer text per engine and day.'
OLD_F2 = re.compile(r'Counts above are computed at generation time from the corpus file read for this run and can be reproduced by running gen_market_pages\.py again against the same file\.')
NEW_F2 = 'Counts above are computed from the data file named above and can be reproduced by running scripts/rebuild_market_pages.py against the same file.'

def section(p):
    a = p['asked_by_engine']
    s = '<h3 style="font-size:16px;margin:26px 0 8px;">%s, %s to %s</h3>\n' % (E(p['niche']), p['window_start'], p['window_end'])
    s += P13 + 'Answers that returned text: ' + ', '.join('%s %d' % (l, a[k]) for k, l in ENG if k in a) + '.</p>\n'
    tb = p['top_businesses']
    if not tb:
        return s + P13 + E(p['finding']) + '</p>\n'
    s += '<table><thead><tr><th class="seq">No.</th><th>Business</th>' + ''.join('<th class="num">%s</th>' % l for k, l in ENG) + '</tr></thead><tbody>\n'
    for i, b in enumerate(tb, 1):
        s += '<tr><td class="seq">%d</td><td>%s</td>' % (i, E(b['business']))
        for k, l in ENG:
            c = b['by_engine'][k]
            s += '<td class="num">%d/%d</td>' % (c['named'], c['asked'])
        s += '</tr>\n'
    s += '</tbody></table>\n'
    more = p['businesses_named_total'] - len(tb)
    s += P13 + '%d businesses named in this niche and window; the top %d are shown, ordered by total namings across the engines (used only to order the rows). This is a count, not a ranking and not an endorsement.' % (p['businesses_named_total'], len(tb)) + '</p>\n'
    if p['guarded_not_ranked']:
        s += P13 + '%d generic phrases (directories, review sites, certifications, topic words) were set apart and are not counted as businesses.' % p['guarded_not_ranked'] + '</p>\n'
    return s

def build(t, city, pairs):
    h = t[:t.index('<div class="meta">')]
    disc = re.search(r'<div class="disclosure">.*?</div>', t, re.S).group(0)
    foot = t[t.index('<div class="footer">'):]
    foot = foot.replace(OLD_F1, NEW_F1); foot = OLD_F2.sub(NEW_F2, foot)
    ws = min(p['window_start'] for p in pairs); we = max(p['window_end'] for p in pairs)
    meta = ('<div class="meta">\n<p>As of %s. Page built %s.</p>\n<p>%d niche%s for this market, 4 engines asked per niche.</p>\n'
            '<p>Windows run from each niche\'s earliest to its latest row date, within %s to %s.</p>\n</div>\n') % (
            BUILT, BUILT, len(pairs), '' if len(pairs) == 1 else 's', ws, we)
    body = '<h2>Engine coverage</h2>\n<p>Each niche below was asked of Perplexity, OpenAI, Anthropic and Gemini on its own days; the answers that returned text per engine are stated with each niche.</p>\n'
    body += '<h2>Businesses named, by engine</h2>\n<p style="font-size:13px;color:#666;">' + RULE + '</p>\n<p style="font-size:13px;color:#666;">' + DQ5 + '</p>\n'
    body += ''.join(section(p) for p in pairs)
    body += '<h2>Markets and query segments covered</h2>\n' + P13 + 'Niches rolled into this market page: ' + ', '.join(E(p['niche']) for p in pairs) + '.</p>\n'
    return h + meta + disc + '\n' + body + foot

d = json.load(open(DATA))
changed, left = [], []
for mk, f in PAGES.items():
    pairs = sorted([p for p in d['pairs'] if p['market'] == mk], key=lambda p: p['niche'])
    if not pairs: left.append(f); continue
    t = open(f, encoding='utf-8').read()
    open(f, 'w', encoding='utf-8', newline='').write(build(t, mk, pairs)); changed.append(f)
import glob
print('rebuilt', len(changed), changed); print('unchanged (market not in data file)', sorted(set(glob.glob('market_*.html')) - set(changed)))
