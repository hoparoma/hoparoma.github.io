#!/usr/bin/env python3
"""Tell IndexNow which URLs changed (Bing and the engines that share its feed; ChatGPT search reads Bing's index).

Run AFTER the push is live: the engines fetch https://<host>/<key>.txt to verify ownership.
The default is a dry run.

  python3 tools/indexnow_ping.py                               # print what would be sent
  python3 tools/indexnow_ping.py --send                        # submit every sitemap URL
  python3 tools/indexnow_ping.py --send /calculator/ /hops/    # submit selected paths

Exit 0 accepted or dry run / 1 rejected or not ready.
"""
from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import SplitResult, urlsplit

SITE_ROOT = Path(__file__).resolve().parent.parent
ENDPOINT = "https://api.indexnow.org/indexnow"
MAX_URLS = 10_000  # IndexNow protocol limit per request
USER_AGENT = "hoparoma-site-indexnow/1.0"
TIMEOUT_S = 20


def fetch(url: str, data: bytes | None = None, headers: dict[str, str] | None = None) -> tuple[int, str]:
    req = urllib.request.Request(url, data=data, headers={"User-Agent": USER_AGENT, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as err:
        return err.code, err.read().decode("utf-8", errors="replace")


def read_local(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as err:
        print(f"[indexnow] cannot read {path.relative_to(SITE_ROOT)}: {err.strerror or err}")
        return None


def split_url(url: str) -> SplitResult | None:
    try:
        return urlsplit(url)
    except ValueError:
        return None


def sitemap_locs(xml_text: str) -> list[str] | None:
    """Decoded <loc> values in document order, without duplicates. None when the XML does not parse."""
    try:
        root = ET.fromstring(xml_text)  # our own generated file, not untrusted input
    except ET.ParseError as err:
        print(f"[indexnow] sitemap.xml does not parse: {err}")
        return None
    locs = [(el.text or "").strip() for el in root.iter() if el.tag == "loc" or el.tag.endswith("}loc")]
    return list(dict.fromkeys(u for u in locs if u))


def main(argv: list[str]) -> int:
    send = "--send" in argv
    paths = [a for a in argv if a.startswith("/")]
    unknown = [a for a in argv if a != "--send" and not a.startswith("/")]
    if unknown:
        print(f"[indexnow] unknown argument(s): {' '.join(unknown)}")
        return 1

    cfg_text = read_local(SITE_ROOT / "tools" / "site_config.json")
    if cfg_text is None:
        return 1
    try:
        cfg = json.loads(cfg_text)
        base = str(cfg["base_url"]).rstrip("/")
    except (json.JSONDecodeError, KeyError, TypeError) as err:
        print(f"[indexnow] tools/site_config.json is not usable: {err!r}")
        return 1
    base_parts = split_url(base)
    if base_parts is None or base_parts.scheme != "https" or not base_parts.netloc:
        print(f"[indexnow] base_url must be an https URL, got {base!r}")
        return 1
    host = base_parts.netloc
    key = str(cfg.get("indexnow_key", ""))
    if not re.fullmatch(r"[a-zA-Z0-9-]{8,128}", key):
        print("[indexnow] indexnow_key is missing or malformed in tools/site_config.json")
        return 1
    key_text = read_local(SITE_ROOT / f"{key}.txt")
    if key_text is None:
        return 1
    if key_text.strip() != key:
        print(f"[indexnow] {key}.txt at the site root does not contain the key")
        return 1

    sitemap = read_local(SITE_ROOT / "sitemap.xml")
    if sitemap is None:
        return 1
    listed = sitemap_locs(sitemap)
    if listed is None:
        return 1
    parsed = {u: split_url(u) for u in listed}
    foreign = [u for u, parts in parsed.items() if parts is None or parts.scheme != "https" or parts.netloc != host]
    if foreign:
        print(f"[indexnow] sitemap.xml lists URLs outside https://{host}: {' '.join(foreign[:5])}")
        return 1
    urls = list(dict.fromkeys(base + p for p in paths)) if paths else listed
    not_listed = [u for u in urls if u not in listed]
    if not_listed:
        print(f"[indexnow] not in sitemap.xml: {' '.join(not_listed)}")
        return 1
    if not urls:
        print("[indexnow] nothing to submit: sitemap.xml lists no URLs")
        return 1
    if len(urls) > MAX_URLS:
        print(f"[indexnow] {len(urls)} URLs exceeds the {MAX_URLS} per-request limit; pass paths explicitly")
        return 1

    payload = {
        "host": host,
        "key": key,
        "keyLocation": f"{base}/{key}.txt",
        "urlList": urls,
    }
    print(f"[indexnow] {len(urls)} URL(s), key file {payload['keyLocation']}")
    if not send:
        print("[indexnow] dry run. Re-run with --send after the push is live.")
        return 0

    try:
        status, body = fetch(payload["keyLocation"])
    except OSError as err:  # URLError, timeouts and socket errors
        print(f"[indexnow] could not reach the live key file: {err}")
        return 1
    if status != 200 or body.strip() != key:
        print(f"[indexnow] live key file is not ready (HTTP {status}). Push first, then retry.")
        return 1

    try:
        status, body = fetch(
            ENDPOINT,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"},
        )
    except OSError as err:  # URLError, timeouts and socket errors
        print(f"[indexnow] submit failed: {err}")
        return 1
    if status in (200, 202):
        print(f"[indexnow] accepted (HTTP {status})")
        return 0
    print(f"[indexnow] rejected (HTTP {status}): {body[:300]}")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
