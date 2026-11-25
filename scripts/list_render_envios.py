import httpx

client = httpx.Client(timeout=20.0)
login = client.post('https://shop-now-ew77.onrender.com/api/admin/login', json={'username': 'admin', 'password': 'admin2026'})
token = login.json()['token']
res = client.get('https://shop-now-ew77.onrender.com/api/admin/envios?estado=TODOS', headers={'Authorization': f'Bearer {token}'})
envios = res.json().get('envios', [])
print(f'Total envíos en Render: {len(envios)}')
for e in envios:
    print(f"{e.get('codigo_registro')} | DNI: {e.get('dni')} | {e.get('nombres')} {e.get('apellido_paterno')} | Agencia: {e.get('nombre_agencia')} | Estado: {e.get('estado_registro')} | Fecha: {e.get('fecha_registro')}")
