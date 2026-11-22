#!/usr/bin/env python3
"""Look for provider API origin and public playback mechanism in LSM JS (read only)."""
from collections import Counter
import re
from urllib.parse import urlsplit
from urllib.request import Request,urlopen
base="https://telpa.lsm.lv/player/redge-media-player/0.17.0/"
for name in ("lsm-player.min.js","lsm-player.js"):
    try:
        req=Request(base+name,headers={"User-Agent":"Mozilla/5.0","Referer":"https://replay.lsm.lv/"})
        with urlopen(req,timeout=35) as rsp: src=rsp.read(6_000_000).decode("utf-8","replace")
        print("SCRIPT",name,len(src))
        hosts=Counter()
        for full in re.findall(r"https?:(?:\\?/){2}[^\s\"'<>\\]{2,180}",src):
            host=urlsplit(full.replace("\\/","/")).hostname
            if host:hosts[host]+=1
        print("HOSTS",hosts.most_common(60))
        for term in ("assetId","sourceUrl","appId","loadAsset","getAsset","getMedia","mediaUrl","m3u8","redge.media","contentUrl","streamingUrl","manifestUrl","serviceUrl"):
            spots=[m.start() for m in re.finditer(re.escape(term),src,re.I)]
            print("TOKEN",term,len(spots))
            if term in ("assetId","sourceUrl","appId","loadAsset","getAsset","getMedia","mediaUrl","redge.media","contentUrl","streamingUrl","manifestUrl","serviceUrl"):
                for p in (spots[-6:] if len(spots)>6 else spots):
                    nearby=src[max(0,p-240):p+350].replace("\n"," ")
                    nearby=re.sub(r'https?://[^\s"<>]+',lambda m:"[HOST:"+str(urlsplit(m.group()).hostname)+"]",nearby)
                    print("CONTEXT",nearby[:590])
        print("LAST",src[-3200:].replace("\n"," "))
    except Exception as e:print("ERROR",name,type(e).__name__,str(e)[:190])
