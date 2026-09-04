#!/usr/bin/env python3
"""Extract publishable reference data from the Hoparoma iOS sources.

Single source of truth stays in the app repo:
  Sources/Core/EmbeddedData.swift   (hopMedicsCSV / hopCropYearCSV / yeastProfilesCSV)
  Sources/Models/MaltType.swift      (enum + lovibond + thiolPrecursorLevel + category)
  Sources/Models/HopOrigin.swift     (origin catalog)

Publication line v2 (site_redesign_design_2026-09-02.md §3):
  * supplier / literature derived chemistry and qualitative tiers are published
  * engine-internal coefficients are dropped here, so templates can never see them

Output: data/hops.json, data/yeast.json, data/malt.json, data/meta.json
        tools/.cache/forbidden_values.json (for site_gate.py, never published)
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SITE_ROOT = Path(__file__).resolve().parent.parent
APP_ROOT = SITE_ROOT.parent / "HopAromaPredictor"
EMBEDDED = APP_ROOT / "Sources" / "Core" / "EmbeddedData.swift"
MALT_SWIFT = APP_ROOT / "Sources" / "Models" / "MaltType.swift"
ORIGIN_SWIFT = APP_ROOT / "Sources" / "Models" / "HopOrigin.swift"
PROJECT_YML = APP_ROOT / "project.yml"
DATA_DIR = SITE_ROOT / "data"
CACHE_DIR = SITE_ROOT / "tools" / ".cache"

# ---- publication line v2 -------------------------------------------------
HOP_FORBIDDEN = {"thiol_3mh_median", "thiol_4mmp_median", "sulfur_proxy", "tier"}
YEAST_FORBIDDEN = {
    "myrcene_factor", "linalool_factor", "geraniol_factor", "thiol_boost",
    "conversion_rate", "mha_multiplier", "ester_level", "bioT_sensitivity",
    "thiol_biotransformation_activity", "segment_main", "tier",
}
# BiotransformationLevel thresholds mirror YeastProfile.swift (the tier label is
# what the app shows in its yeast picker, so the label is publishable).
def biotransformation_level(activity: float) -> str:
    if activity < 0.70:
        return "low"
    if activity < 0.85:
        return "medium"
    return "high"


# ---- helpers ---------------------------------------------------------------
def norm_key(name: str) -> str:
    """Mirror CSVLoader.normKey: lowercase alphanumerics only."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def slugify(name: str) -> str:
    s = name.lower().replace("ü", "u").replace("é", "e")
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s


def num(v: str | None) -> float | None:
    if v is None:
        return None
    v = v.strip()
    if v == "":
        return None
    try:
        return float(v)
    except ValueError:
        return None


def read_csv_literal(swift_src: str, name: str) -> list[dict]:
    m = re.search(rf'static let {name} = """\n(.*?)\n"""', swift_src, re.S)
    if not m:
        sys.exit(f"CSV literal {name} not found in {EMBEDDED}")
    rows = list(csv.DictReader(io.StringIO(m.group(1))))
    return rows


# ---- hops ------------------------------------------------------------------
def build_hops(swift_src: str, origins: dict) -> tuple[list[dict], dict]:
    medics = read_csv_literal(swift_src, "hopMedicsCSV")
    crop = read_csv_literal(swift_src, "hopCropYearCSV")
    crop_by_name: dict[str, list[dict]] = {}
    for r in crop:
        crop_by_name.setdefault(r["hop_variety"].strip(), []).append(r)

    forbidden: dict[str, dict] = {}
    hops: list[dict] = []
    unmatched_crop = set(crop_by_name) - {r["hop_variety"].strip() for r in medics}

    for r in medics:
        name = r["hop_variety"].strip()
        forbidden[name] = {k: r[k] for k in HOP_FORBIDDEN if k in r}
        rows = crop_by_name.get(name, [])
        agg = next((x for x in rows if x["crop_year_scope"] == "typical_4yr_aggregate"), None)
        years = sorted(
            (x for x in rows if x["crop_year_scope"] != "typical_4yr_aggregate"),
            key=lambda x: x["crop_year_scope"],
        )

        def rng(prefix: str, src: dict | None) -> dict | None:
            if not src:
                return None
            lo, hi = num(src.get(f"{prefix}_min")), num(src.get(f"{prefix}_max"))
            if lo is None and hi is None:
                return None
            return {"min": lo, "max": hi}

        def year_row(x: dict) -> dict:
            return {
                "year": x["crop_year_scope"],
                "alpha_acid": rng("alpha_acid", x),
                "beta_acid": rng("beta_acid", x),
                "cohumulone": rng("cohumulone", x),
                "total_oil": rng("total_oil", x),
                "myrcene": rng("myrcene", x),
                "humulene": rng("humulene", x),
                "caryophyllene": rng("caryophyllene", x),
                "farnesene": rng("farnesene", x),
                "linalool": rng("linalool", x),
                "geraniol": rng("geraniol", x),
                "b_pinene": rng("b_pinene", x),
                "thiol_3mh_qualitative": x.get("thiol_3mh_qualitative", "").strip() or None,
                "thiol_4mmp_qualitative": x.get("thiol_4mmp_qualitative", "").strip() or None,
                "data_source": x.get("data_source", "").strip(),
                "note": x.get("crop_year_note", "").strip() or None,
            }

        agg_source = (agg or {}).get("data_source", "").strip()
        backfill = agg_source.startswith("hopMedics-derived")
        quality = r.get("data_quality_note", "").strip()
        thiol_3mh_q = (agg or {}).get("thiol_3mh_qualitative", "").strip() or None
        thiol_4mmp_q = (agg or {}).get("thiol_4mmp_qualitative", "").strip() or None

        # Individual-page rule (design §4): needs at least one of
        #   (a) year-specific lot rows, (b) an externally sourced aggregate row,
        #   (c) a verified/supplier-referenced medians row that is not a bare estimate.
        has_years = len(years) > 0
        external_agg = agg is not None and not backfill
        verified_medians = quality != "2026 estimate"
        individual_page = has_years or external_agg or (verified_medians and thiol_3mh_q not in (None, "low"))

        origin = origins.get(norm_key(name))
        hops.append({
            "name": name,
            "slug": slugify(name),
            "key": norm_key(name),
            "origin": origin,
            "n_sources": int(num(r.get("n_sources")) or 0),
            "sensory_summary": r.get("sensory_summary", "").strip(),
            "thiol_note_summary": r.get("thiol_note_summary", "").strip(),
            "data_quality_note": quality,
            "medians": {
                "alpha_acid": {"median": num(r.get("alpha_acid_median")), "min": num(r.get("alpha_acid_min")), "max": num(r.get("alpha_acid_max"))},
                "total_oil": {"median": num(r.get("total_oil_median")), "min": num(r.get("total_oil_min")), "max": num(r.get("total_oil_max"))},
                "myrcene": {"median": num(r.get("myrcene_median")), "min": num(r.get("myrcene_min")), "max": num(r.get("myrcene_max"))},
                "humulene": {"median": num(r.get("humulene_median")), "min": num(r.get("humulene_min")), "max": num(r.get("humulene_max"))},
                "beta_caryophyllene": {"median": num(r.get("beta_caryophyllene_median")), "min": num(r.get("beta_caryophyllene_min")), "max": num(r.get("beta_caryophyllene_max"))},
                "farnesene": {"median": num(r.get("farnesene_median")), "min": num(r.get("farnesene_min")), "max": num(r.get("farnesene_max"))},
                "b_pinene": {"median": num(r.get("pinene_median"))},
                "linalool": {"median": num(r.get("linalool_median")), "min": num(r.get("linalool_min")), "max": num(r.get("linalool_max"))},
                "geraniol": {"median": num(r.get("geraniol_median")), "min": num(r.get("geraniol_min")), "max": num(r.get("geraniol_max"))},
            },
            "aggregate": year_row(agg) if agg else None,
            "aggregate_is_backfill": backfill,
            "crop_years": [year_row(x) for x in years],
            "thiol_3mh_qualitative": thiol_3mh_q,
            "thiol_4mmp_qualitative": thiol_4mmp_q,
            "individual_page": individual_page,
        })

    hops.sort(key=lambda h: h["name"].lower())
    if unmatched_crop:
        print(f"[extract] crop-year rows without a medians row (ignored): {sorted(unmatched_crop)}")
    return hops, forbidden


# ---- yeast -----------------------------------------------------------------
def build_yeast(swift_src: str) -> tuple[list[dict], dict]:
    rows = read_csv_literal(swift_src, "yeastProfilesCSV")
    forbidden: dict[str, dict] = {}
    out: list[dict] = []
    for r in rows:
        yid = r["yeast_name"].strip()
        forbidden[yid] = {k: r[k] for k in YEAST_FORBIDDEN if k in r}
        activity = num(r.get("thiol_biotransformation_activity")) or 0.0
        style_tag = r.get("style_tag", "").strip()
        out.append({
            "id": yid,
            "slug": slugify(yid),
            "alias": r.get("alias", "").strip(),
            "temp_c": {"min": num(r.get("temp_min")), "opt": num(r.get("temp_opt")), "max": num(r.get("temp_max"))},
            "attenuation": num(r.get("attenuation")),
            "style_tag": style_tag,
            "style_tags": [t for t in style_tag.split("+") if t],
            "availability": r.get("availability", "").strip(),
            "fermentation_type": r.get("fermentation_type", "").strip() or "ale",
            "biotransformation_level": biotransformation_level(activity),
            "thiol_relevant": biotransformation_level(activity) == "high" or "bioT" in style_tag,
        })
    return out, forbidden


# ---- malt ------------------------------------------------------------------
def parse_switch(block: str) -> dict[str, str]:
    """Parse `case .a, .b:\n return .x` (multi-line) and `case .a: return N` (single-line)."""
    mapping: dict[str, str] = {}
    pending: list[str] = []
    # Join `case .a, .b,\n .c:` continuation lines so every case list sits on one line.
    joined: list[str] = []
    for raw in block.splitlines():
        line = raw.split("//")[0].strip()
        if not line:
            continue
        if joined and joined[-1].startswith("case ") and ":" not in joined[-1]:
            joined[-1] = joined[-1] + " " + line
        else:
            joined.append(line)
    for line in joined:
        m = re.match(r"case ([^:]+):\s*(?:return\s+(.+))?$", line)
        if m:
            names = [c.strip().lstrip(".") for c in m.group(1).split(",")]
            if m.group(2):
                for n in names:
                    mapping[n] = m.group(2).strip()
            else:
                pending.extend(names)
            continue
        m = re.match(r"return\s+(.+)$", line)
        if m and pending:
            for n in pending:
                mapping[n] = m.group(1).strip()
            pending = []
    return mapping


def switch_block(src: str, header_regex: str) -> str:
    m = re.search(header_regex + r".*?switch self \{(.*?)\n    \}", src, re.S)
    if not m:
        sys.exit(f"switch block not found: {header_regex}")
    return m.group(1)


def build_malt(malt_src: str) -> list[dict]:
    cases = re.findall(r'case (\w+)\s*=\s*"([^"]+)"', malt_src)
    display_override = parse_switch(switch_block(malt_src, r"var displayName: String \{"))
    lovibond = parse_switch(switch_block(malt_src, r"var lovibond: Double \{"))
    level = parse_switch(switch_block(malt_src, r"var thiolPrecursorLevel: ThiolPrecursorLevel \{"))
    category = parse_switch(switch_block(malt_src, r"func category\(_ lang: AppLanguage = \.japanese\) -> String \{"))
    cat_names = {
        "L10n.maltCategoryBase.t(lang)": "base",
        "L10n.maltCategoryCrystal.t(lang)": "crystal",
        "L10n.maltCategoryRoast.t(lang)": "roast",
        "L10n.maltCategoryAdjunct.t(lang)": "adjunct",
        "L10n.maltCategoryOther.t(lang)": "other",
    }
    out = []
    for case_name, raw in cases:
        if case_name == "other":
            continue
        name = display_override.get(case_name, f'"{raw}"').strip('"')
        out.append({
            "id": case_name,
            "name": name,
            "lovibond": float(lovibond[case_name]),
            "category": cat_names.get(category.get(case_name, ""), "other"),
            "thiol_precursor_level": level[case_name].lstrip("."),
        })
    return out


# ---- origins ---------------------------------------------------------------
def build_origins(src: str) -> dict:
    out = {}
    for m in re.finditer(r'"(\w+)": HopOrigin\(flagEmoji: "([^"]*)", countryCode: "(\w+)", detail: "([^"]*)"\)', src):
        out[m.group(1)] = {"flag": m.group(2), "country": m.group(3), "detail": m.group(4)}
    return out


# ---- meta ------------------------------------------------------------------
def build_meta() -> dict:
    version = re.search(r'MARKETING_VERSION: "([^"]+)"', PROJECT_YML.read_text()).group(1)
    build = re.search(r'CURRENT_PROJECT_VERSION: "([^"]+)"', PROJECT_YML.read_text()).group(1)
    sha = hashlib.sha256(EMBEDDED.read_bytes()).hexdigest()[:12]
    try:
        head = subprocess.run(["git", "-C", str(APP_ROOT), "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        head = "unknown"
    site_cfg_path = SITE_ROOT / "tools" / "site_config.json"
    site_cfg = json.loads(site_cfg_path.read_text()) if site_cfg_path.exists() else {}
    return {
        "app_version": version,
        "app_build": build,
        "app_head": head,
        "embedded_data_sha": sha,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "license": site_cfg.get("dataset_license", ""),
        "license_name": site_cfg.get("dataset_license_name", ""),
        "attribution": site_cfg.get("dataset_attribution", ""),
    }


def main() -> None:
    swift_src = EMBEDDED.read_text(encoding="utf-8")
    origins = build_origins(ORIGIN_SWIFT.read_text(encoding="utf-8"))
    hops, hop_forbidden = build_hops(swift_src, origins)
    yeast, yeast_forbidden = build_yeast(swift_src)
    malt = build_malt(MALT_SWIFT.read_text(encoding="utf-8"))
    meta = build_meta()

    DATA_DIR.mkdir(exist_ok=True)
    CACHE_DIR.mkdir(exist_ok=True)
    (DATA_DIR / "hops.json").write_text(json.dumps({"meta": meta, "hops": hops}, indent=1, ensure_ascii=False) + "\n")
    (DATA_DIR / "yeast.json").write_text(json.dumps({"meta": meta, "yeast": yeast}, indent=1, ensure_ascii=False) + "\n")
    (DATA_DIR / "malt.json").write_text(json.dumps({"meta": meta, "malt": malt}, indent=1, ensure_ascii=False) + "\n")
    (DATA_DIR / "meta.json").write_text(json.dumps(meta, indent=1) + "\n")
    (CACHE_DIR / "forbidden_values.json").write_text(json.dumps({"hops": hop_forbidden, "yeast": yeast_forbidden}, indent=1) + "\n")

    pages = [h["name"] for h in hops if h["individual_page"]]
    print(f"[extract] hops={len(hops)} individual_pages={len(pages)} yeast={len(yeast)} thiol_relevant={sum(y['thiol_relevant'] for y in yeast)} malt={len(malt)}")
    print(f"[extract] index-only hops: {[h['name'] for h in hops if not h['individual_page']]}")
    missing_origin = [h["name"] for h in hops if not h["origin"]]
    if missing_origin:
        print(f"[extract] WARNING hops without origin entry: {missing_origin}")
    print(f"[extract] meta={meta}")


if __name__ == "__main__":
    main()
