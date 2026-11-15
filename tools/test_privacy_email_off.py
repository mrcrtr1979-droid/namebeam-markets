"""Pins the /privacy/ email addresses outside Cloudflare Email Address Obfuscation.

Cloudflare rewrites plain addresses in served HTML into a script-decoded
placeholder. The email_off markers opt each address out, so the address shows
without JavaScript. Stdlib only.
"""
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ANCHOR = re.compile(r'<a [^>]*href="mailto:[^"]*"[^>]*>[^<]*</a>')


class PrivacyEmailOff(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(ROOT, "privacy", "index.html"), encoding="utf-8") as f:
            self.raw = f.read()

    def test_every_email_is_outside_cloudflare_obfuscation(self):
        anchors = ANCHOR.findall(self.raw)
        self.assertEqual(len(anchors), 5)
        for a in anchors:
            self.assertIn("<!--email_off-->" + a + "<!--/email_off-->", self.raw)

    def test_no_address_outside_an_anchor(self):
        bare = ANCHOR.sub("", self.raw)
        self.assertNotIn("@namebeam.ai", bare)

    def test_markers_balanced(self):
        self.assertEqual(self.raw.count("<!--email_off-->"), self.raw.count("<!--/email_off-->"))


if __name__ == "__main__":
    unittest.main()
