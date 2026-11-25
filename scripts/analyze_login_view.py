import httpx
import re

client = httpx.Client(timeout=25.0)
r = client.get("https://pro.shalom.pe/assets/LoginView-BcaBGpH0.js")
text = r.text
print("LoginView length:", len(text))

# Search for post, login, endpoints
endpoints = re.findall(r'["\'](/[^"\']+)["\']', text)
print("Endpoints in LoginView:", set(endpoints))

# Print snippets with post or submit
for m in re.finditer(r'(?:post|api|login|auth|axios|lt\.)', text, re.IGNORECASE):
    start = max(0, m.start() - 40)
    end = min(len(text), m.end() + 100)
    print(f"Context [{m.group(0)}]:", text[start:end])
    print("-" * 40)
