#!/usr/bin/env python3
"""Test LTV domestic HLS through a private, Latvia-located HTTP(S) proxy.

No credentials, public playback URLs, viewer tokens or IPs are logged.
Does not write or deploy IPTV playlists. By default a proxy is REQUIRED.
--geo-only --optional: for existing build workflow, if proxy missing do nothing.
"""
from __future__ import annotations

import argparse
import json
import os
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, ProxyHandler, build_opener
from urllib.error import HTTPError, URLError


def get_proxy(required: bool):
    raw = os.environ.get("LV_PROXY_URL", "").strip()
    if not raw:
        if required:
            raise RuntimeError(
                "LV_PROXY_URL missing: add a Latvian HTTP CONNECT proxy to "
                "GitHub repository Actions secret LV_PROXY_URL"
            )
        return None
    parsed = urlsplit(raw)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or not parsed.port:
        raise RuntimeError(
            "LV_PROXY_URL must be http://user:password@host:port "
            "or https://user:password@host:port"
        )
    if any(c in raw for c in "\r\n"):
        raise RuntimeError("Malformed proxy address")
    return raw


def setup(proxy):
    # Explicitly route every URL via the proxy, avoiding environmental bypasses.
    return build_opener(ProxyHandler({"http": proxy, "https": proxy}))


def read_json(opener, url, referer=None):
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
    }
    if referer:
        headers.update({"Referer": referer, "Origin": "https://replay.lsm.lv"})
    with opener.open(Request(url, headers=headers), timeout=22) as response:
        return json.loads(response.read(350_000))


def probe_geo(opener):
    providers = (
        ("ipinfo", "https://ipinfo.io/json", "country"),
        ("ipapi", "https://ipapi.co/json/", "country_code"),
    )
    errors = []
    for label, url, key in providers:
        try:
            data = read_json(opener, url)
            country = str(data.get(key, "")).upper()
            if country and len(country) == 2:
                print("Proxy egress country:", country, "as reported by", label)
                if country != "LV":
                    raise RuntimeError("Proxy is NOT located in Latvia")
                return
            errors.append(label + ": no country code")
        except (OSError, ValueError, HTTPError, URLError) as error:
            errors.append(label + ": " + type(error).__name__)
    raise RuntimeError("Proxy country could not be verified: " + ", ".join(errors))


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument("--geo-only", action="store_true")
    parser.add_argument("--optional", action="store_true")
    args = parser.parse_args()
    proxy = get_proxy(required=not args.optional)
    if not proxy:
        print("LV proxy not configured; existing build unchanged (direct requests).")
        return
    opener = setup(proxy)
    probe_geo(opener)
    if args.geo_only:
        print("Latvian proxy egress verified; all build network requests may use it.")
        return
    for channel, asset_id in (("LTV1", "6379352"), ("LTV7", "6379432")):
        query = urlencode({
            "videoType": "LIVE", "platform": "BROWSER", "tenantUid": "LsmP"
        })
        url = ("https://telpa.lsm.lv/api/products/" + asset_id
               + "/videos/playlist?" + query)
        response = read_json(opener, url, referer="https://replay.lsm.lv/")
        sources = response.get("sources", {}).get("HLS", [])
        if not sources:
            print(channel, "No HLS source in official playlist response")
            continue
        for item in sources:
            stream = item.get("src", "")
            if not stream.startswith("https://"):
                print(channel, "Non-HTTPS source ignored")
                continue
            parsed = urlsplit(stream)
            if parsed.hostname not in (
                "lsm.eu.cdns-redge.media", "lsm.cdns-redge.media",
                "lsm.lv"
            ) and not (parsed.hostname or "").endswith(".cdns-redge.media"):
                print(channel, "Unknown stream host; not probed")
                continue
            is_pasaule = "_pasaule" in parsed.path
            if is_pasaule:
                print(channel, "Official API still returns international/Pasaule feed")
            else:
                print(channel, "Candidate domestic HLS host:", parsed.hostname)
            try:
                req = Request(stream, headers={
                    "User-Agent": "Mozilla/5.0",
                    "Referer": "https://replay.lsm.lv/"
                })
                with opener.open(req, timeout=20) as opened:
                    valid = opened.read(256).lstrip().startswith(b"#EXTM3U")
                    print(channel, "HLS manifest valid:", bool(valid),
                          "signed query:", bool(parsed.query))
            except (OSError, ValueError, HTTPError, URLError) as error:
                print(channel, "HLS check failed:", type(error).__name__)
    print("A valid HLS manifest does not prove actual domestic video playback.")
    print("Never publish session/IP-bound URLs into a public static M3U.")


if __name__ == "__main__":
    run()
