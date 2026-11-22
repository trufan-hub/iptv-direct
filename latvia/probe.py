#!/usr/bin/env python3
"""Independently diagnose public Latvian HLS URLs. Read-only; no IPTV release modified."""
import concurrent.futures
import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "*/*"}

def check(pair):
    name, url = pair
    try:
        req = Request(url, headers=HEADERS)
        with urlopen(req, timeout=13) as r:
            data = r.read(2048)
            status = r.status
        return {"name": name, "url": url,
                "http": status,
                "hls": bool(data.lstrip(b"\xef\xbb\xbf \r\n").startswith(b"#EXTM3U")),
                "note": "ok" if data.lstrip(b"\xef\xbb\xbf \r\n").startswith(b"#EXTM3U") else "not_m3u"}
    except HTTPError as e:
        return {"name": name, "url": url, "http": e.code, "hls": False, "note": "http_error"}
    except (OSError, ValueError, URLError) as e:
        return {"name": name, "url": url, "http": None, "hls": False, "note": type(e).__name__}

if __name__ == "__main__":
    channels = json.load(open("latvia/candidates.json",encoding="utf-8"))
    jobs = [(ch["name"], u) for ch in channels for u in ch["urls"]]
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(check,jobs))
    for row in results:
        print(json.dumps(row,ensure_ascii=False))
    print(f"SUMMARY: {sum(r['hls'] for r in results)} valid manifests / {len(results)} URLs")
