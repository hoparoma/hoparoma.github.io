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
  W5  a file the site references (link, image, script, sitemap entry, IndexNow key) is not tracked by git,
      so a selective `git add` would ship a broken page
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

SITE_ROOT = Path(__file__).resolve().parent.parent
CACHE = SITE_ROOT / "tools" / ".cache" / "forbidden_values.json"
GENERATED_DIRS = ["hops", "yeast", "malt", "sources", "calculator"]

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


class RefCollector(HTMLParser):
    """href / src / content attribute values, whatever the quoting style."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.refs: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if value and name in ("href", "src", "content"):
                self.refs.append((name, value.strip()))


def resolve_file(href: str, referrer: Path | None = None) -> Path | None:
    """Local file a site URL points at, or None when it does not resolve.

    Root-relative paths resolve against the site root; relative paths against the referring file.
    """
    path = unquote(urlsplit(href).path)
    if path.startswith("/") or referrer is None:
        target = SITE_ROOT / path.lstrip("/")
    else:
        target = referrer.parent / path
    target = target.resolve()
    if SITE_ROOT not in target.parents and target != SITE_ROOT:
        return None  # points outside the site
    if path.endswith("/") or target.is_dir():
        target = target / "index.html"
    return target if target.is_file() else None


def local_ref(name: str, value: str, base: str) -> str | None:
    """The site-local URL inside an attribute value, or None when the value is external or not a URL."""
    if name == "content" and (not value.startswith(("/", "http://", "https://")) or any(c.isspace() for c in value)):
        return None  # meta content is free text; only a complete URL or a bare root-relative path is a reference
    try:
        parts = urlsplit(value)
        own_host = urlsplit(base).netloc.lower()
    except ValueError:
        return None
    if parts.netloc:  # absolute or protocol-relative: ours only when the host matches
        if parts.scheme not in ("", "http", "https") or parts.netloc.lower() != own_host:
            return None
        return parts.path or "/"
    if parts.scheme or not parts.path:
        return None  # mailto:, tel:, data:, javascript:, fragment-only, query-only
    return value


def resolve_link(href: str) -> bool:
    return resolve_file(href) is not None


def tracked_files() -> set[str] | None:
    try:
        out = subprocess.run(["git", "-C", str(SITE_ROOT), "ls-files"], capture_output=True, text=True, check=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None  # not a git checkout: skip W5
    return set(out.stdout.splitlines())


def main() -> int:
    blocks: list[str] = []
    warns: list[str] = []
    forb = json.loads(CACHE.read_text()) if CACHE.exists() else {"hops": {}, "yeast": {}}

    cfg = json.loads((SITE_ROOT / "tools" / "site_config.json").read_text(encoding="utf-8"))
    base = cfg["base_url"].rstrip("/")

    files = html_files()
    gen = set(generated_files())
    referenced: set[Path] = set(files)
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

        collector = RefCollector()
        collector.feed(text)
        for name, value in collector.refs:  # root-relative, relative, and absolute URLs to this site
            href = local_ref(name, value, base)
            if href is None:
                continue
            target = resolve_file(href, referrer=f)
            if target is None:
                blocks.append(f"B4 {rel}: broken internal link {value}")
            else:
                referenced.add(target)

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
            else:
                referenced.add(resolve_file(urlsplit(loc).path))
        listed = {urlsplit(l).path for l in locs}
        for g in gen:
            p = "/" + g.relative_to(SITE_ROOT).as_posix()
            p = p[: -len("index.html")] if p.endswith("index.html") else p
            if p not in listed:
                warns.append(f"W2 sitemap: generated page {p} not listed")
    else:
        warns.append("W2 sitemap.xml missing")

    # IndexNow key file
    key = cfg.get("indexnow_key")
    if key:
        key_file = SITE_ROOT / f"{key}.txt"
        if not key_file.is_file() or key_file.read_text(encoding="utf-8").strip() != key:
            blocks.append(f"B4 {key}.txt: IndexNow key file is missing or does not contain the key")
        else:
            referenced.add(key_file)

    # everything the site points at should be in git
    tracked = tracked_files()
    if tracked is not None:
        for f in sorted(referenced):
            rel_path = f.relative_to(SITE_ROOT).as_posix()
            if rel_path not in tracked:
                warns.append(f"W5 not tracked by git: {rel_path}")

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
