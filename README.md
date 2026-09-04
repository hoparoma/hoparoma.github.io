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
| `/data/*.json` | Machine-readable copies of the published tables | generated |
| `/support.html` `/privacy.html` `/terms.html` | App Store required pages | hand-written |
| `/editorial-submission.html` `/bibliography.html` | Apple Editorial press kit (legacy, not in nav) | hand-written |

## Build

The app repo is the single source of truth for the data. Nothing is typed twice.

```bash
python3 tools/extract_data.py   # reads ../HopAromaPredictor/Sources/{Core/EmbeddedData.swift, Models/MaltType.swift, Models/HopOrigin.swift} → data/*.json
python3 tools/build_site.py     # data/*.json + templates/*.j2 → hops/ yeast/ malt/ sources/ 404.html sitemap.xml robots.txt
python3 tools/site_gate.py      # exit 0 PASS / 1 WARN / 2 BLOCK. Do not deploy on BLOCK.
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

- `tools/site_config.json`: base URL, App Store URL, `analytics_id` (GA4, empty = no tag), `dataset_license`.
- `tools/yeast_names.json`: display names for app yeast ids.
- `tools/yeast_verified.json`: manufacturer URLs and official thiol statements (verified 2026-09-02).
- `tools/yeast_notes.json`: evidence text per thiol-relevant strain; only strains listed here get a page.
- `tools/overrides.json`: dated site-side suppressions while the app dataset is corrected (each has a BACKLOG item in the app repo).
- `data/sources.json`: bibliography; entries must be `VERIFIED` before deploy.

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
