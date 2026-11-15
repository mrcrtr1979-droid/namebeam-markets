#!/usr/bin/env python3
"""Tests for the /buy/ buyer-gap copy (CPEO-1114, 2026-11-14): cancel method, free versus paid, what is verified,
day counts, buyer data. Stdlib only. Run: python3 -I tools/test_buy_buyer_gaps.py
Gap 2 (refund terms) is a founder policy call and is deliberately NOT on the page: test_no_refund_line pins that."""
import html
import os
import re
import unittest
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BLOCK = {"p", "div", "li", "h1", "h2", "h3", "h4", "ul", "br", "section", "tr", "td", "th"}


class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        elif tag in BLOCK and not self.skip:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip = max(0, self.skip - 1)
        elif tag in BLOCK and not self.skip:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def lines(path):
    p = _Text()
    with open(os.path.join(ROOT, path), encoding="utf-8") as fh:
        p.feed(fh.read())
    out = [re.sub(r"\s+", " ", ln).strip() for ln in html.unescape("".join(p.parts)).splitlines()]
    return [ln for ln in out if ln]


class BuyGaps(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.buy = lines("buy/index.html")
        cls.text = "\n".join(cls.buy)

    def test_cancel_method_on_both_subscriptions(self):
        sents = [ln for ln in self.buy if ln.startswith("Renews monthly until you cancel.")]
        self.assertEqual(len(sents), 2)
        for s in sents:
            self.assertIn("email terry@namebeam.ai from the address you used at checkout", s)
            self.assertIn("The next monthly charge stops.", s)

    def test_free_and_paid_one_line_each(self):
        free = [ln for ln in self.buy if ln.startswith("Free: ")]
        paid = [ln for ln in self.buy if ln.startswith("Paid adds: ")]
        self.assertEqual((len(free), len(paid)), (1, 1))
        self.assertIn("CC BY 4.0", free[0])

    def test_verified_in_one_place(self):
        i = next(k for k, ln in enumerate(self.buy) if ln.startswith("Every capture is a dated capture"))
        win = " ".join(self.buy[i:i + 3])
        for need in ("dated capture", "engine", "answer hash", "SHA-256", "verify the hash yourself"):
            self.assertIn(need, win)
        self.assertNotIn("not verified by", win.lower())

    def test_day_counts_defined(self):
        d = [ln for ln in self.buy if ln.startswith("A record page counts days two ways.")]
        self.assertEqual(len(d), 1)
        self.assertIn("Tracked days are the days we ran an engine.", d[0])
        self.assertIn("Answered days are the days that run returned an answer.", d[0])

    def test_buyer_data_fields_and_durations(self):
        d = [ln for ln in self.buy if ln.startswith("Collected about a buyer:")]
        self.assertEqual(len(d), 1)
        for need in ("your name", "your email address", "payment status", "up to 30 days", "up to 90 days", "terry@namebeam.ai"):
            self.assertIn(need, d[0])

    def test_no_refund_line(self):
        # Gap 2 is Terry's policy call (status/inbox/TO_TEAM-OFA.md desk row). Nothing may invent a refund term.
        self.assertIsNone(re.search(r"refund", self.text, re.I))

    def test_added_copy_ascii_and_no_dashes(self):
        added = [ln for ln in self.buy if ln.startswith(("Free: ", "Paid adds: ", "Every capture", "A record page counts",
                                                         "Collected about a buyer", "Renews monthly until you cancel."))]
        for ln in added:
            self.assertTrue(ln.isascii(), ln)
            self.assertIsNone(re.search(r" - | -- ", ln), ln)

    def test_retired_names_absent(self):
        low = self.text.lower()
        self.assertNotIn("alpha vault", low)
        self.assertNotIn("carter studio", low)

    def test_every_email_is_outside_cloudflare_obfuscation(self):
        # CPEO-1114 5:45PM CT: the served raw HTML showed 0 plain addresses (Cloudflare Email Address Obfuscation
        # rewrote all of them), so a reader without JavaScript saw no address on the cancel and data lines.
        raw = open(os.path.join(ROOT, "buy/index.html"), encoding="utf-8").read()
        anchors = re.findall(r'<a [^>]*href="mailto:[^"]*"[^>]*>[^<]*</a>', raw)
        self.assertEqual(len(anchors), 8)
        for a in anchors:
            self.assertIn("<!--email_off-->" + a + "<!--/email_off-->", raw)

    def test_asof_markers_kept(self):
        raw = open(os.path.join(ROOT, "buy/index.html"), encoding="utf-8").read()
        self.assertEqual(raw.count("<!--nb:buy-asof-->"), 1)
        self.assertEqual(raw.count("<!--/nb:buy-asof-->"), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
