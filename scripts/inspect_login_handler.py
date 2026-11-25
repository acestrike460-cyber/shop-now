import httpx

client = httpx.Client(timeout=25.0)
r = client.get("https://pro.shalom.pe/assets/LoginView-BcaBGpH0.js")
text = r.text

idx = text.find('/auth/login')
print(text[max(0, idx-50):min(len(text), idx+500)])
