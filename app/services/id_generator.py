import secrets
import string
import hashlib
from datetime import datetime
import zoneinfo

def get_lima_now() -> datetime:
    """Devuelve la fecha y hora actual en zona horaria America/Lima."""
    try:
        return datetime.now(zoneinfo.ZoneInfo("America/Lima"))
    except Exception:
        return datetime.now()

def generate_codigo_registro() -> str:
    """
    Genera un código único legible de registro interno, e.g., 'SHP-2026-X9K2F'.
    Aviso explícito: Este código corresponde a la solicitud interna del negocio,
    NO debe confundirse con la guía de remisión oficial generada por Shalom.
    """
    now = get_lima_now()
    year = now.year
    chars = string.ascii_uppercase + string.digits
    # Excluir caracteres confusos (O, 0, I, 1)
    chars = chars.replace('O', '').replace('0', '').replace('I', '').replace('1', '')
    token = ''.join(secrets.choice(chars) for _ in range(5))
    return f"SHP-{year}-{token}"

def generate_idempotency_key(dni: str, codigo_agencia: str, session_seed: str = "") -> str:
    """
    Genera una clave de idempotencia determinista o por sesión
    para evitar envíos duplicados por doble clic o reintentos de red.
    """
    seed = f"{dni.strip()}:{codigo_agencia.strip()}:{session_seed.strip()}"
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()
