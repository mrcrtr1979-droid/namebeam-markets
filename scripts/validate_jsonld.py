#!/usr/bin/env python3
"""Validate every schema.org JSON-LD block in an HTML tree. Exit 0 only when all blocks pass.
Dataset checks follow Google's Dataset structured-data requirements (name; description 50-5000 chars)
plus the fields this record promises (url, license, creator, distribution with contentUrl and encodingFormat).
Usage: python3 scripts/validate_jsonld.py <dir> [--expect-url URL]   |   --selftest"""
import json, re, sys, glob, os

BLOCK = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)

def check_dataset(d, expect_url=None):
    errs = []
    for k in ('name', 'description', 'url', 'license', 'creator', 'distribution'):
        if not d.get(k):
            errs.append('missing ' + k)
    desc = d.get('description') or ''
    if not 50 <= len(desc) <= 5000:
        errs.append('description length %d not in 50..5000' % len(desc))
    if expect_url and d.get('url', '').rstrip('/') != expect_url.rstrip('/'):
        errs.append('url %r != %r' % (d.get('url'), expect_url))
    if d.get('license') and not str(d['license']).startswith('https://creativecommons.org/licenses/by/4.0'):
        errs.append('license is not CC BY 4.0')
    for i, x in enumerate(d.get('distribution') or []):
        if x.get('@type') != 'DataDownload':
            errs.append('distribution[%d] not DataDownload' % i)
        if not str(x.get('contentUrl', '')).startswith('https://'):
            errs.append('distribution[%d] contentUrl missing or not https' % i)
        if not x.get('encodingFormat'):
            errs.append('distribution[%d] encodingFormat missing' % i)
    if re.search('[–—]', json.dumps(d, ensure_ascii=False)):
        errs.append('em or en dash in JSON-LD')
    return errs

def check_html(text, expect_url=None):
    out = []
    blocks = BLOCK.findall(text)
    for b in blocks:
        try:
            d = json.loads(b)
        except Exception as e:
            out.append('JSON parse error: %s' % e); continue
        if d.get('@context') not in ('https://schema.org/', 'https://schema.org', 'http://schema.org'):
            out.append('bad @context')
        if d.get('@type') == 'Dataset':
            out += check_dataset(d, expect_url)
    return len(blocks), out

def selftest():
    good = '<script type="application/ld+json">{"@context":"https://schema.org/","@type":"Dataset","name":"x","description":"%s","url":"https://e.x/edition-1","license":"https://creativecommons.org/licenses/by/4.0/","creator":{"@type":"Organization","name":"c"},"distribution":[{"@type":"DataDownload","contentUrl":"https://e.x/a.csv","encodingFormat":"text/csv"}]}</script>' % ('d' * 60)
    bad = good.replace('"license":"https://creativecommons.org/licenses/by/4.0/",', '').replace('d' * 60, 'short')
    n, e = check_html(good, 'https://e.x/edition-1'); assert n == 1 and not e, e
    n, e = check_html(bad); assert n == 1 and len(e) >= 2, e
    n, e = check_html('<script type="application/ld+json">{oops</script>'); assert e and 'parse' in e[0]
    print('SELFTEST GREEN (good passes, planted bad fixtures caught)')
    return 0

def main(a):
    if a[:1] == ['--selftest']:
        return selftest()
    root = a[0]; exp = a[a.index('--expect-url') + 1] if '--expect-url' in a else None
    total = 0; bad = 0; files = 0
    for f in sorted(glob.glob(os.path.join(root, '**', '*.html'), recursive=True)):
        n, errs = check_html(open(f, encoding='utf-8').read(), exp if f.endswith(os.path.join('edition-1', 'index.html')) else None)
        if n: files += 1; total += n
        for e in errs:
            bad += 1; print('FAIL', f, e)
    print('JSONLD %s: %d blocks in %d files, %d failures' % ('PASS' if not bad else 'FAIL', total, files, bad))
    return 1 if bad or not total else 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
