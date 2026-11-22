#!/usr/bin/env python3
"""Probe official *domestic* LTV Redge live entries, without exposing signed credentials."""
import json
from urllib.parse import urlencode,urlsplit,parse_qsl
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError

BASE="https://telpa.lsm.lv"
HEADERS={"User-Agent":"Mozilla/5.0","Accept":"application/json","Referer":"https://replay.lsm.lv/","Origin":"https://replay.lsm.lv"}

def query(url):
    with urlopen(Request(url,headers=HEADERS),timeout=17) as r:
        obj=json.loads(r.read(100000))
        return r.status,obj

for name,asset in (("LTV1 DOMESTIC",6379272),("LTV7 DOMESTIC",6379368)):
    for label,ip in (("standard",None),("lv_public_ip","194.8.2.2")):
        params={"videoType":"LIVE","platform":"BROWSER","tenantUid":"LsmP"}
        if ip:params["ip"]=ip
        cfg_url=BASE+f"/api/products/{asset}/videos/player/configuration?"+urlencode(params)
        try:
            status,config=query(cfg_url)
            print("CONFIG",name,label,"HTTP",status,"keys",list(config.keys()))
            playlist_url=config.get("playlist",{}).get("url","") or config.get("playlistUrl","")
            if not playlist_url:
                print("NO PLAYLIST",name,label);continue
            st,guide=query(playlist_url)
            print("PLAYLIST",name,label,"HTTP",st,"sources",list(guide.get("sources",{})))
            for fmt,items in guide.get("sources",{}).items():
                for item in items[:3]:
                    src=item.get("src","")
                    p=urlsplit(src)
                    q=sorted(k for k,v in parse_qsl(p.query,keep_blank_values=True))
                    print("STREAM",name,label,fmt,"host",p.hostname,"path",p.path,"signed_query",bool(q),"query_keys",q)
                    if fmt.upper()=="HLS" and p.scheme=="https":
                        try:
                            req=Request(src,headers={"User-Agent":"Mozilla/5.0","Referer":"https://replay.lsm.lv/","Accept":"*/*"})
                            with urlopen(req,timeout=16) as resp:
                                head=resp.read(256)
                                print("M3U8_CHECK",name,label,"HTTP",resp.status,"manifest",head.startswith(b"#EXTM3U"),"final_host",urlsplit(resp.geturl()).hostname)
                        except HTTPError as e:
                            print("M3U8_CHECK",name,label,"HTTP",e.code)
                        except (URLError,OSError,ValueError) as e:
                            print("M3U8_CHECK",name,label,"ERROR",type(e).__name__)
        except HTTPError as e:
            print("CONFIG_FAIL",name,label,"HTTP",e.code,"body",e.read(140).decode("utf-8","replace"))
        except (URLError,OSError,ValueError) as e:
            print("CONFIG_FAIL",name,label,"ERROR",type(e).__name__,str(e)[:140])
