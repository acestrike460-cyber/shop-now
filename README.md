# Sistema Inteligente de Envíos Shalom Perú (Gestión Independiente v3.0)

Plataforma Web Full Stack de producción para recolección asistida de datos de clientes y selección inteligente de agencias de **Shalom Empresarial** en los 25 departamentos del Perú.

---

## 🌟 Novedades de la Versión 3.0

### 1. Integración Integral de Agencias de Shalom a Nivel Nacional
* **Investigación de API Oficial:** Se evaluó la disponibilidad de APIs de Shalom Empresarial. Shalom no ofrece un portal público de API abierta; las integraciones formales se gestionan mediante credenciales corporativas (*Shalom Pro*). El sistema cuenta con conector para API corporativa (`SHALOM_API_URL` y `SHALOM_API_KEY`) y soporte para importación de snapshots oficiales.
* **Cobertura Nacional Completa:** Catálogo canónico con **más de 500 agencias activas habilitadas como destino** en los 25 departamentos, 117 provincias y más de 270 distritos del Perú.
* **Depuración Automática de Registros:**
  * Eliminación de agencias duplicadas por ubicación física y dirección exacta.
  * Descarte de agencias inactivas, cerradas o en estado *"POR DEFINIR"*.
  * Validación y descarte de coordenadas fuera del territorio peruano.
* **Selectores Dinámicos y Jerárquicos:**
  * Cascada dependiente: **Departamento $\to$ Provincia $\to$ Distrito**.
  * Selector inteligente que filtra las agencias de acuerdo a la demarcación elegida.
* **Buscador Inteligente con Autocompletado:**
  * Búsqueda predictiva insensible a mayúsculas, minúsculas y tildes (Unicode NFKD).
  * Tolerancia a errores de tipeo y soporte de alias populares (`smp`, `sjl`, `sjm`, `ves`, `vitarte`, `cercado`, etc.).
  * Sugerencias automáticas desplegables con distritos y agencias coincidentes.
* **Ficha de Agencia Detallada:**
  * Código identificador (ej: `LIM.L`, `BGACHCA`), dirección completa, referencias viales, horarios de atención normalizados, teléfono oficial y enlace directo a Google Maps.

### 2. Optimización del Formulario de Registro
* **Interfaz Profesional y Fluida:** Checkout segmentado en 3 pasos con microinteracciones y barra de progreso.
* **Validación en Tiempo Real:**
  * Validación estricta del DNI peruano de 8 dígitos y Carnet de Extranjería (CE).
  * Validación de celular peruano de 9 dígitos iniciando con `9`.
  * **Cálculo instantáneo del Dígito Verificador (Dígito de Control) del DNI** mediante el algoritmo oficial **Módulo 11** de RENIEC (pesos `3, 2, 7, 6, 5, 4, 3, 2`).
* **Protección de Datos Personales (Ley N° 29733):**
  * Consentimiento informado explícito del titular.
  * Integración con endpoints autorizados de validación de identidad (convenio PIDE / credenciales autorizadas).
  * **Modo manual respetuoso:** Si el servicio externo no está configurado o falla, el usuario completa sus datos manualmente sin ser bloqueado.
* **Prevención de Duplicados y Envíos Accidentales:**
  * Control estricto de **Idempotencia Criptográfica** (`idempotency_key`).
  * Bloqueo visual e inhabilitación inmediata del botón tras el primer clic.
* **Resumen Exhaustivo Previo:**
  * En el Paso 3, el cliente visualiza un resumen detallado de su documento, nombres, celular, agencia de destino, horario y fecha programada de despacho antes de confirmar.

---

## 📂 Estructura del Proyecto

```text
shalom-envios-pe/
├── app/
│   ├── main.py                     # API REST FastAPI y controladores
│   ├── config.py                   # Ajustes y variables de entorno (.env)
│   ├── database.py                 # Persistencia dual SQLite local + Supabase
│   ├── models.py                   # Modelos de validación con Pydantic V2
│   ├── services/
│   │   ├── agency_normalizer.py    # Normalizador, validador y depurador de agencias
│   │   ├── shalom_service.py       # Catálogo, cascada dependiente y buscador
│   │   ├── reniec_service.py       # Verificación de identidad y Dígito de Control
│   │   ├── id_generator.py         # Generador de códigos únicos e idempotencia
│   │   └── auth_service.py         # Seguridad PBKDF2 y JWT para el panel admin
│   ├── static/
│   │   ├── js/form.js              # Checkout wizard, mapa Leaflet y autocompletado
│   │   ├── js/admin.js             # Dashboard administrativo y gestión de catálogo
│   │   └── css/custom.css          # Estilos personalizados
│   └── templates/
│       ├── base.html               # Base layout con Tailwind y Leaflet
│       ├── form.html               # Formulario público optimizado
│       ├── success.html            # Pantalla de confirmación y WhatsApp
│       ├── login.html              # Login seguro del panel
│       └── admin.html              # Panel con gestión de envíos y agencias
├── data/
│   ├── agencias_peru.json          # Catálogo canónico de más de 500 agencias activas
│   ├── agencias_meta.json          # Metadatos, auditoría y trazabilidad del catálogo
│   └── app.db                      # Base de datos SQLite local
├── scripts/
│   └── actualizar_agencias.py      # Script CLI para actualizar desde API o archivo
├── test_app.py                     # Suite de pruebas automatizadas con pytest
└── README.md                       # Documentación técnica
```

---

## 🚀 Puesta en Marcha

### 1. Iniciar el Servidor Web
```powershell
python run.py
```
- **Formulario Público:** [http://localhost:8000/](http://localhost:8000/)
- **Panel Administrativo:** [http://localhost:8000/admin](http://localhost:8000/admin)
  - Usuario: `admin`
  - Contraseña: `admin2026`

### 2. Ejecutar Pruebas Automatizadas
```powershell
python -m pytest test_app.py -v
```

### 3. Actualización del Catálogo por CLI
```powershell
# Previsualizar cambios sin aplicar (dry-run):
python scripts/actualizar_agencias.py --archivo ruta/al/archivo.json --dry-run

# Aplicar actualización oficial:
python scripts/actualizar_agencias.py --archivo ruta/al/archivo.json --fuente "Actualización Shalom Pro"
```
