#!/usr/bin/env python3
"""
Try the newwebservices.shalomcontrol.com API to get all agencies.
"""
import urllib.request
import ssl
import json

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "es-PE,es;q=0.9",
    "Referer": "https://shalom.com.pe/agencias",
    "Origin": "https://shalom.com.pe",
}

def fetch(url, method="GET", data=None, extra_headers=None):
    h = dict(HEADERS)
    if extra_headers:
        h.update(extra_headers)
    body = json.dumps(data).encode() if data else None
    if body:
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20, context=ctx) as r:
            content = r.read().decode("utf-8", errors="ignore")
            print(f"  {method} {url} -> {r.status} ({len(content)} bytes)")
            return content, r.status
    except urllib.error.HTTPError as e:
        content = e.read().decode("utf-8", errors="ignore")
        print(f"  {method} {url} -> HTTP {e.code}: {content[:200]}")
        return content, e.code
    except Exception as e:
        print(f"  {method} {url} -> ERROR: {e}")
        return None, str(e)

BASE = "https://newwebservices.shalomcontrol.com/api/v1/web"

endpoints = [
    f"{BASE}/agencias",
    f"{BASE}/agencias/listar",
    f"{BASE}/agencias/departamentos",
    f"{BASE}/agencias/all",
    f"{BASE}/agencias/list",
    f"{BASE}/store/agencias",
    f"{BASE}/store/departamentos",
    "https://newwebservices.shalomcontrol.com/api/v1/agencias",
    "https://newwebservices.shalomcontrol.com/api/agencias",
    # Try servicesweb too
    "https://servicesweb.shalomcontrol.com/api/v1/web/agencias/listar",
    "https://servicesweb.shalomcontrol.com/api/v1/agencias",
]

print("=== Testing newwebservices.shalomcontrol.com endpoints ===\n")
for ep in endpoints:
    content, status = fetch(ep)
    if content and status == 200 and "{" in content[:20]:
        print(f"  >>> JSON RESPONSE: {content[:1000]}")
        with open("shalom_agencies_raw.json", "w") as f:
            f.write(content)
        print("  Saved to shalom_agencies_raw.json")
        break

print("\nDone.")
