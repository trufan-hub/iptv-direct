#!/usr/bin/env python3
"""Read-only inspection of official LTV webpages and public player API.

No authentication, geo-bypass, redistribution or token logging.
"""
import html
import json
import re
import urllib.request
from urllib.parse import urlsplit

HEADERS={"User-Agent":"Mozilla/5.0","Accept":"text/html,application/json,*/*"}
PAGES=[
"https://ltv.lsm.lv/lv/tiesraide/ltv1",
"https://ltv.lsm.lv/lv/tiesraide/ltv7",
"https://replay.lsm.lv/lv/skaties/tiesraide/ltv1",
"https://replay.lsm.lv/lv/skaties/tiesraide/ltv7",
]
def fetch(url, data=None, referer=None):
    headers=dict(HEADERS)
    if referer:
        headers["Referer"]=referer
    req=urllib.request.Request(url,data=data,headers=headers)
    with urllib.request.urlopen(req,timeout=17) as response:
        return response.status,response.geturl(),response.read(2_000_000).decode("utf-8","replace")
def cleanhost(url):
    p=urlsplit(url)
    return p.scheme+"://"+(p.hostname or "")+p.path[:110]
for url in PAGES:
    try:
        status,final,body=fetch(url)
        print("PAGE",cleanhost(url),"HTTP",status,"REDIRECT",cleanhost(final),"bytes",len(body))
        for field in ("embed/live","cloudycdn","ltv1_pasaule","ltv7_pasaule","ltv1_g","ltv7_g","channelId","item_id"):
            print("  token",field,"found",field in body)
        encoded=re.findall(r'https:\\(?:\\u002[Ff]|/)+ltv\.lsm\.lv\\(?:\\u002[Ff]|/)+embed\\(?:\\u002[Ff]|/)+live[^\"]{0,500}',body)
        plain=re.findall(r'https://ltv\.lsm\.lv/embed/live[^"\' <]{0,500}',body)
        urls=[]
        for x in encoded+plain:
            try:
                val=json.loads('"'+x+'"') if "\\u002F" in x else html.unescape(x)
                if val not in urls: urls.append(val)
            except (ValueError,json.JSONDecodeError):pass
        for marker in ("__REPLAY__", "redge", "playback", "source", "embed", "__NUXT_DATA__"):
            matches=list(re.finditer(re.escape(marker),body,re.I))
            print("  marker",marker,"count",len(matches))
            if marker in ("__REPLAY__", "redge", "playback") and matches:
                for m in matches[:2]:
                    snippet=body[max(0,m.start()-90):m.start()+190]
                    snippet=re.sub(r'https?://[^\\s"<>]+',"[url]",snippet)
                    print("    snippet",snippet[:260].replace("\\n"," "))
        print("  scripts",sorted(set(re.findall(r'<script[^>]+src=["\\\']([^"\\\']+)',body)))[:10])
        print("  embeds",len(urls))
        for iframe in urls[:3]:
            try:
                stat,final,payload=fetch(iframe,referer=url)
                print("  EMBED HTTP",stat,cleanhost(final),"bytes",len(payload))
                matches=re.findall(r'item_id(?:&quot;|\\?\"|\"|\\?&#34;)?\s*[:=]\s*(?:&quot;|")?([a-zA-Z0-9_-]{5,100})',payload)
                matches+=re.findall(r'"item_id"\s*:\s*"([^"]+)"',html.unescape(payload))
                print("    ids",sorted(set(matches))[:5])
                for channel_id in sorted(set(matches))[:2]:
                    api="https://player.cloudycdn.services/player/ltvlive/channel/"+channel_id+"/"
                    try:
                        status,redirect,data=fetch(api,data=b"refer=ltv.lsm.lv&playertype=regular&protocol=hls",referer=iframe)
                        parsed=json.loads(data)
                        sources=parsed.get("source",{}).get("sources",[])
                        print("    PLAYER",status,"count",len(sources),"sourceHosts",[
                            cleanhost(src.get("src","")) for src in sources[:5]
                        ])
                    except Exception as exc:
                        print("    PLAYER FAIL",type(exc).__name__,str(exc)[:90])
            except Exception as exc:
                print("  EMBED FAIL",type(exc).__name__,str(exc)[:90])
    except Exception as exc:
        print("PAGE FAIL",cleanhost(url),type(exc).__name__,str(exc)[:100])
