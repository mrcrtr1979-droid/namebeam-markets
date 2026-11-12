/* sample.js: the free market sample form (LB-23, 2026-11-09). Loaded on every page that carries the LB-19 offer line.
   It finds the offer paragraph, reads the market slug from its buy link, and adds one plain form after it. The post
   goes to the ce-edge Worker, which checks Turnstile, the honeypot and consent, writes the D1 lead and consent rows
   and starts the sample mail. Nothing here stores or reads anything but the PostHog distinct id, if present.
   Turnstile sitekey: the documented always-pass TEST key until the owner creates the widget; then swap the one
   constant below and the Worker's TURNSTILE_MODE together. */
(function () {
  var EDGE = "https://ce-edge.mrcrtr1979.workers.dev";
  var SITEKEY = "0x4AAAAAAF657LfunEwSgGdr";
  var CONSENT = "Email me the free sample for this market and up to 3 follow-ups about the Namebeam record. Reply no to stop.";

  function slugOf(p) {
    var a = p.querySelector('a[href*="/buy/"]');
    if (!a) return "";
    var m = (a.getAttribute("href") || "").match(/utm_content=([a-z0-9-]+)/);
    return m ? m[1] : "";
  }
  function phId() {
    try {
      var ph = window.posthog;
      if (ph && typeof ph.get_distinct_id === "function") return ph.get_distinct_id();
    } catch (e) {}
    return "";
  }
  function el(tag, attrs, text) {
    var e = document.createElement(tag);
    for (var k in attrs) if (attrs.hasOwnProperty(k)) e.setAttribute(k, attrs[k]);
    if (text) e.appendChild(document.createTextNode(text));
    return e;
  }
  function build(p, slug) {
    var form = el("form", { "id": "nb-sample", "class": "nb-sample", "action": EDGE + "/api/sample", "method": "post", "novalidate": "novalidate" });
    form.appendChild(el("h3", {}, "Get the free sample for this market by email"));
    form.appendChild(el("p", { "class": "pv-note" }, "The public rows for this market as a CSV with its hash, a one-page summary of counts by engine and date, and the scope of the $49 Market Record. For agencies. A count, not a ranking."));
    var row = el("div", { "class": "nb-sample-row" });
    var email = el("input", { type: "email", name: "email", required: "required", placeholder: "you@agency.com", autocomplete: "email", "aria-label": "Email" });
    row.appendChild(email);
    var aud = el("select", { name: "audience", "aria-label": "I am" });
    [["", "I am: choose one"], ["agency", "an agency"], ["vendor", "a software vendor"], ["other", "other"]].forEach(function (o) {
      aud.appendChild(el("option", { value: o[0] }, o[1]));
    });
    row.appendChild(aud);
    form.appendChild(row);
    var lab = el("label", { "class": "nb-sample-consent" });
    var cb = el("input", { type: "checkbox", name: "consent", value: "yes", required: "required" });
    lab.appendChild(cb);
    lab.appendChild(document.createTextNode(" " + CONSENT));
    form.appendChild(lab);
    var hp = el("div", { "style": "position:absolute;left:-9999px;top:-9999px", "aria-hidden": "true" });
    hp.appendChild(el("input", { type: "text", name: "website", tabindex: "-1", autocomplete: "off" }));
    form.appendChild(hp);
    form.appendChild(el("input", { type: "hidden", name: "market", value: slug }));
    var ts = el("div", { "class": "cf-turnstile", "data-sitekey": SITEKEY, "data-size": "flexible" });
    form.appendChild(ts);
    var btn = el("button", { type: "submit", "class": "btn" }, "Send me the sample");
    form.appendChild(btn);
    var msg = el("p", { "class": "nb-sample-msg", "role": "status" });
    form.appendChild(msg);
    form.addEventListener("submit", function (ev) {
      ev.preventDefault();
      msg.textContent = "Sending...";
      btn.disabled = true;
      var fd = new FormData(form);
      var body = {};
      fd.forEach(function (v, k) { body[k] = v; });
      body.ph_id = phId();
      try {
        var q = new URLSearchParams(location.search);
        q.forEach(function (v, k) { if (k.indexOf("utm_") === 0) body[k] = v; });
      } catch (e) {}
      fetch(EDGE + "/api/sample", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) })
        .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
        .then(function (res) {
          msg.textContent = (res.j && res.j.message) || (res.ok ? "Sent." : "That did not go through. Try again.");
          if (!res.ok) { btn.disabled = false; if (window.turnstile) { try { window.turnstile.reset(); } catch (e) {} } }
        })
        .catch(function () { msg.textContent = "The form could not reach the server. Email terry@namebeam.ai with the market name instead."; btn.disabled = false; });
    });
    p.parentNode.insertBefore(form, p.nextSibling);
    var s = document.createElement("script");
    s.src = "https://challenges.cloudflare.com/turnstile/v0/api.js";
    s.async = true; s.defer = true;
    document.head.appendChild(s);
    var css = document.createElement("style");
    css.textContent = ".nb-sample{margin:18px 0;padding:16px 18px;border:1px solid #d9d9d9;border-radius:10px;background:#fafafa}.nb-sample h3{margin:0 0 6px;font-size:1.05em}.nb-sample-row{display:flex;gap:8px;flex-wrap:wrap;margin:8px 0}.nb-sample input[type=email],.nb-sample select{padding:8px 10px;font-size:15px;border:1px solid #bbb;border-radius:6px;min-width:220px}.nb-sample-consent{display:block;margin:8px 0;font-size:14px}.nb-sample .cf-turnstile{margin:8px 0}.nb-sample-msg{min-height:1.2em;font-size:14px}";
    document.head.appendChild(css);
  }
  function init() {
    var p = document.querySelector("p.nb-offer");
    if (!p) return;
    var slug = slugOf(p);
    if (!slug) return;
    slug = slug.split("/")[0];
    if (!/^[a-z0-9][a-z0-9-]{1,63}$/.test(slug)) return;
    if (document.querySelector("form.nb-sample")) return;
    build(p, slug);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();
