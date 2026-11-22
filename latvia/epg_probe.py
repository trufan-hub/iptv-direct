#!/usr/bin/env python3
import gzip
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
URL="https://epgshare01.online/epgshare01/epg_ripper_LV1.xml.gz"
with urllib.request.urlopen(urllib.request.Request(URL,headers={"User-Agent":"Mozilla/5.0"}),timeout=30) as r:
    data=r.read(8_000_001)
assert len(data)<8_000_000
if data.startswith(b"\x1f\x8b"): data=gzip.decompress(data)
root=ET.fromstring(data)
channels=[(c.get("id"),[x.text for x in c.findall("display-name")]) for c in root.findall("channel")]
print("SOURCE CHANNELS:",len(channels),"PROGRAMMES:",len(root.findall("programme")))
for cid,names in channels:
    if any(any(z in (a or "").lower() for z in ("ltv","retv","swh","vidusdaugavas","jurmala","jūrmala","tvnet","chaula")) for a in [cid,*names]):
        print("MATCH",cid,names)
