#!/usr/bin/env python3
"""Compare public Latvian and overseas LSM playback API routing; redact token URLs."""
import json
from urllib.parse import urlencode, urlsplit
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError

BASE="https://telpa.lsm.lv"
TEST_IPS=[("default",None),("NIC-LV", "194.8.2.2"),("LV-DNS2","212.142.79.6")]
HEADERS={"User-Agent":"Mozilla/5.0","Accept":"application/json","Referer":"https://replay.lsm.lv/","Origin":"https://replay.lsm.lv"}
def get(url):
    with urlopen(Request(url,headers=HEADERS), timeout=20) as r:
        return json.loads(r.read(40000))
for ch,asset in (("LTV1","6379352"),("LTV7","6379432")):
    detail=get(BASE+f"/api/products/lives/{asset}?"+urlencode({"platform":"BROWSER","tenantUid":"LsmP"}))
    print("CHANNEL",ch,"ASSET_DETAIL_TITLE",detail.get("title"),"WEB_URL",detail.get("webUrl"),"GEO_MANUAL_LOCK",detail.get("geoipManualLock"),"ACTIVE",detail.get("active"),"LOGIN",detail.get("loginRequired"))
    for name,ip in TEST_IPS:
        params={"videoType":"LIVE","platform":"BROWSER","tenantUid":"LsmP"}
        if ip:params["ip"]=ip
        url=BASE+f"/api/products/{asset}/videos/player/configuration?"+urlencode(params)
        try:
            config=get(url)
            print(" CONFIG",ch,name,"keys",list(config.keys()))
            playlist_url=config.get("playlist",{}).get("url","") or config.get("playlistUrl","")
            if not playlist_url:
                print("  NO_PLAYLIST");continue
            p=get(playlist_url)
            for fmt,items in p.get("sources",{}).items():
                for item in items[:3]:
                    raw=item.get("src","")
                    parsed=urlsplit(raw)
                    print("  SOURCE",fmt,"host",parsed.hostname,"path",parsed.path,"query_present",bool(parsed.query))
        except HTTPError as e:
            print(" FAIL",ch,name,"HTTP",e.code,"BODY",e.read(180).decode("utf-8","replace"))
        except (ValueError,OSError,URLError) as e:
            print(" FAIL",ch,name,type(e).__name__,str(e)[:160])
