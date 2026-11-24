"""mvc_counts.py - mentions versus citations: reproduces every count on the Namebeam "mentions vs citations" page.
Reads (read-only) the daily raw archives corpus/e1_raw/<date>.tar.gz (each holds e1/NB-CZ-API_*, e1/NB-CZ-SERP_*, e1/NB-CZ-AGREE_* JSON rows)
or a public repository tarball with the same e1/ folder. Writes nothing except the one CSV named by --csv.
The script requires the local domain-classification file used for this count. The input defines excluded directory, marketplace, national-brand and other domains, along with private normalization terms. The public script contains no private classification entries. Reproducing the counts requires this private file and eligible archive inputs.

Engines counted: only engines whose rows carry cited source URLs.
  perplexity : API rows, field sources_cited (a list of URLs). The 2026-11-08 policy took effect in the 2026-11-09 run, when the source lists were withheld.
               Those rows count as answered. A positive sources_count records that sources were returned. Their domains are unknown.
  google_ai_overview : SERP rows, field ai_overview_references (list of {href, title, source}); answer text is private under R82 for
               most rows, so only citation counts are made for it, never naming.
  anthropic, gemini, openai : rows carry no cited-URL field (sources_cited empty on every OK row), so they are not in the cross-tab.
               OpenAI changed at 2026-11-10 by OUR collection change (gpt-5-mini to gpt-5.6-terra); the split is only shown as row counts.
Answer text of Perplexity and of Google AI Overview is never printed or written: counts and rates only (R82).

Definitions (all mechanical, no judgment):
  answer row     : API row with run_status OK, row_type research_segment (the market question: "Who is the best <trade> in <city>?"), engine perplexity,
                   date 2026-09-28 to 2026-11-23 (Perplexity moved to the Agent API on 2026-09-28; earlier days are not mixed in).
  cited domain   : registered domain (last two host labels, three for co.uk style) of a URL in sources_cited.
  third party    : the cited domain is on the exclusion lists of the local classification file (directories, review sites, social, media,
                   marketplaces, government, education, national brands, website builders). The same rule data as scripts/gap_prospects.py; it is not printed here.
  business site  : any cited domain that is not third party.
  named          : a name in the row's recorded competitors_mentioned list matches the business's domain label. STRICT: the label equals the
                   name squashed (letters and digits only), or equals the name with generic words and market words removed. LOOSE (sensitivity):
                   strict, or a prefix match (both sides 8+ characters, or the distinctive part 5+). In the business-day comparison, cited URLs assign exposure and the name match uses the eligible domain label and recorded names. The separate identified-business row can also use cited domains as candidates for that match.
  Google-top business : a non-excluded domain in the organic results (organic_top_results, SERP row OK, same trade and city) on 5 or more
                   distinct days in the window.
  pair           : one Google-top business of a market and one Perplexity answer row of that market (same trade and city) on one day, so a
                   business-day. The unit of the cross-tab.
  own page cited : the pair's business domain is among the row's cited domains.
Usage: py -3 -I mvc_counts.py --classes CLASSES.txt [--csv OUT.csv] ARCHIVE [ARCHIVE ...]
  --classes is required. CLASSES.txt has [excluded_labels], [excluded_domains], [excluded_label_contains], [skip_slug_parts],
  [generic_brand_terms] and [trade_labels] sections; the rest of this script carries no list of individual domains, brands or businesses.
"""
import collections
import csv
import json
import math
import re
import sys
import tarfile
import unicodedata
import urllib.parse

WS, WE = "2026-09-28", "2026-11-23"          # answer-row window (Perplexity Agent API era through the last archive day)
CS, CE = "2026-10-02", "2026-10-24"          # window of the earlier 2026-11-03 cut, recounted here
MIN_DAYS = 5                                 # Google-top rule: on 5 or more days
OPENAI_SPLIT = "2026-11-10"                  # OUR collection change in the OpenAI series

SKIP_SLUG_PARTS = ()    # filled from the classification file: slug parts of single-business pilots and nationwide questions, which are not local-market rows

NAME = re.compile(r"NB-CZ-(API|SERP)_(\d{4}-\d\d-\d\d)_(segment_.+?)(?:_(openai|gemini|anthropic|perplexity))?\.json$")

# ---- domain classification: the rule data comes from the local classification file (--classes); no entry is embedded in this script ------
EXCLUDE_LABELS = set()
EXCLUDE_DOMAINS = set()
TRADE_LABELS = {}
EXCLUDE_TLDS = {'gov', 'edu', 'mil'}
EXCLUDE_LABEL_CONTAINS = ()
LOCAL_GOV_RE = re.compile(r'(^|\.)(state|ci|cityof|town|co|county)\.[a-z]{2}\.us$')
TWO_PART_SECOND_LEVEL = {'co', 'com', 'org', 'net', 'gov', 'edu', 'ac'}
GENERIC = set('''
hvac heating heat cooling cool air conditioning conditioner conditioners ac a c repair repairs service services company
co inc llc llp pllc pc pa corp corporation ltd the and of for in on at by to home homes residential commercial roofing
roof roofs roofer roofers contractor contractors construction exteriors plumbing plumber plumbers electric electrical
mechanical systems system solutions group enterprises associates partners law firm offices office lawyer lawyers attorney
attorneys injury injuries personal accident accidents legal dentist dentists dental dentistry orthodontics orthodontist
orthodontists family care health insurance agency agents agent real estate realty rentals rental management property
properties moving movers tanning salon salons tire tires shop shops auto oil change lube pros pro specialists experts
implant implants periodontics periodontist periodontists orthodontic braces cosmetic oral surgeons surgery
team technicians tech installation install replacement maintenance emergency local licensed certified professional
'''.split())


def load_classes(path):
    """Fill the rule data from the local domain-classification file. Required sections: excluded_labels, excluded_domains,
    excluded_label_contains, skip_slug_parts, generic_brand_terms (whitespace-separated tokens). Optional: trade_labels (lines 'raw => public')."""
    global EXCLUDE_LABELS, EXCLUDE_DOMAINS, EXCLUDE_LABEL_CONTAINS, SKIP_SLUG_PARTS, TRADE_LABELS
    sections, cur = {}, None
    with open(path, encoding="ascii") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("[") and line.endswith("]"):
                cur = line[1:-1].strip()
                sections.setdefault(cur, [])
                continue
            if cur is None:
                sys.exit("classification file: text before the first [section]")
            sections[cur].append(line)
    need = ("excluded_labels", "excluded_domains", "excluded_label_contains", "skip_slug_parts", "generic_brand_terms")
    missing = [k for k in need if not any(sections.get(k, []))]
    if missing:
        sys.exit("classification file is missing section(s): " + ", ".join(missing))
    EXCLUDE_LABELS = set(" ".join(sections["excluded_labels"]).split())
    EXCLUDE_DOMAINS = set(" ".join(sections["excluded_domains"]).split())
    EXCLUDE_LABEL_CONTAINS = tuple(" ".join(sections["excluded_label_contains"]).split())
    SKIP_SLUG_PARTS = tuple(" ".join(sections["skip_slug_parts"]).split())
    GENERIC.update(" ".join(sections["generic_brand_terms"]).split())
    TRADE_LABELS = {}
    for line in sections.get("trade_labels", []):
        if " => " in line:
            raw, public = line.split(" => ", 1)
            TRADE_LABELS[raw.strip()] = public.strip()


def clean(s):
    s = (s or '').replace('\u2013', '-').replace('\u2014', '-').replace('\u2019', "'").replace('\u2018', "'")
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('ascii')
    return re.sub(r'\s+', ' ', s).strip()


def tokens_of(s):
    t = clean(s).casefold().replace('&', ' and ')
    t = t.replace("'s ", 's ').replace("'", '')
    return re.findall(r'[a-z0-9]+', t)


def squash(s):
    return ''.join(tokens_of(s))


def squash_variants(s):
    a = squash(s)
    b = ''.join(re.findall(r'[a-z0-9]+', clean(s).casefold().replace('&', ' and ').replace("'s", '').replace("'", '')))
    c = ''.join(t for t in tokens_of(s) if t != 'and')
    return {x for x in (a, b, c) if x}


def url_host(url):
    try:
        h = urllib.parse.urlsplit((url or '').strip()).hostname or ''
    except ValueError:
        return ''
    h = h.lower().strip('.')
    return h[4:] if h.startswith('www.') else h


def reg_domain(host):
    parts = [p for p in (host or '').split('.') if p]
    if len(parts) < 2:
        return ''
    if len(parts) >= 3 and len(parts[-1]) == 2 and parts[-2] in TWO_PART_SECOND_LEVEL:
        return '.'.join(parts[-3:])
    return '.'.join(parts[-2:])


def domain_label(domain):
    parts = domain.split('.')
    if len(parts) >= 3 and len(parts[-1]) == 2 and parts[-2] in TWO_PART_SECOND_LEVEL:
        return parts[-3]
    return parts[-2] if len(parts) >= 2 else domain


def is_excluded(domain, host=''):
    if not domain:
        return True
    if domain.rsplit('.', 1)[-1] in EXCLUDE_TLDS or domain in EXCLUDE_DOMAINS:
        return True
    lab = domain_label(domain)
    if lab in EXCLUDE_LABELS or any(x in lab for x in EXCLUDE_LABEL_CONTAINS):
        return True
    return bool(LOCAL_GOV_RE.search(host or domain))


class NameKey(object):
    __slots__ = ('full', 'distinct')

    def __init__(self, name, market_tokens):
        self.full = squash_variants(name)
        self.distinct = ''.join(t for t in tokens_of(name) if t not in GENERIC and t not in market_tokens)


def match_strict(label, nk):
    return bool(label) and (label in nk.full or (nk.distinct != '' and label == nk.distinct))


def match_loose(label, nk):
    if match_strict(label, nk):
        return True
    if not label:
        return False
    for f in nk.full:
        if len(f) >= 8 and len(label) >= 8 and (label.startswith(f) or f.startswith(label)):
            return True
    d = nk.distinct
    return len(d) >= 5 and (label.startswith(d) or (len(label) >= 5 and d.startswith(label)))


def wilson(k, n, z=1.96):
    if n == 0:
        return ('', '')
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (round(max(0.0, 100 * (c - h)), 1), round(min(100.0, 100 * (c + h)), 1))


# ---- loading -------------------------------------------------------------------------------------------------------------
def load(archives):
    seen = set()
    perp = []          # Perplexity segment answer rows, status OK
    nosrc = []         # Claude, Gemini and OpenAI segment answer rows (names only; these engines carry no cited URLs)
    serp = []          # SERP segment rows, status OK
    eng = collections.Counter()   # (engine, period, field) counts for every OK API row
    biz = collections.Counter()   # Perplexity business-target rows
    for tgz in archives:
        with tarfile.open(tgz, "r:gz") as t:
            for m in t:
                if not m.isfile():
                    continue
                parts = m.name.split("/")
                if len(parts) < 2 or parts[-2] != "e1":
                    continue
                fn = parts[-1]
                if not (fn.startswith("NB-CZ-API_") or fn.startswith("NB-CZ-SERP_")):
                    continue
                if fn in seen:
                    raise ValueError("Duplicate file: " + fn)
                seen.add(fn)
                d = json.load(t.extractfile(m))
                date = d.get("date_utc") or ""
                if not (WS <= date <= WE):
                    continue
                if d.get("run_status") != "OK":
                    continue
                if fn.startswith("NB-CZ-API_"):
                    e = d.get("engine")
                    period = ("before_" if date < OPENAI_SPLIT else "from_") + OPENAI_SPLIT
                    cited = d.get("sources_cited") or []
                    eng[(e, period, "ok_rows")] += 1
                    eng[(e, period, "cited_url_field_nonempty")] += bool(cited)
                    if d.get("row_type") == "business":
                        if e == "perplexity":
                            biz["rows"] += 1
                            biz["cited_open"] += bool(cited)
                            biz["cited_private"] += bool(d.get("sources_private") and (d.get("sources_count") or 0) > 0)
                        continue
                    if d.get("row_type") != "research_segment":
                        continue
                    mm = NAME.search(fn)
                    if not mm:
                        continue
                    if e in ("anthropic", "gemini", "openai") and not any(x in mm.group(3) for x in SKIP_SLUG_PARTS):
                        nosrc.append({"engine": e, "date": date, "slug": mm.group(3), "market": d.get("market") or "",
                                      "names": [clean(n) for n in (d.get("competitors_mentioned") or []) if isinstance(n, str) and clean(n)]})
                    if e != "perplexity":
                        continue
                    if any(x in mm.group(3) for x in SKIP_SLUG_PARTS):
                        eng[("perplexity", "skipped_pilot_or_nationwide", "ok_rows")] += 1
                        continue
                    private = bool(d.get("sources_private"))
                    perp.append({
                        "date": date, "slug": mm.group(3), "niche": d.get("niche") or "", "market": d.get("market") or "",
                        "private": private, "nsrc": (d.get("sources_count") or 0) if private else len(cited),
                        "urls": [u for u in cited if isinstance(u, str)],
                        "names": [clean(n) for n in (d.get("competitors_mentioned") or []) if isinstance(n, str) and clean(n)],
                    })
                else:
                    mm = NAME.search(fn)
                    if not mm or d.get("row_type") != "research_segment" or any(x in mm.group(3) for x in SKIP_SLUG_PARTS):
                        continue
                    refs = d.get("ai_overview_references") or []
                    serp.append({
                        "date": date, "slug": mm.group(3),
                        "urls": [u for u in (d.get("organic_top_results") or []) if isinstance(u, str)],
                        "aio_present": bool(d.get("ai_overview_present")),
                        "aio_refs": [r.get("href") for r in refs if isinstance(r, dict) and isinstance(r.get("href"), str)],
                        "aio_text_held": bool(d.get("ai_overview_text")) and not d.get("ai_overview_private"),
                    })
    return perp, serp, eng, biz, nosrc


# ---- computing ------------------------------------------------------------------------------------------------------------
def google_top(serp, w0, w1):
    """{slug: set of domains that sit in Google organic results on MIN_DAYS or more distinct days}."""
    days = collections.defaultdict(lambda: collections.defaultdict(set))
    for r in serp:
        if not (w0 <= r["date"] <= w1):
            continue
        for u in r["urls"]:
            h = url_host(u)
            dom = reg_domain(h)
            if dom and not is_excluded(dom, h):
                days[r["slug"]][dom].add(r["date"])
    return {s: {d for d, ds in doms.items() if len(ds) >= MIN_DAYS} for s, doms in days.items()}


def classify_urls(urls):
    """(business domains, third-party domains, business domains whose homepage was cited)."""
    biz, third, home = set(), set(), set()
    for u in urls:
        h = url_host(u)
        dom = reg_domain(h)
        if not dom:
            continue
        if is_excluded(dom, h):
            third.add(dom)
            continue
        biz.add(dom)
        try:
            path = urllib.parse.urlsplit(u.strip()).path
        except ValueError:
            path = '/'
        if path in ('', '/'):
            home.add(dom)
    return biz, third, home


def analyze(perp, serp, w0, w1):
    """Row and pair counts for Perplexity segment rows dated w0..w1 (rows whose cited URLs are withheld are counted, then skipped)."""
    top = google_top(serp, w0, w1)
    C = collections.Counter()
    by_trade = collections.defaultdict(collections.Counter)
    per_biz = collections.defaultdict(lambda: [0, 0, 0, 0])   # (slug, domain): cited days, cited and named, not-cited days, not-cited and named (strict)
    for r in perp:
        if not (w0 <= r["date"] <= w1):
            continue
        T = by_trade[r["niche"]]
        C["answer_rows"] += 1
        T["answer_rows"] += 1
        if r["private"]:
            C["rows_urls_withheld"] += 1
            C["rows_urls_withheld_with_count"] += r["nsrc"] > 0
            continue
        C["rows_urls_readable"] += 1
        T["rows_urls_readable"] += 1
        mt = set(tokens_of(r["market"]))
        nks = [NameKey(n, mt) for n in r["names"]]
        C["rows_extracted_names_ge1"] += bool(nks)
        if not r["urls"]:
            C["rows_no_citation"] += 1
            T["rows_no_citation"] += 1
            continue
        C["rows_cited_ge1"] += 1
        T["rows_cited_ge1"] += 1
        biz, third, home = classify_urls(r["urls"])
        labels = {d: squash(domain_label(d)) for d in biz}
        own_named = any(match_strict(labels[d], nk) for d in biz for nk in nks)
        own_named_loose = own_named or any(match_loose(labels[d], nk) for d in biz for nk in nks)
        C["rows_own_site_of_named_business_cited_strict"] += own_named
        C["rows_own_site_of_named_business_cited_loose"] += own_named_loose
        if biz:
            C["rows_business_site_cited"] += 1
            T["rows_business_site_cited"] += 1
            if not own_named:
                C["rows_business_sites_cited_none_named_strict"] += 1
        else:
            C["rows_third_parties_only"] += 1
            T["rows_third_parties_only"] += 1
        tops = top.get(r["slug"], set())
        C["rows_in_markets_with_google_top_set"] += bool(tops)
        grp_other = "other_sites" if biz else "third_only"
        any_named_top = False
        for b in sorted(tops):
            lab = squash(domain_label(b))
            cited = b in biz
            ns = any(match_strict(lab, nk) for nk in nks)
            nl = ns or any(match_loose(lab, nk) for nk in nks)
            any_named_top = any_named_top or ns
            if cited:
                keys = ["own_cited", "own_cited_" + ("home" if b in home else "inner")]
            else:
                keys = ["not_cited_row_" + grp_other]
            for k in keys + ["all_pairs"]:
                for X in (C, T):
                    X["pairs_" + k] += 1
                    X["named_strict_" + k] += ns
                    X["named_loose_" + k] += nl
            pb = per_biz[(r["slug"], b)]
            if cited:
                pb[0] += 1
                pb[1] += ns
            else:
                pb[2] += 1
                pb[3] += ns
        C["rows_naming_google_top_strict"] += any_named_top
        C["rows_naming_identified_business_strict"] += (any_named_top or own_named)
    both = [v for v in per_biz.values() if v[0] > 0 and v[2] > 0]
    hi = sum(1 for v in both if v[1] / v[0] > v[3] / v[2])
    lo = sum(1 for v in both if v[1] / v[0] < v[3] / v[2])
    C["within_business_n"] = len(both)
    C["within_business_cited_rate_higher"] = hi
    C["within_business_cited_rate_lower"] = lo
    C["within_business_cited_rate_equal"] = len(both) - hi - lo
    answered = {r["slug"] for r in perp if w0 <= r["date"] <= w1 and not r["private"]}
    C["google_top_businesses_in_answered_markets"] = sum(len(top.get(s, ())) for s in answered)
    C["markets_answered"] = len({r["slug"] for r in perp if w0 <= r["date"] <= w1})
    C["answer_days"] = len({r["date"] for r in perp if w0 <= r["date"] <= w1})
    C["segments_with_google_top_set"] = len([s for s in answered if top.get(s)])
    return C, by_trade


def named_rate(rows, serp, w0, w1):
    """(named, pairs, answer rows in markets with a Google-top set) for engines that carry no cited URLs: same pairs, same strict rule."""
    top = google_top(serp, w0, w1)
    named = pairs = nrows = 0
    for r in rows:
        if not (w0 <= r["date"] <= w1):
            continue
        tops = top.get(r["slug"], set())
        if not tops:
            continue
        nrows += 1
        mt = set(tokens_of(r["market"]))
        nks = [NameKey(n, mt) for n in r["names"]]
        for b in tops:
            lab = squash(domain_label(b))
            pairs += 1
            named += any(match_strict(lab, nk) for nk in nks)
    return named, pairs, nrows


def aio_counts(serp, w0, w1, top):
    """Google AI Overview: SERP rows OK, research_segment, overview captured. Citation counts only; naming not computed (text private, R82)."""
    C = collections.Counter()
    for r in serp:
        if not (w0 <= r["date"] <= w1):
            continue
        C["serp_rows_ok"] += 1
        if not r["aio_present"]:
            continue
        C["aio_rows"] += 1
        C["aio_rows_text_held"] += r["aio_text_held"]
        if not r["aio_refs"]:
            C["aio_rows_no_reference"] += 1
            continue
        C["aio_rows_cited_ge1"] += 1
        biz, third, _ = classify_urls(r["aio_refs"])
        if biz & top.get(r["slug"], set()):
            C["aio_rows_cites_google_top_business_site"] += 1
        elif biz:
            C["aio_rows_cites_other_business_sites_only"] += 1
        else:
            C["aio_rows_cites_third_parties_only"] += 1
    return C


PAIR_KEYS = ("all_pairs", "own_cited", "own_cited_home", "own_cited_inner", "not_cited_row_third_only", "not_cited_row_other_sites")


def main(archives, csv_path):
    perp, serp, eng, biz, nosrc = load(archives)
    rows = []

    def add(window, engine, population, measure, num, den=None, note=""):
        rate, lo, hi = "", "", ""
        if den:
            rate = round(100.0 * num / den, 1)
            lo, hi = wilson(num, den)
        rows.append([window[0], window[1], engine, population, measure, num, "" if den is None else den, rate, lo, hi, note])

    W = (WS, WE)
    before, after = "before_" + OPENAI_SPLIT, "from_" + OPENAI_SPLIT
    for e in sorted({k[0] for k in eng}):
        carries = eng[(e, before, "cited_url_field_nonempty")] + eng[(e, after, "cited_url_field_nonempty")] > 0
        for period in (before, after):
            add(W, e, "ok_api_rows_" + period, "ok_rows_with_nonempty_cited_url_field", eng[(e, period, "cited_url_field_nonempty")], eng[(e, period, "ok_rows")],
                "carries cited URLs" if carries else "no cited-URL field on any OK row: not in the cross-tab")
    opens = [r["date"] for r in perp if not r["private"]]
    open_end = max(opens) if opens else WE
    firstpriv = min([r["date"] for r in perp if r["private"]] or [WE])
    wd = (WS, open_end)
    Ca, _ = analyze(perp, serp, WS, WE)
    add(W, "perplexity", "segment_rows", "answer_rows_ok", Ca["answer_rows"], None,
        "run_status OK, row_type research_segment, local-market segments only; %d run days, %d segments" % (Ca["answer_days"], Ca["markets_answered"]))
    add(W, "perplexity", "segment_rows", "rows_skipped_pilot_or_nationwide_segments", eng[("perplexity", "skipped_pilot_or_nationwide", "ok_rows")], None, "slugs of single-business pilots and of nationwide questions: not counted anywhere below")
    add(W, "perplexity", "segment_rows", "rows_cited_urls_withheld_from_" + firstpriv, Ca["rows_urls_withheld"], Ca["answer_rows"], "sources_private true (policy CAP 2026-11-08); sources_count kept; domains unknown")
    add(W, "perplexity", "segment_rows", "rows_withheld_with_sources_count_ge1", Ca["rows_urls_withheld_with_count"], Ca["rows_urls_withheld"])
    C, byT = analyze(perp, serp, WS, open_end)
    add(wd, "perplexity", "segment_rows", "rows_with_readable_cited_urls", C["rows_urls_readable"], Ca["answer_rows"], "denominator is all answer rows 2026-09-28 to 2026-11-23")
    rd = C["rows_urls_readable"]
    add(wd, "perplexity", "readable_rows", "rows_cited_ge1_url", C["rows_cited_ge1"], rd)
    add(wd, "perplexity", "readable_rows", "rows_no_citation", C["rows_no_citation"], rd)
    add(wd, "perplexity", "readable_rows", "rows_citing_only_third_parties", C["rows_third_parties_only"], C["rows_cited_ge1"], "directories, review sites, social, media, government, national brands (exclusion lists of the classification file)")
    add(wd, "perplexity", "readable_rows", "rows_citing_at_least_one_business_site", C["rows_business_site_cited"], C["rows_cited_ge1"])
    add(wd, "perplexity", "readable_rows", "rows_own_site_of_a_named_business_cited_strict", C["rows_own_site_of_named_business_cited_strict"], C["rows_cited_ge1"], "a cited domain label equals a name in the row's extracted names")
    add(wd, "perplexity", "readable_rows", "rows_own_site_of_a_named_business_cited_loose", C["rows_own_site_of_named_business_cited_loose"], C["rows_cited_ge1"], "sensitivity: prefix matches added")
    add(wd, "perplexity", "readable_rows", "rows_business_sites_cited_but_none_named_strict", C["rows_business_sites_cited_none_named_strict"], C["rows_cited_ge1"])
    add(wd, "perplexity", "readable_rows", "rows_with_extracted_names_ge1", C["rows_extracted_names_ge1"], rd, "raw extracted list; includes headings and place names: upper bound")
    add(wd, "perplexity", "readable_rows", "rows_in_markets_with_a_google_top_set", C["rows_in_markets_with_google_top_set"], rd, "markets with a Google-top business on 5 or more days")
    add(wd, "perplexity", "readable_rows", "rows_naming_a_google_top_business_strict", C["rows_naming_google_top_strict"], C["rows_in_markets_with_google_top_set"], "a recorded name strictly matches an eligible organic-result domain in the same market")
    add(wd, "perplexity", "readable_rows", "rows_naming_an_identified_business_strict", C["rows_naming_identified_business_strict"], rd, "a recorded name strictly matches an eligible organic-result domain or an eligible cited domain")
    add(wd, "perplexity", "readable_rows", "google_top_businesses_in_answered_markets", C["google_top_businesses_in_answered_markets"], None, "domains on %d or more Google days, %d segments" % (MIN_DAYS, C["segments_with_google_top_set"]))
    for k in PAIR_KEYS:
        add(wd, "perplexity", "pairs", "pairs_" + k, C["pairs_" + k], C["pairs_all_pairs"] if k != "all_pairs" else None)
    for rule in ("strict", "loose"):
        for k in PAIR_KEYS:
            add(wd, "perplexity", "pairs", "P(named | %s) %s" % (k, rule), C["named_%s_%s" % (rule, k)], C["pairs_" + k], "business named in the row's extracted names; cited URLs not used")
    add(wd, "perplexity", "pairs", "P(named | no citations)", 0, 0, "no readable row has zero cited URLs: undefined")
    for rule in ("strict", "loose"):
        add(wd, "perplexity", "pairs", "P(own page cited | named) " + rule, C["named_%s_own_cited" % rule], C["named_%s_all_pairs" % rule], "of business-days on which the business was named")
    add(wd, "perplexity", "within_business", "businesses_with_cited_days_and_not_cited_days", C["within_business_n"], None, "strict naming")
    add(wd, "perplexity", "within_business", "of_those_named_rate_higher_on_cited_days", C["within_business_cited_rate_higher"], C["within_business_n"])
    add(wd, "perplexity", "within_business", "of_those_named_rate_lower_on_cited_days", C["within_business_cited_rate_lower"], C["within_business_n"])
    add(wd, "perplexity", "within_business", "of_those_named_rate_equal", C["within_business_cited_rate_equal"], C["within_business_n"])
    for trade, T in sorted(byT.items()):
        pop = "trade=" + TRADE_LABELS.get(trade, trade)
        add(wd, "perplexity", pop, "readable_rows", T["rows_urls_readable"], None)
        add(wd, "perplexity", pop, "rows_citing_only_third_parties", T["rows_third_parties_only"], T["rows_cited_ge1"])
        add(wd, "perplexity", pop, "P(named | own_cited) strict", T["named_strict_own_cited"], T["pairs_own_cited"])
        add(wd, "perplexity", pop, "P(named | not_cited_row_third_only) strict", T["named_strict_not_cited_row_third_only"], T["pairs_not_cited_row_third_only"])
        add(wd, "perplexity", pop, "P(named | not_cited_row_other_sites) strict", T["named_strict_not_cited_row_other_sites"], T["pairs_not_cited_row_other_sites"])
    CW = (CS, CE)
    C2, _ = analyze(perp, serp, CS, CE)
    add(CW, "perplexity", "recount_of_earlier_cut", "answer_rows_ok", C2["answer_rows"], None, "%d segments, %d with a Google-top set; the 2026-11-03 email said 30 markets" % (C2["markets_answered"], C2["segments_with_google_top_set"]))
    add(CW, "perplexity", "recount_of_earlier_cut", "pairs_all_pairs", C2["pairs_all_pairs"], None, "own page cited: %d (homepage %d, inner page %d); the 2026-11-03 email counted 337 homepage and 239 location-page days" % (C2["pairs_own_cited"], C2["pairs_own_cited_home"], C2["pairs_own_cited_inner"]))
    for k in PAIR_KEYS[1:]:
        add(CW, "perplexity", "recount_of_earlier_cut", "P(named | %s) strict" % k, C2["named_strict_" + k], C2["pairs_" + k])
        add(CW, "perplexity", "recount_of_earlier_cut", "P(named | %s) loose" % k, C2["named_loose_" + k], C2["pairs_" + k])
    for e in ("anthropic", "gemini", "openai"):
        for (a0, a1), tag in (((WS, "2026-11-09"), "before_" + OPENAI_SPLIT), (("2026-11-10", WE), "from_" + OPENAI_SPLIT)):
            n, pr, nr = named_rate([x for x in nosrc if x["engine"] == e], serp, a0, a1)
            add((a0, a1), e, "no_source_list_" + tag, "P(named) strict, same business-days", n, pr, "%d answer rows in markets with a Google-top set; no cited URLs, so no cross-tab" % nr)
    add(W, "perplexity", "business_target_rows", "ok_rows", biz["rows"], None, "single-business pilot rows: outside the market cross-tab")
    top = google_top(serp, WS, WE)
    A = aio_counts(serp, WS, WE, top)
    add(W, "google_ai_overview", "segment_serp_rows", "serp_rows_ok", A["serp_rows_ok"], None)
    add(W, "google_ai_overview", "segment_serp_rows", "rows_with_overview_captured", A["aio_rows"], A["serp_rows_ok"], "ai_overview_present true; capture can miss overviews and does not estimate how often Google displays one")
    add(W, "google_ai_overview", "overview_rows", "rows_with_text_held_public", A["aio_rows_text_held"], A["aio_rows"], "all other overview text withheld under R82; naming not computed")
    add(W, "google_ai_overview", "overview_rows", "rows_cited_ge1_reference", A["aio_rows_cited_ge1"], A["aio_rows"])
    add(W, "google_ai_overview", "overview_rows", "rows_citing_only_third_parties", A["aio_rows_cites_third_parties_only"], A["aio_rows_cited_ge1"])
    add(W, "google_ai_overview", "overview_rows", "rows_citing_a_google_top_business_site", A["aio_rows_cites_google_top_business_site"], A["aio_rows_cited_ge1"])
    add(W, "google_ai_overview", "overview_rows", "rows_citing_other_business_sites_only", A["aio_rows_cites_other_business_sites_only"], A["aio_rows_cited_ge1"])

    head = ["window_start", "window_end", "engine", "population", "measure", "numerator", "denominator", "rate_pct", "ci95_lo", "ci95_hi", "note"]
    out = [head] + rows
    csv.writer(sys.stdout, lineterminator="\n").writerows(out)
    if csv_path:
        with open(csv_path, "w", newline="", encoding="ascii") as f:
            csv.writer(f, lineterminator="\n").writerows(out)


if __name__ == "__main__":
    usage = "Usage: mvc_counts.py --classes CLASSES.txt [--csv OUT.csv] ARCHIVE [ARCHIVE ...]"
    args = sys.argv[1:]
    csv_path = classes = None
    while args[:1] and args[0] in ("--csv", "--classes"):
        if len(args) < 2:
            sys.exit(usage)
        if args[0] == "--csv":
            csv_path = args[1]
        else:
            classes = args[1]
        args = args[2:]
    if not classes or not args:
        sys.exit(usage)
    load_classes(classes)
    main(args, csv_path)
