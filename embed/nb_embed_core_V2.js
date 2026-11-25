// nb_embed_core_V2.js - source of truth for the Namebeam embeddable record badge and market card (L3, round 2 after the Counter read BADGE-READ-1, staged 2026-11-24).
// Includes browser DOM mounting and a streaming fetch loader. Works in node (builder, test) and in a browser (live card). The block between the
// NB-CORE markers is copied verbatim into market_card_live_v1_V2.html by build_demo_V2.js, and test_badge_V2.js checks the copy.
// It reads just these fields: pairs, market, niche, asked_by_engine (engine keys and counts), window_start, window_end, businesses_named_total, and the numeric top_businesses[].by_engine[engine].named flags.
// It never reads, copies or prints a business name, the finding text, or any provider answer text.
/*NB-CORE-BEGIN*/
(function (root) {
  "use strict";

  var DATA_URL = "https://namebeam.ai/data/explorer_data.json";
  var VERIFY_URL = "https://namebeam.ai/verify/";
  var RECORD_BASE = "https://markets.namebeam.ai/record/";
  var UTM = "utm_source=embed&utm_medium=badge&utm_campaign=record_badge_1125";
  var MODEL_CHANGE_DATE = "2026-11-10";
  var ENGINE_LABEL = { openai: "OpenAI", perplexity: "Perplexity", gemini: "Gemini", anthropic: "Anthropic" };
  var ENGINE_ORDER = ["openai", "perplexity", "gemini", "anthropic"];

  // Record pages read 2026-11-24 22:56 to 23:05 CT on markets.namebeam.ai/record/ (page title or description matched the pair).
  // Three pairs whose label names a firm are held out of this map and out of PUBLIC_PAIRS until they are reviewed (Counter read BADGE-READ-1, check 6).
  var RECORD_SLUGS = {
    "Atlanta GA|dentists": "atlanta-dentists", "Atlanta GA|hvac repair and replacement": "atlanta-hvac",
    "Atlanta GA|orthodontists": "atlanta-orthodontists", "Atlanta GA|personal injury attorneys": "atlanta-personal-injury",
    "Charlotte NC|tanning salons": "charlotte-tanning-salons",
    "Chicago IL|personal injury attorneys": "chicago-personal-injury", "Columbus OH|tanning salons": "columbus-tanning-salons",
    "Dallas TX|dentists": "dallas-dentists", "Dallas TX|orthodontists": "dallas-orthodontists",
    "Dallas TX|personal injury attorneys": "dallas-personal-injury", "Dallas TX|residential roofing": "dallas-roofing",
    "Denver CO|residential roofing": "denver-roofing", "Houston TX|hvac repair and replacement": "houston-hvac",
    "Houston TX|personal injury attorneys": "houston-personal-injury", "Kansas City MO|health insurance brokers": "kansas-city-health-insurance",
    "Miami FL|residential roofing": "miami-roofing",
    "Phoenix AZ|dentists": "phoenix-dentists", "Phoenix AZ|hvac repair and replacement": "phoenix-hvac",
    "Phoenix AZ|orthodontists": "phoenix-orthodontists", "Pleasanton CA|dentists": "pleasanton-dentists",
    "Pleasanton CA|home care agencies": "pleasanton-home-care", "Pleasanton CA|moving companies": "pleasanton-moving-companies",
    "Pleasanton CA|oil change shops": "pleasanton-oil-change", "Pleasanton CA|real estate agents": "pleasanton-real-estate-agents",
    "Pleasanton CA|tanning salons": "pleasanton-tanning-salons", "Pleasanton CA|tire shops": "pleasanton-tire-shops",
    "Tyler TX|tanning salons": "tyler-tanning-salons",
    "US nationwide|short-term rental": "us-short-term-rental-booking-platforms",
    "US nationwide|short-term rental business model": "us-short-term-rental-business-model",
    "US nationwide|short-term rental software": "us-short-term-rental-software"
  };

  // The reviewed public label list: a market and kind of business is shown when this exact pair is on it.
  // The last entry is a sample label that is not in the saved public file, kept so the pair-missing state can be demonstrated.
  var PUBLIC_PAIRS = [
    "Atlanta GA|dentists", "Atlanta GA|hvac repair and replacement", "Atlanta GA|orthodontists", "Atlanta GA|personal injury attorneys",
    "Charlotte NC|tanning salons", "Chicago IL|personal injury attorneys", "Columbus OH|tanning salons",
    "Dallas TX|dentists", "Dallas TX|orthodontists", "Dallas TX|personal injury attorneys", "Dallas TX|residential roofing",
    "Denver CO|residential roofing", "Houston TX|hvac repair and replacement", "Houston TX|personal injury attorneys",
    "Kansas City MO|health insurance brokers", "Miami FL|residential roofing",
    "Phoenix AZ|dentists", "Phoenix AZ|hvac repair and replacement", "Phoenix AZ|orthodontists",
    "Pleasanton CA|dentists", "Pleasanton CA|home care agencies", "Pleasanton CA|moving companies", "Pleasanton CA|oil change shops",
    "Pleasanton CA|real estate agents", "Pleasanton CA|tanning salons", "Pleasanton CA|tire shops", "Tyler TX|tanning salons",
    "US nationwide|short-term rental", "US nationwide|short-term rental business model", "US nationwide|short-term rental software",
    "Atlanta GA|plumbers"
  ];

  var MSG = {
    loading: "Loading the public file. Counts appear here when it arrives.",
    no_date: "Data date: not available.",
    loading_date: "Data date: not loaded yet.",
    fail: "The public file could not be loaded, so no counts are shown.",
    nopair: "This market and kind of business is not in the public file.",
    format: "The public file is not in a format this card can read.",
    refused: "This card does not show this market and kind of business.",
    over_window: "Counts are unavailable for this window because a source reports more answer days than the window contains.",
    config: "This card needs a market and kind of business.",
    open_record: "Use the links below to browse the record or verify a dated answer."
  };

  // Words the public copy law keeps out of our text. A market or niche label that carries one is refused, not edited.
  var LABEL_WORD_RE = /(^|[^a-z0-9])(best|better than|top|first|only|leading|income|guarantee|guaranteed|ranking|ranked|ranks|honest|earn|roi|unlock|proven|exclusive|revenue|number one|hype)(?![a-z0-9])/i;

  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;" }[c];
    });
  }

  function isDate(s) {
    if (typeof s !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(s)) { return false; }
    var d = new Date(Date.UTC(+s.slice(0, 4), +s.slice(5, 7) - 1, +s.slice(8, 10)));
    return !isNaN(d.getTime()) && d.toISOString().slice(0, 10) === s;
  }

  function isCount(v) { return typeof v === "number" && isFinite(v) && Math.floor(v) === v && v >= 0 && v <= 9007199254740991; }

  function calendarDays(a, b) {
    return Math.round((Date.UTC(+b.slice(0, 4), +b.slice(5, 7) - 1, +b.slice(8, 10)) - Date.UTC(+a.slice(0, 4), +a.slice(5, 7) - 1, +a.slice(8, 10))) / 86400000) + 1;
  }

  function slugify(s) { return String(s).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 60); }

  function labelWord(text) {
    var m = LABEL_WORD_RE.exec(String(text).replace(/[^A-Za-z0-9]+/g, " "));
    return m ? m[2].toLowerCase() : "";
  }

  // The public-label gate: both labels are printable ASCII with no edge space, carry no screened word, and the exact pair is on the reviewed list.
  // Returns "" when the pair may be shown, otherwise a reason that never repeats the label.
  function labelProblem(market, niche) {
    var vals = [market, niche], i;
    for (i = 0; i < vals.length; i++) {
      if (!(typeof vals[i] === "string" && /^[\x20-\x7e]+$/.test(vals[i]) && vals[i].trim() === vals[i])) { return "label-format"; }
    }
    var w = labelWord(market + " " + niche);
    if (w) { return "label-word:" + w; }
    return PUBLIC_PAIRS.indexOf(market + "|" + niche) < 0 ? "label-unreviewed" : "";
  }

  // The file must be an object with a non-empty pairs array; each pair is checked again when it is summarized.
  function fileProblem(data) {
    if (!data || typeof data !== "object" || !Array.isArray(data.pairs) || data.pairs.length === 0) { return "format"; }
    return "";
  }

  function findPair(data, market, niche) {
    var m = String(market || "").trim().toLowerCase(), n = String(niche || "").trim().toLowerCase();
    if (!m || !n || fileProblem(data)) { return null; }
    for (var i = 0; i < data.pairs.length; i++) {
      var p = data.pairs[i];
      if (p && typeof p.market === "string" && typeof p.niche === "string" && p.market.toLowerCase() === m && p.niche.toLowerCase() === n) { return p; }
    }
    return null;
  }

  // One pair to the numbers the badge and card print. Counts, no names: the by_engine flags are counted, never copied.
  function summarizePair(p) {
    if (!p || typeof p !== "object" || typeof p.market !== "string" || typeof p.niche !== "string" || !isDate(p.window_start) ||
        !isDate(p.window_end) || p.window_start > p.window_end || !p.asked_by_engine || typeof p.asked_by_engine !== "object" ||
        Array.isArray(p.asked_by_engine)) { return { ok: false, reason: "format" }; }
    var keys = Object.keys(p.asked_by_engine), i, ordered = [];
    for (i = 0; i < ENGINE_ORDER.length; i++) { if (keys.indexOf(ENGINE_ORDER[i]) >= 0) { ordered.push(ENGINE_ORDER[i]); } }
    if (keys.some(function (key) { return ENGINE_ORDER.indexOf(key) < 0; })) { return { ok: false, reason: "format" }; }
    var list = Array.isArray(p.top_businesses) ? p.top_businesses : [];
    var rows = [], maxDays = 0;
    for (i = 0; i < ordered.length; i++) {
      var eng = ordered[i], asked = p.asked_by_engine[eng];
      if (!isCount(asked)) { return { ok: false, reason: "format" }; }
      if (asked === 0) { continue; }
      var named = 0;
      for (var j = 0; j < list.length; j++) {
        var e = list[j] && list[j].by_engine && list[j].by_engine[eng];
        if (e && typeof e.named === "number" && e.named > 0) { named += 1; }
      }
      rows.push({ engine: eng, label: ENGINE_LABEL[eng], asked_days: asked, listed_named_at_least_once: named, listed_count: list.length });
      if (asked > maxDays) { maxDays = asked; }
    }
    var total = isCount(p.businesses_named_total) ? p.businesses_named_total : null;
    var winDays = calendarDays(p.window_start, p.window_end);
    return { ok: true, market: p.market, niche: p.niche, window_start: p.window_start, window_end: p.window_end,
             rows: rows, engine_count: rows.length, answer_days: maxDays, window_days: winDays, over_window: maxDays > winDays,
             businesses_named_total: total };
  }

  // Why a summary cannot be shown as a badge or card; empty string means it can. The kind argument is kept for the callers; both are held to the same rule.
  function problem(s, kind) {
    if (!s || !s.ok) { return (s && s.reason) || "format"; }
    if (s.engine_count < 1) { return "no-engines"; }
    var w = labelProblem(s.market, s.niche);
    if (w) { return w; }
    if (s.over_window) { return "over-window"; }
    return "";
  }

  function recordUrl(market, niche) {
    var slug = RECORD_SLUGS[market + "|" + niche];
    return slug ? RECORD_BASE + slug + "/" : RECORD_BASE;
  }

  // A reference code becomes a lowercase URL slug of at most 40 characters. That slug is sent as utm_term to whichever destination the visitor clicks, the record page or the Verify page.
  function normalizeRef(ref) { return ref ? slugify(ref).slice(0, 40) : ""; }

  function tagged(url, kind, market, niche, ref) {
    var q = UTM + "&utm_content=" + encodeURIComponent(kind + "_" + slugify(market + " " + niche));
    var r = normalizeRef(ref);
    if (r) { q += "&utm_term=" + encodeURIComponent(r); }
    return url + (url.indexOf("?") < 0 ? "?" : "&") + q;
  }

  var LINK_STYLE = "color:#0b4ea2;text-decoration:underline;display:inline-block;min-width:24px;min-height:24px";
  var SMALL_STYLE = "font-size:12px;color:#333333;margin:4px 0 0;overflow-wrap:anywhere";
  var BOX_FONT = "font:14px/1.4 system-ui,-apple-system,'Segoe UI',Arial,sans-serif;text-align:left";

  function linksHtml(market, niche, kind, ref) {
    if (labelProblem(market, niche)) { return ""; }
    var haveRec = !!RECORD_SLUGS[market + "|" + niche], recWord = haveRec ? "Record page" : "Record index", pair = esc(market) + ", " + esc(niche);
    return "<div style=\"" + SMALL_STYLE + "\"><a href=\"" + esc(tagged(recordUrl(market, niche), kind, market, niche, ref)) + "\" rel=\"noopener noreferrer\" aria-label=\"" + recWord + " for " + pair + "\" style=\"" + LINK_STYLE + "\">" +
      recWord + "</a> | <a href=\"" + esc(tagged(VERIFY_URL, kind, market, niche, ref)) + "\" rel=\"noopener noreferrer\" aria-label=\"Verify a dated answer for " + pair + "\" style=\"" + LINK_STYLE + "\">Verify a dated answer</a></div>";
  }

  function plural(n, one, many) { return n + " " + (n === 1 ? one : many); }

  var SNAPSHOT_NOTE = "This snapshot uses the public explorer file. The linked record page may show different counts.";

  // The dated record badge: static HTML, no script, inline styles, one tag on each link.
  function badgeHtml(s, o) {
    o = o || {};
    var why = problem(s, "badge");
    if (why) { throw new Error(why); }
    if (!isDate(o.built)) { throw new Error("built-date"); }
    var attrs = " data-nb=\"record-badge-v1\" data-market=\"" + esc(s.market) + "\" data-niche=\"" + esc(s.niche) + "\" data-engines=\"" + esc(s.engine_count) +
      "\" data-answer-days=\"" + esc(s.answer_days) + "\" data-window-start=\"" + esc(s.window_start) + "\" data-window-end=\"" + esc(s.window_end) +
      "\" data-built=\"" + esc(o.built) + "\"";
    return "<div" + attrs + " role=\"group\" aria-label=\"Namebeam record badge\" style=\"display:block;max-width:420px;box-sizing:border-box;margin:8px 0;padding:10px 12px;border:1px solid #1b1b1b;border-radius:4px;background:#ffffff;color:#1b1b1b;" + BOX_FONT + "\">\n" +
      "  <div style=\"font-weight:700;overflow-wrap:anywhere\">Namebeam record: " + plural(s.engine_count, "source", "sources") + ", up to " + plural(s.answer_days, "reported answer day", "reported answer days") + ", data through " + esc(s.window_end) + "</div>\n" +
      "  <div style=\"" + SMALL_STYLE + "\">" + esc(s.market) + ", " + esc(s.niche) + ". Source window: " + esc(s.window_start) + " to " + esc(s.window_end) + ". The figure is the largest answer-day count reported for one source.</div>\n" +
      "  <div style=\"" + SMALL_STYLE + "\">" + SNAPSHOT_NOTE + "</div>\n" +
      "  " + linksHtml(s.market, s.niche, "badge", o.ref) + "\n" +
      "  <div style=\"" + SMALL_STYLE + "\">Source: " + esc(DATA_URL) + ", window ending " + esc(s.window_end) + ". Embed built " + esc(o.built) + ".</div>\n" +
      "</div>";
  }

  var LICENSE_TEXT = "CC BY 4.0 applies to the eligible Namebeam compilation, code, annotations, derived columns and documentation within each release's stated scope. Provider answer text and search-result rows are outside Namebeam's license grant. Provider terms may apply.";

  var TH = "border:1px solid #767676;padding:5px 8px;background:#f1f1f1;color:#1b1b1b;text-align:left;font-weight:700;font-size:13px;overflow-wrap:anywhere";
  var TD = "border:1px solid #767676;padding:5px 8px;color:#1b1b1b;font-size:13px;overflow-wrap:anywhere";
  var TR_HEAD = "border:1px solid #767676;padding:5px 8px;color:#1b1b1b;text-align:left;font-weight:400;font-size:13px;overflow-wrap:anywhere";

  function wrapperOpen(s, mode, o) {
    return "<div data-nb=\"" + (mode === "live" ? "market-card-live-v1" : "market-card-static-v1") + "\" data-market=\"" + esc(s.market) + "\" data-niche=\"" + esc(s.niche) + "\"" +
      (mode === "live" ? (o.ref ? " data-ref=\"" + esc(o.ref) + "\"" : "") + " role=\"status\"" : " data-window-start=\"" + esc(s.window_start) + "\" data-window-end=\"" + esc(s.window_end) + "\" data-built=\"" + esc(o.built) + "\"") +
      " style=\"display:block;max-width:640px;box-sizing:border-box;margin:8px 0;padding:12px;border:1px solid #1b1b1b;border-radius:4px;background:#ffffff;color:#1b1b1b;" + BOX_FONT + "\">";
  }

  // The inside of the market card: same text for the build-time card and the live card.
  function cardInner(s, o) {
    o = o || {};
    var mode = o.mode === "live" ? "live" : "static";
    var why = problem(s, "card");
    if (why) { throw new Error(why); }
    if (mode === "static" && !isDate(o.built)) { throw new Error("built-date"); }
    var h = "";
    h += "\n  <div style=\"font-weight:700;overflow-wrap:anywhere\">Namebeam record: " + esc(s.market) + ", " + esc(s.niche) + "</div>";
    h += "\n  <div>Data date: " + esc(s.window_end) + ". Source window: " + esc(s.window_start) + " to " + esc(s.window_end) + "." +
      (s.businesses_named_total === null ? "" : " The source reports " + esc(s.businesses_named_total) + " business names for this market and kind of business.") + "</div>";
    h += "\n  <table style=\"border-collapse:collapse;width:100%;margin:8px 0\">";
    h += "<caption style=\"text-align:left;font-size:12px;color:#333333;padding-bottom:4px\">Counts by source, window " + esc(s.window_start) + " to " + esc(s.window_end) + "</caption>";
    h += "<tr><th scope=\"col\" style=\"" + TH + "\">Source</th><th scope=\"col\" style=\"" + TH + "\">Answer days in the source</th><th scope=\"col\" style=\"" + TH + "\">Selected entries named on at least one answer day</th></tr>";
    for (var i = 0; i < s.rows.length; i++) {
      var r = s.rows[i];
      h += "<tr><th scope=\"row\" style=\"" + TR_HEAD + "\">" + esc(r.label) + "</th><td style=\"" + TD + "\">" + esc(r.asked_days) + "</td><td style=\"" + TD + "\">" + esc(r.listed_named_at_least_once) + " of " + esc(r.listed_count) + "</td></tr>";
    }
    h += "</table>";
    h += "\n  <div style=\"" + SMALL_STYLE + "\">Selected entries are the subset supplied by the source file. The figures describe name matches in saved answers.</div>";
    if (s.window_start <= MODEL_CHANGE_DATE && MODEL_CHANGE_DATE <= s.window_end) {
      h += "\n  <div style=\"" + SMALL_STYLE + "\">On " + MODEL_CHANGE_DATE + " we changed the OpenAI model we ask from gpt-5-mini to gpt-5.6-terra. Where the window spans that date, OpenAI counts combine both collection periods.</div>";
    }
    h += "\n  <div style=\"" + SMALL_STYLE + "\">" + SNAPSHOT_NOTE + "</div>";
    h += "\n  " + linksHtml(s.market, s.niche, "card", o.ref);
    h += "\n  <div style=\"" + SMALL_STYLE + "\">" + esc(LICENSE_TEXT) + "</div>";
    h += "\n  <div style=\"" + SMALL_STYLE + "\">Source: " + esc(DATA_URL) + ", window " + esc(s.window_start) + " to " + esc(s.window_end) +
      (mode === "live" ? ", loaded when this page opened" : ", embed built " + esc(o.built)) + ". Carter Enterprise LLC.</div>\n";
    return h;
  }

  function cardHtml(s, o) {
    o = o || {};
    var inner = cardInner(s, { mode: "static", built: o.built, ref: o.ref });
    return wrapperOpen(s, "static", o) + inner + "</div>";
  }

  // The inside of a live card that has no counts to show: loading, or a plain reason, always with a data-date line. A pair that is not on the
  // reviewed list gets a neutral state: no label, no links, no tags. A reviewed pair keeps its heading and its links.
  function stateInner(kind, market, niche, ref, dataDate) {
    if (kind === "refused" || kind === "config" || labelProblem(market, niche)) {
      return "\n  <div style=\"font-weight:700\">Namebeam record</div>" +
        "\n  <div>" + esc(kind === "config" ? MSG.config : MSG.refused) + "</div>" +
        "\n  <div style=\"" + SMALL_STYLE + "\">" + esc(MSG.no_date) + "</div>\n";
    }
    var line = MSG[kind] || MSG.fail;
    var dateLine = kind === "loading" ? MSG.loading_date : (kind === "over_window" && isDate(dataDate) ? "Data date: " + dataDate + "." : MSG.no_date);
    return "\n  <div style=\"font-weight:700;overflow-wrap:anywhere\">Namebeam record: " + esc(market) + ", " + esc(niche) + "</div>" +
      "\n  <div>" + esc(line) + (kind === "loading" ? "" : " " + esc(MSG.open_record)) + "</div>" +
      "\n  <div style=\"" + SMALL_STYLE + "\">" + esc(dateLine) + "</div>" +
      "\n  " + linksHtml(market, niche, "card", ref) + "\n";
  }

  function liveShell(market, niche, ref) {
    var why = labelProblem(market, niche);
    if (why) { throw new Error(why); }
    var r = ref ? slugify(ref).slice(0, 40) : "";
    return wrapperOpen({ market: market, niche: niche }, "live", { ref: r }) + stateInner("loading", market, niche, r) + "</div>";
  }

  // Fetch the public file from the visitor's browser: no credentials, no referrer, 15 second limit, 3,000,000 byte limit.
  async function loadData(fetchFn, timeoutMs) {
    if (typeof fetchFn !== "function") { throw new Error("nofetch"); }

    var controller = typeof AbortController === "function" ? new AbortController() : null;
    var options = {
      method: "GET", mode: "cors", credentials: "omit", referrerPolicy: "no-referrer"
    };
    if (controller) { options.signal = controller.signal; }

    var byteLimit = 3000000;
    var timer;
    var reader;
    var expired = false;
    var deadline = new Promise(function (_, reject) {
      timer = setTimeout(function () {
        expired = true;
        reject(new Error("timeout"));
        if (controller) { controller.abort(); }
        if (reader) { reader.cancel().catch(function () {}); }
      }, timeoutMs || 15000);
    });

    async function read() {
      var response = await fetchFn(DATA_URL, options);
      if (expired) { throw new Error("timeout"); }
      if (!response || !response.ok) { throw new Error("http"); }
      if (!response.body || typeof response.body.getReader !== "function" ||
          typeof TextDecoder !== "function") { throw new Error("format"); }

      reader = response.body.getReader();
      var decoder = new TextDecoder("utf-8", { fatal: true });
      var chunks = [];
      var bytes = 0;
      try {
        for (;;) {
          var chunk = await reader.read();
          if (expired) { throw new Error("timeout"); }
          if (chunk.done) { break; }
          bytes += chunk.value.byteLength;
          if (bytes > byteLimit) { throw new Error("format"); }
          try { chunks.push(decoder.decode(chunk.value, { stream: true })); }
          catch (_) { throw new Error("format"); }
        }
        try {
          chunks.push(decoder.decode());
          return JSON.parse(chunks.join(""));
        } catch (_) {
          throw new Error("format");
        }
      } catch (error) {
        reader.cancel().catch(function () {});
        throw error;
      }
    }

    try { return await Promise.race([deadline, read()]); }
    finally { clearTimeout(timer); }
  }

  // Fill one live container (it needs getAttribute and innerHTML, nothing more). Every failure ends in a plain message, never a thrown error.
  // The labels are checked before any request is used: a container without both labels gets the configuration message, and a pair that is not
  // on the reviewed list gets the neutral state with no label echoed.
  function mount(el, dataPromise) {
    var market = el.getAttribute("data-market") || "", niche = el.getAttribute("data-niche") || "", ref = normalizeRef(el.getAttribute("data-ref") || "");
    if (!market || !niche) { el.innerHTML = stateInner("config", "", "", ""); return Promise.resolve("config"); }
    if (labelProblem(market, niche)) { el.innerHTML = stateInner("refused", "", "", ""); return Promise.resolve("refused"); }
    return dataPromise.then(function (data) {
      if (fileProblem(data)) { el.innerHTML = stateInner("format", market, niche, ref); return "format"; }
      var p = findPair(data, market, niche);
      if (!p) { el.innerHTML = stateInner("nopair", market, niche, ref); return "nopair"; }
      var s = summarizePair(p);
      var why = problem(s, "card");
      if (why) {
        var k2 = why === "format" ? "format" : why === "over-window" ? "over_window" : "refused";
        el.innerHTML = stateInner(k2, market, niche, ref, s.window_end); return k2;
      }
      el.innerHTML = cardInner(s, { mode: "live", ref: ref });
      return "ok";
    }, function (e) {
      var k = e && e.message === "format" ? "format" : "fail";
      el.innerHTML = stateInner(k, market, niche, ref); return k;
    }).then(null, function () {
      el.innerHTML = stateInner("format", market, niche, ref); return "format";
    });
  }

  function mountAll(doc, fetchFn) {
    var nodes = doc.querySelectorAll("[data-nb=\"market-card-live-v1\"]");
    if (!nodes.length) { return Promise.resolve([]); }
    var needsFile = false, i;
    for (i = 0; i < nodes.length; i++) {
      var m = nodes[i].getAttribute("data-market") || "", n = nodes[i].getAttribute("data-niche") || "";
      if (m && n && !labelProblem(m, n)) { needsFile = true; }
    }
    var shared = needsFile ? loadData(fetchFn) : null;
    var all = [];
    for (i = 0; i < nodes.length; i++) { all.push(mount(nodes[i], shared)); }
    return Promise.all(all);
  }

  var api = { DATA_URL: DATA_URL, VERIFY_URL: VERIFY_URL, RECORD_BASE: RECORD_BASE, RECORD_SLUGS: RECORD_SLUGS, PUBLIC_PAIRS: PUBLIC_PAIRS, MSG: MSG, LICENSE_TEXT: LICENSE_TEXT,
              esc: esc, isDate: isDate, calendarDays: calendarDays, slugify: slugify, labelWord: labelWord, labelProblem: labelProblem, normalizeRef: normalizeRef,
              fileProblem: fileProblem, findPair: findPair, summarizePair: summarizePair, problem: problem, recordUrl: recordUrl, tagged: tagged,
              badgeHtml: badgeHtml, cardHtml: cardHtml, cardInner: cardInner, stateInner: stateInner, liveShell: liveShell, loadData: loadData,
              mount: mount, mountAll: mountAll };
  if (typeof module !== "undefined" && module.exports) { module.exports = api; } else { root.NBEmbed = api; }
})(typeof window !== "undefined" ? window : this);
/*NB-CORE-END*/
