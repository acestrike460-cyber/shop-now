import hashlib
import hmac
import time
import json
import base64
from app.config import settings

def hash_password(password: str, salt: str = "shalom_envios_salt_2026") -> str:
    """Hashea una contraseña usando PBKDF2-HMAC-SHA256."""
    return hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000
    ).hex()

def verify_password(plain_password: str, hashed_password: str, salt: str = "shalom_envios_salt_2026") -> bool:
    """Verifica si la contraseña ingresada coincide con el hash almacenado."""
    candidate_hash = hash_password(plain_password, salt)
    return hmac.compare_digest(candidate_hash, hashed_password)

def create_access_token(username: str, expires_in_seconds: int = 86400) -> str:
    """Crea un token JWT/HMAC firmado con expiración segura de 24 horas."""
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": username,
        "exp": int(time.time()) + expires_in_seconds,
        "iat": int(time.time()),
        "iss": "shalom-envios-pe"
    }
    
    header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip('=')
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip('=')
    
    signature = hmac.new(
        settings.ADMIN_SECRET_KEY.encode('utf-8'),
        f"{header_b64}.{payload_b64}".encode('utf-8'),
        hashlib.sha256
    ).digest()
    sig_b64 = base64.urlsafe_b64encode(signature).decode().rstrip('=')
    
    return f"{header_b64}.{payload_b64}.{sig_b64}"

def verify_access_token(token: str) -> dict | None:
    """Verifica la validez y firma del token de acceso administrativo."""
    try:
        parts = token.split('.')
        if len(parts) != 3:
            return None
        header_b64, payload_b64, sig_b64 = parts
        
        expected_sig = hmac.new(
            settings.ADMIN_SECRET_KEY.encode('utf-8'),
            f"{header_b64}.{payload_b64}".encode('utf-8'),
            hashlib.sha256
        ).digest()
        
        sig_padded = sig_b64 + '=' * (-len(sig_b64) % 4)
        received_sig = base64.urlsafe_b64decode(sig_padded.encode())
        
        if not hmac.compare_digest(expected_sig, received_sig):
            return None
            
        payload_padded = payload_b64 + '=' * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_padded.encode()).decode())
        
        if payload.get("exp", 0) < int(time.time()):
            return None # Expirado
            
        return payload
    except Exception:
        return None
