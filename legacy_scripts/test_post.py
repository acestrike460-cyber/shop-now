import urllib.request
import json

endpoints = [
    ('https://shalom.com.pe/agencias/departamentos', {}),
    ('https://shalom.com.pe/agencias', {})
]

for url, data in endpoints:
    try:
        req = urllib.request.Request(
            url, 
            data=json.dumps(data).encode('utf-8'),
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
                'Content-Type': 'application/json',
                'Referer': 'https://shalom.com.pe/agencias'
            }
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            res_data = json.loads(resp.read().decode('utf-8'))
            print("URL:", url, "Status:", resp.status)
            print("Data preview:", str(res_data)[:300])
    except Exception as e:
        print("URL:", url, "Error:", e)
