#!/usr/bin/env python3
"""Independent live IPTV resolver. No third-party M3U sources."""
from __future__ import annotations
import concurrent.futures
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

CATALOG = Path("channels.json")
OUTPUT = Path("docs/direct.m3u")
REPORT = Path("docs/report.json")
EPG = "https://iptvx.one/EPG,http://epg.one/epg2.xml.gz"
AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
ID_RE = re.compile(r"^[0-9a-f]{32}$")


def load_options(video_id):
    url = f"https://rutube.ru/api/play/options/{video_id}/?format=json"
    req = Request(url, headers={
        "User-Agent": AGENT, "Accept": "application/json",
        "Referer": f"https://rutube.ru/live/video/{video_id}/",
        "Accept-Language": "ru-RU,ru;q=0.9"
    })
    with urlopen(req, timeout=16) as response:
        raw = response.read(2_000_001)
        if len(raw) > 2_000_000:
            raise ValueError("Oversized API response")
    result = json.loads(raw)
    if not isinstance(result, dict):
        raise ValueError("Unexpected API response")
    return result


def hls_options(data):
    candidates = []
    live = data.get("live_streams") or {}
    if isinstance(live, dict):
        hls = live.get("hls") or []
        for entry in hls if isinstance(hls, list) else [hls]:
            if isinstance(entry, str):
                candidates.append(entry)
            if isinstance(entry, dict):
                candidates.append(entry.get("url"))
    balancer = data.get("video_balancer") or {}
    if isinstance(balancer, dict):
        candidates.append(balancer.get("m3u8"))
        candidates.extend(val for key, val in balancer.items() if "m3u8" in key.lower())
    result = []
    for candidate in candidates:
        if not isinstance(candidate, str):
            continue
        u = urlsplit(candidate)
        if u.scheme == "https" and u.hostname and not u.username and candidate not in result:
            result.append(candidate)
    return result


def probe_manifest(url):
    try:
        req = Request(url, headers={
            "User-Agent": AGENT,
            "Referer": "https://rutube.ru/",
            "Accept": "application/vnd.apple.mpegurl,*/*"
        })
        with urlopen(req, timeout=9) as res:
            content = res.read(4096)
        return "manifest_ok" if content.lstrip().startswith(b"#EXTM3U") else "unexpected_content"
    except (OSError, ValueError) as exc:
        return "unverified:" + type(exc).__name__


def resolve(channel):
    result = {
        "name": channel["name"], "rutube_id": channel["rutube_id"],
        "status": "unavailable", "probe": "not_checked"
    }
    for attempt in range(2):
        try:
            candidates = hls_options(load_options(channel["rutube_id"]))
            if not candidates:
                result["status"] = "no_hls_in_api"
                return result
            result["_hls"] = candidates[0]
            result["status"] = "api_resolved"
            result["probe"] = probe_manifest(candidates[0])
            return result
        except (HTTPError, URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
            result["status"] = "api_error:" + type(exc).__name__
            if attempt == 0:
                time.sleep(1)
    return result


def attr(value):
    return str(value).replace("&", "&amp;").replace('"', "&quot;").replace("\r", " ").replace("\n", " ")


def main():
    channels = json.loads(CATALOG.read_text(encoding="utf-8"))
    if not isinstance(channels, list) or not channels:
        raise ValueError("Empty catalog")
    seen = set()
    for row in channels:
        if not isinstance(row, dict) or not ID_RE.fullmatch(row.get("rutube_id", "")):
            raise ValueError("Invalid Rutube ID in catalog")
        if not row.get("name") or row["rutube_id"] in seen:
            raise ValueError("Unnamed or duplicate channel")
        seen.add(row["rutube_id"])

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(resolve, channels))

    playlist = [f'#EXTM3U url-tvg="{EPG}"',
                "# Independent Rutube playback API source (not Dimonovich)",
                "# Generated UTC: " + datetime.now(timezone.utc).isoformat()]
    count = 0
    for channel, item in zip(channels, results):
        if item["status"] != "api_resolved":
            continue
        meta = (f'tvg-id="{attr(channel.get("tvg_id", ""))}" '
                f'tvg-name="{attr(channel["name"])}" group-title="Rutube Direct"')
        playlist.append("#EXTINF:-1 " + meta + "," + channel["name"])
        playlist.append("#EXTVLCOPT:http-user-agent=" + AGENT)
        playlist.append(item["_hls"])
        count += 1

    public = [{key: value for key, value in item.items() if key != "_hls"} for item in results]
    if count == 0:
        print(json.dumps({"resolved": 0, "channels": public}, ensure_ascii=False, indent=2))
        raise RuntimeError("API returned no HLS streams; preserving prior playlist")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\n".join(playlist) + "\n", encoding="utf-8")
    report = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "catalog_count": len(channels), "resolved": count,
        "manifest_ok": sum(x["probe"] == "manifest_ok" for x in results),
        "channels": public,
    }
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"catalog_count": len(channels), "resolved": count,
                      "manifest_ok": report["manifest_ok"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
