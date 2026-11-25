import sys
sys.path.insert(0, ".")
from app.database import DatabaseManager

locales = DatabaseManager.obtener_envios(limite=50)
print(f"Total locales: {len(locales)}")
for e in locales:
    print(f"{e.get('codigo_registro')} | DNI: {e.get('dni')} | {e.get('nombres')} {e.get('apellido_paterno')}")
