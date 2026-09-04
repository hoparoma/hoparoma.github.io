#!/usr/bin/env python3
"""Pre-deploy gate for hoparoma-site. Exit 0 PASS / 1 WARN / 2 BLOCK.

Checks (design §3 "gate 化"):
  B1  forbidden claims / phrases (honest-positioning constitution)
  B2  engine-internal column names must not appear in HTML or published JSON
  B3  yeast pages must not leak the internal coefficient values
  B4  internal links resolve to a file
  B5  generated pages carry title, meta description, canonical
  W2  sitemap entries exist / generated pages are listed
  W3  sources.json entries not VERIFIED
  W4  placeholder text (TODO / TBD / lorem / PENDING) in HTML
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

SITE_ROOT = Path(__file__).resolve().parent.parent
CACHE = SITE_ROOT / "tools" / ".cache" / "forbidden_values.json"
GENERATED_DIRS = ["hops", "yeast", "malt", "sources"]

FORBIDDEN_PHRASES = [
    "first ios app", "first brewing app", "the first to ", "the first app",
    "predicts what your beer will smell like", "internal median", "internal medians",
    "auditable in-app", "know how it will turn out", "see your beer before",
]
FORBIDDEN_COLUMNS = [
    "thiol_3mh_median", "thiol_4mmp_median", "sulfur_proxy",
    "thiol_boost", "conversion_rate", "mha_multiplier", "bioT_sensitivity",
    "thiol_biotransformation_activity", "myrcene_factor", "linalool_factor",
    "geraniol_factor", "ester_level",
]
PLACEHOLDER = re.compile(r"\b(TODO|TBD|PENDING)\b|lorem ipsum")
DECIMAL = r"(?<![\d.])({v})(?![\d])"


def html_files() -> list[Path]:
    files = list(SITE_ROOT.glob("*.html"))
    for d in GENERATED_DIRS:
        files += list((SITE_ROOT / d).rglob("*.html"))
    return sorted(f for f in files if "_archive" not in f.parts and "stitch" not in str(f))


def generated_files() -> list[Path]:
    out = []
    for d in GENERATED_DIRS:
        out += list((SITE_ROOT / d).rglob("*.html"))
    return sorted(out)


def resolve_link(href: str) -> bool:
    path = urlsplit(href).path
    if not path.startswith("/"):
        return True  # relative links are checked by the browser; external ones are out of scope
    target = SITE_ROOT / path.lstrip("/")
    if path.endswith("/"):
        return (target / "index.html").exists()
    return target.exists() or (target / "index.html").exists()


def main() -> int:
    blocks: list[str] = []
    warns: list[str] = []
    forb = json.loads(CACHE.read_text()) if CACHE.exists() else {"hops": {}, "yeast": {}}

    files = html_files()
    gen = set(generated_files())
    for f in files:
        rel = f.relative_to(SITE_ROOT).as_posix()
        text = f.read_text(encoding="utf-8")
        low = text.lower()

        for p in FORBIDDEN_PHRASES:
            if p in low:
                blocks.append(f"B1 {rel}: forbidden phrase '{p}'")
        for c in FORBIDDEN_COLUMNS:
            if c in text:
                blocks.append(f"B2 {rel}: internal column name '{c}'")
        if PLACEHOLDER.search(text):
            warns.append(f"W4 {rel}: placeholder text present")

        for href in re.findall(r'href="([^"]+)"', text):
            if href.startswith(("http", "mailto:", "#", "tel:")) or href.startswith("//"):
                continue
            if not resolve_link(href):
                blocks.append(f"B4 {rel}: broken internal link {href}")

        if f in gen:
            if "<title>" not in text:
                blocks.append(f"B5 {rel}: missing <title>")
            if 'name="description"' not in text:
                blocks.append(f"B5 {rel}: missing meta description")
            if 'rel="canonical"' not in text:
                blocks.append(f"B5 {rel}: missing canonical")

        # numeric leak check (yeast coefficients are decimals such as 0.85 / 1.30; integers are skipped
        # because they collide with temperatures and page numbers). Hop medians are not checked here:
        # their values collide with oil fractions, so the structural drop in extract_data.py is the guarantee.
        if rel.startswith("yeast/") and rel != "yeast/index.html":
            slug = rel.split("/")[1]
            for yid, vals in forb["yeast"].items():
                if re.sub(r"[^a-z0-9]+", "-", yid.lower()).strip("-") != slug:
                    continue
                for col, v in vals.items():
                    if col in ("segment_main", "tier") or "." not in v:
                        continue
                    if re.search(DECIMAL.format(v=re.escape(v)), text):
                        blocks.append(f"B3 {rel}: coefficient value {v} ({col}) appears in page")

    # published JSON must not carry internal columns
    for j in (SITE_ROOT / "data").glob("*.json"):
        t = j.read_text(encoding="utf-8")
        for c in FORBIDDEN_COLUMNS:
            if c in t:
                blocks.append(f"B2 data/{j.name}: internal column name '{c}'")

    # sitemap
    sm = SITE_ROOT / "sitemap.xml"
    if sm.exists():
        locs = re.findall(r"<loc>([^<]+)</loc>", sm.read_text())
        for loc in locs:
            if not resolve_link(urlsplit(loc).path):
                warns.append(f"W2 sitemap: {loc} does not resolve to a file")
        listed = {urlsplit(l).path for l in locs}
        for g in gen:
            p = "/" + g.relative_to(SITE_ROOT).as_posix()
            p = p[: -len("index.html")] if p.endswith("index.html") else p
            if p not in listed:
                warns.append(f"W2 sitemap: generated page {p} not listed")
    else:
        warns.append("W2 sitemap.xml missing")

    # sources status
    src = json.loads((SITE_ROOT / "data" / "sources.json").read_text())
    unverified = [s["id"] for g in src["groups"] for s in g["items"] if s.get("status") != "VERIFIED"]
    if unverified:
        warns.append(f"W3 sources not VERIFIED ({len(unverified)}): {', '.join(unverified)}")

    print(f"[gate] files checked: {len(files)}")
    for b in blocks:
        print("BLOCK", b)
    for w in warns:
        print("WARN ", w)
    if blocks:
        print(f"[gate] RESULT: BLOCK ({len(blocks)} blocking, {len(warns)} warnings)")
        return 2
    if warns:
        print(f"[gate] RESULT: WARN ({len(warns)} warnings)")
        return 1
    print("[gate] RESULT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
