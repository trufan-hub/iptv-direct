#!/usr/bin/env python3
"""Inspect public REplay Nuxt playback metadata without emitting signed URLs."""
import json
import re
import urllib.request
from urllib.parse import urlsplit
for channel in ("ltv1","ltv7"):
    url="https://replay.lsm.lv/lv/skaties/tiesraide/"+channel
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req,timeout=18) as response:
            html=response.read(180000).decode("utf-8","replace")
        i=html.index("window.__REPLAY__=(function(")
        tail=html[i:html.find("</script>",i)]
        formals=re.search(r'function\(([^)]*)\)',tail)
        symbols=formals.group(1).split(",") if formals else []
        source=re.search(r'playback:\{type:([A-Za-z0-9_$]+),service:\{url:([A-Za-z0-9_$]+)',tail)
        print("CHANNEL",channel,"PARAMS",len(symbols),"PLAYBACK_SYMBOLS",source.groups() if source else "not found")
        print("TAIL START",re.sub(r'https?://[^\s"<>]+', "[url]",tail[:320]))
        print("TAIL END",re.sub(r'https?://[^\s"<>]+', "[url]",tail[-520:]))
        if not formals or not source:
            continue
        # The Nuxt 2 HTML serializer invokes an IIFE:
        # (function(a,b,...){return {...}}(null,"...",...))
        parenStart=tail.rfind("}(")
        print("CALL POS",parenStart,"LEN",len(tail))
        if parenStart<0: continue
        call=tail[parenStart+2:]
        if call.endswith("))"): call=call[:-2]
        elif call.endswith(")"): call=call[:-1]
        args=[]
        cur=[]
        inquote=False
        escape=False
        for c in call:
            if inquote:
                cur.append(c)
                if escape:
                    escape=False
                elif c=="\\": escape=True
                elif c=='"': inquote=False
            elif c=='"':
                cur.append(c);inquote=True
            elif c==",":
                args.append("".join(cur).strip());cur=[]
            else:cur.append(c)
        if cur:args.append("".join(cur).strip())
        print("ARGS",len(args),"SYMBOLS",len(symbols))
        for sym in source.groups():
            if sym not in symbols:
                print("SYMBOL MISSING",sym);continue
            idx=symbols.index(sym)
            value=args[idx] if idx<len(args) else "UNDEFINED"
            try:
                value=json.loads(value)
            except (ValueError,TypeError):
                pass
            if isinstance(value,str) and value.startswith("http"):
                p=urlsplit(value)
                value={"scheme":p.scheme,"host":p.hostname,"path":p.path[:120],"query_present":bool(p.query)}
            elif isinstance(value,str) and len(value)>100: value=value[:100]
            print("DECODED",sym,value)
    except Exception as e:
        print("ERROR",channel,type(e).__name__,str(e)[:120])
