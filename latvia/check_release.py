#!/usr/bin/env python3
"""Reject malformed Latvia IPTV releases before GitHub Pages deployment."""
from __future__ import annotations
import gzip
import json
import re
from html import unescape
from pathlib import Path
from xml.etree import ElementTree as ET

root = Path("docs")
catalog = json.loads(Path("latvia/channels.json").read_text(encoding="utf-8"))
registry = json.loads((root / "latvia-logos.json").read_text(encoding="utf-8"))
report = json.loads((root / "latvia-report.json").read_text(encoding="utf-8"))
m3u = (root / "latvia.m3u").read_text(encoding="utf-8").splitlines()
assert m3u and m3u[0] == '#EXTM3U url-tvg="https://trufan-hub.github.io/iptv-direct/latvia-guide.xml"'
infos = [line for line in m3u if line.startswith("#EXTINF")]
assert len(infos) == len(catalog) and len(catalog) >= 5
found = {}
for info in infos:
    channel_id = re.search(r'tvg-id="(lv\.[a-z0-9]+)"', info)
    assert channel_id is not None and channel_id.group(1) not in found
    ident = channel_id.group(1)
    logo = re.search(r'tvg-logo="([^"]+)"', info)
    if ident in registry:
        assert logo and unescape(logo.group(1)) == registry[ident]
    found[ident] = True
assert set(found) == {c["id"] for c in catalog}
xml = (root / "latvia-guide.xml").read_bytes()
assert gzip.decompress((root / "latvia-guide.xml.gz").read_bytes()) == xml
tv = ET.fromstring(xml)
assert tv.tag == "tv"
assert {node.get("id") for node in tv.findall("channel")} == set(found)
p = tv.findall("programme")
assert len(p) >= 30 and all(node.get("channel") in found for node in p)
desc = sum(bool(node.findtext("desc")) for node in p)
assert report["programmes"] == len(p) and report["descriptions"] == desc
assert report["catalog_channels"] == len(infos)
assert report["guide_channels"] >= 3 and report["verified_manifests"] >= 3
for channel in tv.findall("channel"):
    ident = channel.get("id")
    if ident in registry:
        icon = channel.find("icon")
        assert icon is not None and icon.get("src") == registry[ident]
print(json.dumps({"result":"PASS","channels":len(infos),"EPG_programmes":len(p),
                  "synopses":desc,"logos":len(registry)},ensure_ascii=False))
