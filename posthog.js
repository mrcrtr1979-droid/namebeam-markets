/* posthog.js: PostHog loader and dataLayer bridge. Key and host are placeholders filled at deploy. */
(function () {
  var KEY = 'phc_kKsaZbRt2hgQG4a24VW7VFEPxkcESnKWWWHaYRwyYc2v', HOST = 'https://us.i.posthog.com';
  var EVENTS = { buy_click: 1, sample_open: 1, lead_submit: 1 };
  try {
    !function (t, e) {
      var o, n, p, r;
      e.__SV || (window.posthog = e, e._i = [], e.init = function (i, s, a) {
        function g(t, e) { var o = e.split('.'); 2 == o.length && (t = t[o[0]], e = o[1]); t[e] = function () { t.push([e].concat(Array.prototype.slice.call(arguments, 0))); }; }
        (p = t.createElement('script')).type = 'text/javascript'; p.crossOrigin = 'anonymous'; p.async = !0;
        p.src = s.api_host.replace('.i.posthog.com', '-assets.i.posthog.com') + '/static/array.js';
        (r = t.getElementsByTagName('script')[0]).parentNode.insertBefore(p, r);
        var u = e; for (void 0 !== a ? u = e[a] = [] : a = 'posthog', u.people = u.people || [], u.toString = function (t) { var e = 'posthog'; return 'posthog' !== a && (e += '.' + a), t || (e += ' (stub)'), e; }, u.people.toString = function () { return u.toString(1) + '.people (stub)'; }, o = 'capture identify alias people.set people.set_once set_config register register_once unregister opt_out_capturing has_opted_out_capturing opt_in_capturing reset isFeatureEnabled onFeatureFlags getFeatureFlag getFeatureFlagPayload reloadFeatureFlags group updateEarlyAccessFeatureEnrollment getEarlyAccessFeatures getActiveMatchingSurveys getSurveys getNextSurveyStep onSessionId'.split(' '), n = 0; n < o.length; n++) g(u, o[n]);
        e._i.push([i, s, a]);
      }, e.__SV = 1);
    }(document, window.posthog || []);
    window.posthog.init(KEY, { api_host: HOST, capture_pageview: true, autocapture: false, persistence: 'localStorage+cookie' });
  } catch (e) {}
  function fwd(d) {
    try {
      if (!d || typeof d !== 'object' || !EVENTS[d.event]) return;
      window.posthog.capture(d.event, { market: d.market, price: d.price, page: location.pathname });
    } catch (e) {}
  }
  try {
    var dl = window.dataLayer = window.dataLayer || [], i, orig = dl.push;
    for (i = 0; i < dl.length; i++) fwd(dl[i]);
    dl.push = function () {
      for (var j = 0; j < arguments.length; j++) fwd(arguments[j]);
      return orig.apply(dl, arguments);
    };
  } catch (e) {}
})();
