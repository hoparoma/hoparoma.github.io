# hoparoma.github.io → hoparoma.com

Marketing, legal, and reference-library pages for the Hoparoma iOS app.

Published with GitHub Pages. Custom domain migration to `hoparoma.com` is described in
`../HopAromaPredictor/launch-startup/site_phaseA_runbook_2026-09-02.md`.

## Pages

| URL | Purpose | Source |
|---|---|---|
| `/` | Hub: honest positioning, reference-library entrances, App Store CTA, email capture | hand-written `index.html` |
| `/hops/`, `/hops/{slug}/` | 70 hop varieties (index) and individual pages for varieties with verified data | generated |
| `/yeast/`, `/yeast/{slug}/` | 29 strains rated for β-lyase thiol release; evidence pages for thiol-relevant strains | generated |
| `/malt/thiol-precursors/` | 40 malts and grains rated for thiol precursor level | generated |
| `/sources/` | Bibliography with DOIs; every data page cites into it | generated from `data/sources.json` |
| `/calculator/` | Names the tool category ("hop aroma calculator"), explains inputs, outputs and limits, links to the web app and the App Store; WebApplication + FAQPage JSON-LD | generated (`templates/calculator.html.j2` + `tools/calculator_faq.json`) |
| `/data/*.json` | Machine-readable copies of the published tables | generated |
| `/support.html` `/privacy.html` `/terms.html` | App Store required pages | hand-written |
| `/editorial-submission.html` `/bibliography.html` | Apple Editorial press kit (legacy, not in nav) | hand-written |

## Build

The app repo is the single source of truth for the data. Nothing is typed twice.

```bash
python3 tools/extract_data.py   # reads ../HopAromaPredictor/Sources/{Core/EmbeddedData.swift, Models/MaltType.swift, Models/HopOrigin.swift} → data/*.json
python3 tools/build_site.py     # data/*.json + templates/*.j2 → hops/ yeast/ malt/ sources/ 404.html sitemap.xml robots.txt
python3 tools/site_gate.py      # exit 0 PASS / 1 WARN / 2 BLOCK. Do not deploy on BLOCK. W5 lists referenced files that git does not track yet (stage them by name; never `git add .`).
python3 tools/indexnow_ping.py  # dry run. After the push is live: --send (all sitemap URLs) or --send /calculator/ ...
```

Requires Python 3 and Jinja2. Output is committed; GitHub Pages serves static files.

### Publication line (what is and is not published)

`tools/extract_data.py` drops the engine-internal columns before anything reaches a template
(hop `thiol_*_median`, `sulfur_proxy`, app tiers; yeast `thiol_boost`, `conversion_rate`, `*_factor`,
`thiol_biotransformation_activity`, and so on). Published: supplier and literature values, qualitative
tiers, crop-year lots, and the level labels the app itself shows. `tools/site_gate.py` checks that no
internal column name or coefficient value leaks and that no forbidden claim ("first", bare "predicts")
appears anywhere on the site.

### Config and overrides

- `tools/site_config.json`: base URL, App Store URL, `web_app_url`, `analytics_id` (GA4, empty = no tag), `dataset_license`, `css_version` (hand-written pages carry the same `?v=` by hand), `indexnow_key` (public by design; the matching `<key>.txt` sits at the site root).
- `tools/calculator_faq.json`: the Q&A on `/calculator/`, rendered as visible text and as FAQPage JSON-LD.
- `tools/yeast_names.json`: display names for app yeast ids.
- `tools/yeast_verified.json`: manufacturer URLs and official thiol statements (verified 2026-09-02).
- `tools/yeast_notes.json`: evidence text per thiol-relevant strain; only strains listed here get a page.
- `tools/overrides.json`: dated site-side suppressions while the app dataset is corrected (each has a BACKLOG item in the app repo).
- `data/sources.json`: bibliography; entries must be `VERIFIED` before deploy.

## Calls to action and click counts

Reference pages offer the web calculator first and the App Store second (`app_links` in `templates/_macros.html.j2`).
`/track.js` sends two GA4 events, `web_app_click` and `app_store_click`, with a `placement` parameter read from
`data-placement`. `privacy.html` (Website section, EN and JA) describes exactly this; change both together.

### Copies of the same facts (change them together)

Web allowances (3 recipes / 2 comparisons / 3 saved; Pro 30 / 10 / 50 within 200), the web Pro price (US$4.99 plus applicable tax), the SMS
regions and the phone-number explanation appear in: the web app (`Web/public/index.html` in the app repo), `support.html`
(EN and JA), `tokushoho.html`, `terms.html`, `tools/calculator_faq.json`, `templates/calculator.html.j2`,
`templates/_macros.html.j2` (CTA note), the JSON-LD offers in `tools/build_site.py` and in the hub's hand-written JSON-LD block, and the hub (`index.html`: hero note,
pricing intro, FAQ). The header nav and footer are duplicated by hand in `index.html`, `support.html`, `privacy.html`,
`terms.html` and `tokushoho.html`; generated pages take them from `templates/base.html.j2`.

## Data license

The reference tables and `data/*.json` are published under CC BY 4.0 (decided 2026-09-04): reuse and
adaptation are welcome with credit to Hoparoma and a link to hoparoma.com. The license covers the published
compilation only; the app's aroma engine and its coefficients are not published. Article text under `/notes/`
keeps ordinary copyright. Configured in `tools/site_config.json` (`dataset_license*`).

## Stack

Static HTML, `style.css` (tokens, marketing pages) plus `ref.css` (reference-library components using the
same tokens). No JavaScript except the optional GA4 tag. Google Fonts for Hanken Grotesk / Inter / JetBrains Mono.

## Source of truth

- Data: `hoparoma-ios` `Sources/Core/EmbeddedData.swift` and `Sources/Models/MaltType.swift`.
- Legal content: mirrored from `hoparoma-ios` `docs/legal/`.
- Copy rules: `launch-startup/positioning_honest_recalibration_2026-07-13.md` (two-layer message architecture, banned phrases).

## Contact

<hoparoma.support@gmail.com>
