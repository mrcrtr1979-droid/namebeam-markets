/* nb-funnel.js: funnel events buy_click, sample_open, lead_submit. Sends to GA4 via gtag if present,
   else via Cloudflare Zaraz if present; always pushes to window.dataLayer. Needs no measurement ID. */
(function () {
  'use strict';
  window.dataLayer = window.dataLayer || [];
  function send(name, p) {
    var ev = { event: name }, k;
    for (k in p) { ev[k] = p[k]; }
    window.dataLayer.push(ev);
    if (typeof gtag === 'function') { gtag('event', name, p); }
    else if (window.zaraz && typeof window.zaraz.track === 'function') { window.zaraz.track(name, p); }
  }
  function txt(el) { return el ? (el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 80) : ''; }
  function market(a) {
    var c = a.closest('[data-market]');
    if (c) { return c.getAttribute('data-market'); }
    var card = a.closest('section,article,.card,.tier,.pv-prod,div') || document.body, h;
    while (card && !(h = card.querySelector('h1,h2,h3,h4'))) { card = card.parentElement; }
    return txt(h) || txt(document.querySelector('h1'));
  }
  function price(a) {
    var v = a.getAttribute('data-price');
    if (v) { return v; }
    var card = a.closest('.tier,.pv-prod,.card,section,div'), m;
    while (card && !(m = /\$\s?([0-9][0-9,]*)/.exec(card.textContent))) { card = card.parentElement; }
    return m ? m[1].replace(/,/g, '') : '';
  }
  document.addEventListener('click', function (e) {
    var a = e.target.closest ? e.target.closest('a[href]') : null, h;
    if (!a) { return; }
    h = a.getAttribute('href') || '';
    if (h.indexOf('buy.stripe.com') > -1) { send('buy_click', { market: market(a), price: price(a) }); }
    else if (h.indexOf('/samples/') > -1 || /\.pdf($|[?#])/i.test(h)) { send('sample_open', { market: market(a) }); }
  }, true);
  document.addEventListener('submit', function (e) {
    var f = e.target;
    send('lead_submit', { form: f.id || f.getAttribute('action') || 'form' });
  }, true);
}());
