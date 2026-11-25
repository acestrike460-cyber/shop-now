#!/usr/bin/env python3
"""Scrape Shalom.com.pe JS bundle to extract agency data or find API patterns."""
import urllib.request
import re
import ssl
import json
import sys

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
}

def fetch(url, extra_headers=None):
    h = dict(HEADERS)
    if extra_headers:
        h.update(extra_headers)
    req = urllib.request.Request(url, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=20, context=ctx) as r:
            return r.read().decode("utf-8", errors="ignore"), r.status
    except Exception as e:
        return None, str(e)

# 1. Get main page to find JS assets
print("[1] Fetching main page...")
html, status = fetch("https://shalom.com.pe/agencias")
if not html:
    print(f"ERROR: {status}")
    sys.exit(1)

# Find JS bundles
scripts = re.findall(r'src=["\']?(/assets/[^"\'>\s]+\.js)', html)
print(f"Found {len(scripts)} JS files: {scripts[:5]}")

# 2. Download main bundle (largest file usually)
main_js = None
main_url = None
for s in scripts:
    url = "https://shalom.com.pe" + s
    print(f"[2] Fetching {url}...")
    js, st = fetch(url)
    if js and len(js) > 50000:
        main_js = js
        main_url = url
        print(f"   Got {len(js)} bytes")
        break

if not main_js:
    print("Could not get main JS bundle")
    # Try index bundle specifically
    for s in scripts:
        if "index" in s:
            url = "https://shalom.com.pe" + s
            js, st = fetch(url)
            if js:
                main_js = js
                main_url = url
                print(f"Found index.js: {len(js)} bytes")
                break

if not main_js:
    print("FATAL: No JS bundle found")
    sys.exit(1)

# 3. Search for agency-related data patterns
print(f"\n[3] Searching for agency data in {main_url}...")

# Look for departamentos list
dep_patterns = [
    r'departamentos["\s:=\[]+([A-ZÁÉÍÓÚÑ][^"]{3,30})',
    r'"departamento"\s*:\s*"([^"]+)"',
    r'Lima["\s,}]+(?:Arequipa|Cusco|Trujillo)',
    r'(LIMA|AREQUIPA|CUSCO|TRUJILLO|PIURA)',
]

for pat in dep_patterns:
    matches = re.findall(pat, main_js)
    if matches:
        print(f"Pattern '{pat[:40]}' -> {matches[:5]}")

# Look for agencia objects
agency_patterns = [
    r'"nombre"\s*:\s*"([^"]{5,60})"[^}]*"codigo"\s*:\s*"([^"]+)"',
    r'"agencia"\s*:\s*"([^"]{5,60})"',
    r'Shalom[^"]{0,30}(Jr\.|Av\.|Calle|Psje\.)[^"]{5,60}',
    r'"direccion"\s*:\s*"([^"]{10,100})"',
]

agencies_found = []
for pat in agency_patterns:
    matches = re.findall(pat, main_js, re.IGNORECASE)
    if matches:
        print(f"\nFound {len(matches)} items with pattern '{pat[:40]}':")
        for m in matches[:10]:
            print(f"  {m}")
        if len(matches) > 5:
            agencies_found.extend(matches)

# 4. Try to find API base URL and token
print("\n[4] Looking for API endpoints...")
api_patterns = [
    r'baseURL["\s:=]+["\']([^"\']{10,100})["\']',
    r'axios[^;]{0,100}(https?://[^"\']{10,80})',
    r'"(https?://[^"]{10,80}agencia[^"]{0,50})"',
    r'X-Proxy-Token[^;]{0,200}',
    r'X-Session-Key[^;]{0,200}',
    r'/agencias/(departamentos|provincias|distritos)',
    r'(servicesweb|shalomcontrol|api\.shalom)',
]

for pat in api_patterns:
    matches = re.findall(pat, main_js)
    if matches:
        print(f"API pattern '{pat[:50]}' -> {matches[:3]}")

print("\nDone.")
