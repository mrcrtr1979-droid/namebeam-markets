// lb105_checkout_ref_test.mjs: build test for nb-checkout-ref.js (LB-105, 2026-11-12).
// Usage: node tools/lb105_checkout_ref_test.mjs <repo root> [markets|site]
// RED on a tree without the script and the page tags; GREEN on a tree that carries them.
// Runs the real script in a vm sandbox with a small fake DOM; no browser, no network.
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const root = process.argv[2] || '.';
const kind = process.argv[3] || (fs.existsSync(path.join(root, 'buy', 'index.html')) ? 'markets' : 'site');
const host = kind === 'markets' ? 'markets.namebeam.ai' : 'namebeam.ai';
const pages = kind === 'markets' ? ['index.html', 'buy/index.html'] : ['index.html'];
const TAG = '<script src="/nb-checkout-ref.js" defer></script>';
const ascii = (s) => /^[\x00-\x7F]*$/.test(s);

let n = 0, pass = 0;
const fails = [];
function check(name, ok, detail) {
  n++;
  if (ok) { pass++; console.log('ok   ' + name); }
  else { fails.push(name); console.log('FAIL ' + name + (detail ? ' : ' + detail : '')); }
}
function read(p) { try { return fs.readFileSync(path.join(root, p), 'utf8'); } catch (e) { return null; } }

// 1. files and page tags
const src = read('nb-checkout-ref.js');
check('nb-checkout-ref.js present', src !== null);
check('nb-checkout-ref.js ASCII only (copy law: no em or en dash)', src !== null && ascii(src));
for (const p of pages) {
  const html = read(p) || '';
  const i = html.indexOf(TAG), j = html.indexOf('<script src="/posthog.js"'), k = html.indexOf('<script src="/nb-funnel.js"');
  check(p + ' loads nb-checkout-ref.js before posthog.js and nb-funnel.js', i > -1 && (j < 0 || i < j) && (k < 0 || i < k),
    'tag index ' + i + ', posthog ' + j + ', funnel ' + k);
  check(p + ' is ASCII only', ascii(html));
}
const ph = read('posthog.js') || '';
check('posthog.js checkout_started carries checkout_ref and does not count the page tag as a referral',
  ph.includes('window.nbCheckoutRef') && ph.includes('checkout_ref'));

// 2. behaviour in a fake DOM
function anchor(href) {
  const at = {};
  return {
    _h: href,
    get href() { return this._h; },
    set href(v) { this._h = String(v); },
    getAttribute(k) { return k in at ? at[k] : null; },
    setAttribute(k, v) { at[k] = String(v); },
    hasAttribute(k) { return k in at; },
    closest() { return this; }
  };
}
function run({ h = host, pathname = '/', search = '', anchors = [], session = {}, endorsely = '' }) {
  const listeners = {};
  const store = new Map(Object.entries(session));
  const sb = {
    URL, URLSearchParams, JSON, String, RegExp, Array, Object, console,
    document: { readyState: 'complete', querySelectorAll: () => anchors, addEventListener: (t, f) => { (listeners[t] = listeners[t] || []).push(f); } },
    location: { hostname: h, pathname, search, href: 'https://' + h + pathname + search },
    sessionStorage: { getItem: (k) => (store.has(k) ? store.get(k) : null), setItem: (k, v) => store.set(k, String(v)) }
  };
  sb.window = sb;
  if (endorsely) sb.endorsely_referral = endorsely;
  vm.createContext(sb);
  vm.runInContext(src, sb);
  return { sb, store, click: (a) => { for (const f of listeners.click || []) f({ target: a }); } };
}
const q = (href) => new URL(href).searchParams;
const BUY = 'https://buy.stripe.com/7sY28rbNy58RbD25ledIA0V?utm_campaign=market_record_release_1105';
const cases = [
  ['direct visit to /buy/: client_reference_id=buy_direct, utm_campaign kept', () => {
    const a = anchor(BUY); const r = run({ h: 'markets.namebeam.ai', pathname: '/buy/', anchors: [a] });
    return q(a.href).get('client_reference_id') === 'buy_direct' && q(a.href).get('utm_campaign') === 'market_record_release_1105' && r.sb.nbCheckoutRef.value === 'buy_direct';
  }],
  ['landing utm_source=study on /buy/: buy_study and the utm set kept in sessionStorage', () => {
    const a = anchor(BUY); const r = run({ h: 'markets.namebeam.ai', pathname: '/buy/', search: '?utm_source=study&utm_content=finding', anchors: [a] });
    const s = JSON.parse(r.store.get('nb_landing_utm') || '{}');
    return q(a.href).get('client_reference_id') === 'buy_study' && s.utm_source === 'study' && s.utm_content === 'finding';
  }],
  ['landing source wins over a later page utm: stored hn, URL utm_source=site gives buy_hn', () => {
    const a = anchor(BUY); run({ h: 'markets.namebeam.ai', pathname: '/buy/', search: '?utm_source=site&utm_medium=home', anchors: [a], session: { nb_landing_utm: JSON.stringify({ utm_source: 'hn' }) } });
    return q(a.href).get('client_reference_id') === 'buy_hn';
  }],
  ['page tags: namebeam.ai root is home, markets root is markets, nested path is dashed', () => {
    const a = run({ h: 'namebeam.ai', pathname: '/' }).sb.nbCheckoutRef.value;
    const b = run({ h: 'markets.namebeam.ai', pathname: '/' }).sb.nbCheckoutRef.value;
    const c = run({ h: 'markets.namebeam.ai', pathname: '/record/houston-hvac/index.html' }).sb.nbCheckoutRef.value;
    return a === 'home_direct' && b === 'markets_direct' && c === 'record-houston-hvac_direct';
  }],
  ['value is letters, digits, dash, underscore only and at most 200 characters', () => {
    const a = run({ h: 'markets.namebeam.ai', pathname: '/buy/', search: '?utm_source=' + encodeURIComponent('Hacker News! 2026 (front page)') }).sb.nbCheckoutRef.value;
    const b = run({ h: 'markets.namebeam.ai', pathname: '/buy/', search: '?utm_source=' + 'x'.repeat(300) }).sb.nbCheckoutRef.value;
    return a === 'buy_hacker-news-2026-front-page' && /^[A-Za-z0-9_-]{1,200}$/.test(a) && b === 'buy_' + 'x'.repeat(120) && b.length <= 200 && /^[A-Za-z0-9_-]{1,200}$/.test(b);
  }],
  ['an affiliate value already on the link is left alone, and no stamp while endorsely_referral is set', () => {
    const a = anchor('https://buy.stripe.com/7sY28rbNy58RbD25ledIA0V?client_reference_id=aff-123'); run({ h: 'markets.namebeam.ai', pathname: '/buy/', anchors: [a] });
    const b = anchor(BUY); run({ h: 'markets.namebeam.ai', pathname: '/buy/', anchors: [b], endorsely: 'aff-123' });
    return q(a.href).get('client_reference_id') === 'aff-123' && q(b.href).get('client_reference_id') === null;
  }],
  ['other links untouched; a same-host /buy/ link is not rewritten', () => {
    const a = anchor('https://example.com/x?y=1'); const b = anchor('https://markets.namebeam.ai/buy/#edition-license');
    run({ h: 'markets.namebeam.ai', pathname: '/', anchors: [a, b] });
    return a.href === 'https://example.com/x?y=1' && b.href === 'https://markets.namebeam.ai/buy/#edition-license';
  }],
  ['home to markets /buy/ with no landing utm carries utm_source=namebeam and utm_medium=home; a tagged link keeps its utm_content', () => {
    const a = anchor('https://markets.namebeam.ai/buy/'); const b = anchor('https://markets.namebeam.ai/buy/?utm_source=namebeam&utm_medium=home&utm_content=hero');
    run({ h: 'namebeam.ai', pathname: '/', anchors: [a, b] });
    return q(a.href).get('utm_source') === 'namebeam' && q(a.href).get('utm_medium') === 'home' && b.href === 'https://markets.namebeam.ai/buy/?utm_source=namebeam&utm_medium=home&utm_content=hero';
  }],
  ['home to markets /buy/ with a landing utm forwards it across hosts (sessionStorage does not cross hosts)', () => {
    const a = anchor('https://markets.namebeam.ai/buy/?utm_source=namebeam&utm_medium=home&utm_content=hero');
    run({ h: 'namebeam.ai', pathname: '/', search: '?utm_source=hn&utm_medium=social&utm_campaign=launch', anchors: [a] });
    const s = q(a.href);
    return s.get('utm_source') === 'hn' && s.get('utm_medium') === 'social' && s.get('utm_campaign') === 'launch' && s.get('utm_content') === 'hero';
  }],
  ['a link inserted after load is stamped at click time; stamping twice leaves one client_reference_id', () => {
    const r = run({ h: 'namebeam.ai', pathname: '/', search: '?utm_source=chat' });
    const a = anchor('https://buy.stripe.com/28EaEX8Bm0SB5eE4hadIA0T');
    r.click(a); r.click(a); r.sb.nbCheckoutRef.stampAll();
    return q(a.href).get('client_reference_id') === 'home_chat' && (a.href.match(/client_reference_id/g) || []).length === 1;
  }]
];
for (const [name, fn] of cases) {
  let ok = false, detail = '';
  if (src === null) { detail = 'script missing'; }
  else { try { ok = !!fn(); } catch (e) { detail = String(e && e.message || e); } }
  check(name, ok, detail);
}

// 3. every static buy.stripe.com anchor on each page gets the page tag
for (const p of pages) {
  const html = read(p) || '';
  const pathname = '/' + p.replace(/index\.html$/, '');
  const hrefs = [...html.matchAll(/<a [^>]*href="(https:\/\/buy\.stripe\.com\/[^"]+)"/g)].map((m) => m[1].replace(/&amp;/g, '&'));
  const want = (pathname.replace(/^\/+|\/+$/g, '').replace(/\//g, '-') || (kind === 'markets' ? 'markets' : 'home')) + '_direct';
  let ok = hrefs.length >= 0, detail = hrefs.length + ' static Stripe anchors';
  if (src !== null && hrefs.length) {
    const as = hrefs.map(anchor);
    run({ h: host, pathname, anchors: as });
    ok = as.every((a) => q(a.href).get('client_reference_id') === want);
    detail += ', stamped ' + as.filter((a) => q(a.href).get('client_reference_id') === want).length + ' as ' + want;
  } else if (src === null) { ok = false; detail = 'script missing'; }
  check(p + ': every static Stripe anchor stamped ' + want, ok, detail);
}

console.log('LB105 TEST ' + (fails.length ? 'RED' : 'GREEN') + ' ' + pass + ' of ' + n + ' (' + kind + ', ' + root + ')');
process.exit(fails.length ? 1 : 0);
