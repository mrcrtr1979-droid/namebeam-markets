/* nb-checkout-ref.js: ties every Stripe Payment Link click to a page and a source (LB-105, 2026-11-12).
   Stripe Payment Links accept client_reference_id as a URL parameter and store it on the Checkout Session.
   Before this file every session was anonymous (client_reference_id null on all 53 sessions 10-30 to 11-10).
   1. The landing UTM (utm_source, utm_medium, utm_campaign, utm_content) is read from the first URL of the visit
      and kept in sessionStorage, so a visit that lands with a source and then moves to /buy/ keeps that source.
   2. Every buy.stripe.com link on the page gets client_reference_id=<page>_<utm_source or direct>, where <page> is
      the path with slashes turned to dashes ("buy"), or "home" (namebeam.ai root) or "markets" (markets root).
      Letters, digits, dash and underscore only, 200 characters at most, lower case. The link's own parameters stay.
   3. A link that already carries someone else's client_reference_id is left alone, and nothing is written while
      window.endorsely_referral is set: an affiliate referral (nb-endorsely.js) owns the field and wins.
   4. Links from one namebeam.ai host to another host's /buy/ page carry the landing UTM forward, because
      sessionStorage does not cross hosts; with no landing UTM they carry utm_source=namebeam and utm_medium=<page>,
      the same values the hand-written home links already use.
   5. Links are stamped once the DOM is parsed and again at click time (capture phase), so a link inserted later by
      a script (the home page chat answers) is stamped before the browser follows it. posthog.js reads the same value
      on checkout_started as checkout_ref. No visible text changes. No cookie. */
(function () {
  'use strict';
  var UTM_NAMES = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content'];
  var STORE = 'nb_landing_utm';
  function clean(s, n) {
    return String(s || '').toLowerCase().replace(/[^a-z0-9_-]+/g, '-').replace(/^-+|-+$/g, '').slice(0, n);
  }
  function landing() {
    var cur = {}, stored = null, q, i, v;
    try {
      q = new URLSearchParams(location.search);
      for (i = 0; i < UTM_NAMES.length; i++) { v = q.get(UTM_NAMES[i]); if (v) { cur[UTM_NAMES[i]] = String(v).slice(0, 120); } }
    } catch (e) {}
    try { v = sessionStorage.getItem(STORE); if (v) { stored = JSON.parse(v); } } catch (e) { stored = null; }
    if (stored && typeof stored === 'object' && stored.utm_source) { return stored; }
    if (cur.utm_source) {
      try { sessionStorage.setItem(STORE, JSON.stringify(cur)); } catch (e) {}
      return cur;
    }
    return {};
  }
  function pageTag() {
    var p = '';
    try { p = clean(location.pathname.replace(/\/index\.html?$/i, '').replace(/^\/+|\/+$/g, ''), 60); } catch (e) {}
    if (!p) { p = /^markets\./i.test(location.hostname) ? 'markets' : 'home'; }
    return p;
  }
  var UTM = landing();
  var PAGE = pageTag();
  var TAG = (PAGE + '_' + (clean(UTM.utm_source, 120) || 'direct')).slice(0, 200);
  window.nbCheckoutRef = { value: TAG, page: PAGE, utm: UTM };

  function stampStripe(a) {
    try {
      var u = new URL(a.href, location.href), cur;
      if (u.hostname !== 'buy.stripe.com') { return false; }
      if (window.endorsely_referral) { return false; }
      cur = u.searchParams.get('client_reference_id');
      if (cur && cur !== TAG && a.getAttribute('data-nb-ref') !== cur) { return false; }
      if (cur === TAG) { return true; }
      u.searchParams.set('client_reference_id', TAG);
      a.href = u.toString();
      a.setAttribute('data-nb-ref', TAG);
      return true;
    } catch (e) { return false; }
  }
  function forwardUtm(a) {
    try {
      var u = new URL(a.href, location.href), i, k;
      if (u.hostname === location.hostname) { return false; }
      if (!/(^|\.)namebeam\.ai$/i.test(u.hostname) || !/^\/buy(\/|$)/.test(u.pathname)) { return false; }
      if (UTM.utm_source) {
        for (i = 0; i < UTM_NAMES.length; i++) {
          k = UTM_NAMES[i];
          if (!UTM[k]) { continue; }
          if (k === 'utm_content' && u.searchParams.get('utm_content')) { continue; }
          u.searchParams.set(k, UTM[k]);
        }
      } else if (!u.searchParams.get('utm_source')) {
        u.searchParams.set('utm_source', 'namebeam');
        u.searchParams.set('utm_medium', PAGE);
      } else { return false; }
      if (a.href !== u.toString()) { a.href = u.toString(); }
      return true;
    } catch (e) { return false; }
  }
  function stampAll() {
    var as, i;
    try {
      as = document.querySelectorAll('a[href]');
      for (i = 0; i < as.length; i++) { stampStripe(as[i]); forwardUtm(as[i]); }
    } catch (e) {}
  }
  try {
    document.addEventListener('click', function (e) {
      try {
        var a = e.target && e.target.closest ? e.target.closest('a[href]') : null;
        if (a) { stampStripe(a); forwardUtm(a); }
      } catch (err) {}
    }, true);
  } catch (e) {}
  if (document.readyState === 'loading') {
    try { document.addEventListener('DOMContentLoaded', stampAll); } catch (e) {}
  } else { stampAll(); }
  window.nbCheckoutRef.stampAll = stampAll;
}());
