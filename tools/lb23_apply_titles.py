#!/usr/bin/env python3
"""lb23_apply_titles.py: agency-intent <title> and <meta name="description"> on the 3 sale-market record hubs, the 3 city
panels and /buy/ (LB-23 part 5, 2026-11-09). Self-canonicals untouched. Every string is ASCII, carries its date, names no
competitor and makes no ranking or outcome promise. Run from the repo root: py -I tools/lb23_apply_titles.py [--check]
"""
import re, sys, os

PAGES = {
    "record/dallas-dentists/index.html": (
        "Dallas dentists: dated AI answer record for agencies | Namebeam",
        "Asked word for word: Who is the best dentist in Dallas for a dental implant? The names each AI engine returned, counted by day, 2026-10-02 to 2026-10-24, free CSV. A count, not a ranking."),
    "record/houston-hvac/index.html": (
        "Houston HVAC: dated AI answer record for agencies | Namebeam",
        "Asked word for word: Who is the best HVAC company in Houston for AC repair? The names each AI engine returned, counted by day, 2026-08-09 to 2026-10-07, free CSV. A count, not a ranking."),
    "record/atlanta-personal-injury/index.html": (
        "Atlanta injury law: dated AI answer record for agencies | Namebeam",
        "Asked word for word: Who is the best personal injury lawyer in Atlanta for a car accident case? The names each AI engine returned by day, 2026-08-09 to 2026-10-07, free CSV. A count, not a ranking."),
    "panels/dallas-tx.html": (
        "Dallas TX: AI answer record by engine, for agencies | Namebeam",
        "Dallas TX panel: which local businesses four AI answer engines named for fixed buyer questions, 2026-09-01 to 2026-09-30, counted from the dated daily record. For agencies. A count, not a ranking."),
    "panels/houston-tx.html": (
        "Houston TX: AI answer record by engine, for agencies | Namebeam",
        "Houston TX panel: which local businesses four AI answer engines named for fixed buyer questions, 2026-09-01 to 2026-09-30, counted from the dated daily record. For agencies. A count, not a ranking."),
    "panels/atlanta-ga.html": (
        "Atlanta GA: AI answer record by engine, for agencies | Namebeam",
        "Atlanta GA panel: which local businesses four AI answer engines named for fixed buyer questions, 2026-09-01 to 2026-09-30, counted from the dated daily record. For agencies. A count, not a ranking."),
    "buy/index.html": (
        "Buy the dated AI answer record, for agencies | Namebeam",
        "Market Record, $49 a month per market as of 2026-11-09: the names AI answer engines returned, day by day, as a dated CSV and PDF. Fixed scope, what you keep, renewal terms. For agencies."),
}
BANNED = re.compile(r"\b(best|top|boost|guarantee|grow|leads|rank(?!ing\b))\w*", re.I)


def check():
    bad = 0
    for p, (t, d) in PAGES.items():
        for label, s, lo, hi in (("title", t, 20, 66), ("description", d, 110, 200)):
            if any(ord(c) > 126 for c in s): print("NON-ASCII", p, label); bad += 1
            if " - " in s or "\u2013" in s or "\u2014" in s: print("DASH", p, label); bad += 1
            if not (lo <= len(s) <= hi): print("LENGTH", p, label, len(s)); bad += 1
            words = [m.group(0) for m in BANNED.finditer(s) if not (m.group(0).lower() == "best" and "Asked word for word" in s)]
            if words: print("BANNED", p, label, words); bad += 1
            if not re.search(r"20\d\d-\d\d-\d\d", s) and label == "description": print("NO DATE", p); bad += 1
    print("check:", "PASS" if bad == 0 else "FAIL %d" % bad)
    return bad == 0


def apply(root):
    changed = 0
    for p, (t, d) in PAGES.items():
        path = os.path.join(root, p)
        s = open(path, encoding="utf-8").read()
        s2, n1 = re.subn(r"<title>[^<]*</title>", "<title>" + t + "</title>", s, count=1)
        s2, n2 = re.subn(r'<meta name="description" content="[^"]*"', '<meta name="description" content="' + d.replace('"', "&quot;") + '"', s2, count=1)
        if n1 != 1 or n2 != 1:
            print("SKIP (tags not found exactly once):", p, n1, n2); continue
        if s2 != s:
            open(path, "w", encoding="utf-8", newline="").write(s2)
            changed += 1
            print("updated", p)
    print("files changed:", changed)
    return changed


if __name__ == "__main__":
    ok = check()
    if "--check" in sys.argv or not ok:
        sys.exit(0 if ok else 1)
    apply(os.getcwd())
