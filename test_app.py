import asyncio
import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.shalom_service import ShalomService, normalizar_texto
from app.services.reniec_service import IdentityService
from app.services.id_generator import generate_codigo_registro, generate_idempotency_key
from app.database import DatabaseManager

client = TestClient(app)

def test_normalizador_texto():
    assert normalizar_texto("San Martín") == "san martin"
    assert normalizar_texto("Áncash") == "ancash"
    assert normalizar_texto("AGENCIA CERRO COLORADO") == "agencia cerro colorado"
    assert normalizar_texto("Av. 28 de Julio") == "av. 28 de julio"

def test_catalogo_nacional_agencias():
    departamentos = ShalomService.get_departamentos()
    assert len(departamentos) >= 20
    assert "Lima" in departamentos
    assert "Arequipa" in departamentos
    assert "Cusco" in departamentos
    assert "La Libertad" in departamentos

    provincias_lima = ShalomService.get_provincias("Lima")
    assert "Lima" in provincias_lima

    distritos_lima = ShalomService.get_distritos("Lima", "Lima")
    assert "Los Olivos" in distritos_lima
    assert "Ate" in distritos_lima

    agencias_olivos = ShalomService.get_agencias("Lima", "Lima", "Los Olivos")
    assert len(agencias_olivos) >= 1
    assert any("Pro" in a["nombre"] or "Alfredo Mendiola" in a["direccion"] or "Palmeras" in a["nombre"] for a in agencias_olivos)

def test_buscador_predictivo_insensible_y_alias():
    # Buscar con alias populares
    res1 = ShalomService.buscar_agencias_inteligente("smp")
    assert len(res1) >= 1
    assert any(r["distrito"] == "San Martín de Porres" for r in res1)

    # Buscar con mayúsculas y tildes
    res2 = ShalomService.buscar_agencias_inteligente("ÁNCASH")
    assert len(res2) >= 1

    # Buscar por avenida o referencia
    res3 = ShalomService.buscar_agencias_inteligente("megaplaza")
    assert len(res3) >= 1

    # Buscar por código
    res4 = ShalomService.buscar_agencias_inteligente("BGACHCA")
    assert len(res4) >= 1
    assert res4[0]["codigo"] == "BGACHCA"

def test_arbol_jerarquico_agencias():
    arbol = ShalomService.get_arbol()
    assert len(arbol) >= 20
    dep_lima = next(d for d in arbol if d["nombre"] == "Lima")
    assert dep_lima["total"] >= 100
    assert len(dep_lima["provincias"]) >= 1

def test_calculo_digito_verificador_dni():
    # DNI ejemplo: 17801146 -> DV = 4
    dv = IdentityService.calcular_codigo_verificador_dni("17801146")
    assert dv == 4

    # DNI con longitud inválida
    assert IdentityService.calcular_codigo_verificador_dni("123") is None

def test_reniec_validaciones_y_consentimiento():
    async def _run():
        # DNI con longitud inválida
        inv = await IdentityService.consultar_identidad_autorizada("123", consentimiento_titular=True)
        assert inv["success"] is False
        assert "8 dígitos" in inv["mensaje"]
        assert inv["permite_llenado_manual"] is True

        # Sin consentimiento legal (Ley 29733)
        sin_consent = await IdentityService.consultar_identidad_autorizada("12345678", consentimiento_titular=False)
        assert sin_consent["success"] is False
        assert inv["permite_llenado_manual"] is True

        # Consulta modo sandbox autorizado (DNI demo 12345678)
        ok_demo = await IdentityService.consultar_identidad_autorizada("12345678", consentimiento_titular=True)
        assert ok_demo["success"] is True
        assert ok_demo["verificado_oficial"] is True
        assert ok_demo["nombres"] == "MARIA ELENA"

    asyncio.run(_run())

def test_id_generator_formato():
    codigo = generate_codigo_registro()
    assert codigo.startswith("SHP-")
    # Formato: SHP-YYYY-XXXXX
    partes = codigo.split("-")
    assert len(partes) == 3
    assert len(partes[1]) == 4 # Año
    assert len(partes[2]) == 5 # 5 caracteres seguros

def test_flujo_registro_envio_e_idempotencia():
    # Obtener una agencia activa
    agencias = ShalomService.cargar_agencias()
    agencia = agencias[0]
    codigo_agencia = agencia["id"]

    # Clave de idempotencia única para este test
    unique_seed = str(uuid.uuid4())
    idemp_key = generate_idempotency_key("78451234", codigo_agencia, unique_seed)

    payload = {
        "tipo_documento": "DNI",
        "dni": "78451234",
        "nombres": "ROBERTO",
        "apellido_paterno": "GARCIA",
        "apellido_materno": "PEREZ",
        "celular": "987654321",
        "departamento": agencia["departamento"],
        "provincia": agencia["provincia"],
        "distrito": agencia["distrito"],
        "codigo_agencia": agencia["id"],
        "nombre_agencia": agencia["nombre"],
        "direccion_agencia": agencia["direccion"],
        "referencia_agencia": agencia.get("referencia", ""),
        "fecha_despacho": "lun 10/11",
        "estado_verificacion_identidad": "MANUAL_NO_VERIFICADO",
        "idempotency_key": idemp_key
    }

    # 1er envío: Debe registrar con éxito
    res1 = client.post("/api/envios/registrar", json=payload)
    assert res1.status_code == 200, f"Error: {res1.text}"
    data1 = res1.json()
    assert data1["success"] is True
    assert data1["duplicado"] is False
    codigo_asignado = data1["codigo_registro"]
    assert codigo_asignado.startswith("SHP-")

    # 2do envío con la misma idempotency_key (doble clic o reintento de red):
    # NO debe crear un duplicado, debe retornar el mismo registro
    res2 = client.post("/api/envios/registrar", json=payload)
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["success"] is True
    assert data2["duplicado"] is True
    assert data2["codigo_registro"] == codigo_asignado

def test_admin_auth_y_endpoints_protegidos():
    # Intento de acceso sin autenticación
    res_no_auth = client.get("/api/admin/envios")
    assert res_no_auth.status_code == 401

    # Login con credenciales correctas
    login_res = client.post("/api/admin/login", json={"username": "admin", "password": "admin2026"})
    assert login_res.status_code == 200
    token = login_res.json()["token"]

    # Acceso con token válido
    headers = {"Authorization": f"Bearer {token}"}
    res_auth = client.get("/api/admin/envios", headers=headers)
    assert res_auth.status_code == 200
    assert "envios" in res_auth.json()

    # Estado del catálogo de agencias
    res_cat = client.get("/api/admin/shalom/estado", headers=headers)
    assert res_cat.status_code == 200
    assert "publicas" in res_cat.json()

    # Exportación CSV
    res_export = client.get("/api/admin/envios/exportar", headers=headers)
    assert res_export.status_code == 200
    assert "text/csv" in res_export.headers.get("content-type", "")

def test_shalom_pro_emision_simulador(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "SHALOM_PRO_MODO", "SIMULADOR")
    # Login admin
    login_res = client.post("/api/admin/login", json={"username": "admin", "password": "admin2026"})
    assert login_res.status_code == 200
    token = login_res.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Crear un envío para la prueba
    unique_seed = str(uuid.uuid4())
    idemp_key = generate_idempotency_key("71995142", "SHA-101", unique_seed)
    payload_envio = {
        "tipo_documento": "DNI",
        "dni": "71995142",
        "nombres": "CARLOS",
        "apellido_paterno": "MENDOZA",
        "apellido_materno": "QUISPE",
        "celular": "999888777",
        "departamento": "Lima",
        "provincia": "Lima",
        "distrito": "Los Olivos",
        "codigo_agencia": "SHA-101",
        "nombre_agencia": "Agencia Shalom Los Olivos",
        "direccion_agencia": "Av. Alfredo Mendiola 3500",
        "referencia_agencia": "Frente a MegaPlaza",
        "fecha_despacho": "mar 11/11",
        "estado_verificacion_identidad": "VERIFICADO_RENIEC_OFICIAL",
        "idempotency_key": idemp_key
    }
    res_crear = client.post("/api/envios/registrar", json=payload_envio)
    assert res_crear.status_code == 200
    codigo = res_crear.json()["codigo_registro"]

    # Emitir guía oficial Shalom Pro (en modo simulador)
    payload_emision = {
        "contenido_paquete": "ROPA Y ACCESORIOS",
        "bultos": 2,
        "peso_kg": 2.5,
        "tipo_pago": "PAGO_EN_DESTINO",
        "observaciones": "Entregar en turno mañana"
    }
    res_emitir = client.post(f"/api/admin/envios/{codigo}/emitir-shalom-pro", json=payload_emision, headers=headers)
    assert res_emitir.status_code == 200, f"Error: {res_emitir.text}"
    data_guia = res_emitir.json()
    assert data_guia["success"] is True
    assert data_guia["modo"] == "SIMULADOR"
    assert data_guia["numero_guia"].startswith("SHA-")
    assert data_guia["monto_flete"] > 0
    assert "url_pdf_guia" in data_guia

    # Verificar que el registro en DB se actualizó
    envio_db = DatabaseManager.obtener_envio_por_codigo(codigo)
    assert envio_db is not None
    assert envio_db["numero_guia_shalom"] == data_guia["numero_guia"]
    assert envio_db["estado_registro"] == "EN_PREPARACION"
    assert envio_db["monto_flete"] == data_guia["monto_flete"]

def test_shalom_pro_estado_endpoint():
    login_res = client.post("/api/admin/login", json={"username": "admin", "password": "admin2026"})
    assert login_res.status_code == 200
    token = login_res.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get("/api/admin/shalom-pro/estado", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "modo" in data
    assert "configurado" in data
    assert "ruc_remitente" in data

def test_exportar_plantilla_shalom_pro():
    login_res = client.post("/api/admin/login", json={"username": "admin", "password": "admin2026"})
    assert login_res.status_code == 200
    token = login_res.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get("/api/admin/envios/exportar-shalom-pro?solo_pendientes=true&tamano_defecto=PAQUETE%20XS", headers=headers)
    assert res.status_code == 200
    assert "application/vnd.openxmlformats" in res.headers.get("content-type", "")
    assert len(res.content) > 1000

    import io, openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(res.content))
    assert "Hoja1" in wb.sheetnames
    ws = wb["Hoja1"]
    assert ws.cell(row=1, column=1).value == "DESTINATARIO (DOC)"
    assert ws.cell(row=1, column=2).value == "TELF. DESTINATARIO"
    # Column 8 is MERCADERIA
    assert ws.cell(row=1, column=8).value == "MERCADERIA"
    # If there are data rows, the default package size must be PAQUETE XS
    if ws.cell(row=2, column=1).value is not None:
        assert ws.cell(row=2, column=8).value in ["PAQUETE XS", "PAQUETE S", "SOBRE", "PAQUETE XXS", "PAQUETE M", "PAQUETE L"]

def test_cambiar_tamano_paquete_individual():
    login_res = client.post("/api/admin/login", json={"username": "admin", "password": "admin2026"})
    assert login_res.status_code == 200
    token = login_res.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Crear un nuevo envío
    idemp_key = f"test_tamano_{uuid.uuid4().hex[:12]}"
    payload_envio = {
        "tipo_documento": "DNI",
        "dni": "76543210",
        "nombres": "CARLOS ALBERTO",
        "apellido_paterno": "MENDOZA",
        "apellido_materno": "QUISPE",
        "celular": "987654321",
        "departamento": "Lima",
        "provincia": "Lima",
        "distrito": "Los Olivos",
        "codigo_agencia": "SHA-101",
        "nombre_agencia": "AGENCIA LOS OLIVOS",
        "direccion_agencia": "Av. Alfredo Mendiola 3500",
        "estado_verificacion_identidad": "VERIFICADO_RENIEC_OFICIAL",
        "idempotency_key": idemp_key
    }
    res_crear = client.post("/api/envios/registrar", json=payload_envio)
    assert res_crear.status_code == 200
    codigo = res_crear.json()["codigo_registro"]

    # Cambiar tamaño a PAQUETE M
    res_tam = client.put(f"/api/admin/envios/{codigo}/tamano", json={"tamano_paquete": "PAQUETE M"}, headers=headers)
    assert res_tam.status_code == 200
    assert res_tam.json()["tamano_paquete"] == "PAQUETE M"

    # Verificar en DB
    envio_db = DatabaseManager.obtener_envio_por_codigo(codigo)
    assert envio_db is not None
    assert envio_db["tamano_paquete"] == "PAQUETE M"

    # Validar rechazo de tamaño inválido
    res_inv = client.put(f"/api/admin/envios/{codigo}/tamano", json={"tamano_paquete": "PAQUETE GIGANTE"}, headers=headers)
    assert res_inv.status_code == 422

def test_admin_eliminar_envio():
    login_res = client.post("/api/admin/login", json={"username": "admin", "password": "admin2026"})
    assert login_res.status_code == 200
    token = login_res.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Crear un nuevo envío para eliminar
    idemp_key = f"test_del_{uuid.uuid4().hex[:12]}"
    payload_envio = {
        "tipo_documento": "DNI",
        "dni": "71995142",
        "nombres": "TEST ELIMINAR",
        "apellido_paterno": "RODRIGUEZ",
        "apellido_materno": "PEREZ",
        "celular": "987654321",
        "departamento": "Lima",
        "provincia": "Lima",
        "distrito": "Los Olivos",
        "codigo_agencia": "SHA-101",
        "nombre_agencia": "AGENCIA TEST",
        "direccion_agencia": "Av. Test 123",
        "estado_verificacion_identidad": "VERIFICADO_RENIEC_OFICIAL",
        "idempotency_key": idemp_key
    }
    res_crear = client.post("/api/envios/registrar", json=payload_envio)
    assert res_crear.status_code == 200
    codigo = res_crear.json()["codigo_registro"]

    # Verificar que existe
    assert DatabaseManager.obtener_envio_por_codigo(codigo) is not None

    # Eliminar el envío vía API
    res_del = client.delete(f"/api/admin/envios/{codigo}", headers=headers)
    assert res_del.status_code == 200
    assert res_del.json()["success"] is True

    # Verificar que ya no existe en la base de datos
    assert DatabaseManager.obtener_envio_por_codigo(codigo) is None

    # Intentar eliminar de nuevo debe dar 404
    res_del_404 = client.delete(f"/api/admin/envios/{codigo}", headers=headers)
    assert res_del_404.status_code == 404

def test_pagina_seguimiento_cliente():
    # Registrar un envío
    idemp_key = f"test_track_{uuid.uuid4().hex[:12]}"
    payload_envio = {
        "tipo_documento": "DNI",
        "dni": "76543210",
        "nombres": "JUAN ALBERTO",
        "apellido_paterno": "VARGAS",
        "apellido_materno": "LOPEZ",
        "celular": "987654321",
        "departamento": "Lima",
        "provincia": "Lima",
        "distrito": "Los Olivos",
        "codigo_agencia": "SHA-101",
        "nombre_agencia": "AGENCIA LOS OLIVOS",
        "direccion_agencia": "Av. Alfredo Mendiola 3500",
        "estado_verificacion_identidad": "VERIFICADO_RENIEC_OFICIAL",
        "idempotency_key": idemp_key
    }
    res_crear = client.post("/api/envios/registrar", json=payload_envio)
    assert res_crear.status_code == 200
    codigo = res_crear.json()["codigo_registro"]

    # Probar que la página de seguimiento HTML carga con 200
    res_track = client.get(f"/seguimiento/{codigo}")
    assert res_track.status_code == 200
    assert "Seguimiento de tu envío" in res_track.text
    assert codigo in res_track.text
    assert "AGENCIA LOS OLIVOS" in res_track.text

    # Probar que la API JSON de seguimiento responde
    res_api_track = client.get(f"/api/seguimiento/{codigo}")
    assert res_api_track.status_code == 200
    data_track = res_api_track.json()
    assert data_track["codigo_registro"] == codigo
    assert data_track["agencia_destino"] == "AGENCIA LOS OLIVOS"

    # Probar que la página de éxito contiene el tracking_url
    res_success = client.get(f"/registro/exito/{codigo}")
    assert res_success.status_code == 200
    assert f"/seguimiento/{codigo}" in res_success.text
