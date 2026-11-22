#!/usr/bin/env python3
"""Probe official REplay public metadata from an overseas runner without emitting tokens."""
import json
from urllib.parse import urlencode,urlsplit
from urllib.error import HTTPError,URLError
from urllib.request import Request,urlopen
BASE="https://telpa.lsm.lv"
for name,asset in (("LTV1","6379352"),("LTV7","6379432")):
    for path,params in [
        (f"/api/items/{asset}",{"platform":"BROWSER","tenantUid":"LsmP"}),
        (f"/api/products/lives/{asset}",{"platform":"BROWSER","tenantUid":"LsmP"}),
        (f"/api/products/{asset}/videos/player/configuration",{"platform":"BROWSER","videoType":"LIVE","tenantUid":"LsmP"})
    ]:
        url=BASE+path+"?"+urlencode(params)
        req=Request(url,headers={"User-Agent":"Mozilla/5.0","Accept":"application/json","Referer":"https://replay.lsm.lv/","Origin":"https://replay.lsm.lv"})
        try:
            with urlopen(req,timeout=12) as r:
                raw=r.read(100000)
                print(name,path,"HTTP",r.status,"LEN",len(raw),"CONTENT_TYPE",r.headers.get("Content-Type"))
            try:
                obj=json.loads(raw)
                if isinstance(obj,dict):
                    print("  KEYS",list(obj.keys())[:40])
                    if path.endswith("/configuration"):
                        conf=obj.get("playlist",{})
                        if isinstance(conf,dict):
                            rawurl=conf.get("url","")
                            pp=urlsplit(rawurl)
                            print("  PLAYLIST",{"host":pp.hostname,"path":pp.path,"query_keys":[t.split("=")[0] for t in pp.query.split("&") if t]})
                        for key in ("error","status","message"):
                            if key in obj: print(" ",key,str(obj[key])[:120])
                    else:
                        for key in ("type","itemType","id","status","error","message"):
                            if key in obj:print(" ",key,str(obj[key])[:120])
                else:print("  KIND",type(obj).__name__)
            except ValueError:print("  NOT_JSON",raw[:80])
        except HTTPError as e:print(name,path,"HTTP",e.code,"BODY",e.read(300).decode("utf-8","replace")[:160])
        except (URLError,OSError) as e:print(name,path,type(e).__name__,str(e)[:170])
