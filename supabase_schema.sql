-- ==============================================================================
-- SCHEMA POSTGRESQL PARA SUPABASE: FORMULARIO INTELIGENTE DE ENVÍOS SHALOM PERÚ
-- Zona horaria: America/Lima
-- Compatible con Supabase Database, RLS (Row Level Security) y triggers automáticos.
-- ==============================================================================

-- 1. Establecer zona horaria de la sesión
SET timezone = 'America/Lima';

-- Habilitar extensión pgcrypto para UUIDs y funciones criptográficas
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ==============================================================================
-- 2. TABLA: agencias_shalom
-- Catálogo administrable de agencias verificadas de Shalom en Perú
-- ==============================================================================
CREATE TABLE IF NOT EXISTS agencias_shalom (
    id VARCHAR(50) PRIMARY KEY,
    nombre VARCHAR(150) NOT NULL,
    departamento VARCHAR(60) NOT NULL,
    provincia VARCHAR(60) NOT NULL,
    distrito VARCHAR(60) NOT NULL,
    direccion TEXT NOT NULL,
    referencia TEXT,
    horario VARCHAR(200) NOT NULL DEFAULT 'Lunes a Viernes 8:00 AM - 6:30 PM | Sábados 8:00 AM - 2:00 PM',
    telefono VARCHAR(100) DEFAULT '(01) 500-7878',
    latitud NUMERIC(10, 7),
    longitud NUMERIC(10, 7),
    google_maps_url TEXT,
    activo BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT (timezone('America/Lima', now())),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT (timezone('America/Lima', now()))
);

-- Índices para búsqueda rápida en cascada y predictiva
CREATE INDEX IF NOT EXISTS idx_agencias_ubicacion ON agencias_shalom (departamento, provincia, distrito);
CREATE INDEX IF NOT EXISTS idx_agencias_activo ON agencias_shalom (activo);

-- ==============================================================================
-- 3. TABLA: envios_shalom
-- Registros de solicitudes de envío de clientes
-- ==============================================================================
CREATE TABLE IF NOT EXISTS envios_shalom (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    codigo_registro VARCHAR(32) NOT NULL UNIQUE,
    dni VARCHAR(8) NOT NULL CHECK (dni ~ '^[0-9]{8}$'),
    nombres VARCHAR(100) NOT NULL,
    apellido_paterno VARCHAR(100) NOT NULL,
    apellido_materno VARCHAR(100) NOT NULL,
    celular VARCHAR(9) NOT NULL CHECK (celular ~ '^[0-9]{9}$'),
    
    -- Ubicación y Agencia de destino
    departamento VARCHAR(60) NOT NULL,
    provincia VARCHAR(60) NOT NULL,
    distrito VARCHAR(60) NOT NULL,
    codigo_agencia VARCHAR(50) NOT NULL,
    nombre_agencia VARCHAR(150) NOT NULL,
    direccion_agencia TEXT NOT NULL,
    referencia_agencia TEXT,
    
    -- Verificación de identidad oficial (RENIEC / ID Perú) vs Manual
    estado_verificacion_identidad VARCHAR(40) NOT NULL DEFAULT 'MANUAL_NO_VERIFICADO'
        CHECK (estado_verificacion_identidad IN ('VERIFICADO_RENIEC_OFICIAL', 'MANUAL_NO_VERIFICADO')),
        
    -- Estados del registro
    estado_registro VARCHAR(30) NOT NULL DEFAULT 'PENDIENTE'
        CHECK (estado_registro IN ('PENDIENTE', 'CONFIRMADO', 'EN_PREPARACION', 'ENVIADO', 'ENTREGADO', 'CANCELADO')),
        
    -- Clave de idempotencia para evitar duplicados en reintentos o doble clic
    idempotency_key VARCHAR(64) NOT NULL UNIQUE,
    
    -- Metadatos adicionales
    ip_origen VARCHAR(45),
    user_agent TEXT,
    notas_admin TEXT,
    fecha_registro TIMESTAMPTZ NOT NULL DEFAULT (timezone('America/Lima', now())),
    created_at TIMESTAMPTZ NOT NULL DEFAULT (timezone('America/Lima', now())),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT (timezone('America/Lima', now()))
);

-- Índices de consulta y auditoría
CREATE INDEX IF NOT EXISTS idx_envios_dni ON envios_shalom (dni);
CREATE INDEX IF NOT EXISTS idx_envios_codigo ON envios_shalom (codigo_registro);
CREATE INDEX IF NOT EXISTS idx_envios_fecha ON envios_shalom (fecha_registro DESC);
CREATE INDEX IF NOT EXISTS idx_envios_estado ON envios_shalom (estado_registro);
CREATE INDEX IF NOT EXISTS idx_envios_agencia ON envios_shalom (codigo_agencia);

-- ==============================================================================
-- 4. TABLA: admin_users
-- Usuarios administradores para acceso al panel privado
-- ==============================================================================
CREATE TABLE IF NOT EXISTS admin_users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    nombre_completo VARCHAR(150) NOT NULL,
    rol VARCHAR(30) NOT NULL DEFAULT 'ADMIN' CHECK (rol IN ('ADMIN', 'OPERADOR')),
    activo BOOLEAN NOT NULL DEFAULT true,
    ultimo_acceso TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT (timezone('America/Lima', now()))
);

-- ==============================================================================
-- 5. TRIGGER: Actualización automática de updated_at con zona horaria America/Lima
-- ==============================================================================
CREATE OR REPLACE FUNCTION trigger_set_timestamp_lima()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = timezone('America/Lima', now());
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS set_timestamp_envios ON envios_shalom;
CREATE TRIGGER set_timestamp_envios
BEFORE UPDATE ON envios_shalom
FOR EACH ROW
EXECUTE FUNCTION trigger_set_timestamp_lima();

DROP TRIGGER IF EXISTS set_timestamp_agencias ON agencias_shalom;
CREATE TRIGGER set_timestamp_agencias
BEFORE UPDATE ON agencias_shalom
FOR EACH ROW
EXECUTE FUNCTION trigger_set_timestamp_lima();

-- ==============================================================================
-- 6. POLÍTICAS ROW LEVEL SECURITY (RLS) PARA SUPABASE
-- ==============================================================================
ALTER TABLE envios_shalom ENABLE ROW LEVEL SECURITY;
ALTER TABLE agencias_shalom ENABLE ROW LEVEL SECURITY;
ALTER TABLE admin_users ENABLE ROW LEVEL SECURITY;

-- Lectura pública de agencias activas
CREATE POLICY "Permitir lectura publica de agencias activas" 
    ON agencias_shalom FOR SELECT 
    USING (activo = true);

-- Inserción de envíos permitida para clientes (a través de la API/Service Role o autenticado)
CREATE POLICY "Permitir insercion anonima controlada de envios" 
    ON envios_shalom FOR INSERT 
    WITH CHECK (true);

-- ==============================================================================
-- FIN DEL SCRIPT SQL
-- ==============================================================================
