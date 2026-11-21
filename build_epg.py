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
from urllib.parse import urlsplit
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
UA = "Mozilla/5.0 (compatible; TruFan-IPTV-Guide/1.0)"
QUALITY = re.compile(r"\s+(?:hd|fhd|uhd|4k|full\s+hd|sd)$", re.I)


def normalize(value):
    text = unicodedata.normalize("NFKC", value or "").casefold()
    text = text.replace("ё", "е").replace("&", "и")
    text = re.sub(r"[^\w]+", " ", text, flags=re.UNICODE).strip()
    return QUALITY.sub("", text).strip()


def own_id(channel):
    return "rtv." + channel["rutube_id"]


class PrefixReader:
    """Allow a short magic-header read without buffering a huge XMLTV file."""
    def __init__(self, prefix, source):
        self.prefix = prefix
        self.source = source
        self.bytes_read = 0

    def read(self, size=-1):
        if size < 0:
            size = 65536
        head = self.prefix[:size]
        self.prefix = self.prefix[len(head):]
        body = self.source.read(size - len(head)) if len(head) < size else b""
        self.bytes_read += len(head) + len(body)
        if self.bytes_read > 350_000_000:
            raise ValueError("EPG download exceeds 350 MB")
        return head + body


def parse_url(url, channels, utc_date):
    request = Request(url, headers={
        "User-Agent": UA,
        "Accept": "application/xml,application/gzip,*/*"
    })
    with urlopen(request, timeout=70) as response:
        head = response.read(2)
        stream = PrefixReader(head, response)
        if head == b"\x1f\x8b":
            with gzip.GzipFile(fileobj=stream) as xml:
                return parse_provider(xml, channels, utc_date)
        if head not in (b"<?", b"<t", b"\xef\xbb"):
            raise ValueError("Unexpected XMLTV response header")
        return parse_provider(stream, channels, utc_date)


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
    found_icons = {}
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
            target = selected_source_ids.get(cid)
            if target:
                for ico in el.findall("icon"):
                    address = (ico.get("src") or "").strip()
                    parsed = urlsplit(address)
                    if (parsed.scheme == "https" and parsed.hostname
                            and not parsed.username and len(address) < 1000):
                        found_icons[target] = address
                        break
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
    return found_programmes, total_channels, found_icons


def main():
    channels = json.loads(CATALOG.read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc)
    combined = {}
    logos = {}
    sources = {}
    errors = []
    for label, mirrors in FEEDS:
        for url in mirrors:
            try:
                programmes, count, feed_icons = parse_url(url, channels, now.date())
                if count < 50:
                    raise ValueError("Too few channels in provider XMLTV")
                for cid, image_url in feed_icons.items():
                    logos.setdefault(cid, image_url)
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
        if ident in logos:
            ET.SubElement(el, "icon", {"src": logos[ident]})
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
    # Publish both XMLTV transports: plain XML maximizes TV-player compatibility.
    Path("docs/guide.xml").write_bytes(document)
    OUTPUT.write_bytes(gzip.compress(document, compresslevel=8, mtime=0))
    # Embed logos in each M3U entry as well as XMLTV channel metadata.
    updated_playlists = {}
    for filename in ("docs/direct.m3u", "docs/verified.m3u"):
        filename_path = Path(filename)
        raw_lines = filename_path.read_text(encoding="utf-8").splitlines()
        count = 0
        for idx, line in enumerate(raw_lines):
            if not line.startswith("#EXTINF:") or "tvg-logo=" in line:
                continue
            found = re.search(r'tvg-id="(rtv\.[0-9a-f]{32})"', line)
            logo_url = logos.get(found.group(1)) if found else None
            if logo_url:
                before, sep, after = line.partition(",")
                if sep:
                    raw_lines[idx] = before + ' tvg-logo="' + logo_url + '",' + after
                    count += 1
        if count:
            filename_path.write_text("\n".join(raw_lines) + "\n", encoding="utf-8")
        updated_playlists[filename] = count
    report = {
        "updated_at": now.isoformat(),
        "catalog_channels": len(channels),
        "guide_channels": len(combined),
        "programmes": len(parsed.findall("programme")),
        "provider_logo_count": len(logos),
        "logos_added_to_m3u": updated_playlists,
        "compressed_bytes": OUTPUT.stat().st_size,
        "uncompressed_bytes": Path("docs/guide.xml").stat().st_size,
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
