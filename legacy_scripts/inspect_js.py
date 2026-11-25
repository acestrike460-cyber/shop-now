import urllib.request
import re

url_js = 'https://shalom.com.pe/assets/index-57684d39.js'
req = urllib.request.Request(url_js, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})

try:
    with urllib.request.urlopen(req, timeout=15) as resp:
        content = resp.read().decode('utf-8', errors='ignore')
        print(f"JS descargado: {len(content)} bytes")
        
        # Buscar endpoints que contengan 'agencia', 'api', 'shalom', 'terminal'
        urls = re.findall(r'https?://[^\s"\'`<>]+', content)
        print("URLs encontradas en JS:")
        shalom_urls = [u for u in set(urls) if 'shalom' in u.lower() or 'api' in u.lower()]
        for u in shalom_urls[:20]:
            print(" ->", u)
            
        # Buscar rutas de agencias
        rutas = re.findall(r'["\'`](/[a-zA-Z0-9_\-/]*agencia[a-zA-Z0-9_\-/]*)["\'`]', content, re.I)
        print("Rutas encontradas:")
        for r in set(rutas)[:20]:
            print(" =>", r)

        # Buscar llamadas fetch o axios
        apis = re.findall(r'(?:fetch|get|post)\s*\(\s*[`\'"]([^`\'"]+)[`\'"]', content)
        print("Llamadas API:")
        for a in set(apis)[:20]:
            if 'agencia' in a or 'shalom' in a or 'api' in a:
                print(" >>", a)
except Exception as e:
    print("Error:", e)
