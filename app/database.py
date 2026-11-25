import sqlite3
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import httpx
from app.config import settings
from app.services.id_generator import get_lima_now
from app.services.auth_service import hash_password

logger = logging.getLogger("database")

class DatabaseManager:
    """
    Gestor de base de datos híbrido / dual:
    - Persistencia nativa local en SQLite.
    - Sincronización asíncrona hacia Supabase (PostgreSQL) si está configurado.
    - Garantiza idempotencia estricta para evitar dobles registros o envíos accidentales.
    - Soporte para emisión de Guías Oficiales con Shalom Pro.
    """

    @classmethod
    def get_connection(cls) -> sqlite3.Connection:
        settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(settings.SQLITE_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    @classmethod
    def init_db(cls):
        """Inicializa las tablas locales SQLite y asegura que exista el usuario admin por defecto."""
        conn = cls.get_connection()
        cur = conn.cursor()

        # Tabla de envíos
        cur.execute("""
            CREATE TABLE IF NOT EXISTS envios_shalom (
                id TEXT PRIMARY KEY,
                codigo_registro TEXT UNIQUE NOT NULL,
                tipo_documento TEXT NOT NULL DEFAULT 'DNI',
                dni TEXT NOT NULL,
                nombres TEXT NOT NULL,
                apellido_paterno TEXT NOT NULL,
                apellido_materno TEXT NOT NULL,
                celular TEXT NOT NULL,
                departamento TEXT NOT NULL,
                provincia TEXT NOT NULL,
                distrito TEXT NOT NULL,
                codigo_agencia TEXT NOT NULL,
                nombre_agencia TEXT NOT NULL,
                direccion_agencia TEXT NOT NULL,
                referencia_agencia TEXT,
                fecha_despacho TEXT,
                numero_guia_shalom TEXT,
                estado_shalom_pro TEXT DEFAULT 'NO_EMITIDO',
                url_guia_pdf TEXT,
                monto_flete REAL,
                estado_verificacion_identidad TEXT NOT NULL DEFAULT 'MANUAL_NO_VERIFICADO',
                estado_registro TEXT NOT NULL DEFAULT 'PENDIENTE',
                idempotency_key TEXT UNIQUE NOT NULL,
                ip_origen TEXT,
                notas_admin TEXT,
                fecha_registro TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        # Migraciones dinámicas de columnas para Shalom Pro
        columnas_a_verificar = [
            ("fecha_despacho", "TEXT"),
            ("tipo_documento", "TEXT DEFAULT 'DNI'"),
            ("numero_guia_shalom", "TEXT"),
            ("estado_shalom_pro", "TEXT DEFAULT 'NO_EMITIDO'"),
            ("url_guia_pdf", "TEXT"),
            ("monto_flete", "REAL"),
            ("tamano_paquete", "TEXT DEFAULT 'PAQUETE XS'")
        ]

        for col, col_type in columnas_a_verificar:
            try:
                cur.execute(f"ALTER TABLE envios_shalom ADD COLUMN {col} {col_type}")
            except sqlite3.OperationalError:
                pass

        # Índices de optimización
        cur.execute("CREATE INDEX IF NOT EXISTS idx_envios_dni ON envios_shalom(dni)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_envios_codigo ON envios_shalom(codigo_registro)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_envios_idemp ON envios_shalom(idempotency_key)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_envios_fecha ON envios_shalom(fecha_registro)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_envios_guia ON envios_shalom(numero_guia_shalom)")

        # Tabla de administradores
        cur.execute("""
            CREATE TABLE IF NOT EXISTS admin_users (
                id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                nombre_completo TEXT NOT NULL,
                rol TEXT NOT NULL DEFAULT 'ADMIN',
                activo INTEGER NOT NULL DEFAULT 1,
                ultimo_acceso TEXT,
                created_at TEXT NOT NULL
            )
        """)

        # Crear o actualizar admin por defecto
        hashed = hash_password(settings.ADMIN_PASSWORD)
        cur.execute("SELECT id FROM admin_users WHERE username = ?", (settings.ADMIN_USERNAME,))
        row = cur.fetchone()
        if not row:
            now_iso = get_lima_now().isoformat()
            cur.execute("""
                INSERT INTO admin_users (id, username, password_hash, nombre_completo, rol, activo, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, ("usr_admin_default", settings.ADMIN_USERNAME, hashed, "Administrador del Sistema", "ADMIN", 1, now_iso))
        else:
            cur.execute("UPDATE admin_users SET password_hash = ? WHERE username = ?", (hashed, settings.ADMIN_USERNAME))

        conn.commit()
        conn.close()

        # Si Supabase está configurado, sincronizar registros existentes
        cls.sync_from_supabase()

    @classmethod
    def sync_from_supabase(cls):
        """Descarga registros desde Supabase para poblar la base local al iniciar el contenedor."""
        if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
            return
        try:
            url = f"{settings.SUPABASE_URL}/rest/v1/envios_shalom?select=*"
            headers = {
                "apikey": settings.SUPABASE_KEY,
                "Authorization": f"Bearer {settings.SUPABASE_KEY}"
            }
            with httpx.Client(timeout=8.0) as client:
                res = client.get(url, headers=headers)
                if res.status_code == 200:
                    filas = res.json()
                    if isinstance(filas, list) and len(filas) > 0:
                        conn = cls.get_connection()
                        cur = conn.cursor()
                        valid_cols = [
                            'id', 'codigo_registro', 'tipo_documento', 'dni', 'nombres',
                            'apellido_paterno', 'apellido_materno', 'celular', 'departamento',
                            'provincia', 'distrito', 'codigo_agencia', 'nombre_agencia',
                            'direccion_agencia', 'referencia_agencia', 'fecha_despacho',
                            'numero_guia_shalom', 'estado_shalom_pro', 'url_guia_pdf',
                            'monto_flete', 'tamano_paquete', 'estado_verificacion_identidad',
                            'estado_registro', 'idempotency_key', 'ip_origen', 'notas_admin',
                            'fecha_registro', 'created_at', 'updated_at'
                        ]
                        for r in filas:
                            cols = [k for k in r.keys() if k in valid_cols]
                            placeholders = ', '.join(['?'] * len(cols))
                            col_names = ', '.join(cols)
                            vals = [r[c] for c in cols]
                            cur.execute(f"INSERT OR REPLACE INTO envios_shalom ({col_names}) VALUES ({placeholders})", vals)
                        conn.commit()
                        conn.close()
        except Exception as e:
            logger.warning(f"Error sincronizando desde Supabase: {e}")

    @classmethod
    def _update_in_supabase(cls, tabla: str, id_envio: str, data: Dict[str, Any]):
        if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
            return
        try:
            url = f"{settings.SUPABASE_URL}/rest/v1/{tabla}"
            headers = {
                "apikey": settings.SUPABASE_KEY,
                "Authorization": f"Bearer {settings.SUPABASE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal"
            }
            with httpx.Client(timeout=5.0) as client:
                client.patch(f"{url}?or=(id.eq.{id_envio},codigo_registro.eq.{id_envio})", headers=headers, json=data)
        except Exception as e:
            logger.warning(f"No se pudo actualizar en Supabase: {e}")

    @classmethod
    def _delete_in_supabase(cls, id_envio: str):
        if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
            return
        try:
            url = f"{settings.SUPABASE_URL}/rest/v1/envios_shalom"
            headers = {
                "apikey": settings.SUPABASE_KEY,
                "Authorization": f"Bearer {settings.SUPABASE_KEY}"
            }
            with httpx.Client(timeout=5.0) as client:
                client.delete(f"{url}?or=(id.eq.{id_envio},codigo_registro.eq.{id_envio})", headers=headers)
        except Exception as e:
            logger.warning(f"No se pudo eliminar en Supabase: {e}")

    @classmethod
    async def _insert_in_supabase(cls, tabla: str, data: Dict[str, Any]) -> bool:
        if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
            return False

        try:
            url = f"{settings.SUPABASE_URL}/rest/v1/{tabla}"
            headers = {
                "apikey": settings.SUPABASE_KEY,
                "Authorization": f"Bearer {settings.SUPABASE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal"
            }
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.post(url, headers=headers, json=data)
                return res.status_code in (200, 201)
        except Exception as e:
            logger.warning(f"No se pudo sincronizar con Supabase: {e}")
            return False

    @classmethod
    async def crear_envio(cls, envio_data: Dict[str, Any]) -> Dict[str, Any]:
        cls.init_db()
        idemp_key = envio_data["idempotency_key"]

        conn = cls.get_connection()
        cur = conn.cursor()

        cur.execute("SELECT * FROM envios_shalom WHERE idempotency_key = ?", (idemp_key,))
        existente = cur.fetchone()
        if existente:
            conn.close()
            return {
                "duplicado": True,
                "registro": dict(existente)
            }

        now_iso = get_lima_now().isoformat()
        nuevo_id = envio_data.get("id") or f"env_{get_lima_now().strftime('%Y%m%d%H%M%S')}_{idemp_key[:8]}"

        campos = {
            "id": nuevo_id,
            "codigo_registro": envio_data["codigo_registro"],
            "tipo_documento": envio_data.get("tipo_documento", "DNI"),
            "dni": envio_data["dni"],
            "nombres": envio_data["nombres"].strip().upper(),
            "apellido_paterno": envio_data["apellido_paterno"].strip().upper(),
            "apellido_materno": envio_data["apellido_materno"].strip().upper(),
            "celular": envio_data["celular"].strip(),
            "departamento": envio_data["departamento"].strip(),
            "provincia": envio_data["provincia"].strip(),
            "distrito": envio_data["distrito"].strip(),
            "codigo_agencia": envio_data["codigo_agencia"].strip(),
            "nombre_agencia": envio_data["nombre_agencia"].strip(),
            "direccion_agencia": envio_data["direccion_agencia"].strip(),
            "referencia_agencia": envio_data.get("referencia_agencia", "").strip(),
            "fecha_despacho": envio_data.get("fecha_despacho", "").strip(),
            "numero_guia_shalom": None,
            "estado_shalom_pro": "NO_EMITIDO",
            "url_guia_pdf": None,
            "monto_flete": None,
            "tamano_paquete": envio_data.get("tamano_paquete", "PAQUETE XS"),
            "estado_verificacion_identidad": envio_data.get("estado_verificacion_identidad", "MANUAL_NO_VERIFICADO"),
            "estado_registro": envio_data.get("estado_registro", "PENDIENTE"),
            "idempotency_key": idemp_key,
            "ip_origen": envio_data.get("ip_origen", ""),
            "notas_admin": envio_data.get("notas_admin", ""),
            "fecha_registro": now_iso,
            "created_at": now_iso,
            "updated_at": now_iso
        }

        columnas = ", ".join(campos.keys())
        placeholders = ", ".join(["?"] * len(campos))
        valores = list(campos.values())

        cur.execute(f"INSERT INTO envios_shalom ({columnas}) VALUES ({placeholders})", valores)
        conn.commit()
        conn.close()

        await cls._insert_in_supabase("envios_shalom", campos)

        return {
            "duplicado": False,
            "registro": campos
        }

    @classmethod
    def obtener_envios(cls, filtro_estado: Optional[str] = None, busqueda: Optional[str] = None, limite: int = 100) -> List[Dict[str, Any]]:
        cls.init_db()
        conn = cls.get_connection()
        cur = conn.cursor()

        query = "SELECT * FROM envios_shalom WHERE 1=1"
        params = []

        if filtro_estado and filtro_estado != "TODOS":
            query += " AND estado_registro = ?"
            params.append(filtro_estado)

        if busqueda and busqueda.strip():
            b = f"%{busqueda.strip()}%"
            query += " AND (dni LIKE ? OR codigo_registro LIKE ? OR nombres LIKE ? OR apellido_paterno LIKE ? OR celular LIKE ? OR nombre_agencia LIKE ? OR numero_guia_shalom LIKE ?)"
            params.extend([b, b, b, b, b, b, b])

        query += " ORDER BY fecha_registro DESC LIMIT ?"
        params.append(limite)

        cur.execute(query, params)
        filas = cur.fetchall()
        conn.close()
        return [dict(f) for f in filas]

    @classmethod
    def obtener_envio_por_codigo(cls, codigo: str) -> Optional[Dict[str, Any]]:
        cls.init_db()
        conn = cls.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM envios_shalom WHERE codigo_registro = ? OR id = ?", (codigo.strip(), codigo.strip()))
        fila = cur.fetchone()
        conn.close()
        return dict(fila) if fila else None

    @classmethod
    def actualizar_guia_shalom_pro(
        cls, 
        id_envio: str, 
        numero_guia: str, 
        url_pdf: str, 
        monto_flete: float, 
        estado_shalom: str = "EMITIDO"
    ) -> bool:
        """Actualiza el envío con los datos de la guía oficial emitida en Shalom Pro."""
        cls.init_db()
        conn = cls.get_connection()
        cur = conn.cursor()
        now_iso = get_lima_now().isoformat()

        cur.execute("""
            UPDATE envios_shalom 
            SET numero_guia_shalom = ?, url_guia_pdf = ?, monto_flete = ?, estado_shalom_pro = ?, estado_registro = 'EN_PREPARACION', updated_at = ?
            WHERE id = ? OR codigo_registro = ?
        """, (numero_guia, url_pdf, monto_flete, estado_shalom, now_iso, id_envio, id_envio))

        afectados = cur.rowcount
        conn.commit()
        conn.close()

        if afectados > 0:
            cls._update_in_supabase("envios_shalom", id_envio, {
                "numero_guia_shalom": numero_guia,
                "url_guia_pdf": url_pdf,
                "monto_flete": monto_flete,
                "estado_shalom_pro": estado_shalom,
                "estado_registro": "EN_PREPARACION",
                "updated_at": now_iso
            })

        return afectados > 0

    @classmethod
    def actualizar_estado_envio(cls, id_envio: str, nuevo_estado: str, notas_admin: Optional[str] = None) -> bool:
        cls.init_db()
        conn = cls.get_connection()
        cur = conn.cursor()
        now_iso = get_lima_now().isoformat()
        
        datos_supa = {"estado_registro": nuevo_estado, "updated_at": now_iso}
        if notas_admin is not None:
            datos_supa["notas_admin"] = notas_admin
            cur.execute("""
                UPDATE envios_shalom 
                SET estado_registro = ?, notas_admin = ?, updated_at = ? 
                WHERE id = ? OR codigo_registro = ?
            """, (nuevo_estado, notas_admin, now_iso, id_envio, id_envio))
        else:
            cur.execute("""
                UPDATE envios_shalom 
                SET estado_registro = ?, updated_at = ? 
                WHERE id = ? OR codigo_registro = ?
            """, (nuevo_estado, now_iso, id_envio, id_envio))
            
        afectados = cur.rowcount
        conn.commit()
        conn.close()

        if afectados > 0:
            cls._update_in_supabase("envios_shalom", id_envio, datos_supa)

        return afectados > 0

    @classmethod
    def actualizar_tamano_envio(cls, id_envio: str, nuevo_tamano: str) -> bool:
        """Actualiza el tamaño asignado al paquete (SOBRE, PAQUETE XXS, PAQUETE XS, PAQUETE S, etc.)."""
        cls.init_db()
        conn = cls.get_connection()
        cur = conn.cursor()
        now_iso = get_lima_now().isoformat()
        cur.execute("""
            UPDATE envios_shalom 
            SET tamano_paquete = ?, updated_at = ? 
            WHERE id = ? OR codigo_registro = ?
        """, (nuevo_tamano.strip().upper(), now_iso, id_envio, id_envio))
        afectados = cur.rowcount
        conn.commit()
        conn.close()

        if afectados > 0:
            cls._update_in_supabase("envios_shalom", id_envio, {
                "tamano_paquete": nuevo_tamano.strip().upper(),
                "updated_at": now_iso
            })

        return afectados > 0

    @classmethod
    def eliminar_envio(cls, id_envio: str) -> bool:
        """Elimina permanentemente un registro de envío por id o codigo_registro."""
        cls.init_db()
        conn = cls.get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM envios_shalom WHERE id = ? OR codigo_registro = ?", (id_envio.strip(), id_envio.strip()))
        afectados = cur.rowcount
        conn.commit()
        conn.close()

        if afectados > 0:
            cls._delete_in_supabase(id_envio)

        return afectados > 0

    @classmethod
    def obtener_metricas(cls) -> Dict[str, Any]:
        cls.init_db()
        conn = cls.get_connection()
        cur = conn.cursor()

        cur.execute("SELECT COUNT(*) FROM envios_shalom")
        total = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM envios_shalom WHERE estado_registro = 'PENDIENTE'")
        pendientes = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM envios_shalom WHERE estado_registro = 'ENVIADO'")
        enviados = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM envios_shalom WHERE numero_guia_shalom IS NOT NULL")
        guias_emitidas = cur.fetchone()[0]

        conn.close()
        return {
            "total_envios": total,
            "pendientes": pendientes,
            "enviados": enviados,
            "guias_emitidas": guias_emitidas
        }
