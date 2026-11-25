import urllib.request
import re

url_js = 'https://shalom.com.pe/assets/index-57684d39.js'
content = urllib.request.urlopen(urllib.request.Request(url_js, headers={'User-Agent': 'Mozilla/5.0'})).read().decode('utf-8', errors='ignore')

m = re.search(r'v7\s*=\s*l\s*=>\s*([^;]+);', content)
if m:
    print("v7:", m.group(0))
else:
    idx = content.find('v7=')
    print("v7 snippet:", content[idx:idx+200])
