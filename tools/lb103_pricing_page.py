#!/usr/bin/env python3
"""LB-103 (2026-11-12, Laptop Fable): build test for the page of the type AI engines cite for tool-buying questions.

Page: what-ai-visibility-checks-cost/index.html, "What AI visibility checks cost and what each one records".
The test is RED when the page is missing or when any rule below fails, GREEN when every rule holds.

Rules graded (each one is a line in the Carter copy law or in the LB-103 packet):
  1. the page exists at the path above and is ASCII only (so no em or en dash, no emoji, no curly quote)
  2. title and h1 carry the page's question in plain words
  3. one "Last updated" line with a YYYY-MM-DD date, and the same date in the JSON-LD dateModified
  4. JSON-LD present, parses, and carries a WebPage and a Dataset (the record the page draws on)
  5. the free check link, exactly https://check.namebeam.ai/?utm_source=pricing&utm_campaign=lb103
  6. every price row (tr in a table.nb-prices) has five cells: tool, price as printed, what it tracks,
     a source URL starting with https://, and a read time like 2026-11-12 02:30AM CT
  7. no ranking or outcome words on the page (best, guarantee, number one, top rated, leader, first)
  8. the page is in sitemap.xml and llms.txt
  9. canonical link to https://markets.namebeam.ai/what-ai-visibility-checks-cost/

Usage (from the repository root):
  py -3 -I tools/lb103_pricing_page.py --test       exit 1 and list every failed rule (the build test)
  py -3 -I tools/lb103_pricing_page.py --selftest   the grader against a passing and a failing fixture
"""
import json
import re
import sys
import tempfile
from pathlib import Path

PAGE = "what-ai-visibility-checks-cost/index.html"
URL = "https://markets.namebeam.ai/what-ai-visibility-checks-cost/"
TITLE = "What AI visibility checks cost and what each one records"
CHECK_LINK = "https://check.namebeam.ai/?utm_source=pricing&amp;utm_campaign=lb103"
READ_TIME = re.compile(r"\b20\d\d-\d\d-\d\d \d\d:\d\d(?::\d\d)?(?:AM|PM) CT\b")
UPDATED = re.compile(r"Last updated[^<]*?(20\d\d-\d\d-\d\d)")
BANNED = re.compile(r"\b(best|guarantee[ds]?|number one|top[- ]rated|leader|first)\b", re.I)


def strip_tags(html):
    html = re.sub(r"<script.*?</script>", " ", html, flags=re.S)
    return re.sub(r"<[^>]+>", " ", html)


def check_page(html, sitemap="", llms=""):
    """List of failed rules (empty when GREEN)."""
    fails = []
    if not html.isascii():
        bad = sorted({c for c in html if not c.isascii()})
        fails.append("rule 1: non-ASCII characters %s" % " ".join("U+%04X" % ord(c) for c in bad[:8]))
    if not re.search(r"<title>\s*%s" % re.escape(TITLE), html):
        fails.append("rule 2: <title> does not start with the page question")
    if not re.search(r"<h1>\s*%s\s*</h1>" % re.escape(TITLE), html):
        fails.append("rule 2: <h1> is not the page question")
    m = UPDATED.search(html)
    if not m:
        fails.append("rule 3: no 'Last updated' line with a YYYY-MM-DD date")
    blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, flags=re.S)
    if not blocks:
        fails.append("rule 4: no JSON-LD block")
    else:
        types = set()
        dates = set()
        for b in blocks:
            try:
                data = json.loads(b)
            except ValueError as exc:
                fails.append("rule 4: JSON-LD does not parse (%s)" % exc)
                continue
            items = data.get("@graph", [data]) if isinstance(data, dict) else data
            for it in items:
                types.add(it.get("@type"))
                if it.get("dateModified"):
                    dates.add(it["dateModified"][:10])
                about = it.get("about")
                if isinstance(about, dict):
                    types.add(about.get("@type"))
        if "WebPage" not in types:
            fails.append("rule 4: JSON-LD has no WebPage")
        if "Dataset" not in types:
            fails.append("rule 4: JSON-LD has no Dataset")
        if m and m.group(1) not in dates:
            fails.append("rule 3: JSON-LD dateModified does not match the Last updated date")
    if CHECK_LINK not in html:
        fails.append("rule 5: the check link with utm_source=pricing and utm_campaign=lb103 is missing")
    tables = re.findall(r'<table class="nb-prices"[^>]*>(.*?)</table>', html, flags=re.S)
    if not tables:
        fails.append("rule 6: no table.nb-prices")
    rows = 0
    for t in tables:
        for tr in re.findall(r"<tr>(.*?)</tr>", t, flags=re.S):
            cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, flags=re.S)
            if not cells:
                continue  # header row
            rows += 1
            if len(cells) != 5:
                fails.append("rule 6: a price row has %d cells, not 5: %s" % (len(cells), strip_tags(cells[0])[:40]))
                continue
            src = strip_tags(cells[3]).strip()
            if not re.search(r'href="https://', cells[3]) or not src.startswith("https://"):
                fails.append("rule 6: no https source URL on the row for %s" % strip_tags(cells[0]).strip()[:40])
            if not READ_TIME.search(strip_tags(cells[4])):
                fails.append("rule 6: no CT read time on the row for %s" % strip_tags(cells[0]).strip()[:40])
    if tables and rows == 0:
        fails.append("rule 6: table.nb-prices has no price rows")
    body = re.search(r"<main>(.*?)</main>", html, flags=re.S)
    text = strip_tags(body.group(1) if body else html)  # the site footer's standard disclaimer is outside the rule
    hit = BANNED.search(text)
    if hit:
        fails.append("rule 7: banned word '%s'" % hit.group(0))
    if URL not in sitemap:
        fails.append("rule 8: page not in sitemap.xml")
    if URL not in llms:
        fails.append("rule 8: page not in llms.txt")
    if ('<link rel="canonical" href="%s">' % URL) not in html:
        fails.append("rule 9: canonical link missing")
    return fails


def run_test(root, out=sys.stdout):
    root = Path(root)
    page = root / PAGE
    if not page.exists():
        out.write("RED: %s is missing (0 of 9 rules can pass)\n" % PAGE)
        return 1
    html = page.read_text(encoding="utf-8", errors="replace")
    sitemap = (root / "sitemap.xml").read_text(encoding="utf-8", errors="replace") if (root / "sitemap.xml").exists() else ""
    llms = (root / "llms.txt").read_text(encoding="utf-8", errors="replace") if (root / "llms.txt").exists() else ""
    fails = check_page(html, sitemap, llms)
    if fails:
        out.write("RED: %d rule failure(s) on %s\n" % (len(fails), PAGE))
        for f in fails:
            out.write("  - %s\n" % f)
        return 1
    out.write("GREEN: %s passes all 9 rules (%d bytes)\n" % (PAGE, len(html.encode("ascii"))))
    return 0


def _fixture(good=True):
    date = "2026-11-12"
    ld = json.dumps({"@context": "https://schema.org", "@graph": [
        {"@type": "WebPage", "url": URL, "dateModified": date, "about": {"@type": "Dataset", "name": "x"}}]})
    row = ('<tr><td>Tool</td><td>95 USD a month</td><td>prompts</td><td><a href="https://peec.ai/pricing">https://peec.ai/pricing</a></td>'
           '<td>2026-11-12 02:30AM CT</td></tr>')
    html = ('<html><head><title>%s | Namebeam</title><link rel="canonical" href="%s"><script type="application/ld+json">%s</script></head>'
            '<body><h1>%s</h1><p>Last updated %s.</p><a href="%s">Free check</a><table class="nb-prices"><tr><th>a</th></tr>%s</table></body></html>'
            % (TITLE, URL, ld, TITLE, date, CHECK_LINK, row))
    if not good:
        html = html.replace("95 USD a month", "the best plan \u2014 95 USD").replace("2026-11-12 02:30AM CT", "today")
    return html


def selftest():
    good = check_page(_fixture(True), URL, URL)
    bad = check_page(_fixture(False), "", "")
    ok1 = good == []
    ok2 = len(bad) >= 5 and any("rule 1" in f for f in bad) and any("rule 6" in f for f in bad) and any("rule 7" in f for f in bad) and any("rule 8" in f for f in bad)
    with tempfile.TemporaryDirectory() as d:
        ok3 = run_test(d, out=open(Path(d) / "o.txt", "w")) == 1
    for name, ok in (("T1 passing fixture has no failures", ok1), ("T2 failing fixture trips rules 1, 6, 7, 8", ok2), ("T3 missing page is RED", ok3)):
        print("%s %s" % ("GREEN" if ok else "RED", name))
    print("selftest %s" % ("GREEN" if ok1 and ok2 and ok3 else "RED"))
    return 0 if ok1 and ok2 and ok3 else 1


def main(argv):
    if "--selftest" in argv:
        return selftest()
    root = Path(__file__).resolve().parent.parent
    return run_test(root)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
