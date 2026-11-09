"""LB15 deploy kit patch (derived from the laptop seat fable_patch.py).
Runs IN PLACE at the repo root: python3 -I lb15_patch_1108.py   (no arguments; work root and out dir are both ".").
Idempotent: exits 0 and changes nothing if the patch is already applied.
Wording fix (Team COS): new titles and H1s say "which ones AI answer engines named" and name no engines.
PATCH 1  sale-market landings: 3 record pages, agencies/index.html, buy/index.html
PATCH 2  sitemap and canonical truth: sitemap.xml and the 24 city report canonicals
Pure text edits; every edit asserts the anchor it replaces exists exactly once.
"""
import sys, os, re, shutil, html
from xml.etree import ElementTree as ET

W, OUT = ".", "."
HOST = "https://markets.namebeam.ai"
TODAY = "2026-11-08"

def rd(rel):
    with open(os.path.join(W, rel), encoding="utf-8", newline="") as fh:
        return fh.read()
def wr(rel, s):
    p = os.path.join(OUT, rel); os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="") as fh:
        fh.write(s)
def rep1(s, old, new, rel):
    n = s.count(old)
    assert n == 1, f"{rel}: anchor found {n} times: {old[:80]!r}"
    return s.replace(old, new)

changed = []

# ---------------- idempotent guard ----------------
def already_applied():
    try:
        dal = rd("record/dallas-dentists/index.html")
        if f'<link rel="canonical" href="{HOST}/record/dallas-dentists/">' in dal:
            return "Dallas canonical exists"
    except FileNotFoundError:
        pass
    try:
        if rd("sitemap.xml").count("<loc>") == 132:
            return "sitemap already has 132 loc"
    except FileNotFoundError:
        pass
    return None
_why = already_applied()
if _why:
    print(f"LB15 patch already applied ({_why}); nothing changed.")
    sys.exit(0)

# ---------------- PATCH 1 ----------------
SALE = {
 "record/dallas-dentists/index.html": dict(
    slug="dallas-dentists",
    old_title="Dallas TX, dentists, daily record | Namebeam",
    title="Dallas dentists: which ones AI answer engines named, day by day | Namebeam",
    old_h1="<h1>Dallas TX, dentists</h1>",
    h1="<h1>Dallas TX dentists: which ones AI answer engines named, day by day</h1>",
    desc="Asked word for word: Who is the best dentist in Dallas for a dental implant? The Dallas dentists each AI engine named, counted by day, 2026-10-02 to 2026-10-24, with a free CSV. A count, not a ranking."),
 "record/houston-hvac/index.html": dict(
    slug="houston-hvac",
    old_title="Houston TX, hvac repair and replacement, daily record | Namebeam",
    title="Houston HVAC companies: which ones AI answer engines named, day by day | Namebeam",
    old_h1="<h1>Houston TX, hvac repair and replacement</h1>",
    h1="<h1>Houston TX HVAC companies: which ones AI answer engines named, day by day</h1>",
    desc="Asked word for word: Who is the best HVAC company in Houston for AC repair? The Houston HVAC companies each AI engine named, counted by day, 2026-08-09 to 2026-10-07, with a free CSV per day. A count, not a ranking."),
 "record/atlanta-personal-injury/index.html": dict(
    slug="atlanta-personal-injury",
    old_title="Atlanta GA, personal injury attorneys, daily record | Namebeam",
    title="Atlanta personal injury lawyers: which ones AI answer engines named, day by day | Namebeam",
    old_h1="<h1>Atlanta GA, personal injury attorneys</h1>",
    h1="<h1>Atlanta GA personal injury lawyers: which ones AI answer engines named, day by day</h1>",
    desc="Asked word for word: Who is the best personal injury lawyer in Atlanta for a car accident case? The Atlanta personal injury lawyers each AI engine named, counted by day, 2026-08-09 to 2026-10-07, with a free CSV per day. A count, not a ranking."),
}
for rel, c in SALE.items():
    s = rd(rel)
    s = rep1(s, f"<title>{c['old_title']}</title>", f"<title>{c['title']}</title>", rel)
    m = re.search(r'<meta name="description" content="[^"]*">', s); assert m, rel
    s = s.replace(m.group(0), f'<meta name="description" content="{c["desc"]}">\n<link rel="canonical" href="{HOST}/record/{c["slug"]}/">', 1)
    s = rep1(s, c["old_h1"], c["h1"], rel)
    # the agencies paragraph: add a path to the scope page (/buy/) with utm so PostHog can attribute the click to this record page
    anchor = "We do not sell to the businesses we measure."
    assert s.count(anchor) == 1, rel
    s = s.replace(anchor, f'Scope, terms and what you keep: <a href="/buy/?utm_source=record&amp;utm_medium=page&amp;utm_campaign={c["slug"]}#market-record">the buy page</a>. {anchor}', 1)
    wr(rel, s); changed.append(rel)

rel = "agencies/index.html"; s = rd(rel)
s = rep1(s, '<link rel="stylesheet" href="/site.css">', f'<link rel="stylesheet" href="/site.css">\n<link rel="canonical" href="{HOST}/agencies/">', rel)
old_list = ('<h2>Start with a record page</h2><p>Every page below is free and ungated, with a CSV for each day.</p>'
            '<div class="pv-rel"><a href="/record/miami-roofing/">Miami roofing</a><a href="/record/atlanta-hvac/">Atlanta HVAC</a>'
            '<a href="/record/kansas-city-health-insurance/">Kansas City health insurance</a><a href="/record/">All questions</a></div>')
new_list = ('<h2>Start with a record page</h2><p>Three markets to start with. Every page is free and ungated, with a CSV for each day.</p>'
            '<div class="pv-rel"><a href="/record/dallas-dentists/">Dallas TX dentists</a><a href="/record/houston-hvac/">Houston TX HVAC companies</a>'
            '<a href="/record/atlanta-personal-injury/">Atlanta GA personal injury lawyers</a><a href="/record/">All questions</a></div>')
s = rep1(s, old_list, new_list, rel); wr(rel, s); changed.append(rel)

rel = "buy/index.html"; s = rd(rel)
s = rep1(s, '<link rel="stylesheet" href="/site.css">', f'<link rel="stylesheet" href="/site.css">\n<link rel="canonical" href="{HOST}/buy/">', rel)
wr(rel, s); changed.append(rel)

# ---------------- PATCH 2 ----------------
# 2a. report canonicals: point each city report at its own URL
for f in sorted(os.listdir(os.path.join(W, "reports"))):
    if not f.endswith(".html") or f == "index.html": continue
    rel = f"reports/{f}"; s = rd(rel)
    m = re.search(r'<link rel="canonical" href="([^"]*)">', s)
    if not m: continue
    own = f"{HOST}/reports/{f[:-5]}"      # clean URL, the form every other canonical on the site uses
    if m.group(1) == own: continue
    s = s.replace(m.group(0), f'<link rel="canonical" href="{own}">', 1)
    wr(rel, s); changed.append(rel)

# 2b. sitemap: hubs only, true lastmod or none
dated_re = re.compile(r"^record/[^/]+/\d{4}-\d{2}-\d{2}/index\.html$")
files = []
for d, dirs, fs in os.walk(W):
    dirs[:] = [x for x in dirs if not x.startswith(".")]
    for f in fs:
        if f.endswith(".html"):
            files.append(os.path.relpath(os.path.join(d, f), W).replace("\\", "/"))
def noindex(rel): return bool(re.search(r'<meta[^>]+name="robots"[^>]+noindex', rd(rel), re.I))
def url_of(rel):
    if rel == "index.html": return HOST + "/"
    if rel.endswith("/index.html"): return HOST + "/" + rel[:-len("index.html")]
    return HOST + "/" + rel[:-5]          # clean URL, matches the live sitemap's form
def page_date(rel):
    t = rd(rel)
    for pat in (r"Page built (\d{4}-\d{2}-\d{2})", r"As of (\d{4}-\d{2}-\d{2})", r"counted from the daily record on (\d{4}-\d{2}-\d{2})",
                r"[Cc]orrected (\d{4}-\d{2}-\d{2})", r"Released (\d{4}-\d{2}-\d{2})", r"generated (\d{4}-\d{2}-\d{2})"):
        m = re.search(pat, t)
        if m: return m.group(1)
    return None
old_sm = rd("sitemap.xml")
old_lm = dict(re.findall(r"<loc>(.*?)</loc>\s*<lastmod>(.*?)</lastmod>", old_sm))
hubs = [r for r in files if not dated_re.match(r) and not noindex(r) and r not in ("404.html",)]
# order: the three sale pages, agencies, buy, home, record index, then the rest alphabetically
first = ["record/dallas-dentists/index.html","record/houston-hvac/index.html","record/atlanta-personal-injury/index.html",
         "agencies/index.html","buy/index.html","index.html","record/index.html","check/index.html"]
ordered = first + sorted(r for r in hubs if r not in first)
entries = []
for r in ordered:
    lm = TODAY if r in changed else page_date(r)
    # keep the old lastmod only where it is not the bulk 2026-10-15 stamp and the page states no date of its own
    if not lm and old_lm.get(url_of(r)) and old_lm.get(url_of(r)) != "2026-10-15": lm = old_lm[url_of(r)]
    entries.append((url_of(r), lm))
xml = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
for u, lm in entries:
    xml.append("  <url>"); xml.append(f"    <loc>{u}</loc>")
    if lm: xml.append(f"    <lastmod>{lm}</lastmod>")
    xml.append("  </url>")
xml.append("</urlset>\n")
sm = "\n".join(xml); wr("sitemap.xml", sm); changed.append("sitemap.xml")
ET.fromstring(sm.encode())
print("sitemap entries:", len(entries), "with lastmod:", sum(1 for _, lm in entries if lm), "dated urls:", sum(1 for u,_ in entries if re.search(r"/record/[^/]+/\d{4}-", u)))
print("files written:", len(changed))
for c in changed: print("  ", c)
