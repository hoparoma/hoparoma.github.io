#!/usr/bin/env python3
"""Render the reference pages (hops / yeast / malt / sources / 404 / sitemap) from data/*.json.

Usage:  python3 tools/extract_data.py && python3 tools/build_site.py && python3 tools/site_gate.py
Output is committed: GitHub Pages serves the static result, no build step on the server.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

SITE_ROOT = Path(__file__).resolve().parent.parent
TOOLS = SITE_ROOT / "tools"
DATA = SITE_ROOT / "data"
TEMPLATES = SITE_ROOT / "templates"
GENERATED_DIRS = ["hops", "yeast", "malt", "sources"]
STATIC_PAGES = ["/", "/support.html", "/privacy.html", "/terms.html"]

THIOL_HIGH = {"high", "very_high_bound"}


# ---- filters ----------------------------------------------------------------
def fmt_num(v) -> str:
    if v is None:
        return "–"
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    if f == int(f):
        return str(int(f))
    return f"{f:.2f}".rstrip("0").rstrip(".")


def fmt_rng(r) -> str:
    if not r:
        return "–"
    lo, hi = r.get("min"), r.get("max")
    if lo is None and hi is None:
        return "–"
    if lo is None:
        return f"≤ {fmt_num(hi)}"
    if hi is None:
        return f"≥ {fmt_num(lo)}"
    if lo == hi:
        return fmt_num(lo)
    return f"{fmt_num(lo)}–{fmt_num(hi)}"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


# ---- JSON-LD ----------------------------------------------------------------
def breadcrumb_ld(base: str, items: list[tuple[str, str]]) -> dict:
    return {
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": name, "item": base + path}
            for i, (name, path) in enumerate(items)
        ],
    }


def dataset_ld(base: str, path: str, name: str, description: str, keywords: list[str], cfg: dict, meta: dict) -> dict:
    d = {
        "@type": "Dataset",
        "name": name,
        "description": description,
        "url": base + path,
        "keywords": keywords,
        "creator": {"@type": "Organization", "name": "Hoparoma", "url": base + "/"},
        "version": f"{meta['app_version']}-{meta['embedded_data_sha']}",
        "dateModified": meta["generated_at"],
        "isAccessibleForFree": True,
    }
    if cfg.get("dataset_license"):
        d["license"] = cfg["dataset_license"]
    return d


def graph(*nodes: dict) -> dict:
    return {"@context": "https://schema.org", "@graph": list(nodes)}


# ---- main ---------------------------------------------------------------------
def main() -> None:
    cfg = load(TOOLS / "site_config.json")
    base = cfg["base_url"].rstrip("/")
    hops_doc = load(DATA / "hops.json")
    yeast_doc = load(DATA / "yeast.json")
    malt_doc = load(DATA / "malt.json")
    sources = load(DATA / "sources.json")
    names = load(TOOLS / "yeast_names.json")
    notes = load(TOOLS / "yeast_notes.json")
    verified_path = TOOLS / "yeast_verified.json"
    verified = load(verified_path) if verified_path.exists() else {}
    meta = hops_doc["meta"]

    hops = hops_doc["hops"]
    malt = malt_doc["malt"]

    # site-side overrides (dated, mirrored in the app BACKLOG) ---------------------
    overrides_path = TOOLS / "overrides.json"
    overrides = load(overrides_path) if overrides_path.exists() else {}
    suppressed = {(o["hop"], o["year"]) for o in overrides.get("suppress_hop_notes", [])}
    for h in hops:
        if h["aggregate"] and (h["name"], "typical_4yr_aggregate") in suppressed:
            h["aggregate"]["note"] = None
        for cy in h["crop_years"]:
            if (h["name"], cy["year"]) in suppressed:
                cy["note"] = None

    # yeast view models --------------------------------------------------------
    yeast = []
    for y in yeast_doc["yeast"]:
        nm = names.get(y["id"], {})
        vf = verified.get(y["id"], {})
        yv = dict(y)
        yv["display_name"] = nm.get("product_name") or y["id"]
        yv["lab"] = nm.get("lab", "")
        yv["code"] = nm.get("code", "")
        yv["product_url"] = vf.get("url", "")
        yv["thiol_claim"] = vf.get("thiol_claim", "")
        yv["notes"] = notes.get(y["id"])
        yv["has_page"] = bool(yv["notes"]) and y["thiol_relevant"]
        yeast.append(yv)
    yeast.sort(key=lambda v: (v["biotransformation_level"] != "high", v["biotransformation_level"] != "medium", v["display_name"].lower()))

    high_yeasts = [v for v in yeast if v["biotransformation_level"] == "high"]
    thiol_hops = [h for h in hops if h["thiol_3mh_qualitative"] in THIOL_HIGH or h["thiol_4mmp_qualitative"] in THIOL_HIGH]

    S = {}
    for g in sources["groups"]:
        for s in g["items"]:
            S[s["id"]] = s

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES)),
        autoescape=select_autoescape(["html", "j2"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["n"] = fmt_num
    env.filters["rng"] = fmt_rng
    common = {"cfg": cfg, "meta": meta, "S": S}

    for d in GENERATED_DIRS:
        shutil.rmtree(SITE_ROOT / d, ignore_errors=True)

    written: list[str] = []

    def render(template: str, out_path: str, **ctx) -> None:
        html = env.get_template(template).render(**common, page_path=out_path, **ctx)
        target = SITE_ROOT / out_path.lstrip("/")
        if out_path.endswith("/"):
            target = target / "index.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(html, encoding="utf-8")
        written.append(out_path)

    # hops ----------------------------------------------------------------------
    render(
        "hops_index.html.j2", "/hops/",
        nav="hops", hops=hops, og_type="website",
        page_title=f"Hop varieties: oils, thiol potential and crop-year data for {len(hops)} hops | Hoparoma",
        page_description=f"Brewing values, oil composition, bound-thiol ratings and lot-level crop-year data for {len(hops)} hop varieties, with sources. From the Hoparoma reference library.",
        jsonld=graph(
            breadcrumb_ld(base, [("Home", "/"), ("Hops", "/hops/")]),
            dataset_ld(base, "/hops/", "Hoparoma hop variety reference", "Supplier brewing values, oil composition, qualitative thiol precursor ratings and crop-year lot data for hop varieties.", ["hops", "hop aroma", "thiols", "3MH", "4MMP", "crop year"], cfg, meta),
        ),
    )
    for h in hops:
        if not h["individual_page"]:
            continue
        agg = h["aggregate"] or {}
        crop = ", crop-year lots" if h["crop_years"] else ""
        origin = f" ({h['origin']['country']})" if h.get("origin") else ""
        desc = (
            f"{h['name']}{origin}: {h['sensory_summary']}. Alpha acid {fmt_rng(agg.get('alpha_acid'))} %, total oil {fmt_rng(agg.get('total_oil'))} mL/100 g. "
            f"Bound thiol precursors rated {h['thiol_3mh_qualitative'] or 'not rated'} (3MH family) and {h['thiol_4mmp_qualitative'] or 'not rated'} (4MMP), with sources and yeast pairing."
        )
        render(
            "hop.html.j2", f"/hops/{h['slug']}/",
            nav="hops", hop=h, high_yeasts=high_yeasts,
            page_title=f"{h['name']} hops: aroma, oil composition, thiol potential{crop} | Hoparoma",
            page_description=desc[:300],
            jsonld=graph(
                breadcrumb_ld(base, [("Home", "/"), ("Hops", "/hops/"), (h["name"], f"/hops/{h['slug']}/")]),
                dataset_ld(base, f"/hops/{h['slug']}/", f"{h['name']} hop variety data", desc[:300], [h["name"], "hops", "hop aroma", "thiols"], cfg, meta),
            ),
        )

    # yeast ---------------------------------------------------------------------
    render(
        "yeast_index.html.j2", "/yeast/",
        nav="yeast", yeast=yeast, thiol_hops=thiol_hops, og_type="website",
        page_title="Yeast strains rated for thiol release (β-lyase activity) | Hoparoma",
        page_description=f"{len(yeast)} brewing yeast strains rated low, medium or high for thiol biotransformation, with temperature, attenuation, availability and the literature behind each rating.",
        jsonld=graph(
            breadcrumb_ld(base, [("Home", "/"), ("Yeast", "/yeast/")]),
            dataset_ld(base, "/yeast/", "Hoparoma yeast thiol-release reference", "Brewing yeast strains rated for β-lyase thiol release, with fermentation ranges and availability.", ["yeast", "biotransformation", "thiols", "beta-lyase", "hazy IPA"], cfg, meta),
        ),
    )
    for y in yeast:
        if not y["has_page"]:
            continue
        render(
            "yeast.html.j2", f"/yeast/{y['slug']}/",
            nav="yeast", y=y, thiol_hops=thiol_hops,
            page_title=f"{y['display_name']}: thiol release rating and evidence | Hoparoma",
            page_description=(y["notes"]["summary"] + f" Rated {y['biotransformation_level']} for β-lyase activity in Hoparoma, with manufacturer and literature evidence.")[:300],
            jsonld=graph(breadcrumb_ld(base, [("Home", "/"), ("Yeast", "/yeast/"), (y["display_name"], f"/yeast/{y['slug']}/")])),
        )

    # malt ----------------------------------------------------------------------
    render(
        "malt.html.j2", "/malt/thiol-precursors/",
        nav="malt", malt=malt, og_type="website",
        page_title="Malt thiol precursors: which grains carry them | Hoparoma",
        page_description=f"{len(malt)} malts and grains rated for bound 3MH thiol precursor content, with the peer-reviewed measurements behind the scale. Pale barley carries them; roast destroys them; wheat, rye and oats carry little.",
        jsonld=graph(
            breadcrumb_ld(base, [("Home", "/"), ("Malt", "/malt/thiol-precursors/")]),
            dataset_ld(base, "/malt/thiol-precursors/", "Hoparoma malt thiol precursor reference", "Malts and grains rated for thiol precursor content, with colour and category.", ["malt", "thiol precursors", "3MH", "brewing"], cfg, meta),
        ),
    )

    # sources / 404 ---------------------------------------------------------------
    render(
        "sources.html.j2", "/sources/",
        nav="sources", sources=sources, og_type="website",
        page_title="Sources behind Hoparoma's hop, yeast and malt data | Hoparoma",
        page_description="Peer-reviewed papers, manufacturer disclosures and hop supplier data used by Hoparoma's reference tables and aroma model, with links.",
        jsonld=graph(breadcrumb_ld(base, [("Home", "/"), ("Sources", "/sources/")])),
    )
    render(
        "404.html.j2", "/404.html",
        nav="", noindex=True, og_type="website",
        page_title="Page not found | Hoparoma",
        page_description="The page you were looking for is not here.",
    )

    # sitemap / robots ------------------------------------------------------------
    urls = STATIC_PAGES + [p for p in written if p != "/404.html"]
    sitemap = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u in urls:
        sitemap.append(f"  <url><loc>{base}{u}</loc><lastmod>{meta['generated_at']}</lastmod></url>")
    sitemap.append("</urlset>")
    (SITE_ROOT / "sitemap.xml").write_text("\n".join(sitemap) + "\n", encoding="utf-8")
    (SITE_ROOT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {base}/sitemap.xml\n", encoding="utf-8")

    n_hop_pages = sum(1 for p in written if p.startswith("/hops/") and p != "/hops/")
    n_yeast_pages = sum(1 for p in written if p.startswith("/yeast/") and p != "/yeast/")
    print(f"[build] wrote {len(written)} pages: hop pages={n_hop_pages} yeast pages={n_yeast_pages} + indexes, malt, sources, 404; sitemap urls={len(urls)}")
    if not cfg.get("analytics_id"):
        print("[build] note: analytics_id is empty, no GA4 tag emitted")


if __name__ == "__main__":
    sys.exit(main())
