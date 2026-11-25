import httpx
import re

client = httpx.Client(headers={
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}, timeout=20.0)

r = client.get("https://pro.shalom.pe")
print("Status:", r.status_code)
scripts = re.findall(r'src=["\']([^"\']+\.js[^"\']*)["\']', r.text)
print("Scripts:", scripts)

for s in scripts:
    url = s if s.startswith("http") else f"https://pro.shalom.pe{s}"
    try:
        js_r = client.get(url)
        # Search for api endpoints, login, auth
        api_matches = re.findall(r'https?://[a-zA-Z0-9\.\-_/:]*api[a-zA-Z0-9\.\-_/:]*', js_r.text)
        auth_matches = re.findall(r'["\'](/[^"\']*login[^"\']*)["\']', js_r.text)
        endpoints = set(re.findall(r'["\'](/api/[^"\']+)["\']', js_r.text))
        print(f"\nScript: {s}")
        if api_matches:
            print("  API URLs:", list(set(api_matches))[:10])
        if auth_matches:
            print("  Auth paths:", list(set(auth_matches))[:10])
        if endpoints:
            print("  Endpoints:", list(endpoints)[:10])
    except Exception as e:
        print(f"  Error reading {s}: {e}")
