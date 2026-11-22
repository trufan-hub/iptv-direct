#!/usr/bin/env python3
"""Look for *domestic* LTV products via public LSM catalogue API, no token logs."""
import json
from urllib.request import Request,urlopen
from urllib.parse import urlencode,urlsplit
from urllib.error import HTTPError,URLError

base="https://telpa.lsm.lv"
paths=[
 ("/api/products/lives",{"platform":"BROWSER","tenantUid":"LsmP"}),
 ("/api/products/lives",{"platform":"BROWSER"}),
 ("/api/products/lives",{"platform":"BROWSER","tenantUid":"LsmP","page":"1","limit":"150"}),
 ("/api/products/lives/channels",{"platform":"BROWSER","tenantUid":"LsmP"}),
 ("/api/products/lives/epg",{"platform":"BROWSER","tenantUid":"LsmP"})
]
for path,params in paths:
    url=base+path+"?"+urlencode(params)
    try:
        req=Request(url,headers={"User-Agent":"Mozilla/5.0","Accept":"application/json","Referer":"https://replay.lsm.lv/"})
        with urlopen(req,timeout=18) as r:
            buf=r.read(2_000_000)
            print("URL",path,"QUERY",params,"HTTP",r.status,"len",len(buf),"type",r.headers.get("Content-Type"))
        try:obj=json.loads(buf)
        except ValueError: print("NOT_JSON",buf[:60]);continue
        if isinstance(obj,dict):
            print("TOP_LEVEL_KEYS",list(obj)[:20])
            for k,v in obj.items():
                if isinstance(v,list):print(" LIST_KEY",k,"COUNT",len(v))
        elif isinstance(obj,list): print("LIST_COUNT",len(obj))
        found=[]
        def walk(x,depth=0):
            if depth>6 or len(found)>50:return
            if isinstance(x,dict):
                if any(k in x for k in ("title","name","channelName")):
                    text=" ".join(str(x.get(k,"")) for k in ("title","name","channelName"))
                    if any(z in text.lower() for z in ("ltv1","ltv7","latvijas telev")):
                        found.append({k:x.get(k) for k in ("id","externalUid","publicUid","title","name","webUrl","liveType","type","geoipManualLock") if k in x})
                for v in x.values():walk(v,depth+1)
            elif isinstance(x,list):
                for v in x[:400]:walk(v,depth+1)
        walk(obj)
        print("MATCHES",json.dumps(found,ensure_ascii=False)[:9000])
    except HTTPError as e:
        print("URL",path,params,"HTTP",e.code,"BODY",e.read(140).decode("utf-8","replace"))
    except (OSError,URLError,ValueError) as e:
        print("URL",path,params,"ERROR",type(e).__name__,str(e)[:150])
