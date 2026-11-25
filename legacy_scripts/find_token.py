with open('inspect_js.py', 'r') as f:
    pass

import urllib.request, re
url_js = 'https://shalom.com.pe/assets/index-57684d39.js'
content = urllib.request.urlopen(urllib.request.Request(url_js, headers={'User-Agent': 'Mozilla/5.0'})).read().decode('utf-8', errors='ignore')

# Buscar v7 =
pos = 0
for m in re.finditer(r'v7\s*=\s*', content):
    p = m.start()
    print("Match v7:", content[p:p+120])

for m in re.finditer(r'_4\s*=\s*', content):
    p = m.start()
    print("Match _4:", content[p:p+120])
