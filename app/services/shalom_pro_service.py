"""
Servicio Conector con Shalom Pro para la emisión de Guías Oficiales.

Capacidades:
1. Mapea los datos del cliente (DNI validado, nombres completos, celular, ter_id de destino)
   junto con los datos del remitente (tu tienda/RUC) al formato estándar de Shalom Pro.
2. Soporta Modo PRODUCCIÓN: Si configuras SHALOM_PRO_API_URL y SHALOM_PRO_API_KEY,
   envía la orden al endpoint oficial de Shalom Pro para emitir la guía de remisión real.
3. Soporta Modo SIMULADOR / PRUEBAS: Si aún no ingresas tus credenciales de Shalom Pro,
   genera una pre-guía con formato idéntico de Shalom (`SHA-2026-GUIA-XXXXX`),
   calcula el flete estimado y almacena el estado para que puedas probar el flujo completo
   sin pagar ni consumir tu saldo real.
"""
from __future__ import annotations

import logging
import secrets
import string
import httpx
from typing import Dict, Any, Optional
from datetime import datetime
from app.config import settings
from app.services.id_generator import get_lima_now

logger = logging.getLogger("shalom_pro_service")

class ShalomProService:

    @classmethod
    def esta_configurado(cls) -> bool:
        """Verifica si el sistema tiene credenciales reales de Shalom Pro."""
        return bool(settings.SHALOM_PRO_API_URL and settings.SHALOM_PRO_API_KEY and settings.SHALOM_PRO_MODO == "PRODUCCION")

    @classmethod
    async def emitir_guia_oficial(
        cls, 
        envio: Dict[str, Any],
        contenido: str = "PAQUETE / MERCADERÍA",
        bultos: int = 1,
        peso_kg: float = 1.0,
        tipo_pago: str = "PAGO_EN_DESTINO",
        observaciones: str = ""
    ) -> Dict[str, Any]:
        """
        Emite la orden en Shalom Pro.
        Si está en producción, conecta con la API corporativa.
        Si está en modo simulador, genera la estructura de respuesta formal de Shalom.
        """
        now = get_lima_now()

        # Extraer ter_id numérico de la agencia seleccionada (ej: SHA-102 -> 102)
        cod_agencia = str(envio.get("codigo_agencia", "101")).replace("SHA-", "").strip()
        try:
            ter_destino_id = int(cod_agencia)
        except ValueError:
            ter_destino_id = 101

        # Construir payload canónico para Shalom Pro
        payload_shalom = {
            "remitente": {
                "tipo_documento": "RUC" if len(settings.SHALOM_PRO_RUC_REMITENTE) == 11 else "DNI",
                "numero_documento": settings.SHALOM_PRO_RUC_REMITENTE or "20123456789",
                "razon_social": settings.SHALOM_PRO_RAZON_SOCIAL,
                "telefono": settings.SHALOM_PRO_TELEFONO_REMITENTE,
                "agencia_origen_id": settings.SHALOM_PRO_AGENCIA_ORIGEN_ID
            },
            "destinatario": {
                "tipo_documento": envio.get("tipo_documento", "DNI"),
                "numero_documento": envio.get("dni"),
                "nombres": f"{envio.get('nombres', '')} {envio.get('apellido_paterno', '')} {envio.get('apellido_materno', '')}".strip(),
                "celular": envio.get("celular"),
                "agencia_destino_id": ter_destino_id,
                "nombre_agencia_destino": envio.get("nombre_agencia")
            },
            "envio": {
                "referencia_interna": envio.get("codigo_registro"),
                "contenido": contenido,
                "bultos": bultos,
                "peso_kg": peso_kg,
                "modalidad_pago": tipo_pago,  # 'PAGO_EN_DESTINO' o 'PAGADO'
                "observaciones": observaciones or f"Registrado vía Checkout Web {settings.BUSINESS_NAME}"
            }
        }

        # ----------------------------------------------------------------------
        # MODO PRODUCCIÓN: CONEXIÓN REAL CON SHALOM PRO
        # ----------------------------------------------------------------------
        if cls.esta_configurado():
            try:
                headers = {
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "Authorization": f"Bearer {settings.SHALOM_PRO_API_KEY}",
                    "X-Client-ID": settings.SHALOM_PRO_RUC_REMITENTE
                }
                url = f"{settings.SHALOM_PRO_API_URL}/v1/shipments"

                async with httpx.AsyncClient(timeout=60.0) as client:
                    resp = await client.post(url, json=payload_shalom, headers=headers)
                    if resp.status_code in (200, 201):
                        data = resp.json()
                        return {
                            "success": True,
                            "modo": "PRODUCCION",
                            "numero_guia": data.get("numero_guia", data.get("tracking_number")),
                            "serie_guia": data.get("serie_guia", "T001"),
                            "url_pdf_guia": data.get("url_pdf", f"https://pro.shalom.pe/guias/{data.get('numero_guia')}.pdf"),
                            "monto_flete": data.get("monto_flete", 15.00),
                            "estado_shalom": "ORDEN_GENERADA",
                            "mensaje": "¡Guía oficial emitida con éxito en Shalom Pro!",
                            "raw_response": data
                        }
                    else:
                        logger.error(f"Error Shalom Pro API HTTP {resp.status_code}: {resp.text}")
                        return {
                            "success": False,
                            "modo": "PRODUCCION",
                            "mensaje": f"Shalom Pro respondió con error HTTP {resp.status_code}: {resp.text[:200]}"
                        }
            except Exception as e:
                logger.error(f"Excepción conectando con Shalom Pro API: {e}")
                return {
                    "success": False,
                    "modo": "PRODUCCION",
                    "mensaje": f"No se pudo conectar con el servidor de Shalom Pro: {str(e)}"
                }

        # ----------------------------------------------------------------------
        # MODO SIMULADOR / PRE-GUÍA (Listo para cuando agregues tu acceso)
        # ----------------------------------------------------------------------
        chars = string.digits
        token_num = ''.join(secrets.choice(chars) for _ in range(7))
        numero_guia_simulada = f"SHA-{now.year}-{token_num}"
        
        # Estimación de flete según destino
        flete_base = 12.00 if envio.get("departamento") == "Lima" else 18.00

        return {
            "success": True,
            "modo": "SIMULADOR",
            "numero_guia": numero_guia_simulada,
            "serie_guia": "PR01",
            "url_pdf_guia": f"https://pro.shalom.pe/tracking?guia={numero_guia_simulada}",
            "monto_flete": flete_base,
            "estado_shalom": "PRE_GUIA_LISTA",
            "mensaje": f"Pre-guía generada exitosamente. Lista para sincronizar en Shalom Pro.",
            "datos_payload": payload_shalom
        }

    @classmethod
    def generar_excel_masivo_oficial(cls, envios: list, origen: str = "LIMA") -> bytes:
        """
        Genera el archivo Excel (.xlsx) oficial exactamente en el formato
        exigido por la plataforma Shalom Pro (pro.shalom.pe) en su módulo de Envíos Masivos.
        """
        import io
        import openpyxl
        from pathlib import Path
        
        template_path = Path(__file__).resolve().parent.parent.parent / "data" / "plantilla_oficial_shalom_pro.xlsx"
        if not template_path.exists():
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Hoja1"
            ws.append([
                "DESTINATARIO (DOC)", "TELF. DESTINATARIO", "CONTACTO (DOC)", "TELF. CONTACTO",
                "NRO GRR", "ORIGEN", "DESTINO", "MERCADERIA", "ALTO", "ANCHO", "LARGO", "PESO", "CANTIDAD"
            ])
            destinos_validos = []
        else:
            wb = openpyxl.load_workbook(template_path)
            ws = wb["Hoja1"]
            # Limpiar filas 2 a 500 para escribir los datos limpios
            for r in range(2, 501):
                ws.cell(row=r, column=1).value = None
                ws.cell(row=r, column=2).value = None
                ws.cell(row=r, column=3).value = None
                ws.cell(row=r, column=4).value = None
                ws.cell(row=r, column=5).value = None
                ws.cell(row=r, column=6).value = None
                ws.cell(row=r, column=7).value = None
                ws.cell(row=r, column=8).value = None
                ws.cell(row=r, column=13).value = None

            destinos_validos = []
            if "Hoja2" in wb.sheetnames:
                ws_h2 = wb["Hoja2"]
                destinos_validos = [str(ws_h2.cell(row=i, column=2).value).strip() for i in range(1, ws_h2.max_row+1) if ws_h2.cell(row=i, column=2).value]

        for idx, e in enumerate(envios):
            row_idx = 2 + idx
            dni_clean = "".join(filter(str.isdigit, str(e.get("dni", ""))))
            cel_clean = "".join(filter(str.isdigit, str(e.get("celular", ""))))
            nro_orden = e.get("codigo_registro", "")

            nom_agencia = str(e.get("nombre_agencia", "")).strip().upper()
            distrito = str(e.get("distrito", "")).strip().upper()

            # Encontrar la mejor coincidencia en la lista oficial de agencias de Shalom Pro
            destino_final = nom_agencia
            for d in destinos_validos:
                d_upper = d.upper()
                if nom_agencia == d_upper or nom_agencia in d_upper or d_upper in nom_agencia or distrito == d_upper or distrito in d_upper:
                    destino_final = d
                    break

            try:
                ws.cell(row=row_idx, column=1).value = int(dni_clean) if dni_clean else None
            except ValueError:
                ws.cell(row=row_idx, column=1).value = dni_clean

            try:
                ws.cell(row=row_idx, column=2).value = int(cel_clean) if cel_clean else None
            except ValueError:
                ws.cell(row=row_idx, column=2).value = cel_clean

            ws.cell(row=row_idx, column=3).value = None
            ws.cell(row=row_idx, column=4).value = None
            ws.cell(row=row_idx, column=5).value = nro_orden
            ws.cell(row=row_idx, column=6).value = origen.upper()
            ws.cell(row=row_idx, column=7).value = destino_final
            ws.cell(row=row_idx, column=8).value = "PAQUETE S"
            ws.cell(row=row_idx, column=13).value = 1

        out = io.BytesIO()
        wb.save(out)
        return out.getvalue()
