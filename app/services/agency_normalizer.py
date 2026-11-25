"""
Normalización, validación y depuración del catálogo de agencias Shalom.

Acepta registros en tres formatos y los lleva a un ESQUEMA CANÓNICO único:
  1. Formato del localizador/API de Shalom (campos ter_id, ter_abrebiatura, zona, ...).
  2. Formato canónico de esta aplicación (id, codigo, nombre, departamento, ...).
  3. Formato genérico de archivos CSV/JSON entregados por canales oficiales
     (id/codigo, nombre/agencia, departamento, provincia, distrito, direccion, horario...).

Reglas de depuración:
  - Sin duplicados: misma clave `id`, o misma ubicación + dirección normalizada.
  - Sin registros inválidos: dirección vacía o de relleno ("cargando", "v"...).
  - Sin agencias inactivas: estado cerrado/suspendido, "POR DEFINIR", activo=false.
  - Coordenadas fuera del territorio peruano se descartan (no se inventan).
  - Horarios y teléfonos se normalizan; si no existen se dejan vacíos (no se inventan).
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import unicodedata
from typing import Any, Dict, Iterable, List, Optional, Tuple

# ------------------------------------------------------------------------------
# Utilidades de texto
# ------------------------------------------------------------------------------

def normalizar_texto(texto: Any) -> str:
    """'San Martín' -> 'san martin' (sin tildes, minúsculas, espacios colapsados)."""
    if texto is None:
        return ""
    texto = str(texto).replace("\xa0", " ")
    nfkd = unicodedata.normalize("NFKD", texto)
    sin_tildes = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", sin_tildes.lower()).strip()


def limpiar_espacios(texto: Any) -> str:
    if texto is None:
        return ""
    texto = str(texto).replace("\xa0", " ").replace("\\xa0", " ")
    return re.sub(r"\s+", " ", texto).strip()


DEPARTAMENTOS_OFICIALES = {
    "AMAZONAS": "Amazonas", "ANCASH": "Áncash", "APURIMAC": "Apurímac", "AREQUIPA": "Arequipa",
    "AYACUCHO": "Ayacucho", "CAJAMARCA": "Cajamarca", "CALLAO": "Callao", "CUSCO": "Cusco",
    "CUZCO": "Cusco", "HUANCAVELICA": "Huancavelica", "HUANUCO": "Huánuco", "ICA": "Ica",
    "JUNIN": "Junín", "LA LIBERTAD": "La Libertad", "LAMBAYEQUE": "Lambayeque", "LIMA": "Lima",
    "LIMA PROVINCIAS": "Lima", "LIMA METROPOLITANA": "Lima", "LORETO": "Loreto",
    "MADRE DE DIOS": "Madre de Dios", "MOQUEGUA": "Moquegua", "PASCO": "Pasco", "PIURA": "Piura",
    "PUNO": "Puno", "SAN MARTIN": "San Martín", "TACNA": "Tacna", "TUMBES": "Tumbes",
    "UCAYALI": "Ucayali",
}

# Correcciones puntuales de nombres de distrito truncados o compuestos en la fuente
CORRECCIONES_DISTRITO = {
    "SAN VICENTE DE CANET": "San Vicente de Cañete",
    "JOSE CRESPO Y CASTIL": "José Crespo y Castillo",
    "YAURI ( ESPINAR )": "Espinar",
    "PUCALLPA CALLERIA": "Callería",
    "PUCALLPA MANANTAY": "Manantay",
    "PUCALLPA YARINACOCHA": "Yarinacocha",
    "IQUITOS SAN JUAN BAUTISTA": "San Juan Bautista",
    "CERCADO LIMA": "Cercado de Lima",
    "ATE-VITARTE": "Ate",
    "CORONEL GREGORIO ALBARRACIN LANCHIPA": "Coronel Gregorio Albarracín Lanchipa",
}

# Restitución de tildes y eñes frecuentes en topónimos peruanos (palabra completa)
TILDES = {
    "martin": "Martín", "jesus": "Jesús", "maria": "María", "rimac": "Rímac", "brena": "Breña",
    "ferrenafe": "Ferreñafe", "banos": "Baños", "canete": "Cañete", "huanuco": "Huánuco",
    "junin": "Junín", "ancash": "Áncash", "apurimac": "Apurímac", "peru": "Perú",
    "concepcion": "Concepción", "celendin": "Celendín", "contumaza": "Contumazá", "jaen": "Jaén",
    "camana": "Camaná", "caraveli": "Caravelí", "ancon": "Ancón", "lurin": "Lurín",
    "pachacamac": "Pachacámac", "chepen": "Chepén", "viru": "Virú", "monsefu": "Monsefú",
    "tucume": "Túcume", "morrope": "Mórrope", "mochumi": "Mochumí", "tuman": "Tumán",
    "jeronimo": "Jerónimo", "sebastian": "Sebastián", "tomas": "Tomás", "ramon": "Ramón",
    "agustin": "Agustín", "sayan": "Sayán", "churin": "Churín", "paijan": "Paiján",
    "yonan": "Yonán", "azangaro": "Azángaro", "roman": "Román", "galvez": "Gálvez",
    "parinas": "Pariñas", "mancora": "Máncora", "organos": "Órganos", "union": "Unión",
    "calleria": "Callería", "huarochiri": "Huarochirí", "oyon": "Oyón", "caceres": "Cáceres",
    "carrion": "Carrión", "perene": "Perené", "aguaytia": "Aguaytía", "albarracin": "Albarracín",
    "elias": "Elías", "jose": "José", "andres": "Andrés", "victor": "Víctor", "jazan": "Jazán",
    "convencion": "Convención", "pisac": "Pisac", "chiclayo": "Chiclayo", "huanta": "Huanta",
    "bongara": "Bongará", "huancabamba": "Huancabamba", "paimas": "Paimas", "ica": "Ica",
    "maranon": "Marañón", "nazca": "Nasca", "espinar": "Espinar", "satipo": "Satipo",
    "pangoa": "Pangoa", "tambo": "Tambo", "inambari": "Inambari", "sicuani": "Sicuani",
}

PARTICULAS_MINUSCULA = {"de", "del", "y", "e"}
ARTICULOS = {"la", "las", "los", "el"}


def titulo_toponimo(texto: Any) -> str:
    """'SAN MARTIN DE PORRES' -> 'San Martín de Porres'; 'ALTO DE LA ALIANZA' -> 'Alto de la Alianza'."""
    texto = limpiar_espacios(texto)
    if not texto:
        return ""
    palabras = re.split(r"(\s+|-|\(|\))", texto)
    resultado: List[str] = []
    previa = ""
    es_primera = True
    for token in palabras:
        if not token or re.fullmatch(r"\s+|-|\(|\)", token):
            resultado.append(token)
            continue
        base = normalizar_texto(token)
        if not es_primera and base in PARTICULAS_MINUSCULA:
            palabra = token.lower()
        elif not es_primera and base in ARTICULOS and previa in ("de", "del"):
            palabra = token.lower()
        elif base in TILDES:
            palabra = TILDES[base]
        elif re.fullmatch(r"[ivxlc]+", base) and len(base) <= 4 and base not in ("ilo", "ica", "civil"):
            palabra = token.upper()  # numerales romanos
        else:
            palabra = token[:1].upper() + token[1:].lower()
        resultado.append(palabra)
        previa = base
        es_primera = False
    return "".join(resultado).strip()


def normalizar_departamento(valor: Any) -> str:
    clave = normalizar_texto(valor).upper()
    return DEPARTAMENTOS_OFICIALES.get(clave, titulo_toponimo(valor))


def normalizar_distrito(valor: Any) -> str:
    limpio = limpiar_espacios(valor).upper()
    if limpio in CORRECCIONES_DISTRITO:
        return CORRECCIONES_DISTRITO[limpio]
    sin_tildes = normalizar_texto(limpio).upper()
    if sin_tildes in CORRECCIONES_DISTRITO:
        return CORRECCIONES_DISTRITO[sin_tildes]
    return titulo_toponimo(limpio)


# ------------------------------------------------------------------------------
# Dirección, referencia, horario, teléfono, coordenadas
# ------------------------------------------------------------------------------

DIRECCIONES_BASURA = {"", "v", "cargando", "-", "s/n", "null", "none", "por definir", "sin direccion"}
_RE_REFERENCIA = re.compile(r"[\s,;.\-–]*\b(?:REFERENCIA|REF)\b\s*[:.]?\s*", re.IGNORECASE)


def separar_direccion_referencia(direccion: Any, referencia: Any = "") -> Tuple[str, str]:
    direccion = limpiar_espacios(direccion)
    referencia = limpiar_espacios(referencia)
    partes = _RE_REFERENCIA.split(direccion, maxsplit=1)
    if len(partes) == 2:
        direccion, ref_extra = partes[0], partes[1]
        referencia = referencia or ref_extra
    direccion = direccion.strip(" ,;-–.")
    referencia = referencia.strip(" ,;-–.")
    return direccion.upper(), referencia.upper()


def direccion_valida(direccion: str) -> bool:
    d = normalizar_texto(direccion)
    if d in DIRECCIONES_BASURA:
        return False
    return len(re.sub(r"[^a-z0-9]", "", d)) >= 6


_RE_HORA = re.compile(r"(\d{1,2})(?::(\d{2}))?\s*(a\.?\s*m\.?|p\.?\s*m\.?)?", re.IGNORECASE)


def _formatear_hora(h: str, m: Optional[str], sufijo: Optional[str]) -> str:
    hora = int(h)
    minutos = m or "00"
    if sufijo:
        suf = "AM" if sufijo.lower().startswith("a") else "PM"
    else:
        suf = "AM" if hora < 12 else "PM"
        if hora > 12:
            hora -= 12
    return f"{hora}:{minutos} {suf}"


def normalizar_horario(valor: Any) -> str:
    """'LUNES A VIERNES - 8AM A 8PM' -> 'Lunes a viernes: 8:00 AM - 8:00 PM'. Vacío si no hay dato."""
    texto = limpiar_espacios(valor)
    if not texto or normalizar_texto(texto) in ("null", "none", "-"):
        return ""
    bloques = [b.strip() for b in re.split(r"\s*[|/;]\s*", texto) if b.strip()]
    salida = []
    for bloque in bloques:
        m = re.match(r"^(?P<dias>[A-Za-zÁÉÍÓÚáéíóúÑñ ,]+?)\s*[-:]\s*(?P<horas>.+)$", bloque)
        if not m:
            salida.append(bloque[:1].upper() + bloque[1:].lower())
            continue
        dias = m.group("dias").strip().lower()
        dias = dias[:1].upper() + dias[1:]
        dias = dias.replace("sabado", "sábado").replace("miercoles", "miércoles")
        horas_txt = m.group("horas")
        horas = [x for x in _RE_HORA.finditer(horas_txt) if x.group(1)]
        if len(horas) >= 2:
            ini = _formatear_hora(horas[0].group(1), horas[0].group(2), horas[0].group(3))
            fin = _formatear_hora(horas[1].group(1), horas[1].group(2), horas[1].group(3))
            salida.append(f"{dias}: {ini} - {fin}")
        else:
            salida.append(f"{dias}: {horas_txt.strip()}")
    return " | ".join(salida)


def normalizar_telefono(valor: Any) -> str:
    texto = limpiar_espacios(valor)
    digitos = re.sub(r"\D", "", texto)
    if not digitos:
        return ""
    if digitos == "015007878":
        return "(01) 500 7878"
    if len(digitos) == 9 and digitos.startswith("9"):
        return f"{digitos[:3]} {digitos[3:6]} {digitos[6:]}"
    return texto


PERU_LAT = (-18.40, 0.05)
PERU_LON = (-81.40, -68.60)


def normalizar_coordenadas(lat: Any, lon: Any) -> Tuple[Optional[float], Optional[float]]:
    try:
        la, lo = float(lat), float(lon)
    except (TypeError, ValueError):
        return None, None
    if not (PERU_LAT[0] <= la <= PERU_LAT[1] and PERU_LON[0] <= lo <= PERU_LON[1]):
        return None, None
    return round(la, 7), round(lo, 7)


# ------------------------------------------------------------------------------
# Estado / actividad
# ------------------------------------------------------------------------------

PALABRAS_INACTIVA = ("cerrad", "inactiv", "suspend", "clausur", "fuera de servicio", "no operativ",
                     "por definir", "proximamente", "próximamente", "deshabilit")


def _a_bool(valor: Any, defecto: bool = True) -> bool:
    if valor is None or valor == "":
        return defecto
    if isinstance(valor, bool):
        return valor
    return normalizar_texto(valor) in ("1", "true", "si", "sí", "yes", "activo", "activa", "s")


def evaluar_estado(registro: Dict[str, Any], nombre: str, direccion: str) -> Tuple[bool, str]:
    """Devuelve (activo, motivo_inactiva)."""
    if not _a_bool(registro.get("activo", registro.get("activa")), True):
        return False, "Marcada como inactiva en la fuente"
    estado_txt = normalizar_texto(" ".join(str(registro.get(k) or "") for k in
                                           ("estado", "estadoAgencia", "estado_agencia", "status")))
    nombre_txt = normalizar_texto(nombre + " " + str(registro.get("nombre_completo", registro.get("nombre", ""))))
    for palabra in PALABRAS_INACTIVA:
        p = normalizar_texto(palabra)
        if p in estado_txt:
            return False, f"Estado en la fuente: {limpiar_espacios(estado_txt)[:60]}"
        if p in nombre_txt:
            return False, "Agencia aún no habilitada (por definir)"
    if not direccion_valida(direccion):
        return False, "Dirección ausente o inválida en la fuente"
    return True, ""


# ------------------------------------------------------------------------------
# Normalización de un registro
# ------------------------------------------------------------------------------

def _primero(registro: Dict[str, Any], *claves: str) -> Any:
    for c in claves:
        v = registro.get(c)
        if v not in (None, ""):
            return v
    return None


def normalizar_agencia(registro: Dict[str, Any], fuente: str = "") -> Optional[Dict[str, Any]]:
    """Convierte un registro de cualquier formato soportado al esquema canónico. None si es irrecuperable."""
    if not isinstance(registro, dict):
        return None

    es_formato_shalom = "ter_id" in registro
    ident = _primero(registro, "ter_id", "id", "codigo_agencia", "agencia_id")
    codigo = _primero(registro, "ter_abrebiatura", "ter_abreviatura", "codigo", "abreviatura", "code")
    if ident is None and codigo is None:
        return None
    ident = str(ident if ident is not None else codigo).strip()

    nombre_completo = limpiar_espacios(_primero(registro, "nombre_completo") or
                                       (registro.get("nombre") if es_formato_shalom else "") or "")
    if es_formato_shalom:
        partes = [p.strip() for p in str(registro.get("nombre") or "").split("/") if p.strip()]
        nombre_raw = partes[-1] if partes else registro.get("zona", "")
    else:
        nombre_raw = _primero(registro, "nombre", "agencia", "nombre_agencia", "name") or ""
    nombre = titulo_toponimo(nombre_raw)

    departamento = normalizar_departamento(_primero(registro, "departamento", "dep", "region") or "")
    provincia = titulo_toponimo(_primero(registro, "provincia", "prov") or departamento)
    distrito = normalizar_distrito(_primero(registro, "zona", "distrito", "dist") or provincia)
    if not (nombre and departamento and provincia and distrito):
        return None

    direccion, referencia = separar_direccion_referencia(
        _primero(registro, "direccion", "address") or "", _primero(registro, "referencia") or "")
    lat, lon = normalizar_coordenadas(_primero(registro, "latitud", "lat"), _primero(registro, "longitud", "lng", "lon"))

    activo, motivo = evaluar_estado(registro, nombre, direccion)
    acepta_destino = _a_bool(registro.get("destino", registro.get("acepta_destino")), True)
    acepta_origen = _a_bool(registro.get("origen", registro.get("acepta_origen")), True)

    return {
        "id": ident,
        "codigo": limpiar_espacios(codigo or "").upper(),
        "nombre": nombre,
        "nombre_completo": nombre_completo or f"{departamento} / {provincia} / {distrito} / {nombre}".upper(),
        "departamento": departamento,
        "provincia": provincia,
        "distrito": distrito,
        "direccion": direccion,
        "referencia": referencia,
        "horario": normalizar_horario(_primero(registro, "hora_atencion", "horario", "horario_atencion")),
        "telefono": normalizar_telefono(_primero(registro, "telefono", "phone")),
        "latitud": lat,
        "longitud": lon,
        "maps_url": f"https://www.google.com/maps?q={lat},{lon}" if lat is not None else "",
        "categoria": limpiar_espacios(_primero(registro, "ter_categoria", "categoria") or ""),
        "acepta_destino": acepta_destino,
        "acepta_origen": acepta_origen,
        "activo": activo,
        "motivo_inactiva": motivo,
        "fuente": fuente or limpiar_espacios(registro.get("fuente") or ""),
    }


# ------------------------------------------------------------------------------
# Depuración del conjunto
# ------------------------------------------------------------------------------

def _completitud(a: Dict[str, Any]) -> int:
    puntos = sum(1 for k in ("direccion", "referencia", "horario", "telefono", "codigo") if a.get(k))
    puntos += 2 if a.get("latitud") is not None else 0
    puntos += 3 if a.get("activo") else 0
    puntos += 3 if a.get("acepta_destino") else 0
    return puntos


def clave_ubicacion(a: Dict[str, Any]) -> str:
    direccion = re.sub(r"[^a-z0-9]", "", normalizar_texto(a.get("direccion")))
    return "|".join([normalizar_texto(a.get("departamento")), normalizar_texto(a.get("provincia")),
                     normalizar_texto(a.get("distrito")), direccion])


def depurar_agencias(registros: Iterable[Dict[str, Any]], fuente: str = "") -> Dict[str, Any]:
    """
    Normaliza y depura una lista de registros crudos.
    Devuelve {"agencias": [...], "reporte": {...}} con todas las agencias canónicas
    (incluidas las inactivas, para trazabilidad) y estadísticas de depuración.
    """
    reporte = {"recibidos": 0, "descartados_invalidos": 0, "duplicados_id": 0,
               "duplicados_ubicacion": 0, "inactivas": 0, "sin_destino": 0, "sin_coordenadas": 0,
               "ejemplos_descartados": []}
    por_id: Dict[str, Dict[str, Any]] = {}
    for crudo in registros:
        reporte["recibidos"] += 1
        a = normalizar_agencia(crudo, fuente)
        if not a:
            reporte["descartados_invalidos"] += 1
            if len(reporte["ejemplos_descartados"]) < 5:
                reporte["ejemplos_descartados"].append(str(crudo)[:120])
            continue
        if a["id"] in por_id:
            reporte["duplicados_id"] += 1
            if _completitud(a) <= _completitud(por_id[a["id"]]):
                continue
        por_id[a["id"]] = a

    # Duplicados por ubicación física: se conserva el más completo; el resto queda inactivo
    por_ubicacion: Dict[str, Dict[str, Any]] = {}
    for a in sorted(por_id.values(), key=lambda x: (-_completitud(x), _orden_id(x["id"]))):
        if not direccion_valida(a["direccion"]):
            continue
        clave = clave_ubicacion(a)
        if clave in por_ubicacion:
            principal = por_ubicacion[clave]
            if a["activo"]:
                reporte["duplicados_ubicacion"] += 1
            a["activo"] = False
            a["motivo_inactiva"] = f"Duplicada de la agencia {principal['id']} (misma dirección)"
            a["duplicado_de"] = principal["id"]
        else:
            por_ubicacion[clave] = a

    agencias = sorted(por_id.values(), key=lambda x: (normalizar_texto(x["departamento"]),
                                                       normalizar_texto(x["provincia"]),
                                                       normalizar_texto(x["distrito"]),
                                                       normalizar_texto(x["nombre"])))
    for a in agencias:
        if not a["activo"]:
            reporte["inactivas"] += 1
        elif not a["acepta_destino"]:
            reporte["sin_destino"] += 1
        if a["latitud"] is None:
            reporte["sin_coordenadas"] += 1
    reporte["total"] = len(agencias)
    reporte["activas"] = sum(1 for a in agencias if a["activo"])
    reporte["publicables"] = sum(1 for a in agencias if a["activo"] and a["acepta_destino"])
    return {"agencias": agencias, "reporte": reporte}


def _orden_id(ident: str) -> Tuple[int, str]:
    return (int(ident), "") if str(ident).isdigit() else (10**9, str(ident))


# ------------------------------------------------------------------------------
# Comparación entre catálogos (para previsualizar actualizaciones)
# ------------------------------------------------------------------------------

CAMPOS_COMPARABLES = ("nombre", "departamento", "provincia", "distrito", "direccion", "referencia",
                      "horario", "telefono", "latitud", "longitud", "activo", "acepta_destino", "codigo")


def huella_agencia(a: Dict[str, Any]) -> str:
    datos = json.dumps({k: a.get(k) for k in CAMPOS_COMPARABLES}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(datos.encode("utf-8")).hexdigest()


def comparar_catalogos(actual: List[Dict[str, Any]], nuevo: List[Dict[str, Any]]) -> Dict[str, Any]:
    act = {a["id"]: a for a in actual}
    nue = {a["id"]: a for a in nuevo}
    nuevas = [i for i in nue if i not in act]
    retiradas = [i for i in act if i not in nue and act[i].get("activo")]
    modificadas, reactivadas, desactivadas = [], [], []
    for i in nue:
        if i in act and huella_agencia(act[i]) != huella_agencia(nue[i]):
            modificadas.append(i)
            if act[i].get("activo") and not nue[i].get("activo"):
                desactivadas.append(i)
            elif not act[i].get("activo") and nue[i].get("activo"):
                reactivadas.append(i)

    def resumen(ids, origen):
        return [{"id": i, "nombre": origen[i]["nombre"], "distrito": origen[i]["distrito"],
                 "departamento": origen[i]["departamento"]} for i in ids[:25]]

    activas_antes = sum(1 for a in actual if a.get("activo"))
    perdidas = len(retiradas) + len(desactivadas)
    return {
        "nuevas": len(nuevas), "modificadas": len(modificadas), "retiradas": len(retiradas),
        "desactivadas": len(desactivadas), "reactivadas": len(reactivadas),
        "sin_cambios": sum(1 for i in nue if i in act) - len(modificadas),
        "activas_antes": activas_antes,
        "porcentaje_baja": round(100 * perdidas / activas_antes, 1) if activas_antes else 0.0,
        "detalle": {"nuevas": resumen(nuevas, nue), "retiradas": resumen(retiradas, act),
                    "desactivadas": resumen(desactivadas, nue), "modificadas": resumen(modificadas, nue)},
    }


# ------------------------------------------------------------------------------
# Lectura de archivos de importación
# ------------------------------------------------------------------------------

def parsear_contenido(contenido: str, formato: str = "auto") -> List[Dict[str, Any]]:
    """Convierte el contenido de un archivo JSON o CSV (coma o punto y coma) en lista de dicts."""
    contenido = (contenido or "").lstrip("\ufeff").strip()
    if not contenido:
        raise ValueError("El archivo está vacío.")
    formato = (formato or "auto").lower()
    if formato == "auto":
        formato = "json" if contenido[:1] in "[{" else "csv"
    if formato == "json":
        data = json.loads(contenido)
        if isinstance(data, dict):
            for clave in ("data", "agencias", "results", "items"):
                if isinstance(data.get(clave), list):
                    data = data[clave]
                    break
        if not isinstance(data, list):
            raise ValueError("El JSON debe ser una lista de agencias o un objeto con la clave 'data'/'agencias'.")
        return [d for d in data if isinstance(d, dict)]
    if formato == "csv":
        muestra = contenido[:2048]
        delimitador = ";" if muestra.count(";") > muestra.count(",") else ","
        lector = csv.DictReader(io.StringIO(contenido), delimiter=delimitador)
        filas = []
        for fila in lector:
            filas.append({normalizar_texto(k).replace(" ", "_"): (v or "").strip() for k, v in fila.items() if k})
        return filas
    raise ValueError(f"Formato no soportado: {formato}")
