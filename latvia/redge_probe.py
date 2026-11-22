#!/usr/bin/env python3
"""Review public REplay Redge player URL assembly; never print signed tokens."""
import re
from urllib.parse import urlsplit
from urllib.request import Request,urlopen
url="https://telpa.lsm.lv/player/redge-media-player/0.17.0/lsm-player.js"
with urlopen(Request(url,headers={"User-Agent":"Mozilla/5.0","Referer":"https://replay.lsm.lv/"}),timeout=35) as r:
    src=r.read(5_000_000).decode("utf-8","replace")
print("SIZE",len(src))
for name in ("getAssetDetail","getPlayerConfiguration","getPlaylist","wrapper_init","getPlayerConfig","assetDetail","cdnToken","TENANT_UID_BY_APP_ID","ENDPOINT","API_URL","lsm.lv/api"):
    spot=[m.start() for m in re.finditer(re.escape(name),src)]
    print("TERM",name,"count",len(spot))
    defs=[p for p in spot if any(x in src[max(0,p-120):p] for x in ["function ","const ","var ","function* ","function "])]
    for p in (defs[:4] if defs else spot[:2]):
        snippet=src[max(0,p-220):p+3700].replace("\n"," ")
        snippet=re.sub(r'https?://[\w./?=&;%+-]+',lambda m:"["+str(urlsplit(m.group()).hostname)+urlsplit(m.group()).path[:100]+"]",snippet)
        print("CODE",snippet[:3800])
