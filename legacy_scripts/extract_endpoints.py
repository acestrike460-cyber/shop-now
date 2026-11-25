import re

with open('inspect_js.py', 'r') as f:
    pass

# Leer el JS descargado previamente o volver a leerlo
import urllib.request
url_js = 'https://shalom.com.pe/assets/index-57684d39.js'
req = urllib.request.Request(url_js, headers={'User-Agent': 'Mozilla/5.0'})
content = urllib.request.urlopen(req).read().decode('utf-8', errors='ignore')

# Buscar todas las URLs de shalomcontrol
urls = set(re.findall(r'https?://[^\s"\'`<>]*shalomcontrol[^\s"\'`<>]*', content))
for u in urls:
    print("ShalomControl URL:", u)

# Buscar patrones de endpoints con 'agencias'
endpoints_agencia = set(re.findall(r'["\'`](/[^"\'`]*agencia[^"\'`]*)["\'`]', content, re.I))
for e in endpoints_agencia:
    print("Endpoint agencia:", e)

# Buscar baseUrl o VITE_API o similar
env_vars = set(re.findall(r'VITE_[A-Z0-9_]+', content))
print("VITE vars:", env_vars)

# Buscar cadenas como 'api/v1/'
api_v1 = set(re.findall(r'https?://[^"\'`]+api/v1/[^"\'`]+', content))
for a in api_v1:
    print("API v1:", a)
