#!/usr/bin/env python3
import re
from urllib.request import Request,urlopen
url="https://telpa.lsm.lv/player/redge-media-player/0.17.0/lsm-player.js"
with urlopen(Request(url,headers={"User-Agent":"Mozilla/5.0","Referer":"https://replay.lsm.lv/"}),timeout=30) as r:
 src=r.read(4_000_000).decode("utf-8","replace")
for term in ("FO_BASE_URL", "FO_DETAIL_PARAMS", "FO_CONFIGURATION_PARAMS", "TENANT_UID_BY_APP_ID", "function withTenant", "function resolveItemType", "function get(", "FO_CONTENT", "cdnSecret", "getPlaylist(", "getPlayerConfiguration("):
 at=[m.start() for m in re.finditer(re.escape(term),src)]
 print("TERM",term,len(at))
 for p in (at[:4]):
  block=src[max(0,p-430):p+1250].replace("\n"," ")
  print("SNIPPET",block[:1680])
