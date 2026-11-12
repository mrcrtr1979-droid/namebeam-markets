#!/usr/bin/env python3
"""lb23_inject_sample.py: add one <script src="/sample.js" defer></script> tag, right after the /posthog.js tag, to every
page that carries the LB-19 offer line marker (<!-- lb19:offer -->). Idempotent: a page that already has the tag is left
alone. Run from the repo root: py -I tools/lb23_inject_sample.py [--dry-run]. LB-23 part 1a (2026-11-09).
"""
import os, sys

MARK = "<!-- lb19:offer -->"
PH = '<script src="/posthog.js" defer></script>'
TAG = '<script src="/sample.js" defer></script>'


def main(root, dry):
    seen = changed = already = no_ph = 0
    for dp, dn, fn in os.walk(root):
        if "/.git" in dp.replace("\\", "/") or "/node_modules" in dp.replace("\\", "/"):
            continue
        for f in fn:
            if not f.endswith(".html"):
                continue
            p = os.path.join(dp, f)
            s = open(p, encoding="utf-8").read()
            if MARK not in s:
                continue
            seen += 1
            if TAG in s:
                already += 1
                continue
            if PH not in s:
                no_ph += 1
                print("no posthog tag:", os.path.relpath(p, root))
                continue
            s2 = s.replace(PH, PH + "\n" + TAG, 1)
            if not dry:
                open(p, "w", encoding="utf-8", newline="").write(s2)
            changed += 1
    print("pages with offer line: %d | tag added: %d | already had it: %d | no posthog tag: %d%s" % (seen, changed, already, no_ph, " (dry run)" if dry else ""))
    return 0 if no_ph == 0 else 1


if __name__ == "__main__":
    sys.exit(main(os.getcwd(), "--dry-run" in sys.argv))
