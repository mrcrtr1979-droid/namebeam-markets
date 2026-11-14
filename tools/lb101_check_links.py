#!/usr/bin/env python3
"""LB-101 (2026-11-12, Laptop Fable): turn existing readers into free checks.

One plain check link, with its utm, on the study page, on every record page and on every trade page, above the fold on
phones. Three page classes, three utm_content values, one campaign:

  study   https://check.namebeam.ai/?utm_source=study&utm_campaign=lb101&utm_content=study_cta   (after the Finding,
          plus a link to the record pages index)
  record  https://check.namebeam.ai/?utm_source=record&utm_campaign=lb101&utm_content=record_cta (right after the h1)
  trade   https://check.namebeam.ai/?utm_source=trade&utm_campaign=lb101&utm_content=trade_cta   (right after the h1)

The block sits between <!--nb:lb101-cta--> markers so tools/refresh_pages.py can keep it on record pages it refreshes.
No new number appears in the inserted text. ASCII only.

Usage (from the repository root):
  py -3 -I tools/lb101_check_links.py --test    exit 1 and list every page that lacks its link (the build test)
  py -3 -I tools/lb101_check_links.py --apply   insert the block where it is missing (idempotent), then run the test
  py -3 -I tools/lb101_check_links.py --selftest
"""
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


def cta_block(kind):
    """The inserted HTML for one page class. Record and study pages use the site's .btn class; trade pages use .cta."""
    if kind == "study":
        href = CHECK_BASE % ("study", "study_cta")
        return (MARK_OPEN + '<p class="nb-check" id="nb-check"><a class="btn" href="' + href + '">' + CTA_TEXT + '</a>'
                ' <a href="/record/">Record pages, by market</a>.</p>' + MARK_CLOSE)
    if kind == "record":
        href = CHECK_BASE % ("record", "record_cta")
        return MARK_OPEN + '<p class="nb-check" id="nb-check"><a class="btn" href="' + href + '">' + CTA_TEXT + '</a></p>' + MARK_CLOSE
    if kind == "trade":
        href = CHECK_BASE % ("trade", "trade_cta")
        return MARK_OPEN + '<p class="nb-check" id="nb-check"><a class="cta" href="' + href + '">' + CTA_TEXT + '</a></p>' + MARK_CLOSE
    raise ValueError(kind)


def link_re(kind):
    src, content = {"study": ("study", "study_cta"), "record": ("record", "record_cta"), "trade": ("trade", "trade_cta")}[kind]
    return re.compile(r'href="https://check\.namebeam\.ai/\?utm_source=' + src + r'(?:&amp;|&)utm_campaign=lb101(?:&amp;|&)utm_content=' + content + '"')


def pages(root):
    """(kind, relative path) for every page the test grades."""
    root = Path(root)
    out = []
    if (root / STUDY_PATH).exists():
        out.append(("study", STUDY_PATH))
    for p in sorted((root / "record").glob("*/index.html")):
        out.append(("record", p.relative_to(root).as_posix()))
    for p in sorted((root / "trades").glob("*/index.html")):
        out.append(("trade", p.relative_to(root).as_posix()))
    return out


def check_page(kind, html):
    """None when the page carries its link where it must; else the reason."""
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


def insert_block(kind, html):
    """Insert the CTA block when the page lacks it. Returns the new html (unchanged when already present)."""
    if MARK_OPEN in html:
        return html
    block = cta_block(kind)
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


def run_test(root, out=sys.stdout):
    bad = []
    graded = pages(root)
    for kind, rel in graded:
        html = (Path(root) / rel).read_text(encoding="utf-8")
        why = check_page(kind, html)
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
        new = insert_block(kind, html)
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
