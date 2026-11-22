#!/usr/bin/env python3
"""Check official public LSM LIVE playlist response; redact CDN auth tokens."""
import json
from urllib.parse import urlencode,urlsplit,parse_qsl
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError
BASE="https://telpa.lsm.lv"
for name,asset in (("LTV1","6379352"),("LTV7","6379432")):
    url=BASE+f"/api/products/{asset}/videos/playlist?"+urlencode({"videoType":"LIVE","platform":"BROWSER","tenantUid":"LsmP"})
    req=Request(url,headers={"User-Agent":"Mozilla/5.0","Accept":"application/json","Referer":"https://replay.lsm.lv/","Origin":"https://replay.lsm.lv"})
    try:
        with urlopen(req,timeout=16) as resp:
            raw=resp.read(250000)
            print(name,"HTTP",resp.status,"CONTENT_TYPE",resp.headers.get("Content-Type"),"LEN",len(raw))
        data=json.loads(raw)
        def scan(value,path="ROOT",depth=0):
            if depth>6:return
            if isinstance(value,dict):
                print("KEYS",path,list(value.keys())[:25])
                for k,v in value.items():
                    if k in ("drm","contentProtection","drmConfiguration","encrypted","sources","media","formats"):
                        print("  TYPE",path+"."+k,type(v).__name__)
                    scan(v,path+"."+k,depth+1)
            elif isinstance(value,list):
                print("COUNT",path,len(value))
                for v in value[:2]:scan(v,path+"[]",depth+1)
            elif isinstance(value,str) and value.startswith("http"):
                parsed=urlsplit(value)
                print("URL",path,parsed.hostname,parsed.path[:160],"QUERY_KEYS",[k for k,v in parse_qsl(parsed.query)][:12])
            elif isinstance(value,(str,int,bool)) and path.endswith((".format",".type",".protocol",".encrypted",".drm")):
                print("VALUE",path,str(value)[:110])
        scan(data)
    except HTTPError as e:
        print(name,"HTTP",e.code,"BODY",e.read(220).decode("utf-8","replace")[:120])
    except (ValueError,OSError,URLError) as e:print(name,"ERROR",type(e).__name__,str(e)[:130])
