#!/usr/bin/env python3
"""LB-101 (2026-11-12, Laptop Fable): turn existing readers into free checks.

One plain check link, with its utm, on the study page, on every record page and on every trade page, above the fold on
phones. Three page classes, three utm_content values, one campaign:

  study   https://check.namebeam.ai/?utm_source=study&utm_campaign=lb101&utm_content=study_cta   (after the Finding,
          plus a link to the record pages index)
  record  https://check.namebeam.ai/?utm_source=record&utm_campaign=lb101&utm_content=record_cta (right after the h1)
  trade   https://check.namebeam.ai/?utm_source=trade&utm_campaign=lb101&utm_content=trade_cta   (right after the h1)

Deep-link map (2026-11-24, L7 CHANGE 3, Counter J1123-94): tools/deeplink_cta_map.csv maps 18 record slugs to a
check link that carries city, state and trade. A mapped record page carries exactly its slug's deep link; an unmapped
record page carries the generic link above. cta_block, insert_block and check_page take the slug and grade this.
The block sits between <!--nb:lb101-cta--> markers so tools/refresh_pages.py can keep it on record pages it refreshes.
No new number appears in the inserted text. ASCII only.

Usage (from the repository root):
  py -3 -I tools/lb101_check_links.py --test    exit 1 and list every page that lacks its link (the build test)
  py -3 -I tools/lb101_check_links.py --apply   insert the block where it is missing (idempotent), then run the test
  py -3 -I tools/lb101_check_links.py --selftest
"""
import csv
import re
import sys
import tempfile
from pathlib import Path

CHECK_BASE = "https://check.namebeam.ai/?utm_source=%s&amp;utm_campaign=lb101&amp;utm_content=%s"
CTA_TEXT = "Check your own city and trade, free"
MARK_OPEN = "<!--nb:lb101-cta-->"
MARK_CLOSE = "<!--/nb:lb101-cta-->"
STUDY_PATH = "studies/three-engines-agreement-2026-10-24-to-11-09/index.html"
# the fold: the link must sit within this many characters after the h1 close, and before the first h2
FOLD_CHARS = 1500
DEEPLINK_CSV = Path(__file__).resolve().parent / "deeplink_cta_map.csv"
GENERIC_RECORD_HREF = "https://check.namebeam.ai/?utm_source=record&amp;utm_campaign=lb101&amp;utm_content=record_cta"


def load_deeplinks(path=None):
    """{record_slug: deep_link} for the record pages; rows for other page classes (what-ai-checks-*) are skipped."""
    out = {}
    with open(path or DEEPLINK_CSV, newline="", encoding="ascii") as fh:
        for row in csv.DictReader(fh):
            slug = row["record_slug"]
            if not slug.startswith("what-ai-checks-"):
                out[slug] = row["deep_link"]
    return out


def record_href(slug=None, deeplinks=None):
    """The href (HTML-escaped) a record page must carry: its deep link when mapped, else the generic lb101 link."""
    links = load_deeplinks() if deeplinks is None else deeplinks
    if slug in links:
        return links[slug].replace("&", "&amp;")
    return GENERIC_RECORD_HREF


def cta_block(kind, slug=None):
    """The inserted HTML for one page class. Record and study pages use the site's .btn class; trade pages use .cta."""
    if kind == "study":
        href = CHECK_BASE % ("study", "study_cta")
        return (MARK_OPEN + '<p class="nb-check" id="nb-check"><a class="btn" href="' + href + '">' + CTA_TEXT + '</a>'
                ' <a href="/record/">Record pages, by market</a>.</p>' + MARK_CLOSE)
    if kind == "record":
        href = record_href(slug)
        return MARK_OPEN + '<p class="nb-check" id="nb-check"><a class="btn" href="' + href + '">' + CTA_TEXT + '</a></p>' + MARK_CLOSE
    if kind == "trade":
        href = CHECK_BASE % ("trade", "trade_cta")
        return MARK_OPEN + '<p class="nb-check" id="nb-check"><a class="cta" href="' + href + '">' + CTA_TEXT + '</a></p>' + MARK_CLOSE
    raise ValueError(kind)


def link_re(kind):
    src, content = {"study": ("study", "study_cta"), "record": ("record", "record_cta"), "trade": ("trade", "trade_cta")}[kind]
    return re.compile(r'href="https://check\.namebeam\.ai/\?utm_source=' + src + r'(?:&amp;|&)utm_campaign=lb101(?:&amp;|&)utm_content=' + content + '"')


def pages(root):
    """(kind, relative path) for every page the test grades. Record pages are (kind, rel); the slug is the directory."""
    root = Path(root)
    out = []
    if (root / STUDY_PATH).exists():
        out.append(("study", STUDY_PATH))
    for p in sorted((root / "record").glob("*/index.html")):
        out.append(("record", p.relative_to(root).as_posix()))
    for p in sorted((root / "trades").glob("*/index.html")):
        out.append(("trade", p.relative_to(root).as_posix()))
    return out


def check_page(kind, html, slug=None):
    """None when the page carries its link where it must; else the reason."""
    if kind == "record":
        want = record_href(slug)
        mapped = want != GENERIC_RECORD_HREF
        # grade the link inside the marked block when the block is there, so another check link on the page cannot stand in
        a, b = html.find(MARK_OPEN), html.find(MARK_CLOSE)
        m = re.compile(r'href="(https://check\.namebeam\.ai/[^"]*)"').search(html, a if 0 <= a < b else 0)
        if not m:
            return "no check link with utm_source=record"
        got = m.group(1)
        if got != want:
            if mapped:
                return "mapped slug %s must carry its deep link, found %s" % (slug, got)
            if "deeplink1124" in got:
                return "unmapped slug %s carries a deep link" % slug
            return "no check link with utm_source=record utm_campaign=lb101"
    else:
        m = link_re(kind).search(html)
        if not m:
            return "no check link with utm_source=%s utm_campaign=lb101" % kind
    if MARK_OPEN not in html or MARK_CLOSE not in html:
        return "check link outside the nb:lb101-cta markers"
    if CTA_TEXT not in html:
        return "the plain CTA text is missing"
    if not html.isascii():
        return "non-ASCII byte on the page"
    if kind == "study":
        a = html.find("<h2>Finding</h2>")
        b = html.find("<h2>Chart</h2>")
        if a < 0 or b < 0 or not (a < m.start() < b):
            return "study CTA is not between the Finding and the Chart"
        block = html[html.find(MARK_OPEN):html.find(MARK_CLOSE)]
        if 'href="/record/"' not in block:
            return "study CTA block has no link to the record pages index"
        return None
    h1_end = html.find("</h1>")
    first_h2 = html.find("<h2")
    if h1_end < 0:
        return "no h1"
    if m.start() < h1_end:
        return "check link before the h1"
    if first_h2 >= 0 and m.start() > first_h2:
        return "check link below the first h2 (not above the fold)"
    if m.start() - h1_end > FOLD_CHARS:
        return "check link more than %d characters after the h1 (not above the fold)" % FOLD_CHARS
    return None


def insert_block(kind, html, slug=None):
    """Insert the CTA block when the page lacks it. Returns the new html (unchanged when already present)."""
    if MARK_OPEN in html:
        return html
    block = cta_block(kind, slug)
    if kind == "study":
        # after the Finding paragraph: the first </p> that follows <h2>Finding</h2>
        a = html.find("<h2>Finding</h2>")
        if a < 0:
            raise ValueError("study page has no Finding heading")
        p_end = html.find("</p>", a)
        if p_end < 0:
            raise ValueError("study page Finding has no paragraph")
        cut = p_end + len("</p>")
        return html[:cut] + "\n" + block + html[cut:]
    h1_end = html.find("</h1>")
    if h1_end < 0:
        raise ValueError("%s page has no h1" % kind)
    cut = h1_end + len("</h1>")
    return html[:cut] + "\n" + block + html[cut:]


def slug_of(kind, rel):
    return Path(rel).parent.name if kind == "record" else None


def run_test(root, out=sys.stdout):
    bad = []
    graded = pages(root)
    for kind, rel in graded:
        html = (Path(root) / rel).read_text(encoding="utf-8")
        why = check_page(kind, html, slug_of(kind, rel))
        if why:
            bad.append((rel, why))
    for rel, why in bad:
        out.write("RED  %s: %s\n" % (rel, why))
    counts = {k: sum(1 for kk, _ in graded if kk == k) for k in ("study", "record", "trade")}
    verdict = "GREEN" if not bad else "RED"
    out.write("%s lb101 check links: %d pages graded (study %d, record %d, trade %d), %d lacking\n"
              % (verdict, len(graded), counts["study"], counts["record"], counts["trade"], len(bad)))
    return 0 if not bad else 1


def run_apply(root, out=sys.stdout):
    changed = 0
    for kind, rel in pages(root):
        p = Path(root) / rel
        html = p.read_text(encoding="utf-8")
        new = insert_block(kind, html, slug_of(kind, rel))
        if new != html:
            p.write_bytes(new.encode("ascii"))
            changed += 1
            out.write("APPLIED %s\n" % rel)
    out.write("applied to %d pages\n" % changed)
    return run_test(root, out)


def selftest():
    import io
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "studies/three-engines-agreement-2026-10-24-to-11-09").mkdir(parents=True)
        (root / "record/x-dentists").mkdir(parents=True)
        (root / "trades/hvac").mkdir(parents=True)
        (root / STUDY_PATH).write_text("<html><h1>S</h1><h2>Finding</h2><p>Any two.</p><h2>Chart</h2><p>c</p></html>", encoding="utf-8")
        (root / "record/x-dentists/index.html").write_text("<html><h1>X</h1><p>q</p><h2>Receipt</h2></html>", encoding="utf-8")
        (root / "trades/hvac/index.html").write_text("<html><h1>HVAC</h1><p>h</p><h2>Per market</h2></html>", encoding="utf-8")
        buf = io.StringIO()
        red = run_test(root, buf)
        assert red == 1 and buf.getvalue().count("RED  ") == 3, buf.getvalue()
        buf = io.StringIO()
        green = run_apply(root, buf)
        assert green == 0 and "GREEN" in buf.getvalue(), buf.getvalue()
        # idempotent
        before = (root / STUDY_PATH).read_text(encoding="utf-8")
        assert run_apply(root, io.StringIO()) == 0 and before == (root / STUDY_PATH).read_text(encoding="utf-8")
        # a link below the fold is RED
        html = (root / "record/x-dentists/index.html").read_text(encoding="utf-8")
        blk = html[html.find(MARK_OPEN):html.find(MARK_CLOSE) + len(MARK_CLOSE)]
        (root / "record/x-dentists/index.html").write_text(html.replace(blk, "") + blk, encoding="utf-8")
        assert check_page("record", (root / "record/x-dentists/index.html").read_text(encoding="utf-8")) is not None
        # a study block without the record index link is RED
        s = (root / STUDY_PATH).read_text(encoding="utf-8").replace(' <a href="/record/">Record pages, by market</a>.', "")
        assert check_page("study", s) is not None
        # non-ASCII is RED
        assert check_page("trade", cta_block("trade").join(["<h1>T</h1>\n", "<h2>x</h2>—"])) is not None
    # deep-link map cases (2026-11-24)
    links = load_deeplinks()
    assert len(links) == 18 and "houston-hvac" in links and "what-ai-checks-hvac" not in links
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        for slug in ("houston-hvac", "x-tanning"):
            (root / "record" / slug).mkdir(parents=True)
            (root / "record" / slug / "index.html").write_text("<html><h1>X</h1><p>q</p><h2>Receipt</h2></html>", encoding="utf-8")
        run_apply(root, io.StringIO())
        mapped = (root / "record/houston-hvac/index.html").read_text(encoding="utf-8")
        unmapped = (root / "record/x-tanning/index.html").read_text(encoding="utf-8")
        assert links["houston-hvac"].replace("&", "&amp;") in mapped and "campaign=lb101" not in mapped
        assert check_page("record", mapped, "houston-hvac") is None
        assert check_page("record", unmapped, "x-tanning") is None and "campaign=lb101" in unmapped
        # a mapped slug with the generic link is RED; a wrong deep link is RED; an unmapped slug with a deep link is RED
        assert check_page("record", unmapped, "houston-hvac") is not None
        assert check_page("record", mapped.replace("city=Houston", "city=Dallas"), "houston-hvac") is not None
        assert check_page("record", mapped, "x-tanning") is not None
        assert check_page("record", unmapped, "x-tanning") is None
    for k in ("study", "record", "trade"):
        visible = re.sub(r"<!--.*?-->", "", re.sub(r"<[^>]+>", "", cta_block(k)))
        assert cta_block(k).isascii() and not re.search(r"\d", visible), (k, visible)
    print("selftest PASS")
    return 0


def main(argv):
    root = Path(__file__).resolve().parent.parent
    if "--selftest" in argv:
        return selftest()
    if "--apply" in argv:
        return run_apply(root)
    return run_test(root)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
