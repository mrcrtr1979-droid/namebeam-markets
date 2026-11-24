"""Shared metadata for Namebeam record datasets."""

import re

CANONICAL_LINK = re.compile(r'<link\b(?=[^>]*\brel=["\']canonical["\'])[^>]*>', re.I)


def record_dataset_fields(url, market, csv_name):
    return {
        "@id": url + "#dataset",
        "identifier": url,
        "spatialCoverage": {"@type": "Place", "name": market},
        "measurementTechnique": (
            "The same buyer question is asked on each run day. The record logs the engine, "
            "run status and answer hash. Tracked name mentions are counted in saved answer text."
        ),
        "includedInDataCatalog": {
            "@type": "DataCatalog",
            "name": "Namebeam dated AI answer record",
            "url": "https://markets.namebeam.ai/record/",
        },
        "distribution": [{
            "@type": "DataDownload",
            "name": csv_name,
            "encodingFormat": "text/csv",
            "contentUrl": url + csv_name,
        }],
    }


def record_canonical(html, url):
    link = f'<link rel="canonical" href="{url}">'
    if CANONICAL_LINK.search(html):
        return CANONICAL_LINK.sub(link, html, count=1)
    return html.replace("</head>", link + "\n</head>", 1)
