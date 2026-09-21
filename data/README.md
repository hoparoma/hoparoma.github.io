# Hoparoma hop, yeast and malt reference (dataset)

Machine-readable copies of the reference tables published at <https://hoparoma.com/>:
[hops](https://hoparoma.com/hops/), [yeast](https://hoparoma.com/yeast/),
[malt thiol precursors](https://hoparoma.com/malt/thiol-precursors/) and
[sources](https://hoparoma.com/sources/).

- **License**: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Reuse and adaptation are welcome.
- **Attribution**: "Hoparoma hop, yeast and malt reference, https://hoparoma.com/"
- **Version**: `hops.json`, `yeast.json` and `malt.json` embed a `meta` block (`app_version`, `embedded_data_sha`, `generated_at`); `meta.json` holds the same block on its own; `sources.json` has none. Cite the `generated_at` date.
- **Corrections**: support@hoparoma.com. If a value for your variety or strain is wrong, tell us and we will fix it and credit the source.

## Files

| File | Records | What it holds |
|---|---|---|
| `hops.json` | 70 varieties | Supplier and literature brewing values, oil composition, qualitative bound-thiol ratings, crop-year lot rows for 15 varieties |
| `yeast.json` | 29 strains | Fermentation range, attenuation, availability, and a three-step rating for thiol release (β-lyase activity) |
| `malt.json` | 40 malts and grains | Colour, category, and a rating for bound 3MH thiol precursor content |
| `sources.json` | bibliography | Papers, manufacturer disclosures and supplier data behind the tables, with DOIs or URLs and a verification status |
| `meta.json` | — | Version and license block shared by the files above |

## Fields

### `hops.json` → `hops[]`

| Field | Meaning |
|---|---|
| `name`, `slug`, `key` | Variety name, URL slug (`https://hoparoma.com/hops/{slug}/`), internal key |
| `origin` | `country`, `flag`, `detail` (breeder and release year where known) |
| `sensory_summary` | How brewers describe the variety, in a few words |
| `thiol_note_summary` | Short note on the variety's thiol character |
| `thiol_3mh_qualitative`, `thiol_4mmp_qualitative` | Qualitative rating of thiol precursors (3MH family, 4MMP): `low`, `significant` or `high`; `null` when not rated. Aggregate and crop-year rows can carry their own rating |
| `medians` | Typical value per property as `{median, min, max}` |
| `aggregate` | Typical multi-year supplier range per property as `{min, max}`; `aggregate_is_backfill` is `true` when the range was derived from `medians` rather than taken from a supplier sheet |
| `crop_years[]` | Lot-level rows by crop year (`year`, then properties as `{min, max}`, plus a `note` and `data_source` where present) |
| `n_sources` | Number of sources consulted for the variety |
| `data_quality_note` | Provenance of the typical values: `verified 2026`, a supplier reference such as `2026 YCH reference` or `2026 BarthHaas reference`, or `2026 estimate` |
| `individual_page` | Whether the variety has its own page on the site |

Units: `alpha_acid` and `beta_acid` in % w/w; `cohumulone` in % of alpha acids; `total_oil` in mL/100 g;
`myrcene`, `humulene`, `caryophyllene` / `beta_caryophyllene`, `farnesene`, `linalool`, `geraniol`, `b_pinene` in % of total oil.

### `yeast.json` → `yeast[]`

| Field | Meaning |
|---|---|
| `id`, `slug`, `alias` | Strain identifier, URL slug, short alias |
| `temp_c` | `{min, opt, max}` fermentation temperature in °C |
| `attenuation` | Typical apparent attenuation as a fraction (0.74 = 74 %) |
| `style_tag`, `style_tags` | Style family the strain is usually chosen for |
| `fermentation_type` | `ale`, `lager` or `kveik` |
| `availability` | `mainstream_dry`, `mainstream_liquid`, `mainstream_dry+liquid`, `limited_hb_active_pro`, `pro_only` |
| `biotransformation_level` | `low`, `medium` or `high`: rating for thiol release (β-lyase activity), from manufacturer trials and papers |
| `thiol_relevant` | Flag for strains that matter to the site's thiol discussion: set from a high rating or a biotransformation style tag. It includes conventional strains (some lager yeasts, for example) and does not mean a strain was selected or engineered for thiol release |

### `malt.json` → `malt[]`

| Field | Meaning |
|---|---|
| `id`, `name` | Identifier and display name |
| `lovibond` | Colour in °L |
| `category` | `base`, `crystal`, `roast`, `adjunct` or `other` |
| `thiol_precursor_level` | `negligible`, `low`, `lowNonBarley`, `medium`, or `na`: rating for bound 3MH precursor content |

## What is not in here

The Hoparoma aroma engine and its coefficients are not published. The extraction script drops every
engine-internal column before anything reaches these files, and a pre-deploy gate checks that none leaks
(`tools/extract_data.py`, `tools/site_gate.py`). The ratings above are qualitative tiers. No numeric coefficients and no tier-to-coefficient mappings are published.

## How to cite

> Hoparoma. *Hoparoma hop, yeast and malt reference* (dataset), version dated `<generated_at>`. https://hoparoma.com/ . CC BY 4.0.
