#!/usr/bin/env python3
"""Generate opt-in test M3U for official LTV1/LTV7 *domestic* HLS.

Experimental playlist only. Never modify production docs/latvia.m3u.
No DRM/token bypass: only public source addresses with innocuous rendition
selection are eligible. Actual playback must be tested from Latvia.
"""
import json
from urllib.parse import urlencode, urlsplit, parse_qsl, urlunsplit
from urllib.request import Request, urlopen
from pathlib import Path

BASE="https://telpa.lsm.lv"
OUTPUT=Path("docs/latvia-domestic-test.m3u")
CHANNELS=[
  ("LTV1",6379272,"ltv1_latvija","https://upload.wikimedia.org/wikipedia/commons/thumb/4/4a/LTV1_%282022%29.svg/960px-LTV1_%282022%29.svg.png"),
  ("LTV7",6379368,"ltv7_latvija","https://upload.wikimedia.org/wikipedia/commons/thumb/f/f2/LTV7_Logo_2021.svg/960px-LTV7_Logo_2021.svg.png")
]
HEADERS={"User-Agent":"Mozilla/5.0","Accept":"application/json","Referer":"https://replay.lsm.lv/","Origin":"https://replay.lsm.lv"}
lines=["#EXTM3U", "# TruFan Latvia domestic LTV test; NOT validated for actual playback",
       "# Experimental official streams. Production latvia.m3u is unchanged."]
for name,asset,live_id,logo in CHANNELS:
  query=urlencode({"videoType":"LIVE","platform":"BROWSER","tenantUid":"LsmP"})
  api=BASE+f"/api/products/{asset}/videos/player/configuration?"+query
  def json_read(url):
    with urlopen(Request(url,headers=HEADERS),timeout=25) as r:
      return json.loads(r.read(120000))
  configuration=json_read(api)
  playlist_url=configuration.get("playlist",{}).get("url")
  if not playlist_url: raise RuntimeError(name+": missing official playlist URL")
  data=json_read(playlist_url)
  variants=data.get("sources",{}).get("HLS",[])
  if len(variants)!=1: raise RuntimeError(name+": expected one official HLS source")
  full=variants[0].get("src","")
  p=urlsplit(full)
  if p.scheme!="https" or p.hostname!="lsm.eu.cdns-redge.media" or f"/{live_id}/" not in p.path:
    raise RuntimeError(name+": invalid or non-domestic official HLS")
  keys=[key for key,_ in parse_qsl(p.query,keep_blank_values=True)]
  if any(key not in {"renditions"} for key in keys):
    raise RuntimeError(name+": ephemeral or sensitive query parameter detected")
  stable=urlunsplit((p.scheme,p.netloc,p.path,"",""))
  for suffix,href in (("API",full),("DIRECT",stable)):
    lines.extend([
      '#EXTINF:-1 tvg-id="lv.test.'+live_id+'.'+suffix.lower()+'"'
      ' tvg-logo="'+logo+'" group-title="LTV pārbaude",'+name+" LATVIJA "+suffix,
      href
    ])
  print("Prepared",name,"domestic candidates, query keys",keys)
OUTPUT.parent.mkdir(parents=True,exist_ok=True)
OUTPUT.write_text("\n".join(lines)+"\n",encoding="utf-8")
print("Experimental playlist ready:",OUTPUT)
