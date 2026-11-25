import re

with open('inspect_js.py', 'r') as f:
    pass

import urllib.request
url_js = 'https://shalom.com.pe/assets/index-57684d39.js'
content = urllib.request.urlopen(urllib.request.Request(url_js, headers={'User-Agent': 'Mozilla/5.0'})).read().decode('utf-8', errors='ignore')

# Buscar alrededor de /agencias/departamentos
idx = content.find('/agencias/departamentos')
if idx != -1:
    print("Contexto /agencias/departamentos:")
    print(content[max(0, idx-200):idx+300])

idx2 = content.find('newwebservices.shalomcontrol.com')
if idx2 != -1:
    print("Contexto newwebservices:")
    print(content[max(0, idx2-100):idx2+200])

# Buscar axios.create o baseURL
bases = re.findall(r'baseURL\s*:\s*["\'`]?([^"\'`,}]+)', content)
print("BaseURLs:", bases)
