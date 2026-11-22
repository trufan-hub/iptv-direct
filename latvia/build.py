#!/usr/bin/env python3
"""Build a standalone, self-updating Latvian IPTV playlist and narrowed XMLTV EPG.

This does not modify the existing direct.m3u or Rutube playlist. Only
individually verified/direct broadcast stream candidates are in the catalog.
"""
from __future__ import annotations

import concurrent.futures
import gzip
import io
import json
import re
import unicodedata
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

CATALOG = Path("latvia/channels.json")
PLAYLIST = Path("docs/latvia.m3u")
GUIDE = Path("docs/latvia-guide.xml")
GUIDE_GZIP = Path("docs/latvia-guide.xml.gz")
REPORT = Path("docs/latvia-report.json")
LOGOS = Path("docs/latvia-logos.json")
EPG_SRC = "https://epgshare01.online/epgshare01/epg_ripper_LV1.xml.gz"
EPG_URL = "https://trufan-hub.github.io/iptv-direct/latvia-guide.xml"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"


def safe_https(url):
    if not isinstance(url, str) or len(url) > 1200:
        return False
    try:
        p = urlsplit(url)
        return p.scheme == "https" and bool(p.hostname) and not p.username
    except ValueError:
        return False


def canonical(text):
    return re.sub(
        r"[^a-z0-9а-яё]+", "",
        unicodedata.normalize("NFKC", text or "").casefold()
    ).replace("ё", "е")


def existing_streams():
    saved = {}
    if not PLAYLIST.exists():
        return saved
    current = None
    for line in PLAYLIST.read_text(encoding="utf-8-sig").splitlines():
        if line.startswith("#EXTINF"):
            m = re.search(r'tvg-id="([^"]+)"', line)
            current = m.group(1) if m else None
        elif current and line.startswith("https://"):
            saved[current] = line.strip()
            current = None
    return saved


def check_hls(url):
    if not safe_https(url):
        return False, "invalid_url"
    try:
        request = Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
        with urlopen(request, timeout=14) as response:
            content = response.read(4096)
            status = response.status
        return content.lstrip(b"\xef\xbb\xbf \r\n").startswith(b"#EXTM3U"), "HTTP " + str(status)
    except HTTPError as err:
        return False, "HTTP " + str(err.code)
    except (OSError, ValueError, URLError) as err:
        return False, type(err).__name__


def pick_stream(channel, previous):
    urls = list(channel["streams"])
    previous_url = previous.get(channel["id"])
    if previous_url and previous_url not in urls and safe_https(previous_url):
        urls.append(previous_url)
    checked = []
    for url in urls:
        passed, note = check_hls(url)
        checked.append({"url": url, "verified": passed, "status": note})
        if passed:
            return channel["id"], url, True, checked
    # Preserve the last selected stream if GitHub runner is blocked.
    return channel["id"], previous_url or urls[0], False, checked


def read_logo_registry():
    if not LOGOS.exists():
        return {}
    stored = json.loads(LOGOS.read_text(encoding="utf-8"))
    if not isinstance(stored, dict):
        raise ValueError("Broken logo registry")
    if any(not safe_https(link) for link in stored.values()):
        raise ValueError("Broken logo URL in registry")
    return stored


def fetch_guide(channels, logos, now):
    request = Request(EPG_SRC, headers={
        "User-Agent": UA, "Accept": "application/gzip,application/xml,*/*"
    })
    with urlopen(request, timeout=35) as response:
        header = response.read(2)
        # The Latvian EPG archive is a small country-scoped feed.
        compressed = header + response.read(8_000_001)
        if len(compressed) > 8_000_000:
            raise RuntimeError("EPG compressed source exceeded 8 MB")
    if compressed[:2] == b"\x1f\x8b":
        stream = gzip.GzipFile(fileobj=io.BytesIO(compressed))
    elif compressed.lstrip().startswith(b"<"):
        stream = io.BytesIO(compressed)
    else:
        raise RuntimeError("Unexpected EPG format")

    by_provider_id = {
        c["epg_id"]: c for c in channels if c.get("epg_id")
    }
    by_label = {canonical(c["name"]): c for c in channels}
    mapped = {}
    programmes = defaultdict(list)
    early = (now.date() - timedelta(days=1)).strftime("%Y%m%d")
    late = (now.date() + timedelta(days=6)).strftime("%Y%m%d")
    total_source = 0
    with stream:
        iterator = ET.iterparse(stream, events=("start", "end"))
        event, root = next(iterator)
        if event != "start" or root.tag != "tv":
            raise RuntimeError("XMLTV root missing")
        for event, element in iterator:
            if event != "end":
                continue
            if element.tag == "channel":
                total_source += 1
                provider_id = element.get("id") or ""
                candidate = by_provider_id.get(provider_id)
                if not candidate:
                    found = set()
                    for tag in element.findall("display-name"):
                        match = by_label.get(canonical(tag.text or ""))
                        if match:
                            found.add(match["id"])
                    if len(found) == 1:
                        candidate = next(c for c in channels if c["id"] in found)
                if candidate:
                    mapped[provider_id] = candidate["id"]
                    for icon in element.findall("icon"):
                        source_logo = (icon.get("src") or "").strip()
                        if safe_https(source_logo):
                            logos.setdefault(candidate["id"], source_logo)
                            break
                element.clear()
                root.clear()
            elif element.tag == "programme":
                src_id = element.get("channel", "")
                local_id = mapped.get(src_id)
                start = (element.get("start") or "").strip()
                stop = (element.get("stop") or "").strip()
                title_node = element.find("title")
                title = (title_node.text or "").strip() if title_node is not None else ""
                if local_id and early <= start[:8] <= late and start and stop and title:
                    def field(tag, maximum):
                        e = element.find(tag)
                        if e is None:
                            return "", ""
                        value = re.sub(r"\s+", " ", "".join(e.itertext())).strip()
                        return value[:maximum], e.get("lang") or "lv"
                    synopsis, synopsis_lang = field("desc", 5000)
                    subtitle, subtitle_lang = field("sub-title", 250)
                    categories = []
                    for cat in element.findall("category")[:5]:
                        value = re.sub(r"\s+", " ", "".join(cat.itertext())).strip()[:100]
                        if value:
                            categories.append((value, cat.get("lang") or "lv"))
                    programmes[local_id].append((
                        start, stop, title[:500],
                        title_node.get("lang") or "lv", synopsis, synopsis_lang,
                        subtitle, subtitle_lang, categories
                    ))
                element.clear()
                root.clear()
    if total_source < 30:
        raise RuntimeError("EPG source contains too few channels")
    if sum(map(len, programmes.values())) < 30 or len(programmes) < 3:
        raise RuntimeError("EPG source does not cover enough Latvian channels")
    return programmes, mapped, total_source


def main():
    now = datetime.now(timezone.utc)
    channels = json.loads(CATALOG.read_text(encoding="utf-8"))
    if len(channels) < 5:
        raise ValueError("Latvia catalogue unexpectedly small")
    ids = set()
    for channel in channels:
        ident = channel.get("id")
        if not isinstance(ident, str) or not re.fullmatch(r"lv\.[a-z0-9]+", ident):
            raise ValueError("Invalid Latvian channel ID")
        if ident in ids or not channel.get("name") or not channel.get("streams"):
            raise ValueError("Duplicate or missing channel")
        ids.add(ident)
        if any(not safe_https(url) for url in channel["streams"]):
            raise ValueError("Invalid channel stream URL")

    old_report = {}
    if REPORT.exists():
        old_report = json.loads(REPORT.read_text(encoding="utf-8"))
    previous = existing_streams()
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        checks = list(executor.map(lambda c: pick_stream(c, previous), channels))
    checked = {entry[0]: entry for entry in checks}
    ok = sum(entry[2] for entry in checks)
    if ok < 3:
        raise RuntimeError("Fewer than three HLS manifests verified; preserve prior release")
    logos = read_logo_registry()
    for channel in channels:
        if safe_https(channel.get("logo")):
            logos.setdefault(channel["id"], channel["logo"])
    programmes, matched, upstream_count = fetch_guide(channels, logos, now)
    programme_count = sum(len(items) for items in programmes.values())
    description_count = sum(bool(e[4]) for entries in programmes.values() for e in entries)

    # Prevent major loss of previously delivered programme synopsis coverage.
    prior_channels = int(old_report.get("guide_channels", 0))
    prior_synopses = int(old_report.get("descriptions", 0))
    if prior_channels >= 3 and len(programmes) < prior_channels * .8:
        raise RuntimeError("EPG channel coverage regressed; preserving previous release")
    if prior_synopses >= 20 and description_count < prior_synopses * .4:
        raise RuntimeError("EPG description coverage regressed; preserving previous release")

    guide = ET.Element("tv", {
        "generator-info-name": "TruFan Latvia IPTV",
        "generator-info-url": "https://github.com/trufan-hub/iptv-direct"
    })
    for channel in channels:
        node = ET.SubElement(guide, "channel", {"id": channel["id"]})
        ET.SubElement(node, "display-name", {"lang": "lv"}).text = channel["name"]
        if channel["id"] in logos:
            ET.SubElement(node, "icon", {"src": logos[channel["id"]]})
    for channel in channels:
        seen = set()
        for (start, stop, title, language, desc, desc_lang,
             subtitle, sub_lang, categories) in sorted(
                programmes.get(channel["id"], []), key=lambda item: item[0]):
            key = start, stop, title
            if key in seen:
                continue
            seen.add(key)
            node = ET.SubElement(guide, "programme", {
                "channel": channel["id"], "start": start, "stop": stop
            })
            ET.SubElement(node, "title", {"lang": language}).text = title
            if subtitle:
                ET.SubElement(node, "sub-title", {"lang": sub_lang}).text = subtitle
            if desc:
                ET.SubElement(node, "desc", {"lang": desc_lang}).text = desc
            for category, lang in categories:
                ET.SubElement(node, "category", {"lang": lang}).text = category

    playlist = [f'#EXTM3U url-tvg="{EPG_URL}"',
                "# TruFan Latvia IPTV; independently updated; official and public HLS"]
    for channel in channels:
        attrs = [
            f'tvg-id="{channel["id"]}"',
            f'tvg-name="{escape(channel["name"], quote=True)}"',
            f'group-title="{escape(channel["group"], quote=True)}"'
        ]
        if channel["id"] in logos:
            attrs.append(f'tvg-logo="{escape(logos[channel["id"]], quote=True)}"')
        playlist.extend([
            "#EXTINF:-1 " + " ".join(attrs) + "," + channel["name"],
            checked[channel["id"]][1]
        ])

    xml = ET.tostring(guide, encoding="utf-8", xml_declaration=True)
    root = ET.fromstring(xml)
    actual = root.findall("programme")
    if len(actual) < 30 or len(root.findall("channel")) != len(channels):
        raise RuntimeError("Generated guide failed XMLTV validation")
    if set(x.get("channel") for x in actual) - ids:
        raise RuntimeError("Unknown XMLTV channel ID")
    report = {
        "generated_utc": now.isoformat(),
        "catalog_channels": len(channels),
        "verified_manifests": ok,
        "guide_channels": sum(bool(programmes.get(c["id"])) for c in channels),
        "programmes": len(actual),
        "descriptions": sum(bool(item.findtext("desc")) for item in actual),
        "source_epg": EPG_SRC,
        "source_epg_channels": upstream_count,
        "known_logo_count": len(logos),
        "channels": [
            {"id": c["id"], "name": c["name"], "verified": checked[c["id"]][2],
             "probe": checked[c["id"]][3],
             "epg_programmes": len(programmes.get(c["id"], []))}
            for c in channels
        ]
    }
    PLAYLIST.parent.mkdir(parents=True, exist_ok=True)
    PLAYLIST.write_text("\n".join(playlist) + "\n", encoding="utf-8")
    GUIDE.write_bytes(xml)
    GUIDE_GZIP.write_bytes(gzip.compress(xml, compresslevel=8, mtime=0))
    LOGOS.write_text(json.dumps(logos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        k:v for k,v in report.items() if k != "channels"
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
