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
EPG = "https://trufan-hub.github.io/iptv-direct/guide.xml.gz"
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


def cached_streams():
    """Read last published URLs; do not contact third-party playlists."""
    result = {}
    if not OUTPUT.exists():
        return result
    name = None
    for line in OUTPUT.read_text(encoding="utf-8").splitlines():
        if line.startswith("#EXTINF:"):
            name = line.split(",", 1)[-1].strip()
        elif line.startswith("https://") and name:
            result[name] = line
            name = None
    return result


def acceptable_stream(url):
    if not isinstance(url, str) or len(url) > 2048:
        return False
    p = urlsplit(url)
    return bool(p.scheme == "https" and p.hostname and not p.username)


def resolve(channel, previous_url=None):
    result = {
        "name": channel["name"], "rutube_id": channel["rutube_id"],
        "status": "unavailable", "api_status": "not_checked",
        "probe": "not_checked", "source": "none"
    }
    api_url = None
    for attempt in range(2):
        try:
            candidates = hls_options(load_options(channel["rutube_id"]))
            if not candidates:
                result["api_status"] = "no_hls_in_api"
                break
            api_url = candidates[0]
            result["api_status"] = "resolved"
            api_probe = probe_manifest(api_url)
            if api_probe == "manifest_ok":
                result.update(status="verified", probe=api_probe,
                              source="rutube_api", _hls=api_url)
                return result
            result["api_status"] = "url_unverified:" + api_probe
            break
        except HTTPError as exc:
            result["api_status"] = "http_" + str(exc.code)
            if exc.code in (401, 403, 404, 451):
                break
            if attempt == 0:
                time.sleep(0.3)
        except (URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
            result["api_status"] = "error:" + type(exc).__name__
            if attempt == 0:
                time.sleep(0.3)

    options = [
        ("previous", previous_url),
        ("bootstrap", channel.get("bootstrap_url")),
    ]
    if api_url:
        options.append(("rutube_api_unverified", api_url))

    seen = set()
    first_usable = None
    for source, url in options:
        if not acceptable_stream(url) or url in seen:
            continue
        seen.add(url)
        if first_usable is None:
            first_usable = (source, url)
        check = probe_manifest(url)
        if check == "manifest_ok":
            result.update(status="verified", probe=check,
                          source=source, _hls=url)
            return result
        if result["probe"] == "not_checked":
            result["probe"] = check

    # A candidate can still play on the user's TV despite a blocked
    # GitHub runner. Include it only in the full, *unverified* playlist.
    if first_usable is not None:
        source, url = first_usable
        result.update(status="candidate_unverified",
                      source=source, _hls=url)
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
        if row.get("bootstrap_url") and not acceptable_stream(row["bootstrap_url"]):
            raise ValueError("Invalid bootstrap URL")
        seen.add(row["rutube_id"])

    previous = cached_streams()
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as executor:
        results = list(executor.map(
            lambda channel: resolve(channel, previous.get(channel["name"])),
            channels
        ))

    header = [
        f'#EXTM3U url-tvg="{EPG}"',
        "# Direct Rutube API plus one-time fallback snapshot",
        "# Generated UTC: " + datetime.now(timezone.utc).isoformat()
    ]
    playlist = header.copy()
    verified = header.copy()
    count = 0
    verified_count = 0
    for channel, item in zip(channels, results):
        url = item.get("_hls")
        if not url:
            continue
        meta = (f'tvg-id="{attr("rtv." + channel["rutube_id"])}" '
                f'tvg-name="{attr(channel["name"])}" group-title="Rutube Direct"')
        entry = [
            "#EXTINF:-1 " + meta + "," + channel["name"],
            "#EXTVLCOPT:http-user-agent=" + AGENT,
            url
        ]
        playlist.extend(entry)
        count += 1
        if item["status"] == "verified":
            verified.extend(entry)
            verified_count += 1

    public = [{key: value for key, value in item.items() if key != "_hls"}
              for item in results]
    if count == 0:
        print(json.dumps({"published": 0, "channels": public}, ensure_ascii=False))
        raise RuntimeError("No candidate URLs; preserving prior playlist")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\n".join(playlist) + "\n", encoding="utf-8")
    Path("docs/verified.m3u").write_text(
        "\n".join(verified) + "\n", encoding="utf-8"
    )
    report = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "catalog_count": len(channels),
        "published": count,
        "verified": verified_count,
        "unverified": count - verified_count,
        "api_updated": sum(x["source"] == "rutube_api" for x in results),
        "previous_used": sum(x["source"] == "previous" for x in results),
        "bootstrap_used": sum(x["source"] == "bootstrap" for x in results),
        "channels": public,
    }
    REPORT.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8"
    )
    print(json.dumps(
        {k: v for k, v in report.items() if k != "channels"},
        ensure_ascii=False
    ))


if __name__ == "__main__":
    main()
