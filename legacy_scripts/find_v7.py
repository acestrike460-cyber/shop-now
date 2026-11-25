import urllib.request
import re

url_js = 'https://shalom.com.pe/assets/index-57684d39.js'
content = urllib.request.urlopen(urllib.request.Request(url_js, headers={'User-Agent': 'Mozilla/5.0'})).read().decode('utf-8', errors='ignore')

m = re.search(r'v7\s*=\s*l\s*=>', content)
if m:
    print(content[m.start():m.start()+200])

m2 = re.search(r'R5\s*=\s*', content)
if m2:
    print(content[m2.start():m2.start()+200])
