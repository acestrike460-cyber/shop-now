"""
Servicio del catálogo nacional de agencias Shalom.

Responsabilidades:
  - Cargar el catálogo canónico (data/agencias_peru.json) y sus metadatos (data/agencias_meta.json).
  - Exponer solo agencias ACTIVAS y habilitadas como destino al público.
  - Cascada departamento > provincia > distrito > agencia y árbol jerárquico con conteos.
  - Búsqueda inteligente (sin tildes, prefijos, alias populares y tolerancia a errores de tipeo).
  - Actualización controlada desde FUENTES AUTORIZADAS:
        * API oficial/autorizada configurada en SHALOM_API_URL (+ SHALOM_API_KEY).
        * Archivos JSON/CSV entregados por canales oficiales de Shalom (importación desde el panel).
    Toda actualización se previsualiza (diferencias), tiene umbral de seguridad ante bajas masivas,
    crea respaldo automático y conserva como inactivas las agencias retiradas (trazabilidad).
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import tempfile
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.config import settings
from app.services.agency_normalizer import (
    comparar_catalogos,
    depurar_agencias,
    huella_agencia,
    normalizar_texto,
    parsear_contenido,
)
from app.services.id_generator import get_lima_now

logger = logging.getLogger("shalom_service")

# Compatibilidad con importaciones existentes
__all__ = ["ShalomService", "normalizar_texto"]

ALIAS_BUSQUEDA = {
    "smp": "san martin de porres",
    "sjl": "san juan de lurigancho",
    "sjm": "san juan de miraflores",
    "ves": "villa el salvador",
    "vmt": "villa maria del triunfo",
    "vitarte": "ate",
    "chosica": "lurigancho",
    "cercado": "cercado de lima",
    "huachipa": "lurigancho",
    "tingo": "rupa rupa",
    "pucallpa": "coronel portillo",
    "iquitos": "maynas",
    "tarapoto": "san martin",
    "juliaca": "san roman",
    "chimbote": "santa",
}
PALABRAS_VACIAS = {"de", "del", "la", "las", "los", "el", "y", "av", "av.", "agencia", "agencias",
                   "shalom", "en", "jr", "calle"}
PESOS_CAMPOS = {"nombre": 10, "distrito": 9, "provincia": 6, "departamento": 4, "referencia": 3, "direccion": 3}
CAMPOS_PUBLICOS = ("id", "codigo", "nombre", "departamento", "provincia", "distrito", "direccion",
                   "referencia", "horario", "telefono", "latitud", "longitud", "maps_url", "categoria")


def _distancia_edicion(a: str, b: str, maximo: int) -> int:
    """Levenshtein con corte temprano (devuelve maximo+1 si se excede)."""
    if abs(len(a) - len(b)) > maximo:
        return maximo + 1
    previa = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        actual = [i] + [0] * len(b)
        minimo_fila = i
        for j, cb in enumerate(b, 1):
            actual[j] = min(previa[j] + 1, actual[j - 1] + 1, previa[j - 1] + (ca != cb))
            minimo_fila = min(minimo_fila, actual[j])
        if minimo_fila > maximo:
            return maximo + 1
        previa = actual
    return previa[-1]


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


class ShalomService:
    _catalogo: List[Dict[str, Any]] = []
    _publicas: List[Dict[str, Any]] = []
    _por_id: Dict[str, Dict[str, Any]] = {}
    _indice: List[Tuple[Dict[str, Any], Dict[str, str], Dict[str, List[str]]]] = []
    _meta: Dict[str, Any] = {}
    _cargado: bool = False
    _lock = threading.RLock()

    # ------------------------------------------------------------------
    # Rutas y persistencia
    # ------------------------------------------------------------------
    @staticmethod
    def ruta_catalogo() -> Path:
        return settings.DATA_DIR / "agencias_peru.json"

    @staticmethod
    def ruta_meta() -> Path:
        return settings.DATA_DIR / "agencias_meta.json"

    @staticmethod
    def ruta_respaldos() -> Path:
        return settings.DATA_DIR / "respaldos_agencias"

    @staticmethod
    def _escribir_json_atomico(ruta: Path, datos: Any) -> None:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(ruta.parent), prefix=ruta.stem, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(datos, f, ensure_ascii=False, indent=1)
            os.replace(tmp, ruta)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)

    @classmethod
    def _respaldar(cls) -> Optional[str]:
        origen = cls.ruta_catalogo()
        if not origen.exists():
            return None
        destino_dir = cls.ruta_respaldos()
        destino_dir.mkdir(parents=True, exist_ok=True)
        destino = destino_dir / f"agencias_{get_lima_now().strftime('%Y%m%d_%H%M%S_%f')}.json"
        destino.write_bytes(origen.read_bytes())
        respaldos = sorted(destino_dir.glob("agencias_*.json"))
        for viejo in respaldos[:-10]:
            viejo.unlink(missing_ok=True)
        return destino.name

    # ------------------------------------------------------------------
    # Carga e indexación
    # ------------------------------------------------------------------
    @classmethod
    def cargar(cls, forzar: bool = False) -> None:
        with cls._lock:
            if cls._cargado and not forzar:
                return
            catalogo: List[Dict[str, Any]] = []
            ruta = cls.ruta_catalogo()
            if ruta.exists():
                try:
                    datos = json.loads(ruta.read_text(encoding="utf-8"))
                    catalogo = datos if isinstance(datos, list) else datos.get("agencias", [])
                except Exception as e:  # catálogo corrupto: no tumbar la app
                    logger.error(f"Catálogo de agencias ilegible: {e}")
            meta: Dict[str, Any] = {}
            if cls.ruta_meta().exists():
                try:
                    meta = json.loads(cls.ruta_meta().read_text(encoding="utf-8"))
                except Exception as e:
                    logger.error(f"Metadatos de catálogo ilegibles: {e}")
            # Si el archivo no está en formato canónico (versiones anteriores), normalizarlo en memoria
            if catalogo and "acepta_destino" not in catalogo[0]:
                catalogo = depurar_agencias(catalogo, meta.get("fuente", "Catálogo previo"))["agencias"]
            cls._meta = meta
            cls._aplicar_en_memoria(catalogo)
            cls._cargado = True

    @classmethod
    def _aplicar_en_memoria(cls, catalogo: List[Dict[str, Any]]) -> None:
        overrides = cls._meta.get("overrides", {})
        for a in catalogo:
            ov = overrides.get(a["id"])
            if ov is not None:
                a["activo"] = bool(ov.get("activo"))
                a["motivo_inactiva"] = "" if a["activo"] else ov.get("motivo", "Desactivada manualmente")
                a["override_manual"] = True
            else:
                a.pop("override_manual", None)
        cls._catalogo = catalogo
        cls._por_id = {a["id"]: a for a in catalogo}
        cls._publicas = [a for a in catalogo if a.get("activo") and
                         (a.get("acepta_destino", True) or not settings.AGENCIAS_SOLO_DESTINO)]
        indice = []
        for a in cls._publicas:
            campos = {k: normalizar_texto(a.get(k, "")) for k in PESOS_CAMPOS}
            campos["codigo"] = normalizar_texto(a.get("codigo", ""))
            campos["id"] = normalizar_texto(a.get("id", ""))
            palabras = {k: v.replace("-", " ").replace("/", " ").split() for k, v in campos.items()}
            indice.append((a, campos, palabras))
        cls._indice = indice

    @classmethod
    def huella_publica(cls) -> str:
        cls.cargar()
        base = "".join(huella_agencia(a) for a in cls._publicas)
        return hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]

    @classmethod
    def set_agencias(cls, agencias: List[Dict[str, Any]]) -> None:
        """Reemplaza el catálogo en memoria (útil en pruebas). Normaliza si hace falta."""
        with cls._lock:
            if agencias and "acepta_destino" not in agencias[0]:
                agencias = depurar_agencias(agencias)["agencias"]
            cls._aplicar_en_memoria(agencias)
            cls._cargado = True

    # ------------------------------------------------------------------
    # Consultas públicas
    # ------------------------------------------------------------------
    @staticmethod
    def vista_publica(a: Dict[str, Any]) -> Dict[str, Any]:
        return {k: a.get(k) for k in CAMPOS_PUBLICOS}

    @classmethod
    def cargar_agencias(cls) -> List[Dict[str, Any]]:
        """Agencias visibles para el cliente (activas y habilitadas como destino)."""
        cls.cargar()
        return cls._publicas

    @classmethod
    def get_departamentos(cls) -> List[str]:
        return sorted({a["departamento"] for a in cls.cargar_agencias()}, key=normalizar_texto)

    @classmethod
    def get_provincias(cls, departamento: str) -> List[str]:
        dep = normalizar_texto(departamento)
        return sorted({a["provincia"] for a in cls.cargar_agencias()
                       if normalizar_texto(a["departamento"]) == dep}, key=normalizar_texto)

    @classmethod
    def get_distritos(cls, departamento: str, provincia: str) -> List[str]:
        dep, prov = normalizar_texto(departamento), normalizar_texto(provincia)
        return sorted({a["distrito"] for a in cls.cargar_agencias()
                       if normalizar_texto(a["departamento"]) == dep
                       and normalizar_texto(a["provincia"]) == prov}, key=normalizar_texto)

    @classmethod
    def get_agencias(cls, departamento: str, provincia: str, distrito: Optional[str] = None) -> List[Dict[str, Any]]:
        dep, prov = normalizar_texto(departamento), normalizar_texto(provincia)
        dist = normalizar_texto(distrito) if distrito else None
        res = [a for a in cls.cargar_agencias()
               if normalizar_texto(a["departamento"]) == dep and normalizar_texto(a["provincia"]) == prov
               and (dist is None or normalizar_texto(a["distrito"]) == dist)]
        return sorted(res, key=lambda a: normalizar_texto(a["nombre"]))

    @classmethod
    def get_arbol(cls) -> List[Dict[str, Any]]:
        """Jerarquía departamento > provincia > distrito con número de agencias en cada nivel."""
        arbol: Dict[str, Dict[str, Dict[str, int]]] = {}
        for a in cls.cargar_agencias():
            arbol.setdefault(a["departamento"], {}).setdefault(a["provincia"], {}).setdefault(a["distrito"], 0)
            arbol[a["departamento"]][a["provincia"]][a["distrito"]] += 1
        salida = []
        for dep in sorted(arbol, key=normalizar_texto):
            provincias = []
            for prov in sorted(arbol[dep], key=normalizar_texto):
                distritos = [{"nombre": d, "total": n} for d, n in
                             sorted(arbol[dep][prov].items(), key=lambda x: normalizar_texto(x[0]))]
                provincias.append({"nombre": prov, "total": sum(d["total"] for d in distritos), "distritos": distritos})
            salida.append({"nombre": dep, "total": sum(p["total"] for p in provincias), "provincias": provincias})
        return salida

    @classmethod
    def get_agencia_por_id(cls, agencia_id: str, incluir_inactivas: bool = False) -> Optional[Dict[str, Any]]:
        cls.cargar()
        a = cls._por_id.get(str(agencia_id).strip())
        if not a:
            return None
        if not incluir_inactivas and a not in cls._publicas:
            return None
        return a

    @classmethod
    def agencias_cercanas(cls, lat: float, lng: float, limite: int = 10) -> List[Dict[str, Any]]:
        res = []
        for a in cls.cargar_agencias():
            if a.get("latitud") is None:
                continue
            item = cls.vista_publica(a)
            item["distancia_km"] = round(haversine_km(lat, lng, a["latitud"], a["longitud"]), 2)
            res.append(item)
        return sorted(res, key=lambda x: x["distancia_km"])[:limite]

    # ------------------------------------------------------------------
    # Búsqueda inteligente
    # ------------------------------------------------------------------
    @staticmethod
    def _fuerza_token(token: str, texto: str, palabras: List[str]) -> float:
        if not texto:
            return 0.0
        if token in palabras:
            return 1.0
        if any(p.startswith(token) for p in palabras):
            return 0.8
        if len(token) >= 3 and token in texto:
            return 0.5
        if len(token) >= 4:
            maximo = 1 if len(token) < 7 else 2
            for p in palabras:
                if len(p) >= 4 and (_distancia_edicion(token, p, maximo) <= maximo or
                                    (len(p) > len(token) and _distancia_edicion(token, p[:len(token)], maximo) <= maximo)):
                    return 0.35
        return 0.0

    @classmethod
    def _puntuar(cls, alternativas: List[List[str]], campos: Dict[str, str],
                 palabras: Dict[str, List[str]]) -> Tuple[float, str]:
        total, mejor_campo = 0.0, ""
        for grupo in alternativas:  # cada grupo = alternativas de un token (token original o alias)
            mejor_grupo, campo_grupo = 0.0, ""
            for alternativa in grupo:
                partes = alternativa.split()
                puntaje_alt, campo_alt = 0.0, ""
                for parte in partes:
                    mejor_parte, campo_parte = 0.0, ""
                    if parte == campos["codigo"] or parte == campos["id"]:
                        mejor_parte, campo_parte = 12.0, "codigo"
                    for campo, peso in PESOS_CAMPOS.items():
                        f = cls._fuerza_token(parte, campos[campo], palabras[campo]) * peso
                        if f > mejor_parte:
                            mejor_parte, campo_parte = f, campo
                    if mejor_parte == 0:
                        puntaje_alt = 0.0
                        break
                    puntaje_alt += mejor_parte / len(partes)
                    campo_alt = campo_alt or campo_parte
                if puntaje_alt > mejor_grupo:
                    mejor_grupo, campo_grupo = puntaje_alt, campo_alt
            if mejor_grupo == 0:
                return 0.0, ""
            total += mejor_grupo
            mejor_campo = mejor_campo or campo_grupo
        return total, mejor_campo

    @classmethod
    def _tokens_consulta(cls, query: str) -> Tuple[str, List[List[str]]]:
        q = normalizar_texto(query).replace(",", " ").replace("/", " ").replace("-", " ")
        tokens = [t for t in q.split() if t]
        utiles = [t for t in tokens if t not in PALABRAS_VACIAS] or tokens
        grupos = []
        for t in utiles:
            alternativas = [t]
            if t in ALIAS_BUSQUEDA:
                alternativas.append(ALIAS_BUSQUEDA[t])
            grupos.append(alternativas)
        return q, grupos

    @classmethod
    def buscar_agencias_inteligente(cls, query: str, limite: int = 15, departamento: Optional[str] = None,
                                    provincia: Optional[str] = None, distrito: Optional[str] = None
                                    ) -> List[Dict[str, Any]]:
        if not query or len(query.strip()) < 2:
            return []
        cls.cargar()
        q, grupos = cls._tokens_consulta(query)
        if not grupos:
            return []
        filtros = {k: normalizar_texto(v) for k, v in
                   (("departamento", departamento), ("provincia", provincia), ("distrito", distrito)) if v}
        resultados = []
        for agencia, campos, palabras in cls._indice:
            if any(campos[k] != v for k, v in filtros.items()):
                continue
            score, campo = cls._puntuar(grupos, campos, palabras)
            if score <= 0:
                continue
            if campos["nombre"].startswith(q):
                score += 15
            if campos["distrito"] == q:
                score += 10
            item = cls.vista_publica(agencia)
            item["relevancia"] = round(score, 2)
            item["coincidencia"] = campo
            resultados.append(item)
        resultados.sort(key=lambda x: (-x["relevancia"], normalizar_texto(x["nombre"])))
        return resultados[:limite]

    @classmethod
    def sugerencias(cls, query: str, limite_agencias: int = 8, limite_ubicaciones: int = 5) -> Dict[str, Any]:
        """Autocompletado agrupado: ubicaciones (distritos/provincias) + agencias."""
        agencias = cls.buscar_agencias_inteligente(query, limite=limite_agencias)
        q, grupos = cls._tokens_consulta(query or "")
        ubicaciones: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
        if grupos:
            for a, campos, palabras in cls._indice:
                texto = f"{campos['distrito']} {campos['provincia']} {campos['departamento']}"
                pal = palabras["distrito"] + palabras["provincia"] + palabras["departamento"]
                ok = all(any(all(cls._fuerza_token(p, texto, pal) >= 0.5 for p in alt.split()) for alt in g)
                         for g in grupos)
                if not ok:
                    continue
                clave = (a["departamento"], a["provincia"], a["distrito"])
                u = ubicaciones.setdefault(clave, {"departamento": clave[0], "provincia": clave[1],
                                                   "distrito": clave[2], "total": 0,
                                                   "exacta": campos["distrito"].startswith(q)})
                u["total"] += 1
        lista_u = sorted(ubicaciones.values(), key=lambda u: (not u["exacta"], -u["total"], normalizar_texto(u["distrito"])))
        for u in lista_u:
            u.pop("exacta", None)
        return {"query": query, "ubicaciones": lista_u[:limite_ubicaciones], "agencias": agencias}

    # ------------------------------------------------------------------
    # Estado y metadatos del catálogo
    # ------------------------------------------------------------------
    @classmethod
    def estado_catalogo(cls) -> Dict[str, Any]:
        cls.cargar()
        meta = cls._meta
        actualizado = meta.get("actualizado_en")
        dias = None
        if actualizado:
            try:
                dias = (get_lima_now() - datetime.fromisoformat(actualizado)).days
            except ValueError:
                dias = None
        return {
            "fuente": meta.get("fuente", "Sin información de origen"),
            "tipo_fuente": meta.get("tipo_fuente", "desconocido"),
            "fuente_oficial": meta.get("tipo_fuente") in ("api_autorizada", "archivo_oficial"),
            "actualizado_en": actualizado,
            "dias_desde_actualizacion": dias,
            "desactualizado": dias is None or dias > settings.AGENCIAS_DIAS_VIGENCIA,
            "total_registros": len(cls._catalogo),
            "activas": sum(1 for a in cls._catalogo if a.get("activo")),
            "publicas": len(cls._publicas),
            "inactivas": sum(1 for a in cls._catalogo if not a.get("activo")),
            "sin_destino": sum(1 for a in cls._catalogo if a.get("activo") and not a.get("acepta_destino", True)),
            "departamentos": len({a["departamento"] for a in cls._publicas}),
            "provincias": len({(a["departamento"], a["provincia"]) for a in cls._publicas}),
            "distritos": len({(a["departamento"], a["provincia"], a["distrito"]) for a in cls._publicas}),
            "api_configurada": bool(settings.SHALOM_API_URL),
            "overrides": len(meta.get("overrides", {})),
            "historial": meta.get("historial", [])[:10],
            "version": cls.huella_publica(),
        }

    @classmethod
    def listar_admin(cls, q: str = "", estado: str = "todas", limite: int = 50) -> List[Dict[str, Any]]:
        cls.cargar()
        qn = normalizar_texto(q)
        res = []
        for a in cls._catalogo:
            if estado == "activas" and not a.get("activo"):
                continue
            if estado == "inactivas" and a.get("activo"):
                continue
            if qn:
                corpus = normalizar_texto(" ".join(str(a.get(k, "")) for k in
                                                   ("id", "codigo", "nombre", "distrito", "provincia", "departamento", "direccion")))
                if not all(t in corpus for t in qn.split()):
                    continue
            res.append({k: a.get(k) for k in ("id", "codigo", "nombre", "departamento", "provincia", "distrito",
                                               "direccion", "horario", "activo", "acepta_destino",
                                               "motivo_inactiva", "override_manual")})
            if len(res) >= limite:
                break
        return res

    # ------------------------------------------------------------------
    # Actualización desde fuentes autorizadas
    # ------------------------------------------------------------------
    @classmethod
    def previsualizar(cls, registros: List[Dict[str, Any]], fuente: str) -> Dict[str, Any]:
        cls.cargar()
        depurado = depurar_agencias(registros, fuente)
        nuevo = depurado["agencias"]
        diferencias = comparar_catalogos(cls._catalogo, nuevo)
        requiere = diferencias["porcentaje_baja"] > settings.AGENCIAS_MAX_BAJA_PCT
        return {
            "reporte": depurado["reporte"],
            "diferencias": diferencias,
            "requiere_confirmacion": requiere,
            "advertencia": (f"La actualización retiraría o desactivaría el {diferencias['porcentaje_baja']}% de las "
                            f"agencias activas (umbral {settings.AGENCIAS_MAX_BAJA_PCT}%). Verifica que el archivo "
                            "o la respuesta de la API esté completa antes de confirmar.") if requiere else "",
            "_nuevo": nuevo,
        }

    @classmethod
    def aplicar_actualizacion(cls, registros: List[Dict[str, Any]], fuente: str, tipo_fuente: str,
                              usuario: str = "sistema", forzar: bool = False, dry_run: bool = False) -> Dict[str, Any]:
        with cls._lock:
            previa = cls.previsualizar(registros, fuente)
            nuevo = previa.pop("_nuevo")
            resultado = {"success": True, "aplicado": False, "dry_run": dry_run, **previa}
            if previa["reporte"]["publicables"] == 0:
                resultado.update(success=False, mensaje="La fuente no contiene agencias válidas y activas. No se aplicaron cambios.")
                return resultado
            if dry_run:
                resultado["mensaje"] = "Vista previa generada. No se aplicaron cambios."
                return resultado
            if previa["requiere_confirmacion"] and not forzar:
                resultado.update(success=False, mensaje=previa["advertencia"])
                return resultado

            ahora = get_lima_now().isoformat(timespec="seconds")
            ids_nuevos = {a["id"] for a in nuevo}
            anteriores = {a["id"]: a for a in cls._catalogo}
            for a in nuevo:
                previo = anteriores.get(a["id"])
                if previo and huella_agencia(previo) == huella_agencia(a):
                    a["actualizado_en"] = previo.get("actualizado_en", ahora)
                else:
                    a["actualizado_en"] = ahora
            # Las agencias que ya no figuran en la fuente se conservan como inactivas (trazabilidad de envíos)
            for ident, previo in anteriores.items():
                if ident not in ids_nuevos:
                    retirada = dict(previo)
                    if retirada.get("activo"):
                        retirada["activo"] = False
                        retirada["motivo_inactiva"] = f"No figura en la actualización del {ahora[:10]}"
                        retirada["actualizado_en"] = ahora
                    retirada.pop("override_manual", None)
                    nuevo.append(retirada)

            respaldo = cls._respaldar()
            meta = dict(cls._meta)
            meta.update({
                "fuente": fuente, "tipo_fuente": tipo_fuente, "actualizado_en": ahora,
                "reporte": previa["reporte"],
            })
            historial = meta.get("historial", [])
            historial.insert(0, {
                "fecha": ahora, "fuente": fuente, "tipo": tipo_fuente, "usuario": usuario,
                "nuevas": previa["diferencias"]["nuevas"], "modificadas": previa["diferencias"]["modificadas"],
                "retiradas": previa["diferencias"]["retiradas"] + previa["diferencias"]["desactivadas"],
                "publicables": previa["reporte"]["publicables"], "respaldo": respaldo,
            })
            meta["historial"] = historial[:30]
            for a in nuevo:  # no persistir marcas calculadas
                a.pop("override_manual", None)
            cls._escribir_json_atomico(cls.ruta_catalogo(), nuevo)
            cls._escribir_json_atomico(cls.ruta_meta(), meta)
            cls._meta = meta
            cls._aplicar_en_memoria(nuevo)
            resultado.update(aplicado=True, respaldo=respaldo,
                             mensaje=f"Catálogo actualizado: {len(cls._publicas)} agencias disponibles para los clientes.")
            return resultado

    @classmethod
    def importar_contenido(cls, contenido: str, formato: str, fuente: str, usuario: str = "admin",
                           dry_run: bool = True, forzar: bool = False) -> Dict[str, Any]:
        try:
            registros = parsear_contenido(contenido, formato)
        except (ValueError, json.JSONDecodeError) as e:
            return {"success": False, "aplicado": False, "mensaje": f"No se pudo leer el archivo: {e}"}
        if not registros:
            return {"success": False, "aplicado": False, "mensaje": "El archivo no contiene registros."}
        return cls.aplicar_actualizacion(registros, fuente or "Archivo oficial importado", "archivo_oficial",
                                         usuario=usuario, forzar=forzar, dry_run=dry_run)

    @classmethod
    async def sincronizar_proveedor_externo(cls, dry_run: bool = False, forzar: bool = False,
                                            usuario: str = "admin") -> Dict[str, Any]:
        """Sincroniza con la API oficial/autorizada configurada en SHALOM_API_URL."""
        if not settings.SHALOM_API_URL:
            return {
                "success": False, "aplicado": False,
                "mensaje": ("No hay una API autorizada configurada (SHALOM_API_URL). Shalom no publica una API "
                            "abierta: solicita acceso corporativo a Shalom o importa el archivo oficial de agencias "
                            "desde el panel. Se mantiene el catálogo actual."),
            }
        headers = {"Accept": "application/json", "User-Agent": f"{settings.BUSINESS_NAME} - ShalomEnvios/{settings.APP_VERSION}"}
        if settings.SHALOM_API_KEY:
            headers["Authorization"] = f"Bearer {settings.SHALOM_API_KEY}"
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                res = await client.get(settings.SHALOM_API_URL, headers=headers)
        except httpx.HTTPError as e:
            logger.error(f"Error de red al sincronizar agencias: {e}")
            return {"success": False, "aplicado": False, "mensaje": f"No se pudo conectar con la API autorizada: {e}"}
        if res.status_code != 200:
            return {"success": False, "aplicado": False,
                    "mensaje": f"La API autorizada respondió HTTP {res.status_code}. Se mantiene el catálogo actual."}
        try:
            registros = parsear_contenido(res.text, "json")
        except (ValueError, json.JSONDecodeError) as e:
            return {"success": False, "aplicado": False, "mensaje": f"Respuesta de la API no válida: {e}"}
        return cls.aplicar_actualizacion(registros, settings.SHALOM_API_SOURCE_NAME, "api_autorizada",
                                         usuario=usuario, forzar=forzar, dry_run=dry_run)

    @classmethod
    def cambiar_estado_agencia(cls, agencia_id: str, activo: bool, motivo: str = "",
                               usuario: str = "admin") -> Optional[Dict[str, Any]]:
        """Activa/desactiva manualmente una agencia (p. ej. cierre reportado). Persiste entre sincronizaciones."""
        with cls._lock:
            cls.cargar()
            if agencia_id not in cls._por_id:
                return None
            meta = dict(cls._meta)
            overrides = dict(meta.get("overrides", {}))
            overrides[agencia_id] = {"activo": activo, "motivo": motivo or ("Reactivada manualmente" if activo
                                     else "Desactivada manualmente"), "usuario": usuario,
                                     "fecha": get_lima_now().isoformat(timespec="seconds")}
            meta["overrides"] = overrides
            cls._escribir_json_atomico(cls.ruta_meta(), meta)
            cls._meta = meta
            cls._aplicar_en_memoria(cls._catalogo)
            return cls._por_id[agencia_id]

    @classmethod
    def quitar_override(cls, agencia_id: str) -> bool:
        with cls._lock:
            cls.cargar()
            meta = dict(cls._meta)
            overrides = dict(meta.get("overrides", {}))
            if agencia_id not in overrides:
                return False
            overrides.pop(agencia_id)
            meta["overrides"] = overrides
            cls._escribir_json_atomico(cls.ruta_meta(), meta)
            cls._meta = meta
            # Recargar desde disco para recuperar el estado original de la fuente
            cls.cargar(forzar=True)
            return True
