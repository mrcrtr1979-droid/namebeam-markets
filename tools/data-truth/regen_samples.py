#!/usr/bin/env python3
"""Regenerate the agency sample sheets and patch the October report from the raw corpus.

Usage: regen_samples.py --corpus <path to corpus/e1> --site <path to namebeam-markets> --out <dir>
Everything printed on a sheet is recomputed from raw files. Nothing is typed by hand.
"""
import argparse, collections, html, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import namecount as nc

LO = '2026-09-01'
HI_PERP = '2026-09-26'   # Perplexity collection method changed in the files dated 2026-09-27 (commit 8afb948)
HI_OTHER = '2026-09-27'  # OpenAI, Gemini, Anthropic request payloads unchanged through this window
RETRIEVED = '2026-10-06'
SITE = 'https://markets.namebeam.ai'
ENGINES = [('Perplexity', 'perplexity'), ('OpenAI API', 'openai'), ('Gemini', 'gemini'), ('Anthropic API', 'anthropic')]
TRADE = {'company', 'co', 'inc', 'llc', 'llp', 'pllc', 'air', 'enterprises', 'pros', 'painting', 'painters', 'painter', 'roofing', 'roofers', 'roofer', 'hvac', 'heating', 'cooling', 'plumbing',
         'moving', 'movers', 'mover', 'contractors', 'construction', 'restoration', 'storage', 'services'}
HEAD = {'experience', 'options', 'focus', 'record', 'case', 'type', 'presence', 'resources', 'steps', 'location',
        'costs', 'statement', 'fee', 'structure', 'contact', 'report', 'limitations', 'things', 'evaluate', 'consider',
        'knowledge', 'area', 'bay', 'east', 'valley', 'upfront', 'recorded', 'primary', 'trial', 'local', 'next',
        'also', 'other', 'key', 'tri', 'statute', 'police', 'obtain', 'get', 'do', 'not', 'give', 'no', 'make',
        'call', 'ask', 'consult', 'hire', 'compare', 'research', 'pricing', 'price', 'cost', 'quote', 'quotes',
        'estimate', 'estimates', 'warranty', 'warranties', 'reviews', 'questions', 'tips', 'summary', 'timeline',
        'process', 'services', 'service', 'area', 'areas', 'budget', 'materials', 'material', 'licensing',
        'insured', 'licensed', 'bonded', 'reputation', 'communication', 'reliability', 'quality', 'value',
        'bottom', 'line', 'final', 'recommendation', 'recommendations', 'overview', 'why', 'what', 'how'}
CURATED = {}   # normalised display name -> extra alias strings; empty unless a name is verified by hand


def old_page(html_text):
    d = {'engines': {}, 'pairs': [], 'domains': [], 'serp': []}
    for m in re.finditer(r'<tr><td>(Perplexity|OpenAI|Gemini|Anthropic)</td><td class=n>(\d+) of (\d+)</td><td>(.*?)</td></tr>', html_text):
        names = [(html.unescape(a.strip()), int(b)) for a, b in re.findall(r'(.+?) \((\d+) of \d+\)(?:, |$)', m.group(4))]
        d['engines'][m.group(1)] = {'named': int(m.group(2)), 'den': int(m.group(3)), 'names': names}
    for m in re.finditer(r'<tr><td>([^<]+)</td><td>((?:Perplexity|OpenAI|Gemini|Anthropic): \d+ of \d+ days(?: \| (?:Perplexity|OpenAI|Gemini|Anthropic): \d+ of \d+ days)*)</td></tr>', html_text):
        d['pairs'].append((html.unescape(m.group(1)), re.findall(r'(Perplexity|OpenAI|Gemini|Anthropic): (\d+) of (\d+) days', m.group(2))))
    for m in re.finditer(r'<tr><td>([^<]+)</td><td>([^<]+)</td><td class=n>(\d+) of (\d+)</td></tr>', html_text):
        d['domains'].append((html.unescape(m.group(1)), html.unescape(m.group(2)), int(m.group(3)), int(m.group(4))))
    for m in re.finditer(r'<tr><td>([^<]+)</td><td class=n>(\d+) of (\d+)</td></tr>', html_text):
        d['serp'].append((m.group(1), int(m.group(2)), int(m.group(3))))
    return d


def shape_ok(s, seeds_norm, city_toks, law=False):
    n = nc.norm(nc.strip_paren(s))
    if n in seeds_norm:
        return True
    low = [w for w in re.findall(r"[A-Za-z][A-Za-z.'&-]*", nc.strip_paren(s)) if w[0].islower() and w not in ('and', 'of', 'the', 'at', 'for', 'de', 'la')]
    if low:
        return False        # descriptive phrase, not a proper name
    toks = set(n.split())
    has_word = bool(toks & (nc.LAW_WORDS | TRADE))
    states = {'texas', 'georgia', 'arizona', 'florida', 'illinois', 'colorado', 'missouri', 'california', 'metro', 'area', 'local', 'commercial', 'residential', 'best', 'top', 'the'}
    if not (toks - city_toks - states - nc.GENERIC - TRADE - nc.LAW_WORDS):
        return False        # descriptor such as "Atlanta HVAC", not a business name
    if city_toks & toks and not has_word:
        return False
    if has_word:
        return True
    return law and bool(re.match(r'^[A-Z]{3,6}\b', s.strip())) and not (toks & HEAD)


def engine_rows(rows, eng):
    return [r for r in rows if r['engine'] == eng]


def window(eng):
    return (LO, HI_PERP if eng == 'perplexity' else HI_OTHER)


def day_hits(er, lo, hi, table):
    """per day: (text_hits, field_hits). Pools prompts by day."""
    by = collections.defaultdict(lambda: [set(), set()])
    for r in er:
        if nc.is_answered(r) and lo <= r['date_utc'] <= hi:
            by[r['date_utc']][0] |= nc.text_hits(r['answer_verbatim'], table)
            by[r['date_utc']][1] |= nc.field_hits(r.get('competitors_mentioned'), table)
    return by


def tally(by):
    t, f = collections.Counter(), collections.Counter()
    for d, (th, fh) in by.items():
        for x in th:
            t[x] += 1
        for x in fh:
            f[x] += 1
    return t, f


def top_list(t, f, n=8):
    items = [(name, c) for name, c in t.items() if c > 0]
    items.sort(key=lambda x: (-x[1], x[0].lower()))
    return items[:n]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--corpus', required=True)
    ap.add_argument('--site', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--dry', action='store_true')
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    allrows = nc.load_rows(a.corpus, LO, HI_OTHER)
    sdir = os.path.join(a.site, 'agency', 'samples')
    slugs = sorted(f[:-5] for f in os.listdir(sdir) if f.endswith('.html'))
    olds = {s: old_page(open(os.path.join(sdir, s + '.html'), encoding='utf-8').read()) for s in slugs}
    # global type map and cross-cell recurrence (headings recur across cells, businesses do not)
    typemap = {}
    for s in slugs:
        for dom, typ, _, _ in olds[s]['domains']:
            typemap.setdefault(dom, typ)
    cellkey = lambda r: (r['niche'], r['market'])
    recur = collections.defaultdict(set)
    for r in allrows:
        if nc.is_answered(r):
            for x in set(r.get('competitors_mentioned') or []):
                recur[nc.norm(x)].add(cellkey(r))
    diffs, alias_out, pi_json = [], {}, None
    pages = {}
    for slug in slugs:
        mk, nk = slug.split('__')
        key = lambda t: re.sub(r'[^a-z]', '', t.lower())
        cell = [r for r in allrows if key(r['market']) == key(mk) and key(r['niche']) == key(nk.replace('-', ' '))]
        assert cell, slug
        market, niche = cell[0]['market'], cell[0]['niche']
        prompts = sorted({r['prompt_text'] for r in cell})
        old = olds[slug]
        seeds = [n for e in old['engines'].values() for n, _ in e['names']] + [n for n, _ in old['pairs']]
        seeds_norm = {nc.norm(nc.strip_paren(s)) for s in seeds}
        city_toks = set(nc.norm(market).split()) - {'ca', 'tx', 'ga', 'il', 'co', 'fl', 'az', 'mo'}
        nc.MARKET_TOKS.clear(); nc.MARKET_TOKS.update(set(nc.norm(market).split()) | {'st', 'saint', 'louis'})
        law = 'injury' in niche or 'attorney' in niche or 'law' in niche
        fd = collections.defaultdict(set)
        for r in cell:
            if nc.is_answered(r):
                for x in set(r.get('competitors_mentioned') or []):
                    fd[x].add((r['engine'], r['date_utc']))
        cand = {x: len(v) for x, v in fd.items()
                if (len(v) >= 2 or nc.norm(nc.strip_paren(x)) in seeds_norm)
                and len(recur[nc.norm(x)]) < 2 and nc.is_business_like(x) or nc.norm(nc.strip_paren(x)) in seeds_norm}
        cand = {x: c for x, c in cand.items() if shape_ok(x, seeds_norm, city_toks, law)}
        table = nc.build_alias_table(cand, seeds=seeds, curated=CURATED, lawish_niche=law)
        alias_out[slug] = [{'name': c['name'], 'variants': c['variants'], 'aliases': c['aliases']} for c in table]
        res = {}
        for label, eng in ENGINES:
            lo, hi = window(eng)
            er = engine_rows(cell, eng)
            ans, failed = nc.day_status(er, lo, hi)
            by = day_hits(er, lo, hi, table)
            t, f = tally(by)
            named_days = sum(1 for d, (th, fh) in by.items() if th)
            named_days_field = sum(1 for d, (th, fh) in by.items() if fh)
            by_old = day_hits(er, LO, HI_OTHER, table)
            t27, f27 = tally(by_old)
            ans27, _ = nc.day_status(er, LO, HI_OTHER)
            nofile = [d for d in failed if not any(r['date_utc'] == d for r in er)]
            res[eng] = dict(label=label, lo=lo, hi=hi, answered=len(ans), failed=failed, nofile=nofile,
                            named_days=named_days, named_days_field=named_days_field, t=t, f=f, t27=t27, f27=f27,
                            ans27=len(ans27), top=top_list(t, f), by=by)
        # perplexity domains (pooled by day), window to 09-26 and the old 09-27 for reproduction
        def pdomains(hi):
            er = engine_rows(cell, 'perplexity')
            ans, failed = nc.day_status(er, LO, hi)
            c = collections.Counter()
            for d in ans:
                hs = set()
                for r in er:
                    if r['date_utc'] == d and nc.is_answered(r):
                        for u in (r.get('sources_cited') or []):
                            h = nc.host_fold(u)
                            if h:
                                hs.add(h)
                c.update(hs)
            return c, len(ans), failed
        dom26 = pdomains(HI_PERP)
        dom27 = pdomains(HI_OTHER)
        # google serp (St. Louis only; no source-map cell)
        serp = None
        if old['serp']:
            import glob
            c = collections.Counter(); ok_days = set(); failed = []
            sdays = {}
            for f in glob.glob(os.path.join(a.corpus, 'NB-CZ-SERP_2026-09-*.json')):
                d = json.load(open(f))
                if key(d.get('market', '')) == key(market) and key(d.get('niche', '')) == key(niche) and LO <= d['date_utc'] <= HI_OTHER:
                    sdays.setdefault(d['date_utc'], []).append(d)
            for dt in nc.daterange(LO, HI_OTHER):
                rs = [x for x in sdays.get(dt, []) if x.get('run_status') == 'OK' and x.get('organic_top_results')]
                if rs:
                    ok_days.add(dt)
                    hs = {nc.host_fold(u, fold=False) for x in rs for u in x['organic_top_results']}
                    c.update(h for h in hs if h)
                else:
                    failed.append(dt)
            serp = (c, len(ok_days), failed)
        pages[slug] = dict(cell=cell, market=market, niche=niche, prompts=prompts, table=table, res=res,
                           dom26=dom26, dom27=dom27, serp=serp, old=old)
        if slug == 'pleasanton-ca__personal-injury-law':
            pi_json = build_pi_json(cell, table, prompts)
    json.dump(alias_out, open(os.path.join(a.out, 'alias_tables.json'), 'w'), indent=1)
    json.dump(pi_json, open(os.path.join(a.out, 'pleasanton_pi_corrected.json'), 'w'), indent=1)
    for slug in slugs:
        p = pages[slug]
        new_html, d = render(slug, p, typemap)
        diffs += d
        if not a.dry:
            open(os.path.join(sdir, slug + '.html'), 'w', encoding='utf-8').write(new_html)
    rep = patch_report(a, allrows)
    diffs += rep
    json.dump(diffs, open(os.path.join(a.out, 'number_diff.json'), 'w'), indent=1)
    with open(os.path.join(a.out, 'NUMBER-DIFF.md'), 'w') as fh:
        fh.write('| page | line | old | new | reason |\n|---|---|---|---|---|\n')
        for x in diffs:
            fh.write('| %s | %s | %s | %s | %s |\n' % (x['page'], x['line'], x['old'], x['new'], x['reason']))
    print('pages', len(slugs), 'diff rows', len(diffs))


def build_pi_json(cell, table, prompts):
    out = {'question_cell': 'personal injury law, Pleasanton CA', 'method': 'name or listed alias in answer_verbatim, answered (OK) days only',
           'windows': {'perplexity': [LO, HI_PERP], 'openai': [LO, HI_OTHER], 'gemini': [LO, HI_OTHER], 'anthropic': [LO, HI_OTHER]},
           'perplexity_window_reason': 'Perplexity collection method changed in the files dated 2026-09-27 (commit 8afb948, 2026-09-27T02:24Z)',
           'prompts': {}}
    for p in prompts + ['POOLED (a day counts once if either prompt named the business)']:
        pr = {}
        for label, eng in ENGINES:
            lo, hi = window(eng)
            er = [r for r in cell if r['engine'] == eng and (p.startswith('POOLED') or r['prompt_text'] == p)]
            ans, failed = nc.day_status(er, lo, hi)
            by = day_hits(er, lo, hi, table)
            t, f = tally(by)
            pr[eng] = {'window': [lo, hi], 'answered_days': len(ans), 'failed_days': len(failed), 'failed_dates': failed,
                       'top_businesses_new_method': [{'name': n, 'days_named': c, 'of_answered_days': len(ans),
                                                      'days_in_extractor_field_old_method': f.get(n, 0)} for n, c in top_list(t, f, 12)]}
        out['prompts'][p] = pr
    return out


def esc(s):
    return html.escape(s, quote=False)


def render(slug, p, typemap):
    old = p['old']
    path_old = None
    res, table = p['res'], p['table']
    diffs = []
    pg = slug
    q = ' and '.join('"%s"' % x for x in p['prompts'])
    url = '%s/agency/samples/%s' % (SITE, slug)
    wtxt = '%s to %s (Perplexity to %s)' % (LO, HI_OTHER, HI_PERP)
    pooled = len(p['prompts']) > 1
    qline = 'Questions: %s. A day counts once if either question named the business.' % q if pooled else 'Question: %s' % q
    h1 = None
    # ---- table 1
    rows1 = []
    lab_old = {'Perplexity': 'Perplexity', 'OpenAI API': 'OpenAI', 'Gemini': 'Gemini', 'Anthropic API': 'Anthropic'}
    for label, eng in ENGINES:
        r = res[eng]
        o = old['engines'].get(lab_old[label])
        ans = r['answered']
        nf = len(r['failed'])
        failed_txt = '%d failed days excluded' % nf if nf else 'no failed days'
        if r['named_days'] == 0:
            names = 'No business names returned.'
            if eng in ('openai', 'anthropic'):
                names += ' API run without web search.'
        else:
            names = ', '.join('%s (%d of %d)' % (esc(n), c, ans) for n, c in r['top'])
        rows1.append('<tr><td>%s<br><span class="note">%s to %s</span></td><td class=n>%d<br><span class="note">%s</span></td><td class=n>%d of %d</td><td>%s</td></tr>'
                     % (label, r['lo'], r['hi'], ans, failed_txt, r['named_days'], ans, names))
        # diffs
        if o:
            diffs.append(dict(page=pg, line='%s, days a business was named' % label,
                              old='%d of %d' % (o['named'], o['den']), new='%d of %d' % (r['named_days'], ans),
                              reason=reason_days(o, r)))
            diffs.append(dict(page=pg, line='%s, days with an answer' % label, old='not shown (denominator %d calendar days)' % o['den'],
                              new='%d (%d failed days excluded)' % (ans, nf), reason='denominator is days with an answered OK run'))
            oldmap = dict(o['names'])
            newmap = dict(r['top'])
            for n, c0 in o['names']:
                nm = match_name(n, table)
                if nm is None:
                    diffs.append(dict(page=pg, line='%s, %s' % (label, n), old='%d of %d' % (c0, o['den']), new='not recomputed',
                                      reason='name not in alias table'))
                    continue
                tn = r['t'].get(nm, 0)
                shown = nm in newmap
                diffs.append(dict(page=pg, line='%s, %s' % (label, n), old='%d of %d' % (c0, o['den']),
                                  new='%d of %d' % (tn, ans) + ('' if shown else ' (outside top 8)'),
                                  reason=decomp(c0, r['f27'].get(nm, 0), r['t27'].get(nm, 0), tn, eng)))
            for n, c in r['top']:
                if not any(match_name(on, table) == n for on, _ in o['names']):
                    diffs.append(dict(page=pg, line='%s, %s' % (label, n), old='not in published top list', new='%d of %d' % (c, ans),
                                      reason='enters top 8 under text count and alias merge (field count %d, text count %d in the old window)' % (r['f27'].get(n, 0), r['t27'].get(n, 0))))
    named_by = collections.defaultdict(dict)
    for label, eng in ENGINES:
        for n, c in res[eng]['t'].items():
            if c > 0:
                named_by[n][label] = (c, res[eng]['answered'])
    shared = [(n, v) for n, v in named_by.items() if len(v) >= 2]
    shared.sort(key=lambda x: (-len(x[1]), -sum(c for c, _ in x[1].values()), x[0].lower()))
    shared = shared[:5]
    rows2 = ['<tr><td>%s</td><td>%s</td></tr>' % (esc(n), ' | '.join('%s: %d of %d days' % (lab, c, d) for lab, (c, d) in v.items())) for n, v in shared]
    for n, pairs in old['pairs']:
        nm = match_name(n, table)
        for lab, c0, d0 in pairs:
            l2 = {'Perplexity': 'Perplexity', 'OpenAI': 'OpenAI API', 'Gemini': 'Gemini', 'Anthropic': 'Anthropic API'}[lab]
            e2 = dict((l, e) for l, e in ENGINES)[l2]
            tn = res[e2]['t'].get(nm, 0) if nm else 0
            diffs.append(dict(page=pg, line='Named by 2 or more engines, %s, %s' % (n, lab), old='%s of %s' % (c0, d0),
                              new='%d of %d' % (tn, res[e2]['answered']),
                              reason=decomp(int(c0), res[e2]['f27'].get(nm, 0), res[e2]['t27'].get(nm, 0), tn, e2) if nm else 'name not in alias table'))
    for n, v in shared:
        if not any(match_name(on, table) == n for on, _ in old['pairs']):
            diffs.append(dict(page=pg, line='Named by 2 or more engines, %s' % n, old='not in published table',
                              new='; '.join('%s %d of %d' % (lab, c, d) for lab, (c, d) in v.items()), reason='named by 2 or more engines under the text count'))
    # ---- page 2
    d26, ans26, failed26 = p['dom26']
    d27, ans27, failed27 = p['dom27']
    if p['serp'] is None:
        top = sorted(d26.items(), key=lambda x: (-x[1], x[0]))[:10]
        sub2 = 'Domains cited by Perplexity for this question, %s to %s, counted from the daily answer record.' % (LO, HI_PERP)
        body2 = ''.join('<tr><td>%s</td><td>%s</td><td class=n>%d of %d</td></tr>' % (esc(dm), esc(typemap.get(dm, 'Unclassified')), c, ans26) for dm, c in top)
        tbl2 = '<table><tr><th>Domain</th><th>Type</th><th>Days cited</th></tr>%s<tfoot><tr><td colspan="3">%s</td></tr></tfoot></table>' % (body2, src(LO, HI_PERP))
        note2 = '<p class="note">Type is the Namebeam classification of the domain. Counts are days cited out of days Perplexity answered (%d answered, %d failed days excluded).</p>' % (ans26, len(failed26))
        h2 = 'Top domains cited by Perplexity'
        for dm, typ, c0, d0 in old['domains']:
            c1 = d26.get(dm, 0)
            reproduced = d27.get(dm, 0) == c0
            diffs.append(dict(page=pg, line='Domain table, %s' % dm, old='%d of %d' % (c0, d0), new='%d of %d' % (c1, ans26),
                              reason=('window cut to 2026-09-26 (Perplexity method change); denominator answered days' if reproduced
                                      else 'published value not reproduced from raw: raw to 09-27 gives %d of %d; window cut to 09-26' % (d27.get(dm, 0), ans27))))
        for dm, c in top:
            if not any(dm == x[0] for x in old['domains']):
                diffs.append(dict(page=pg, line='Domain table, %s' % dm, old='not in published top 10', new='%d of %d' % (c, ans26), reason='enters top 10 after window cut and recount'))
    else:
        c, okd, fl = p['serp']
        top = sorted([(dm, n) for dm, n in c.items() if n >= 2], key=lambda x: (-x[1], x[0]))
        sub2 = ("Domains that Google's results listed for the same question, %s to %s. This cell is not in the source map, so the counts below are computed from the Google result rows in the dated record. Google returned links on %d answered days; %d failed days excluded." % (LO, HI_OTHER, okd, len(fl)))
        body2 = ''.join('<tr><td>%s</td><td class=n>%d of %d</td></tr>' % (esc(dm), n, okd) for dm, n in top)
        tbl2 = '<table><tr><th>Domain</th><th>Days listed</th></tr>%s<tfoot><tr><td colspan="2">%s</td></tr></tfoot></table>' % (body2, src(LO, HI_OTHER))
        note2 = '<p class="note">Cited-domain counts for Perplexity are not part of this sheet for this cell, so none are shown.</p>'
        h2 = 'Top domains listed by Google (2 or more days)'
        for dm, c0, d0 in old['serp']:
            diffs.append(dict(page=pg, line='Google domain table, %s' % dm, old='%d of %d' % (c0, d0), new='%d of %d' % (c.get(dm, 0), okd),
                              reason='same window; denominator is answered days (OK run with links)'))
    return assemble(slug, p, rows1, rows2, sub2, h2, tbl2, note2, q, qline, url, wtxt, pooled), diffs


def src(lo, hi):
    return 'Source: Namebeam daily AI answer record, namebeam.ai. Window %s to %s. Counts are days with an answer.' % (lo, hi)


def match_name(n, table):
    nn = nc.norm(nc.strip_paren(n))
    for cl in table:
        if nn in {nc.norm(nc.strip_paren(v)) for v in cl['variants']} or nn == nc.norm(nc.strip_paren(cl['name'])):
            return cl['name']
    return None


def decomp(pub, f27, t27, tnew, eng):
    parts = []
    if f27 - pub:
        parts.append('alias merge %+d' % (f27 - pub))
    if t27 - f27:
        parts.append('name found in answer text, missed by extractor field %+d' % (t27 - f27))
    if tnew - t27:
        parts.append('window to 09-26 %+d' % (tnew - t27))
    parts.append('denominator now answered days')
    return '; '.join(parts)


def reason_days(o, r):
    return 'denominator now answered days (%d failed days excluded)%s; named-day test now reads answer text' % (
        len(r['failed']), '; window to 09-26' if r['hi'] == HI_PERP else '')


def assemble(slug, p, rows1, rows2, sub2, h2, tbl2, note2, q, qline, url, wtxt, pooled):
    pth = os.path.join(ARGS_SITE[0], 'agency', 'samples', slug + '.html')
    old_html = open(pth, encoding='utf-8').read()
    head = old_html.split('<body>')[0]
    head = head.replace('.scroll{overflow-x:auto}', '.scroll{overflow-x:auto} tfoot td{font-size:12px;color:var(--mut);background:var(--soft)}', 1)
    h1_1 = re.search(r'<h1>(.*?)</h1>', old_html).group(1)
    market, niche = p['market'], p['niche']
    sub = '%s, %s. One question per AI engine per day. Windows: Perplexity %s to %s; OpenAI API, Gemini and Anthropic API %s to %s.' % (niche[0].upper() + niche[1:], market, LO, HI_PERP, LO, HI_OTHER)
    cite = 'Cite as: Namebeam, AI answer record for %s, %s, %s, retrieved %s, %s' % (q, market, wtxt, RETRIEVED, url)
    why = 'Perplexity is counted to %s because Namebeam changed how Perplexity answers are collected in the files dated 2026-09-27; OpenAI API, Gemini and Anthropic API request methods did not change and run to %s.' % (HI_PERP, HI_OTHER)
    note1 = ('A business counts as named on a day when its name, or a listed spelling variant, appears in the answer text. '
             'Counts are days with an answer; failed days are shown separately and are not counted as misses. '
             'Platform, directory and non-business strings are removed before counting. '
             'Only businesses that appear in the record\'s extracted name list are searched for in the text, so counts are a floor. ') + why
    if pooled:
        note1 += ' Two questions are asked each day and pooled: ' + ' and '.join('"%s"' % esc(x) for x in p['prompts']) + '. A day counts once if either answer named the business.'
    srcline = 'Source: Namebeam daily AI answer record, namebeam.ai. Window %s to %s (Perplexity to %s). Counts are days with an answer.' % (LO, HI_OTHER, HI_PERP)
    t1 = ('<div class="scroll"><table><tr><th>Engine</th><th>Days with an answer</th><th>Days a business was named</th><th>Top businesses by days named</th></tr>\n%s\n'
          '<tfoot><tr><td colspan="4">%s</td></tr></tfoot></table></div>' % ('\n'.join(rows1), srcline))
    t2 = ('<div class="scroll"><table><tr><th>Business</th><th>Where it was named</th></tr>\n%s\n<tfoot><tr><td colspan="2">%s</td></tr></tfoot></table></div>'
          % ('\n'.join(rows2) if rows2 else '<tr><td colspan="2">No business was named by 2 or more engines in this window.</td></tr>', srcline))
    foot = '<footer>Dated record by NameBeam (markets.namebeam.ai). Businesses do not pay to appear. Record windows: Perplexity %s to %s; other engines %s to %s.</footer>' % (LO, HI_PERP, LO, HI_OTHER)
    tail2 = re.search(r'<h2>What this means for the prospect</h2>.*?<footer>', old_html, re.S).group(0)[:-len('<footer>')]
    s1 = ('<section class="page"><h1>%s</h1>\n<p class="sub">%s</p>\n<p class="sub">%s</p>\n<h2>Per engine: days answered and most-named businesses</h2>\n%s\n<p class="note">%s</p>\n'
          '<h2>Businesses named by 2 or more engines</h2>\n%s\n%s</section>' % (h1_1, esc(sub), esc(cite), t1, note1, t2, foot))
    h1_2 = re.findall(r'<h1>(.*?)</h1>', old_html)[1]
    s2 = ('<section class="page"><h1>%s</h1>\n<p class="sub">%s</p>\n<h2>%s</h2>\n<div class="scroll">%s</div>\n%s\n%s%s</section>'
          % (h1_2, esc(sub2), h2, tbl2, note2, tail2, foot))
    return head + '<body>\n' + s1 + '\n' + s2 + '</body></html>\n'


ARGS_SITE = ['']


def c5(rows, hi):
    cells = collections.defaultdict(set)
    for r in rows:
        if r['engine'] == 'perplexity' and str(r.get('business', '')).startswith('SEGMENT') and r.get('run_status') == 'OK' \
                and r.get('sources_cited') and LO <= r['date_utc'] <= hi:
            cells[(r['niche'], r['market'], r['date_utc'])] |= {nc.host_fold(u, fold=False) for u in r['sources_cited']}
    n = len(cells)

    def cnt(dom):
        return sum(1 for hs in cells.values() if any(h == dom or h.endswith('.' + dom) for h in hs))
    return n, cnt('expertise.com'), cnt('yelp.com')


def patch_report(a, allrows):
    pth = os.path.join(a.site, 'report', 'october-2026', 'index.html')
    t = open(pth, encoding='utf-8').read()
    n27, e27, y27 = c5(allrows, HI_OTHER)
    n26, e26, y26 = c5(allrows, HI_PERP)
    print('C5 at 09-27 (published 670/250/221):', n27, e27, y27, '| at 09-26:', n26, e26, y26)
    assert (n27, e27, y27) == (670, 250, 221), 'published figure not reproduced'
    sh = lambda x, n: '%.1f%%' % (100.0 * x / n)
    d = []
    o_e, o_y = '250 of 670 cell-days with cited sources (37.3%)', '221 of 670 (33.0%)'
    n_e, n_y = '%d of %d cell-days with cited sources (%s)' % (e26, n26, sh(e26, n26)), '%d of %d (%s)' % (y26, n26, sh(y26, n26))
    cnt = t.count(o_e + ' and yelp.com on ' + o_y + ', ' + LO + ' to ' + HI_OTHER)
    assert cnt == 2, cnt
    t = t.replace(o_e + ' and yelp.com on ' + o_y + ', ' + LO + ' to ' + HI_OTHER, n_e + ' and yelp.com on ' + n_y + ', ' + LO + ' to ' + HI_PERP)
    t = t.replace('Most cited domains, Perplexity API answers, 2026-09-01 to 2026-09-27', 'Most cited domains, Perplexity API answers, 2026-09-01 to 2026-09-26')
    t = t.replace('<tr><td>expertise.com</td><td>250</td><td>670</td><td>37.3%</td>', '<tr><td>expertise.com</td><td>%d</td><td>%d</td><td>%s</td>' % (e26, n26, sh(e26, n26)))
    t = t.replace('<tr><td>yelp.com</td><td>221</td><td>670</td><td>33.0%</td>', '<tr><td>yelp.com</td><td>%d</td><td>%d</td><td>%s</td>' % (y26, n26, sh(y26, n26)))
    old_lim = 'Window is 2026-09-01 to 2026-09-27 because the Perplexity method changed on 2026-09-28.'
    new_lim = 'Window is 2026-09-01 to 2026-09-27 for OpenAI, Gemini and Anthropic. Perplexity collection changed in the files dated 2026-09-27, so the Perplexity cited-domain figures in finding 3 use 2026-09-01 to 2026-09-26. Perplexity figures in findings 1 and 4 and the listing comparison were computed through 2026-09-27 and have not been recomputed for the 2026-09-26 cut.'
    assert old_lim in t
    t = t.replace(old_lim, new_lim)
    old_m = 'Perplexity changed its method on 2026-09-28, so later days are not pooled.'
    new_m = 'Perplexity changed its collection method in the files dated 2026-09-27; see Limits for which figures use 2026-09-26 as the last Perplexity day.'
    assert old_m in t
    t = t.replace(old_m, new_m)
    assert 'accessed &lt;date&gt;' in t
    t = t.replace('accessed &lt;date&gt;', 'published 2026-10-05')
    open(pth, 'w', encoding='utf-8').write(t)
    pg = 'report/october-2026'
    d.append(dict(page=pg, line='Finding 3 headline and summary, expertise.com cell-days', old='250 of 670 (37.3%)', new='%d of %d (%s)' % (e26, n26, sh(e26, n26)), reason='Perplexity window cut to 2026-09-26 (collection changed in files dated 2026-09-27); same method as the published figure, reproduced exactly at 09-27'))
    d.append(dict(page=pg, line='Finding 3 headline and summary, yelp.com cell-days', old='221 of 670 (33.0%)', new='%d of %d (%s)' % (y26, n26, sh(y26, n26)), reason='same as above'))
    d.append(dict(page=pg, line='Finding 3 table, caption window', old='2026-09-01 to 2026-09-27', new='2026-09-01 to 2026-09-26', reason='Perplexity method change date'))
    d.append(dict(page=pg, line='Limits and Method, change date', old='Perplexity method changed on 2026-09-28', new='Perplexity collection changed in the files dated 2026-09-27', reason='commit 8afb948 2026-09-27T02:24Z; all 09-27 Perplexity files have 15 sources and no [n] markers'))
    d.append(dict(page=pg, line='How to cite', old='accessed <date>', new='published 2026-10-05', reason='first commit of the page eabe074, 2026-10-05T03:31:24-05:00'))
    return d


if __name__ == '__main__':
    import sys as _s
    for i, x in enumerate(_s.argv):
        if x == '--site':
            ARGS_SITE[0] = _s.argv[i + 1]
    main()
