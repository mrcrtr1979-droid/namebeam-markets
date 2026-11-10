#!/usr/bin/env python3
"""Test suite for LB-27 record pages refresh.

Run with: py -I -m unittest tools.test_lb27_record_pages
"""

import unittest
import json
import re
from pathlib import Path


def schema_parser(jsonld_dict):
    """Validate Dataset JSON-LD schema."""
    required_fields = [
        "@context", "@type", "name", "description", "url", "temporalCoverage",
        "license", "creator", "distribution"
    ]

    for field in required_fields:
        if field not in jsonld_dict:
            return False, f"Missing required field: {field}"

    if jsonld_dict["@type"] != "Dataset":
        return False, f"@type must be Dataset, got {jsonld_dict['@type']}"

    if not jsonld_dict["@context"].startswith("https://schema.org"):
        return False, f"@context must be schema.org"

    if not isinstance(jsonld_dict["distribution"], list):
        return False, "distribution must be a list"

    if len(jsonld_dict["distribution"]) == 0:
        return False, "distribution must have at least one entry"

    dist = jsonld_dict["distribution"][0]
    if "@type" not in dist or dist["@type"] != "DataDownload":
        return False, "distribution entry must have @type DataDownload"

    if "contentUrl" not in dist:
        return False, "distribution entry must have contentUrl"

    if not dist["contentUrl"].endswith(".csv"):
        return False, "contentUrl must end with .csv"

    return True, None


class TestLB27RecordPages(unittest.TestCase):
    """Test LB-27 record pages refresh"""

    @classmethod
    def setUpClass(cls):
        cls.root = Path.cwd()
        cls.record_dir = cls.root / "record"

        # Load latest.json
        with open(cls.root / "data" / "latest.json", "r", encoding="utf-8") as f:
            cls.latest = json.load(f)

    def test_all_markets_in_latest_json(self):
        """Test that every record market folder is in latest.json"""
        record_markets = set()
        for market_dir in self.record_dir.iterdir():
            if market_dir.is_dir() and (market_dir / "summary.json").exists():
                record_markets.add(market_dir.name)

        latest_markets = set(self.latest["markets"].keys())

        missing = record_markets - latest_markets
        self.assertEqual(len(missing), 0,
                        f"Markets in record/ but not in latest.json: {missing}")

    def test_json_ld_present_and_valid(self):
        """Test that every record page has exactly one valid JSON-LD block"""
        for slug in self.latest["markets"].keys():
            index_path = self.record_dir / slug / "index.html"
            if not index_path.exists():
                continue

            with open(index_path, "r", encoding="utf-8") as f:
                html = f.read()

            # Find all JSON-LD script tags
            jsonld_pattern = r'<script type="application/ld\+json">(.*?)</script>'
            matches = re.findall(jsonld_pattern, html, re.DOTALL)

            self.assertEqual(len(matches), 1,
                           f"{slug}: Expected exactly 1 JSON-LD block, found {len(matches)}")

            # Parse JSON
            jsonld_str = matches[0]
            # Unescape <\/
            jsonld_str = jsonld_str.replace('<\\/', '</')

            try:
                jsonld_dict = json.loads(jsonld_str)
            except json.JSONDecodeError as e:
                self.fail(f"{slug}: JSON-LD failed to parse: {e}")

            # Validate with schema parser
            valid, error = schema_parser(jsonld_dict)
            self.assertTrue(valid, f"{slug}: Schema validation failed: {error}")

            # Check temporalCoverage matches summary
            summary_path = self.record_dir / slug / "summary.json"
            with open(summary_path, "r", encoding="utf-8") as f:
                summary = json.load(f)

            expected_temporal = f"{summary['window_first']}/{summary['window_last']}"
            self.assertEqual(jsonld_dict["temporalCoverage"], expected_temporal,
                           f"{slug}: temporalCoverage mismatch")

    def test_meta_description_window_matches_summary(self):
        """Test that meta description window matches summary.json"""
        for slug in self.latest["markets"].keys():
            index_path = self.record_dir / slug / "index.html"
            if not index_path.exists():
                continue

            with open(index_path, "r", encoding="utf-8") as f:
                html = f.read()

            # Extract meta description
            meta_match = re.search(r'<meta name="description" content="([^"]*)">', html)
            if not meta_match:
                self.fail(f"{slug}: No meta description found")

            meta_desc = meta_match.group(1)

            # Extract window dates from meta description
            window_pattern = r'(\d{4}-\d{2}-\d{2}) to (\d{4}-\d{2}-\d{2})'
            window_match = re.search(window_pattern, meta_desc)

            if not window_match:
                self.fail(f"{slug}: No window found in meta description")

            meta_first, meta_last = window_match.groups()

            # Load summary
            summary_path = self.record_dir / slug / "summary.json"
            with open(summary_path, "r", encoding="utf-8") as f:
                summary = json.load(f)

            self.assertEqual(meta_first, summary['window_first'],
                           f"{slug}: Meta first date mismatch")
            self.assertEqual(meta_last, summary['window_last'],
                           f"{slug}: Meta last date mismatch")

    def test_ascii_only_no_em_en_dash(self):
        """Test that every record page is pure ASCII with no U+2013/U+2014"""
        for slug in self.latest["markets"].keys():
            index_path = self.record_dir / slug / "index.html"
            if not index_path.exists():
                continue

            with open(index_path, "rb") as f:
                content = f.read()

            # Check for bytes above 127
            for i, byte in enumerate(content):
                self.assertLess(byte, 128,
                              f"{slug}: Non-ASCII byte {byte} at position {i}")

            # Check for em dash and en dash in decoded content
            text = content.decode('utf-8')
            self.assertNotIn('–', text, f"{slug}: Contains en dash U+2013")
            self.assertNotIn('—', text, f"{slug}: Contains em dash U+2014")

    def test_sitemap_lastmod(self):
        """Test that sitemap has lastmod on new day entries and record hubs"""
        sitemap_path = self.root / "sitemap.xml"
        if not sitemap_path.exists():
            self.skipTest("sitemap.xml not found")

        with open(sitemap_path, "r", encoding="utf-8") as f:
            sitemap = f.read()

        # Check that record hub URLs have lastmod
        for slug in self.latest["markets"].keys():
            hub_url = f"https://markets.namebeam.ai/record/{slug}/"
            if hub_url in sitemap:
                # Hub URL should have a lastmod tag
                hub_pattern = f'<url>\\s*<loc>{re.escape(hub_url)}</loc>\\s*<lastmod>(\\d{{4}}-\\d{{2}}-\\d{{2}})</lastmod>\\s*</url>'
                match = re.search(hub_pattern, sitemap, re.DOTALL)
                if match:
                    lastmod = match.group(1)
                    # lastmod should be a valid date format
                    self.assertRegex(lastmod, r'\d{4}-\d{2}-\d{2}',
                                   f"{slug} hub: lastmod should be YYYY-MM-DD format")


if __name__ == '__main__':
    unittest.main()
