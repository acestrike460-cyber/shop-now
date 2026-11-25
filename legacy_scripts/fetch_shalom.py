import urllib.request
import json
import re

url = 'https://shalom.com.pe/agencias'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})

try:
    with urllib.request.urlopen(req, timeout=10) as resp:
        html = resp.read().decode('utf-8', errors='ignore')
        print(f"HTML recibido. Tamaño: {len(html)} bytes")
        
        # Buscar scripts de Next.js u otros
        scripts = re.findall(r'<script[^>]*src=[\'"]([^\'"]+)[\'"]', html)
        print("Scripts encontrados:", len(scripts))
        for s in scripts[:10]:
            print(" -", s)
            
        # Buscar si hay __NEXT_DATA__
        next_data_match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
        if next_data_match:
            data = json.loads(next_data_match.group(1))
            print("Next.js Data keys:", list(data.keys()))
            props = data.get('props', {}).get('pageProps', {})
            print("pageProps keys:", list(props.keys()))
            with open('next_props.json', 'w', encoding='utf-8') as f:
                json.dump(props, f, ensure_ascii=False, indent=2)
            print("Guardado props en next_props.json")
        else:
            print("No se encontró __NEXT_DATA__ directamente.")
            # Buscar menciones a agencias o endpoints en el html
            matches = re.findall(r'agencia', html, re.I)
            print(f"Menciones a 'agencia': {len(matches)}")
except Exception as e:
    print("Error:", e)
