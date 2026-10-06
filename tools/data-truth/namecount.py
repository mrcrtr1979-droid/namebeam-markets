#!/usr/bin/env python3
"""Namebeam name counting from answer text. Library used by selftest.py and regen_samples.py.

A business counts as named on a day when its name, or a listed alias, appears in the
answer_verbatim text of an answered (run_status OK) run. The extractor field
(competitors_mentioned) is kept only as the OLD method so every change is visible.
"""
import glob, json, os, re, unicodedata, collections, datetime

LEGAL = {'llp', 'llc', 'pc', 'pllc', 'inc', 'corp', 'corporation', 'ltd', 'co', 'company', 'lp'}
LAWGEN = {'law', 'firm', 'offices', 'office', 'attorney', 'attorneys', 'lawyer', 'lawyers', 'legal',
          'group', 'associates', 'accident', 'personal', 'injury', 'trial', 'injuries'}
TRADEGEN = {'painting', 'painters', 'painter', 'roofing', 'roofers', 'roofer', 'roof', 'hvac', 'heating', 'cooling',
            'air', 'conditioning', 'plumbing', 'moving', 'movers', 'mover', 'storage', 'services', 'service', 'ac',
            'contractors', 'contractor', 'construction', 'restoration', 'repair', 'replacement', 'home', 'solutions'}
FILLER = {'and', 'of', 'the', 'at', 'for', 'in'}
GENERIC = LEGAL | LAWGEN | TRADEGEN | FILLER
COMMON = {'smith', 'jones', 'brown', 'davis', 'white', 'green', 'black', 'young', 'moore', 'king', 'scott', 'allen',
          'adams', 'baker', 'clark', 'hall', 'lewis', 'lopez', 'miller', 'nelson', 'parker', 'perez', 'price',
          'roberts', 'turner', 'walker', 'ward', 'watson', 'wood', 'wright', 'harris', 'martin', 'thomas',
          'jackson', 'taylor', 'wilson', 'anderson', 'johnson', 'williams', 'better', 'family', 'premier',
          'express', 'quality', 'affordable', 'first', 'best', 'local', 'american', 'national', 'city'}
NICK = {'tom': 'thomas', 'mike': 'michael', 'chuck': 'charles', 'charlie': 'charles', 'bob': 'robert',
        'bill': 'william', 'jim': 'james', 'joe': 'joseph', 'dan': 'daniel', 'ed': 'edward', 'steve': 'stephen',
        'steven': 'stephen', 'tim': 'timothy', 'tony': 'anthony', 'rick': 'richard', 'dave': 'david',
        'matt': 'matthew', 'chris': 'christopher', 'jeff': 'jeffrey', 'greg': 'gregory', 'ken': 'kenneth',
        'andy': 'andrew', 'nick': 'nicholas', 'pat': 'patrick', 'ben': 'benjamin', 'sam': 'samuel',
        'jon': 'jonathan', 'john': 'jonathan'}
# Platforms, directories, regulators, headings: never counted as a business.
STOP_CONTAINS = ['yelp', 'google', 'bing', 'facebook', 'reddit', 'nextdoor', 'bbb', 'better business bureau', 'avvo',
                 'justia', 'findlaw', 'lawinfo', 'martindale', 'super lawyers', 'superlawyers', 'best lawyers',
                 'expertise', 'thumbtack', 'angi', 'angie', 'homeadvisor', 'houzz', 'porch com', 'yellow pages',
                 'yellowpages', 'mapquest', 'linkedin', 'instagram', 'youtube', 'tiktok', 'quora', 'wikipedia',
                 'chatgpt', 'openai', 'perplexity', 'gemini', 'claude', 'siri', 'state bar', 'bar association',
                 'county', 'department', 'attorney general', 'consumer reports', 'forbes', 'nolo', 'lawyers com',
                 'top rated', 'u s news', 'us news', 'trustpilot', 'homeguide', 'bob vila', 'this old house',
                 'consumeraffairs', 'consumer affairs', 'review', 'rating', 'directory', 'referral', 'research',
                 'questions to ask', 'ask for', 'what to', 'how to', 'tips', 'consultation', 'free', 'contingency',
                 'verify', 'check', 'license', 'insurance', 'consumer attorneys', 'trial lawyers', 'association',
                 'society', 'chamber of commerce', 'cslb', 'department of', 'state of', 'certified', 'master elite', 'platinum',
                 'approved', 'building code', 'product approval', 'registration', 'commission', 'regulation', 'registrar',
                 'bureau', 'hvhz', 'velocity hurricane', 'inspection', 'disciplinary', 'notable attorneys', 'benjamin moore',
                 'owens corning', 'tamko', 'gaf', 'georgia power', 'usdot', 'tacla', 'document everything', 'spoliation',
                 'financial capital', 'bar of', 'georgia bar', 'illinois bar', 'texas bar', 'lead safe', 'epa', 'noa']
STOP_EXACT = {'law', 'lawyer', 'attorney', 'attorneys', 'lawyers', 'search', 'pleasanton', 'california', 'ca',
              'alameda', 'san ramon', 'dublin', 'livermore', 'walnut creek', 'oakland', 'san francisco',
              'atlanta', 'chicago', 'dallas', 'denver', 'houston', 'miami', 'phoenix', 'st louis', 'saint louis',
              'georgia', 'illinois', 'texas', 'colorado', 'florida', 'arizona', 'missouri', 'bbb', 'angi'}


def norm(s):
    s = (s or '').replace('\u2019', "'").replace('\u2018', "'")
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode()
    s = re.sub(r'\ba/c\b', 'ac', s.lower()).replace('&', ' and ')
    return re.sub(r'[^a-z0-9]+', ' ', s).strip()


def strip_paren(s):
    return re.sub(r'\([^)]*\)', ' ', s or '')


def is_business_like(s):
    n = norm(strip_paren(s))
    if not n or n in STOP_EXACT or len(n) < 3:
        return False
    padded = ' ' + n + ' '
    for p in STOP_CONTAINS:
        if (' ' + p + ' ') in padded or (len(p) > 5 and p in n):
            return False
    return bool(re.search(r'[A-Z]', s or ''))


def strip_legal_tail(n):
    t = n.split()
    while t:
        if t[-1] in LEGAL:
            t.pop()
        elif t[-2:] == ['p', 'c']:
            t = t[:-2]
        else:
            break
    return ' '.join(t)


def strip_prefix(n):
    n = re.sub(r'^(the )', '', n)
    n = re.sub(r'^(law offices? of |offices? of |law firm of )', '', n)
    return n


MARKET_TOKS = set()


def core(n):
    t = [x for x in strip_prefix(n).split() if x not in GENERIC]
    while len(t) > 1 and t[-1] in MARKET_TOKS:
        t.pop()
    return tuple(t)


def eq_tok(a, b):
    if a == b:
        return True
    if len(a) == 1 and b.startswith(a):
        return True
    if len(b) == 1 and a.startswith(b):
        return True
    return NICK.get(a) == b or NICK.get(b) == a or (NICK.get(a) and NICK.get(a) == NICK.get(b))


def merge_cores(A, B, law=False):
    if not A or not B:
        return False
    if A == B:
        return True
    if len(A) >= 2 and len(B) > len(A) and B[:len(A)] == A:
        return True         # "air tech houston" inside "air tech houston ac plumbing"
    if len(A) >= 2 and len(A) > len(B) and A[:len(B)] == B and len(B) >= 2:
        return True
    if len(A) >= 2 and len(B) >= 2:
        if len(A) == len(B) and all(eq_tok(x, y) for x, y in zip(A, B)):
            return True
        if eq_tok(A[0], B[0]) and A[-1] == B[-1]:
            return True
        return False
    if not law:
        return False        # single surname-style merges are allowed for law-firm names only
    S, M = (A, B) if len(A) == 1 else (B, A)
    if len(S) == 1 and len(M) >= 2 and len(S[0]) >= 4 and S[0] not in COMMON:
        return S[0] in (M[0], M[-1])
    return False


LAW_WORDS = {'law', 'firm', 'attorney', 'attorneys', 'lawyer', 'lawyers', 'legal', 'offices', 'office'}


def variant_aliases(v, lawish_niche=False):
    """Normalised alias phrases for one observed spelling v."""
    raw = strip_paren(v)
    n = norm(raw)
    out = {n}
    n2 = strip_prefix(n)
    out.add(n2)
    out.add(strip_legal_tail(n2))
    c = core(n)
    lawish = lawish_niche or bool(set(n.split()) & LAW_WORDS)
    if lawish and len(c) >= 2:
        out.add(' '.join(c))        # person-name core of a law firm, e.g. "j michael hosterman"
    m = re.match(r'^([A-Z]{3,6})\b', raw.strip())
    if m:
        out.add(m.group(1).lower())  # acronym firm names such as GJEL
    return {a for a in out if a and len(a) >= 3}


def surname_aliases(variants, lawish_niche=False):
    """Surname alone, only for law-firm clusters that carry a person-name core."""
    cs = [core(norm(strip_paren(v))) for v in variants]
    lawish = lawish_niche or any(set(norm(strip_paren(v)).split()) & LAW_WORDS for v in variants)
    if not lawish or not any(len(c) >= 2 for c in cs):
        return set()
    out = set()
    for c in cs:
        if c and len(c) >= 2:
            out.add(c[-1])
        elif len(c) == 1:
            out.add(c[0])
    return {x for x in out if len(x) >= 5 and x not in COMMON and not x.isdigit()}


class UF:
    def __init__(self):
        self.p = {}
    def f(self, x):
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x
    def u(self, a, b):
        self.p[self.f(a)] = self.f(b)


def build_alias_table(variant_counts, seeds=(), curated=None, lawish_niche=False):
    """variant_counts: {observed string: field-day count}. Returns list of clusters:
    {'name','variants':[..],'aliases':[..],'field_days':n}."""
    curated = curated or {}
    allv = dict(variant_counts)
    for s in seeds:
        allv.setdefault(s, 0)
    allv = {v: c for v, c in allv.items() if is_business_like(v) or v in seeds}
    uf = UF()
    cores = {v: core(norm(strip_paren(v))) for v in allv}
    vs = sorted(allv)
    for v in vs:
        uf.f(v)
    for i, a in enumerate(vs):
        for b in vs[i + 1:]:
            if merge_cores(cores[a], cores[b], lawish_niche):
                uf.u(a, b)
    groups = collections.defaultdict(list)
    for v in vs:
        groups[uf.f(v)].append(v)
    seedn = {norm(strip_paren(s)): s for s in seeds}
    table = []
    for g in groups.values():
        name = None
        for v in g:
            if norm(strip_paren(v)) in seedn:
                name = seedn[norm(strip_paren(v))]
                break
        if name is None:
            name = max(g, key=lambda v: (allv[v], -len(v)))
        aliases = set()
        for v in g:
            aliases |= variant_aliases(v, lawish_niche)
        aliases |= surname_aliases(g, lawish_niche)
        cur = curated.get(norm(strip_paren(name)))
        if cur:
            aliases |= {norm(x) for x in cur}
        table.append({'name': name, 'variants': sorted(g), 'aliases': sorted(aliases),
                      'field_days': sum(allv[v] for v in g)})
    return table


def compile_alias(alias):
    return re.compile(r'(?<![a-z0-9])' + re.escape(alias).replace(r'\ ', ' ') + r'(?![a-z0-9])')


def text_hits(text, table):
    """Names of clusters whose name or alias appears in text."""
    nt = norm(text)
    hits = set()
    for cl in table:
        for a in cl['aliases']:
            if compile_alias(a).search(nt):
                hits.add(cl['name'])
                break
    return hits


def field_hits(field, table):
    """OLD method: clusters present in the extractor list, using the same alias merge."""
    hits = set()
    fn = {norm(strip_paren(x)) for x in (field or [])}
    for cl in table:
        vn = {norm(strip_paren(v)) for v in cl['variants']}
        if fn & vn:
            hits.add(cl['name'])
    return hits


def exact_field_hits(field, names):
    """OLD method, strictest: exact printed string only (no alias merge)."""
    fn = {norm(x) for x in (field or [])}
    return {n for n in names if norm(n) in fn}


# ---------- corpus loading ----------
def load_rows(corpus_dir, lo, hi, pattern='NB-CZ-API_*.json'):
    rows = []
    for f in sorted(glob.glob(os.path.join(corpus_dir, pattern))):
        b = os.path.basename(f)
        m = re.match(r'NB-CZ-API_(\d{4}-\d{2}-\d{2})_', b)
        if not m or not (lo <= m.group(1) <= hi):
            continue
        try:
            d = json.load(open(f))
        except Exception:
            continue
        d['_file'] = b
        rows.append(d)
    return rows


def is_answered(r):
    return (r.get('run_status') in ('OK', None)) and bool((r.get('answer_verbatim') or '').strip())


def daterange(lo, hi):
    a = datetime.date.fromisoformat(lo)
    b = datetime.date.fromisoformat(hi)
    while a <= b:
        yield a.isoformat()
        a += datetime.timedelta(days=1)


def day_status(rows, lo, hi):
    """rows: rows of ONE engine (one or more prompts). Returns answered_days:set, failed_days:list.
    A day with no answered run in the window is a failed day, not a miss."""
    ans = {r['date_utc'] for r in rows if is_answered(r) and lo <= r['date_utc'] <= hi}
    failed = [d for d in daterange(lo, hi) if d not in ans]
    return ans, failed


def fmt_of(n, d):
    return '%d of %d' % (n, d)


def host_fold(u, fold=True):
    if isinstance(u, dict):
        u = u.get('url') or u.get('link') or ''
    m = re.match(r'^[a-z]+://([^/:?#]+)', (u or '').strip().lower())
    h = m.group(1) if m else ''
    h = re.sub(r'^www\.', '', h)
    if fold:
        p = h.split('.')
        if len(p) > 2:
            h = '.'.join(p[-2:])
    return h
