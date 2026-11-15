"""Every email address a reader can SEE on a page (anchor text or plain text) sits inside Cloudflare's email_off markers.

Cloudflare Email Address Obfuscation rewrites a plain address in served HTML into a script-decoded placeholder, so a
reader without JavaScript sees no address. The marker pair opts the address out. Address-only href values with a label
such as "Contact" are not a visible address and are out of scope here. Stdlib only. Run: python3 -B -I tools/test_visible_addresses_email_off.py
"""
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOK = re.compile(r"(<!--.*?-->|<script\b.*?</script>|<style\b.*?</style>|<[^>]+>)", re.S)
ADDR = re.compile(r"(?<![\w.@-])(?:terry|hello)@namebeam\.ai(?![\w-])")


def visible_unwrapped(raw):
    bad, off = [], False
    for part in TOK.split(raw):
        if not part:
            continue
        if part == "<!--email_off-->":
            off = True
        elif part == "<!--/email_off-->":
            off = False
        elif TOK.fullmatch(part):
            continue
        elif not off:
            bad += ADDR.findall(part)
    return bad


class VisibleAddresses(unittest.TestCase):
    def test_no_visible_address_outside_email_off(self):
        problems = []
        for d, dirs, files in os.walk(ROOT):
            dirs[:] = [x for x in dirs if x != ".git"]
            for f in files:
                if f.endswith(".html"):
                    p = os.path.join(d, f)
                    with open(p, encoding="utf-8") as fh:
                        bad = visible_unwrapped(fh.read())
                    if bad:
                        problems.append((os.path.relpath(p, ROOT), bad))
        self.assertEqual(problems, [])


if __name__ == "__main__":
    unittest.main()
