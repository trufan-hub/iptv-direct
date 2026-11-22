#!/usr/bin/env python3
"""Inspect public Redge LSM player JS endpoint patterns, without requesting keys."""
import json
import re
import urllib.request
from urllib.parse import urlsplit
PAGES=[
"https://telpa.lsm.lv/player/redge-media-player/0.17.0/index.html?assetId=6379432&appId=lsm",
"https://telpa.lsm.lv/player/redge-media-player/0.17.0/lsm-player.js"
]
for url in PAGES:
  try:
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0","Referer":"https://replay.lsm.lv/"})
    with urllib.request.urlopen(req,timeout=22) as r:
      data=r.read(2_000_000).decode("utf-8","replace")
      print("URL",urlsplit(url).path,"HTTP",r.status,"SIZE",len(data))
    if url.endswith(".js"):
      tokens=["api.","redge.media","assetId","drm","license","\\.m3u8","streamUrl","asset_id","manifest","playbackUrl","/api/","apiUrl","keySystems","widevine","sourceUrl"]
      for token in tokens:
        hits=list(re.finditer(token,data,re.I))
        print("  TOKEN",token,len(hits))
        for hit in hits[:4]:
          context=data[max(0,hit.start()-95):hit.end()+160]
          context=context.replace("\\n"," ")
          context=re.sub(r'https?://[a-zA-Z0-9./:?=_%-]+',lambda m: "HOST:"+str(urlsplit(m.group()).hostname),context)
          print("    ",context[:280])
      urls=set(re.findall(r'https?:\\?/\\?/[^"' + "'" + r'\s\`\}\);,]{5,190}',data))
      print("  URL_HOSTS",list(sorted({urlsplit(u.replace("\\/","/")).hostname for u in urls if urlsplit(u.replace("\\/","/")).hostname}))[:45])
    else:
      scripts=re.findall(r'<script[^>]+src=["' + "'" + r']([^"' + "'" + r']+)',data)
      print("  JS SCRIPTS",scripts[:15])
  except Exception as e:print("ERROR",str(e)[:250])
