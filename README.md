# README_DEPLOY -- MARKET_PAGES_2026-09-08

RUN_ID: 0908B-L12-MARKETPAGES. STAGED ONLY. NOTHING IN THIS FOLDER IS DEPLOYED OR PUBLISHED.

## File count
13 files: index.html plus 12 market_*.html pages. Zipped as
status/staged/MARKET_PAGES_2026-09-08.zip (index.html at the zip's top level, 13 entries,
123,081 bytes uncompressed, verified by `unzip -l`).

## Intended deploy target, found live in the Brain (not assumed)
Cloudflare Pages project **namebeam-customer-zero**, the same project that already serves
proof.namebeam.ai. Confirmed by a prior seat's own in-browser Cloudflare read, filed at
ACTIVE_THREAD_CLAIMS.md line 1769-1771 (2026-08-27 claim): "Cloudflare Pages project confirmed
in-browser: namebeam-customer-zero (account f78d1a4644be..., domains proof.namebeam.ai +
namebeam-customer-zero.pages.dev, No Git connection), Create deployment page staged on
Production."

That same finding, and this session's own re-confirmation (status/returns/0908B-L6-SERIES.md,
Part 4), both state there is **no Git-connected auto-deploy path** for this project: the confirmed
mechanism is a manual "Create deployment" upload (Terry dragging a zip or folder into Cloudflare
Pages' own upload zone), not a git push. Nothing in this run attempted a git push or any deploy
action; this file only names the target the next human (or gated) step would drag this zip into.

## What a future deploy would need to decide, not decided here
- Whether these 12 market pages become their own Pages project, a new subpath under the existing
  namebeam-customer-zero project (for example proof.namebeam.ai/markets/), or a separate domain.
  This was not decided or assumed by this run; it is Terry's call (gate 4, publish).
- The refused markets (7 of 19 discovered this run) stay refused until the corpus carries enough
  usable rows and distinct days for each; see status/returns/0908B-L12-MARKETPAGES.md for the
  exact shortfall per market.
