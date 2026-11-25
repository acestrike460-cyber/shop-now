#!/usr/bin/env python3
"""
Script de inicio de la aplicación Formulario Inteligente de Envíos Shalom Perú
"""
import sys
import socket
import uvicorn
from app.config import settings

def obtener_ip_local():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def main():
    ip_local = obtener_ip_local()
    print("=" * 70)
    print(f"🚀 INICIANDO {settings.APP_TITLE.upper()}")
    print("=" * 70)
    print(f"💻 En tu Computadora:           http://localhost:8000/")
    print(f"📱 En tu Celular (Android/iOS): http://{ip_local}:8000/")
    print(f"🔒 Panel Administrativo:        http://localhost:8000/admin")
    print(f"👤 Credenciales Admin:          Usuario: {settings.ADMIN_USERNAME} | Clave: {settings.ADMIN_PASSWORD}")
    print("=" * 70)
    print(f"💡 Para abrirlo desde tu celular (Android o iPhone):")
    print(f"   Conéctate a la misma red Wi-Fi y abre:")
    print(f"   👉 http://{ip_local}:8000/")
    print("=" * 70)
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )

if __name__ == "__main__":
    main()
