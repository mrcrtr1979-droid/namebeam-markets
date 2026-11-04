/* nb-endorsely.js: Endorsely affiliate tracking for Namebeam (organization 7377f152-e545-4bc1-bd9e-867eb91aba19).
   1. Loads https://assets.endorsely.com/endorsely.js once, with its data-endorsely attribute (the vendor's Step A tag).
   2. When window.endorsely_referral is set (a visit that came through an affiliate link), writes it as
      client_reference_id on every buy.stripe.com link, and as client-reference-id on Stripe pricing tables and buy
      buttons. Uses the URL API, so a link that already has a '?' gets '&' (the vendor snippet appends '?' blindly
      and needs jQuery). A referral replaces a page tag such as receipt_<market>: Stripe keeps one client_reference_id,
      and Endorsely credits the affiliate only from that field; the page is still known from analytics.
   3. Polls for up to 10 s after load and re-stamps on click, so a referral that lands late still reaches the link.
   No visible text, no cookie of its own. Added 2026-11-03 by OPUS-CPEO-1103 (AFFIL-NB-1103). */
(function () {
  'use strict';
  var ORG = '7377f152-e545-4bc1-bd9e-867eb91aba19';
  var OK = /^[A-Za-z0-9_-]{1,200}$/;
  try {
    if (!document.querySelector('script[data-endorsely]')) {
      var s = document.createElement('script');
      s.async = true;
      s.src = 'https://assets.endorsely.com/endorsely.js';
      s.setAttribute('data-endorsely', ORG);
      (document.head || document.documentElement).appendChild(s);
    }
  } catch (e) {}
  function ref() {
    var r = window.endorsely_referral;
    return (typeof r === 'string' && OK.test(r)) ? r : '';
  }
  function stampLink(a, r) {
    try {
      var u = new URL(a.href);
      if (u.hostname !== 'buy.stripe.com') { return; }
      if (u.searchParams.get('client_reference_id') === r) { return; }
      u.searchParams.set('client_reference_id', r);
      a.href = u.toString();
    } catch (e) {}
  }
  function stampAll(r) {
    var i, as = document.querySelectorAll('a[href^="https://buy.stripe.com/"]');
    for (i = 0; i < as.length; i++) { stampLink(as[i], r); }
    var els = document.querySelectorAll('[pricing-table-id],[buy-button-id]');
    for (i = 0; i < els.length; i++) { els[i].setAttribute('client-reference-id', r); }
  }
  /* PostHog (COO cohort PARTNER REFERRED, 2026-11-03): once the PostHog library has loaded, the referral id goes on as a
     super property (every later event carries it) and a person property, plus one partner_referral_seen event. Visitors with
     Do Not Track or GPC never load PostHog (posthog.js), so nothing is sent for them. */
  var told = false;
  function tell(r) {
    var n = 0;
    (function t() {
      if (told) { return; }
      var ph = window.posthog;
      if (ph && ph.__loaded && typeof ph.register === 'function') {
        told = true;
        try { ph.register({ endorsely_referral: r }); } catch (e) {}
        try { if (typeof ph.setPersonProperties === 'function') { ph.setPersonProperties({ endorsely_referral: r }); } } catch (e) {}
        try { ph.capture('partner_referral_seen', { endorsely_referral: r, path: location.pathname }); } catch (e) {}
        return;
      }
      if (++n < 60) { setTimeout(t, 250); }
    }());
  }
  var tries = 0;
  (function tick() {
    var r = ref();
    if (r) { stampAll(r); tell(r); return; }
    if (++tries < 40) { setTimeout(tick, 250); }
  }());
  document.addEventListener('click', function (e) {
    var a = e.target && e.target.closest ? e.target.closest('a[href^="https://buy.stripe.com/"]') : null, r = ref();
    if (a && r) { stampLink(a, r); }
  }, true);
}());
