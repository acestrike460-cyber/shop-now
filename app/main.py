import os
import csv
import io
from pathlib import Path
from typing import Optional, List
from fastapi import FastAPI, Request, Response, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.models import (
    ReniecVerificationRequest, 
    EnvioCreateRequest, 
    EnvioStatusUpdateRequest,
    EnvioTamanoUpdateRequest,
    AdminLoginRequest,
    AgenciaToggleRequest,
    AgenciaImportRequest,
    ShalomProEmitirRequest
)
from app.services.reniec_service import IdentityService
from app.services.shalom_service import ShalomService
from app.services.shalom_pro_service import ShalomProService
from app.services.id_generator import generate_codigo_registro, get_lima_now
from app.services.auth_service import (
    verify_password, 
    create_access_token, 
    verify_access_token
)
from app.database import DatabaseManager

app = FastAPI(
    title=settings.APP_TITLE,
    version=settings.APP_VERSION,
    description="Sistema inteligente de envíos Shalom Perú con catálogo nacional verificado y gestión de agencias"
)

# Inicializar Base de Datos y Catálogo
DatabaseManager.init_db()
ShalomService.cargar()

# Montar archivos estáticos y plantillas Jinja2
STATIC_DIR = Path(__file__).resolve().parent / "static"
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Dependencia para verificar sesión de administrador
async def get_current_admin(request: Request) -> dict:
    token = request.cookies.get("admin_session")
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Sesión no iniciada o token ausente"
        )
        
    payload = verify_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Sesión expirada o token inválido"
        )
    return payload

# ==============================================================================
# RUTAS PÚBLICAS Y VISTAS HTML
# ==============================================================================

@app.get("/", response_class=HTMLResponse)
async def view_form(request: Request):
    """Página principal: Formulario moderno para clientes."""
    departamentos = ShalomService.get_departamentos()
    return templates.TemplateResponse(
        request=request,
        name="form.html",
        context={
            "business_name": settings.BUSINESS_NAME,
            "departamentos": departamentos,
            "reniec_sandbox": settings.RENIEC_SANDBOX_DEMO
        }
    )

@app.get("/registro/exito/{codigo}", response_class=HTMLResponse)
async def view_success(codigo: str, request: Request):
    """Pantalla de confirmación y resumen ordenado del registro para enviar por WhatsApp."""
    envio = DatabaseManager.obtener_envio_por_codigo(codigo)
    if not envio:
        return RedirectResponse(url="/?error=registro_no_encontrado")

    # Armar mensaje estructurado y ordenado con todas las elecciones previas del cliente
    nombre_completo = f"{envio.get('nombres', '')} {envio.get('apellido_paterno', '')} {envio.get('apellido_materno', '')}".strip()
    tipo_doc = envio.get('tipo_documento') or 'DNI'
    doc_num = envio.get('dni', '')
    celular = envio.get('celular', '')
    agencia = envio.get('nombre_agencia', '')
    codigo_ag = envio.get('codigo_agencia', '')
    direccion = envio.get('direccion_agencia', '')
    referencia = envio.get('referencia_agencia', '')
    distrito = envio.get('distrito', '')
    provincia = envio.get('provincia', '')
    departamento = envio.get('departamento', '')
    fecha_despacho = envio.get('fecha_despacho', '')
    codigo_registro = envio.get('codigo_registro', '')

    lineas = [
        f"📦 *NUEVO REGISTRO DE ENVÍO SHALOM*",
        f"🏷️ *Código:* #{codigo_registro}",
        f"━━━━━━━━━━━━━━━━━━━",
        f"👤 *DATOS DEL DESTINATARIO*",
        f"• *Nombre completo:* {nombre_completo}",
        f"• *Documento:* {tipo_doc} {doc_num}",
        f"• *Celular:* +51 {celular}",
        f"━━━━━━━━━━━━━━━━━━━",
        f"🏢 *AGENCIA SHALOM DE DESTINO*",
        f"• *Agencia:* {agencia} (Cód: {codigo_ag})",
        f"• *Dirección:* {direccion}",
    ]

    if referencia:
        lineas.append(f"• *Referencia:* {referencia}")

    lineas.append(f"• *Ubicación:* {distrito}, {provincia}, {departamento}")

    if fecha_despacho:
        lineas.extend([
            f"━━━━━━━━━━━━━━━━━━━",
            f"📅 *Día programado de despacho:* {fecha_despacho}"
        ])

    base_url = str(request.base_url).rstrip("/")
    if "onrender.com" in base_url and base_url.startswith("http://"):
        base_url = base_url.replace("http://", "https://")
    tracking_url = f"{base_url}/seguimiento/{codigo_registro}"

    lineas.extend([
        f"━━━━━━━━━━━━━━━━━━━",
        f"💬 *Estado:* Esperando coordinación de pago y despacho con la tienda.",
        f"🔍 *Link de seguimiento en vivo:* {tracking_url}"
    ])

    mensaje_whatsapp = "\n".join(lineas)
    
    # Número de destino (si está configurado en .env o vacío para abrir selector de chat)
    num_wa = settings.BUSINESS_WHATSAPP.replace("+", "").replace(" ", "").strip()
    from urllib.parse import quote
    if num_wa:
        whatsapp_link = f"https://api.whatsapp.com/send?phone={num_wa}&text={quote(mensaje_whatsapp)}"
    else:
        whatsapp_link = f"https://api.whatsapp.com/send?text={quote(mensaje_whatsapp)}"

    return templates.TemplateResponse(
        request=request,
        name="success.html",
        context={
            "business_name": settings.BUSINESS_NAME,
            "envio": envio,
            "mensaje_whatsapp": mensaje_whatsapp,
            "whatsapp_link": whatsapp_link,
            "tracking_url": tracking_url
        }
    )

@app.get("/seguimiento/{codigo}", response_class=HTMLResponse)
@app.get("/tracking/{codigo}", response_class=HTMLResponse)
async def view_tracking(codigo: str, request: Request):
    """Página interactiva de seguimiento para los clientes."""
    envio = DatabaseManager.obtener_envio_por_codigo(codigo)
    if not envio:
        return RedirectResponse(url="/?error=envio_no_encontrado")

    num_wa = settings.BUSINESS_WHATSAPP.replace("+", "").replace(" ", "").strip()
    msg = f"Hola {settings.BUSINESS_NAME}, tengo una consulta sobre mi envío #{envio.get('codigo_registro')} a Shalom {envio.get('nombre_agencia')}."
    from urllib.parse import quote
    if num_wa:
        wa_link = f"https://api.whatsapp.com/send?phone={num_wa}&text={quote(msg)}"
    else:
        wa_link = f"https://api.whatsapp.com/send?text={quote(msg)}"

    base_url = str(request.base_url).rstrip("/")
    if "onrender.com" in base_url and base_url.startswith("http://"):
        base_url = base_url.replace("http://", "https://")
    tracking_url = f"{base_url}/seguimiento/{envio.get('codigo_registro')}"

    return templates.TemplateResponse(
        request=request,
        name="tracking.html",
        context={
            "business_name": settings.BUSINESS_NAME,
            "envio": envio,
            "whatsapp_tienda_link": wa_link,
            "tracking_url": tracking_url
        }
    )

@app.get("/api/seguimiento/{codigo}")
async def api_seguimiento_detalle(codigo: str):
    """API JSON pública para consultar el estado en tiempo real de un envío."""
    envio = DatabaseManager.obtener_envio_por_codigo(codigo)
    if not envio:
        raise HTTPException(status_code=404, detail="Envío no encontrado")
    return {
        "success": True,
        "codigo_registro": envio.get("codigo_registro"),
        "estado_registro": envio.get("estado_registro"),
        "destinatario": f"{envio.get('nombres')} {envio.get('apellido_paterno')}",
        "agencia_destino": envio.get("nombre_agencia"),
        "direccion_agencia": envio.get("direccion_agencia"),
        "numero_guia_shalom": envio.get("numero_guia_shalom"),
        "url_guia_pdf": envio.get("url_guia_pdf"),
        "fecha_registro": envio.get("fecha_registro"),
        "updated_at": envio.get("updated_at")
    }

# ==============================================================================
# APIS PARA RENIEC Y VALIDACIONES
# ==============================================================================

@app.post("/api/reniec/consultar")
async def consultar_reniec(body: ReniecVerificationRequest, request: Request):
    """
    Consulta autorizada de identidad en RENIEC / ID Perú según normativa legal.
    Requiere consentimiento previo del titular. Si no hay credenciales, orienta al llenado manual.
    """
    client_ip = request.client.host if request.client else "127.0.0.1"
    resultado = await IdentityService.consultar_identidad_autorizada(
        dni=body.dni,
        consentimiento_titular=body.consentimiento_titular,
        ip_cliente=client_ip
    )
    return resultado

# ==============================================================================
# APIS PARA SELECCIÓN INTELIGENTE DE AGENCIAS SHALOM
# ==============================================================================

@app.get("/api/agencias/departamentos")
async def get_departamentos():
    """Devuelve la lista de departamentos que cuentan con agencias activas."""
    return {"departamentos": ShalomService.get_departamentos()}

@app.get("/api/agencias/provincias")
async def get_provincias(departamento: str = Query(..., description="Nombre del departamento")):
    """Devuelve las provincias pertenecientes a un departamento."""
    return {"provincias": ShalomService.get_provincias(departamento)}

@app.get("/api/agencias/distritos")
async def get_distritos(
    departamento: str = Query(...),
    provincia: str = Query(...)
):
    """Devuelve los distritos pertenecientes a una provincia y departamento."""
    return {"distritos": ShalomService.get_distritos(departamento, provincia)}

@app.get("/api/agencias/lista")
async def get_agencias(
    departamento: str = Query(...),
    provincia: str = Query(...),
    distrito: Optional[str] = Query(None)
):
    """Devuelve las agencias disponibles para la cascada territorial seleccionada."""
    agencias = ShalomService.get_agencias(departamento, provincia, distrito)
    return {"agencias": [ShalomService.vista_publica(a) for a in agencias], "total": len(agencias)}

@app.get("/api/agencias/arbol")
async def get_arbol_agencias():
    """Devuelve la jerarquía completa departamento > provincia > distrito con conteos para selectores rápidos."""
    return {"arbol": ShalomService.get_arbol()}

@app.get("/api/agencias/buscar")
async def search_agencias(
    q: str = Query(..., min_length=2),
    departamento: Optional[str] = None,
    provincia: Optional[str] = None,
    distrito: Optional[str] = None
):
    """Buscador predictivo inteligente (insensible a mayúsculas, minúsculas, tildes, con alias y tolerancia a tipeo)."""
    resultados = ShalomService.buscar_agencias_inteligente(
        query=q, limite=30, departamento=departamento, provincia=provincia, distrito=distrito
    )
    return {"query": q, "total": len(resultados), "resultados": resultados}

@app.get("/api/agencias/sugerencias")
async def get_sugerencias(q: str = Query(..., min_length=2)):
    """Autocompletado combinado: ubicaciones (distritos) y agencias específicas."""
    return ShalomService.sugerencias(q)

@app.get("/api/agencias/cercanas")
async def get_agencias_cercanas(
    lat: float = Query(...),
    lng: float = Query(...),
    limite: int = Query(15, ge=1, le=50)
):
    """Devuelve las agencias más cercanas calculadas por distancia geodésica."""
    return {"cercanas": ShalomService.agencias_cercanas(lat, lng, limite)}

@app.get("/api/agencias/all")
async def get_all_agencias():
    """Devuelve el catálogo completo de agencias activas y publicables para carga inicial del frontend."""
    agencias = ShalomService.cargar_agencias()
    return {
        "total": len(agencias), 
        "version": ShalomService.huella_publica(),
        "agencias": [ShalomService.vista_publica(a) for a in agencias]
    }

@app.get("/api/agencias/{agencia_id}")
async def get_agencia_detail(agencia_id: str):
    """Obtiene el detalle completo de una agencia por su ID."""
    agencia = ShalomService.get_agencia_por_id(agencia_id, incluir_inactivas=True)
    if not agencia:
        raise HTTPException(status_code=404, detail="Agencia no encontrada")
    return agencia

# ==============================================================================
# API PARA REGISTRO DE ENVÍOS
# ==============================================================================

@app.post("/api/envios/registrar")
async def registrar_envio(payload: EnvioCreateRequest, request: Request):
    """
    Registra los datos del cliente y la agencia seleccionada.
    Genera un código único de registro interno y aplica control estricto de idempotencia.
    """
    client_ip = request.client.host if request.client else ""
    user_agent = request.headers.get("user-agent", "")

    # Validar que la agencia elegida sea válida
    agencia = ShalomService.get_agencia_por_id(payload.codigo_agencia, incluir_inactivas=True)
    if agencia:
        agencia_nombre = agencia["nombre"]
        direccion_final = agencia["direccion"]
        referencia_final = agencia.get("referencia", "") or payload.referencia_agencia or ""
        dep_final = agencia["departamento"]
        prov_final = agencia["provincia"]
        dist_final = agencia["distrito"]
    else:
        agencia_nombre = payload.nombre_agencia
        direccion_final = payload.direccion_agencia
        referencia_final = payload.referencia_agencia or ""
        dep_final = payload.departamento
        prov_final = payload.provincia
        dist_final = payload.distrito

    codigo_reg = generate_codigo_registro()

    datos = {
        "codigo_registro": codigo_reg,
        "tipo_documento": payload.tipo_documento,
        "dni": payload.dni,
        "nombres": payload.nombres,
        "apellido_paterno": payload.apellido_paterno,
        "apellido_materno": payload.apellido_materno,
        "celular": payload.celular,
        "departamento": dep_final,
        "provincia": prov_final,
        "distrito": dist_final,
        "codigo_agencia": payload.codigo_agencia,
        "nombre_agencia": agencia_nombre,
        "direccion_agencia": direccion_final,
        "referencia_agencia": referencia_final,
        "fecha_despacho": payload.fecha_despacho or "",
        "estado_verificacion_identidad": payload.estado_verificacion_identidad,
        "estado_registro": "PENDIENTE",
        "idempotency_key": payload.idempotency_key,
        "ip_origen": client_ip,
        "user_agent": user_agent
    }

    resultado = await DatabaseManager.crear_envio(datos)
    registro_final = resultado["registro"]

    return {
        "success": True,
        "duplicado": resultado["duplicado"],
        "mensaje": "¡Registro exitoso! Tus datos han sido registrados correctamente para la coordinación de tu envío mediante Shalom.",
        "codigo_registro": registro_final["codigo_registro"],
        "aviso_legal": "Este código es un identificador interno de nuestro negocio para coordinar tu paquete, no es la guía oficial de Shalom.",
        "redirect_url": f"/registro/exito/{registro_final['codigo_registro']}"
    }

# ==============================================================================
# PANEL ADMINISTRATIVO PRIVADO
# ==============================================================================

@app.get("/admin/login", response_class=HTMLResponse)
async def admin_login_view(request: Request):
    """Página de inicio de sesión para el personal autorizado."""
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "business_name": settings.BUSINESS_NAME
        }
    )

@app.post("/api/admin/login")
async def admin_login_action(credentials: AdminLoginRequest, response: Response):
    """Autentica las credenciales de administración y emite una cookie HTTPOnly."""
    valido = False
    if credentials.username == settings.ADMIN_USERNAME:
        if verify_password(credentials.password, settings.ADMIN_PASSWORD):
            valido = True
        elif credentials.password == settings.ADMIN_PASSWORD:
            valido = True

    if not valido:
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")

    token = create_access_token(credentials.username)
    response.set_cookie(
        key="admin_session",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=86400,
        secure=settings.COOKIE_SECURE
    )
    return {"success": True, "token": token, "redirect_url": "/admin"}

@app.get("/admin/logout")
async def admin_logout(response: Response):
    """Cierra la sesión administrativa."""
    res = RedirectResponse(url="/admin/login")
    res.delete_cookie("admin_session")
    return res

@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard_view(request: Request):
    """Panel de administración principal."""
    try:
        await get_current_admin(request)
    except HTTPException:
        return RedirectResponse(url="/admin/login")

    metricas = DatabaseManager.obtener_metricas()
    envios = DatabaseManager.obtener_envios(limite=50)
    estado_cat = ShalomService.estado_catalogo()

    return templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={
            "business_name": settings.BUSINESS_NAME,
            "metricas": metricas,
            "envios": envios,
            "estado_catalogo": estado_cat,
            "total_agencias": estado_cat["publicas"],
            "shalom_pro_modo": settings.SHALOM_PRO_MODO,
            "shalom_pro_configurado": ShalomProService.esta_configurado(),
            "shalom_pro_ruc": settings.SHALOM_PRO_RUC_REMITENTE
        }
    )

@app.get("/api/admin/envios")
async def api_admin_envios(
    estado: Optional[str] = "TODOS",
    q: Optional[str] = None,
    admin: dict = Depends(get_current_admin)
):
    """Endpoint JSON para filtrado dinámico en la tabla administrativa."""
    envios = DatabaseManager.obtener_envios(filtro_estado=estado, busqueda=q, limite=100)
    return {"envios": envios, "total": len(envios)}

@app.put("/api/admin/envios/{id_envio}/estado")
async def api_admin_update_envio(
    id_envio: str,
    payload: EnvioStatusUpdateRequest,
    admin: dict = Depends(get_current_admin)
):
    """Permite al operador cambiar el estado del envío."""
    exito = DatabaseManager.actualizar_estado_envio(
        id_envio=id_envio,
        nuevo_estado=payload.estado_registro,
        notas_admin=payload.notas_admin
    )
    if not exito:
        raise HTTPException(status_code=404, detail="Envío no encontrado")
    return {"success": True, "mensaje": f"Estado actualizado a {payload.estado_registro}"}

@app.put("/api/admin/envios/{id_envio}/tamano")
async def api_admin_update_envio_tamano(
    id_envio: str,
    payload: EnvioTamanoUpdateRequest,
    admin: dict = Depends(get_current_admin)
):
    """Permite al operador cambiar el tamaño del paquete de un envío fácilmente (SOBRE, PAQUETE XXS, PAQUETE XS, PAQUETE S, etc.)."""
    exito = DatabaseManager.actualizar_tamano_envio(
        id_envio=id_envio,
        nuevo_tamano=payload.tamano_paquete
    )
    if not exito:
        raise HTTPException(status_code=404, detail="Envío no encontrado")
    return {
        "success": True, 
        "tamano_paquete": payload.tamano_paquete, 
        "mensaje": f"Tamaño actualizado a {payload.tamano_paquete}"
    }

@app.delete("/api/admin/envios/{id_envio}")
async def api_admin_eliminar_envio(
    id_envio: str,
    admin: dict = Depends(get_current_admin)
):
    """Permite al operador eliminar permanentemente un registro de envío."""
    envio = DatabaseManager.obtener_envio_por_codigo(id_envio)
    if not envio:
        raise HTTPException(status_code=404, detail="Envío no encontrado")
    
    exito = DatabaseManager.eliminar_envio(id_envio)
    if not exito:
        raise HTTPException(status_code=500, detail="No se pudo eliminar el registro de envío")
    
    return {
        "success": True,
        "mensaje": f"Envío {envio.get('codigo_registro')} eliminado permanentemente"
    }

@app.post("/api/admin/envios/{id_envio}/emitir-shalom-pro")
async def api_admin_emitir_guia_shalom_pro(
    id_envio: str,
    payload: Optional[ShalomProEmitirRequest] = None,
    admin: dict = Depends(get_current_admin)
):
    """
    Emite la guía oficial en Shalom Pro (o pre-guía en modo simulador si no hay API key aún).
    Actualiza automáticamente el número de guía, flete, enlace y estado en la base de datos.
    """
    envio = DatabaseManager.obtener_envio_por_codigo(id_envio)
    if not envio:
        raise HTTPException(status_code=404, detail="Registro de envío no encontrado")

    contenido = payload.contenido_paquete if payload else "PAQUETE / MERCADERÍA"
    bultos = payload.bultos if payload else 1
    peso_kg = payload.peso_kg if payload else 1.0
    tipo_pago = payload.tipo_pago if payload else "PAGO_EN_DESTINO"
    observaciones = payload.observaciones if payload else ""

    resultado = await ShalomProService.emitir_guia_oficial(
        envio=envio,
        contenido=contenido,
        bultos=bultos,
        peso_kg=peso_kg,
        tipo_pago=tipo_pago,
        observaciones=observaciones
    )

    if not resultado.get("success"):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=resultado.get("mensaje", "Error al emitir guía en Shalom Pro")
        )

    # Actualizar en la base de datos
    DatabaseManager.actualizar_guia_shalom_pro(
        id_envio=envio["id"],
        numero_guia=resultado["numero_guia"],
        url_pdf=resultado.get("url_pdf_guia", ""),
        monto_flete=float(resultado.get("monto_flete", 0.0)),
        estado_shalom=resultado.get("estado_shalom", "EMITIDO")
    )

    return resultado

@app.get("/api/admin/shalom-pro/estado")
async def api_admin_shalom_pro_estado(admin: dict = Depends(get_current_admin)):
    """Informa sobre el estado actual de la integración con Shalom Pro."""
    return {
        "modo": settings.SHALOM_PRO_MODO,
        "configurado": ShalomProService.esta_configurado(),
        "ruc_remitente": settings.SHALOM_PRO_RUC_REMITENTE,
        "razon_social": settings.SHALOM_PRO_RAZON_SOCIAL,
        "api_url": settings.SHALOM_PRO_API_URL or "https://api.pro.shalom.pe"
    }

@app.get("/api/admin/envios/exportar")
async def api_admin_exportar_csv(admin: dict = Depends(get_current_admin)):
    """Exporta todos los registros de envío en formato CSV compatible con Excel."""
    envios = DatabaseManager.obtener_envios(limite=10000)
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')

    # Encabezados
    writer.writerow([
        "Código Registro", "Tipo Doc", "DNI/Doc", "Nombres", "Apellido Paterno", "Apellido Materno",
        "Celular", "Departamento", "Provincia", "Distrito", "Código Agencia",
        "Nombre Agencia", "Dirección Agencia", "Referencia", "Fecha Despacho", "Verificación RENIEC",
        "Estado Envío", "Fecha Registro (Lima)", "Notas Admin"
    ])

    for e in envios:
        writer.writerow([
            e.get("codigo_registro", ""),
            e.get("tipo_documento", "DNI"),
            e.get("dni", ""),
            e.get("nombres", ""),
            e.get("apellido_paterno", ""),
            e.get("apellido_materno", ""),
            e.get("celular", ""),
            e.get("departamento", ""),
            e.get("provincia", ""),
            e.get("distrito", ""),
            e.get("codigo_agencia", ""),
            e.get("nombre_agencia", ""),
            e.get("direccion_agencia", ""),
            e.get("referencia_agencia", ""),
            e.get("fecha_despacho", ""),
            e.get("estado_verificacion_identidad", ""),
            e.get("estado_registro", ""),
            e.get("fecha_registro", ""),
            e.get("notas_admin", "")
        ])

    output.seek(0)
    filename = f"envios_shalom_{get_lima_now().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8-sig")),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@app.get("/api/admin/envios/exportar-shalom-pro")
async def api_admin_exportar_plantilla_shalom_pro(
    solo_pendientes: bool = Query(True),
    tamano_defecto: str = Query("PAQUETE XS"),
    admin: dict = Depends(get_current_admin)
):
    """
    Exporta los pedidos en el archivo Excel oficial (.xlsx) de Shalom Pro (Formato-Pro-Masivo.xlsx).
    Listo para arrastrar directamente en pro.shalom.pe sin errores de formato.
    """
    filtro = "PENDIENTE" if solo_pendientes else "TODOS"
    envios = DatabaseManager.obtener_envios(filtro_estado=filtro, limite=5000)
    
    excel_bytes = ShalomProService.generar_excel_masivo_oficial(envios, tamano_defecto=tamano_defecto)
    tipo_nombre = "pendientes" if solo_pendientes else "todos"
    filename = f"Formato-Pro-Masivo-{tipo_nombre}_{get_lima_now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    
    return StreamingResponse(
        io.BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

# ------------------------------------------------------------------------------
# ENDPOINTS ADMINISTRATIVOS DE GESTIÓN DE AGENCIAS
# ------------------------------------------------------------------------------

@app.get("/api/admin/shalom/estado")
async def api_admin_shalom_estado(admin: dict = Depends(get_current_admin)):
    """Devuelve el estado, metadatos y vigencia del catálogo de agencias."""
    return ShalomService.estado_catalogo()

@app.get("/api/admin/shalom/agencias")
async def api_admin_shalom_agencias(
    q: str = "",
    estado: str = "todas",
    admin: dict = Depends(get_current_admin)
):
    """Lista las agencias para el panel administrativo, con búsqueda y estado."""
    return {"agencias": ShalomService.listar_admin(q=q, estado=estado, limite=100)}

@app.put("/api/admin/shalom/agencias/{agencia_id}/estado")
async def api_admin_toggle_agencia(
    agencia_id: str,
    payload: AgenciaToggleRequest,
    admin: dict = Depends(get_current_admin)
):
    """Activa o desactiva manualmente una agencia (override administrativo persistente)."""
    agencia = ShalomService.cambiar_estado_agencia(
        agencia_id=agencia_id,
        activo=payload.activo,
        motivo=payload.motivo or "",
        usuario=admin.get("sub", "admin")
    )
    if not agencia:
        raise HTTPException(status_code=404, detail="Agencia no encontrada")
    return {"success": True, "agencia": agencia, "mensaje": "Estado de agencia actualizado."}

@app.delete("/api/admin/shalom/agencias/{agencia_id}/override")
async def api_admin_quitar_override(
    agencia_id: str,
    admin: dict = Depends(get_current_admin)
):
    """Elimina el override manual de una agencia para restaurar su estado original de la fuente."""
    exito = ShalomService.quitar_override(agencia_id)
    if not exito:
        raise HTTPException(status_code=404, detail="No existe override manual para esta agencia")
    return {"success": True, "mensaje": "Override eliminado. Estado restaurado a la fuente."}

@app.post("/api/admin/shalom/importar")
async def api_admin_importar_catalogo(
    payload: AgenciaImportRequest,
    admin: dict = Depends(get_current_admin)
):
    """Importa un archivo JSON o CSV entregado por canales oficiales de Shalom."""
    resultado = ShalomService.importar_contenido(
        contenido=payload.contenido,
        formato=payload.formato or "auto",
        fuente=payload.fuente or "Archivo oficial importado desde el panel",
        usuario=admin.get("sub", "admin"),
        dry_run=payload.dry_run,
        forzar=payload.forzar
    )
    return resultado

@app.post("/api/admin/shalom/sincronizar")
async def api_admin_sync_shalom(
    dry_run: bool = Query(False),
    forzar: bool = Query(False),
    admin: dict = Depends(get_current_admin)
):
    """Sincroniza el catálogo de agencias con la API autorizada de Shalom si está configurada."""
    res = await ShalomService.sincronizar_proveedor_externo(
        dry_run=dry_run,
        forzar=forzar,
        usuario=admin.get("sub", "admin")
    )
    return res
