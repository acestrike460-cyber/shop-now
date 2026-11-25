#!/usr/bin/env python3
"""
Attempt to get Shalom's CSRF token and then call their API to get all agencies.
Based on JS analysis: 
  - GET /csrf or similar endpoint to get X-Proxy-Token
  - Then POST /agencias/departamentos with that token
"""
import urllib.request
import urllib.parse
import re
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

def fetch_json(url, method="GET", data=None, headers=None):
    h = dict(HEADERS)
    if headers:
        h.update(headers)
    body = json.dumps(data).encode() if data else None
    if body:
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20, context=ctx) as r:
            content = r.read().decode("utf-8", errors="ignore")
            print(f"  {method} {url} -> {r.status}")
            return content, r.status, dict(r.headers)
    except urllib.error.HTTPError as e:
        content = e.read().decode("utf-8", errors="ignore")
        print(f"  {method} {url} -> HTTP {e.code}")
        return content, e.code, {}
    except Exception as e:
        print(f"  {method} {url} -> ERROR: {e}")
        return None, str(e), {}

# Step 1: Try to find the CSRF/token endpoint from JS
print("=== Step 1: Find CSRF endpoint ===")
# The JS shows: k7 = X-Session-Key from some JSON response with .csrf and .expiresAt
# Let's try common CSRF endpoints
csrf_endpoints = [
    "https://shalom.com.pe/csrf",
    "https://shalom.com.pe/sanctum/csrf-cookie",
    "https://shalom.com.pe/api/csrf",
    "https://shalom.com.pe/token",
    "https://shalom.com.pe/session",
    "https://shalom.com.pe/init",
]

for ep in csrf_endpoints:
    content, status, resp_headers = fetch_json(ep)
    if content and status == 200:
        print(f"  RESPONSE: {content[:300]}")
        break

# Step 2: Try direct API endpoints with and without token
print("\n=== Step 2: Try API endpoints ===")
test_endpoints = [
    ("GET", "https://shalom.com.pe/agencias/departamentos", None),
    ("POST", "https://shalom.com.pe/agencias/departamentos", {}),
    ("GET", "https://shalom.com.pe/agencias/listar", None),
    ("GET", "https://shalom.com.pe/api/agencias/departamentos", None),
]

for method, url, data in test_endpoints:
    content, status, hdrs = fetch_json(url, method, data)
    if content and status == 200:
        print(f"  SUCCESS! Content: {content[:500]}")

# Step 3: Search for shalomcontrol.com endpoints in JS
print("\n=== Step 3: Analyze JS for shalomcontrol endpoints ===")
req = urllib.request.Request(
    "https://shalom.com.pe/assets/index-57684d39.js",
    headers={"User-Agent": HEADERS["User-Agent"]}
)
with urllib.request.urlopen(req, timeout=30, context=ctx) as r:
    js = r.read().decode("utf-8", errors="ignore")

# Find shalomcontrol references
sc_matches = [(m.start(), js[max(0,m.start()-100):m.start()+200]) 
              for m in re.finditer(r'shalomcontrol', js)]
print(f"Found {len(sc_matches)} shalomcontrol references")
for pos, ctx_text in sc_matches[:5]:
    print(f"\n  pos={pos}: ...{ctx_text}...")

# Find all HTTPS URLs
all_urls = re.findall(r'https://[a-zA-Z0-9._/-]{10,100}', js)
unique_urls = sorted(set(all_urls))
print(f"\nAll unique HTTPS URLs in JS ({len(unique_urls)}):")
for u in unique_urls:
    print(f"  {u}")

print("\nDone.")
