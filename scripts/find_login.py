import httpx
import re

client = httpx.Client(timeout=25.0)
r = client.get("https://pro.shalom.pe/assets/index-J0FQK8vM.js")
text = r.text

idx = text.find('"/login"')
while idx != -1:
    print("MATCH AT:", idx)
    print(text[max(0, idx-50):min(len(text), idx+150)])
    print("-" * 50)
    idx = text.find('"/login"', idx + 1)

# Find all asset chunks imported
chunks = re.findall(r'import\("([^"]+)"\)', text)
print("Imported chunks:", chunks[:10])

# Find axios / http requests
post_calls = re.findall(r'\.post\("([^"]+)"', text)
print("POST endpoints:", set(post_calls))
