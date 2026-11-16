#!/usr/bin/env python3
"""Build a playlist-specific XMLTV guide published by this repository.

Only programme start/end times and titles are retained from public EPG feeds.
No EPG data is fabricated. An invalid or empty guide fails the workflow
before publication, preserving the last successful GitHub Pages deployment.
"""
from __future__ import annotations

import gzip
import io
import json
import re
import unicodedata
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

CATALOG = Path("channels.json")
OUTPUT = Path("docs/guide.xml.gz")
STATUS = Path("docs/epg_status.json")
FEEDS = (
    ("IPTVX", ("https://iptvx.one/EPG",
                "https://iptvx.one/epg/epg.xml.gz")),
    ("EPG.ONE", ("https://epg.one/epg2.xml.gz",
                  "http://epg.one/epg2.xml.gz")),
)
MAX_DOWNLOAD = 45_000_000
UA = "Mozilla/5.0 (compatible; TruFan-IPTV-Guide/1.0)"
QUALITY = re.compile(r"\s+(?:hd|fhd|uhd|4k|full\s+hd|sd)$", re.I)


def normalize(value):
    text = unicodedata.normalize("NFKC", value or "").casefold()
    text = text.replace("ё", "е").replace("&", "и")
    text = re.sub(r"[^\w]+", " ", text, flags=re.UNICODE).strip()
    return QUALITY.sub("", text).strip()


def own_id(channel):
    return "rtv." + channel["rutube_id"]


def fetch_feed(url):
    request = Request(url, headers={
        "User-Agent": UA,
        "Accept": "application/xml,application/gzip,*/*"
    })
    with urlopen(request, timeout=50) as response:
        raw = response.read(MAX_DOWNLOAD + 1)
    if len(raw) > MAX_DOWNLOAD:
        raise ValueError("Guide download exceeds safety limit")
    if raw.startswith(b"\x1f\x8b"):
        return gzip.GzipFile(fileobj=io.BytesIO(raw))
    if raw.lstrip().startswith(b"<"):
        return io.BytesIO(raw)
    raise ValueError("Not an XMLTV or gzip document")


def parse_provider(stream, channels, utc_date):
    """Read XMLTV incrementally; retain only matched channels and programmes."""
    by_epg = defaultdict(list)
    by_name = defaultdict(list)
    for ch in channels:
        if ch.get("tvg_id"):
            by_epg[ch["tvg_id"]].append(ch)
        by_name[normalize(ch["name"])].append(ch)

    start_day = (utc_date - timedelta(days=1)).strftime("%Y%m%d")
    end_day = (utc_date + timedelta(days=4)).strftime("%Y%m%d")
    selected_source_ids = {}
    found_programmes = defaultdict(list)
    total_channels = 0
    context = ET.iterparse(stream, events=("start", "end"))
    event, root = next(context)
    if event != "start" or root.tag != "tv":
        raise ValueError("Not an XMLTV <tv> root")
    for event, el in context:
        if event != "end":
            continue
        if el.tag == "channel":
            total_channels += 1
            cid = (el.get("id") or "").strip()
            direct = by_epg.get(cid, [])
            if len(direct) == 1:
                selected_source_ids[cid] = own_id(direct[0])
            elif cid:
                candidates = {}
                for tag in el.findall("display-name"):
                    for ch in by_name.get(normalize(tag.text), []):
                        candidates[own_id(ch)] = ch
                if len(candidates) == 1:
                    selected_source_ids[cid] = next(iter(candidates))
            el.clear()
            root.clear()
        elif el.tag == "programme":
            cid = (el.get("channel") or "").strip()
            target = selected_source_ids.get(cid)
            beginning = (el.get("start") or "").strip()
            finish = (el.get("stop") or "").strip()
            if target and start_day <= beginning[:8] <= end_day and finish:
                node = el.find("title")
                name = ("".join(node.itertext()).strip()
                        if node is not None else "")
                if name and len(name) <= 500:
                    found_programmes[target].append(
                        (beginning, finish, name, node.get("lang") or "")
                    )
            el.clear()
            root.clear()
    return found_programmes, total_channels


def main():
    channels = json.loads(CATALOG.read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc)
    combined = {}
    sources = {}
    errors = []
    for label, mirrors in FEEDS:
        for url in mirrors:
            try:
                with fetch_feed(url) as stream:
                    programmes, count = parse_provider(stream, channels, now.date())
                if count < 50:
                    raise ValueError("Too few channels in provider XMLTV")
                added = 0
                for cid, entries in programmes.items():
                    if cid not in combined and entries:
                        combined[cid] = entries
                        added += 1
                sources[label] = {
                    "url": url, "source_channels": count,
                    "matched_channels": len(programmes),
                    "new_channels": added
                }
                print(label + ": " + json.dumps(sources[label]))
                break
            except (OSError, ValueError, ET.ParseError, EOFError,
                    HTTPError, URLError) as exc:
                error = f"{label} {url}: {type(exc).__name__}: {exc}"
                errors.append(error)
                print("WARNING: " + error)
    total_events = sum(len(p) for p in combined.values())
    if len(combined) < 20 or total_events < 100:
        raise RuntimeError(
            f"Refusing to publish insufficient guide: "
            f"{len(combined)} channels / {total_events} programmes. "
            + " | ".join(errors)
        )

    tv = ET.Element("tv", {
        "generator-info-name": "TruFan IPTV Direct",
        "generator-info-url": "https://github.com/trufan-hub/iptv-direct"
    })
    for channel in channels:
        ident = own_id(channel)
        el = ET.SubElement(tv, "channel", {"id": ident})
        name = ET.SubElement(el, "display-name", {"lang": "ru"})
        name.text = channel["name"]
    for cid, entries in combined.items():
        seen = set()
        for start, stop, title, lang in sorted(entries):
            key = (start, stop, title)
            if key in seen:
                continue
            seen.add(key)
            el = ET.SubElement(tv, "programme", {
                "start": start, "stop": stop, "channel": cid
            })
            title_el = ET.SubElement(
                el, "title", {"lang": lang or "ru"}
            )
            title_el.text = title
    document = ET.tostring(tv, encoding="utf-8", xml_declaration=True)
    # Validate the exact bytes which will be served as XMLTV.
    parsed = ET.fromstring(document)
    if parsed.tag != "tv" or len(parsed.findall("programme")) < 100:
        raise RuntimeError("Generated XMLTV failed validation")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes(gzip.compress(document, compresslevel=8, mtime=0))
    report = {
        "updated_at": now.isoformat(),
        "catalog_channels": len(channels),
        "guide_channels": len(combined),
        "programmes": len(parsed.findall("programme")),
        "compressed_bytes": OUTPUT.stat().st_size,
        "feeds": sources,
        "warnings": errors,
    }
    STATUS.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
