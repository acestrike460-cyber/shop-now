import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

def _bool(name: str, default: str) -> bool:
    return os.getenv(name, default).strip().lower() in ("true", "1", "yes", "si", "sí")

class Settings:
    # Negocio e identidad
    BUSINESS_NAME: str = os.getenv("BUSINESS_NAME", "SHOP NOW")
    BUSINESS_WHATSAPP: str = os.getenv("BUSINESS_WHATSAPP", "").strip()  # Ej: 51987654321
    APP_TITLE: str = "Registro de Envíos Shalom | " + os.getenv("BUSINESS_NAME", "Tienda Express Perú")
    APP_VERSION: str = "3.1.0"
    TIMEZONE: str = "America/Lima"

    # Rutas de datos
    DATA_DIR: Path = Path(os.getenv("APP_DATA_DIR", str(BASE_DIR / "data")))
    SQLITE_PATH: Path = Path(os.getenv("APP_DB_PATH", str(DATA_DIR / "app.db")))

    # Base de datos Supabase (Opcional - con fallback transparente a SQLite local)
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "").strip()

    # Credenciales del Panel Administrativo
    ADMIN_USERNAME: str = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "Admin2026!Shalom")
    ADMIN_SECRET_KEY: str = os.getenv("ADMIN_SECRET_KEY", "shalom_envios_secret_key_2026_pe_secure_token_588392")
    COOKIE_SECURE: bool = _bool("COOKIE_SECURE", "false")

    # Verificación de identidad
    RENIEC_API_URL: str = os.getenv("RENIEC_API_URL", "").strip()
    RENIEC_TOKEN: str = os.getenv("RENIEC_TOKEN", "").strip()
    RENIEC_PROVIDER_NAME: str = os.getenv("RENIEC_PROVIDER_NAME", "Servicio autorizado de identidad").strip()
    RENIEC_TIMEOUT: float = float(os.getenv("RENIEC_TIMEOUT", "5"))
    RENIEC_SANDBOX_DEMO: bool = _bool("RENIEC_SANDBOX_DEMO", "true")
    IDENTIDAD_MAX_CONSULTAS: int = int(os.getenv("IDENTIDAD_MAX_CONSULTAS", "50"))
    IDENTIDAD_VENTANA_SEG: int = int(os.getenv("IDENTIDAD_VENTANA_SEG", "600"))

    # Catálogo de agencias Shalom
    SHALOM_API_URL: str = os.getenv("SHALOM_API_URL", "").strip()
    SHALOM_API_KEY: str = os.getenv("SHALOM_API_KEY", "").strip()
    SHALOM_API_SOURCE_NAME: str = os.getenv("SHALOM_API_SOURCE_NAME", "API autorizada de Shalom").strip()
    AGENCIAS_SOLO_DESTINO: bool = _bool("AGENCIAS_SOLO_DESTINO", "true")
    AGENCIAS_MAX_BAJA_PCT: float = float(os.getenv("AGENCIAS_MAX_BAJA_PCT", "30"))
    AGENCIAS_DIAS_VIGENCIA: int = int(os.getenv("AGENCIAS_DIAS_VIGENCIA", "30"))

    # ==========================================================================
    # INTEGRACIÓN CON SHALOM PRO (EMISIÓN AUTOMÁTICA O CON 1 CLIC)
    # ==========================================================================
    # Puedes configurar aquí tu cuenta de Shalom Pro cuando la tengas lista:
    SHALOM_PRO_MODO: str = os.getenv("SHALOM_PRO_MODO", "SIMULADOR").upper()  # 'SIMULADOR' o 'PRODUCCION'
    SHALOM_PRO_API_URL: str = os.getenv("SHALOM_PRO_API_URL", "").strip().rstrip("/")
    SHALOM_PRO_API_KEY: str = os.getenv("SHALOM_PRO_API_KEY", "").strip()
    SHALOM_PRO_RUC_REMITENTE: str = os.getenv("SHALOM_PRO_RUC_REMITENTE", "").strip()
    SHALOM_PRO_RAZON_SOCIAL: str = os.getenv("SHALOM_PRO_RAZON_SOCIAL", "MI TIENDA E-COMMERCE").strip()
    SHALOM_PRO_TELEFONO_REMITENTE: str = os.getenv("SHALOM_PRO_TELEFONO_REMITENTE", "987654321").strip()
    SHALOM_PRO_AGENCIA_ORIGEN_ID: str = os.getenv("SHALOM_PRO_AGENCIA_ORIGEN_ID", "101").strip()  # ID de agencia donde dejas paquetes

    # Registro de envíos
    DUPLICADO_VENTANA_HORAS: int = int(os.getenv("DUPLICADO_VENTANA_HORAS", "24"))
    DESPACHO_DIAS_MAX: int = int(os.getenv("DESPACHO_DIAS_MAX", "14"))

settings = Settings()
