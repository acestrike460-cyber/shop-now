import httpx
import re

client = httpx.Client(timeout=25.0)
r = client.get("https://pro.shalom.pe/assets/index-J0FQK8vM.js")
text = r.text

print("Bundle length:", len(text))

# Search for API base URL
base_urls = re.findall(r'(https?://[a-zA-Z0-9\.\-]+(?:shalom|api)[a-zA-Z0-9\.\-_/]*)', text)
print("Base URLs found:", set(base_urls))

# Search for login endpoint
login_contexts = re.findall(r'.{0,50}/login.{0,50}', text)
for c in login_contexts[:5]:
    print("Login context:", c)

# Search for login payload keys (email, password, etc)
auth_funcs = re.findall(r'["\']?(?:email|usuario|password|clave|token)["\']?\s*:', text)
print("Auth keys sample:", auth_funcs[:10])
