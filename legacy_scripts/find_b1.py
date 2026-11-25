import urllib.request
import re

url_js = 'https://shalom.com.pe/assets/index-57684d39.js'
content = urllib.request.urlopen(urllib.request.Request(url_js, headers={'User-Agent': 'Mozilla/5.0'})).read().decode('utf-8', errors='ignore')

# Buscar 'const b1=' o 'function b1'
m = re.search(r'b1\s*=\s*(?:async)?\s*\(?([^\)]*)\)?\s*=>', content)
if m:
    start = m.start()
    print("Definición de b1:")
    print(content[start:start+400])
else:
    # Buscar donde se define b1
    idx = content.find('b1(')
    print("b1 uso:", content[idx-100:idx+200])

# Buscar endpoints con 'https://'
for u in re.findall(r'https?://[a-zA-Z0-9_\-\.]+(?:/[a-zA-Z0-9_\-\.]+)*', content):
    if 'api' in u or 'shalom' in u:
        print("URL encontrada:", u)
