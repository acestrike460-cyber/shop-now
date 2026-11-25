/**
 * FORMULARIO INTELIGENTE DE ENVÍOS SHALOM PERÚ (V3.0)
 * Incluye:
 * - Selectores dependientes Departamento > Provincia > Distrito
 * - Buscador predictivo inteligente con autocompletado y debounce
 * - Validación en tiempo real (DNI de 8 dígitos, CE, Celular de 9 dígitos)
 * - Cálculo instantáneo de dígito verificador de DNI (Módulo 11)
 * - Integración con servicio autorizado de identidad y modo manual respetuoso
 * - Mapa interactivo Leaflet con cálculo de distancias y geolocalización
 * - Prevención estricta de doble clic e idempotencia
 * - Resumen exhaustivo de datos antes de confirmar
 */

// Estado global de la aplicación
const AppState = {
    pasoActual: 1,
    tipoEnvio: 'shalom',
    tipoDocumento: 'DNI',
    dni: '',
    nombreCompleto: '',
    celular: '',
    digitoVerificador: null,
    estadoVerificacion: 'MANUAL_NO_VERIFICADO',
    todasLasAgencias: [],
    agenciasFiltradas: [],
    agenciaSeleccionada: null,
    arbolUbicaciones: [],
    filtroDep: '',
    filtroProv: '',
    filtroDist: '',
    ubicacionUsuario: null,
    fechaDespachoSeleccionada: '',
    idempotencyKey: '',
    enviando: false
};

// Variables del mapa Leaflet
let mapInstance = null;
let markersGroup = null;
let userMarker = null;
let debounceBuscarTimer = null;
let debounceDniTimer = null;

document.addEventListener('DOMContentLoaded', async () => {
    generarNuevoTokenIdempotencia();
    initToastContainer();
    initFechasDespacho();
    initValidacionesPaso1();
    
    // Cargar agencias y árbol en paralelo
    await Promise.all([
        cargarCatalogoAgencias(),
        cargarArbolUbicaciones()
    ]);
});

function generarNuevoTokenIdempotencia() {
    AppState.idempotencyKey = 'idemp_' + Math.random().toString(36).substring(2, 11) + '_' + Date.now().toString(36);
    const keyInput = document.getElementById('idempotency_key');
    if (keyInput) keyInput.value = AppState.idempotencyKey;
}

// ==============================================================================
// 0. SISTEMA DE TOASTS MODERNOS (CERO ALERTS NATIVOS)
// ==============================================================================
function initToastContainer() {
    if (!document.getElementById('toast-container')) {
        const c = document.createElement('div');
        c.id = 'toast-container';
        c.className = 'fixed top-4 right-4 z-[9999] flex flex-col gap-2 max-w-sm w-full pointer-events-none px-3';
        document.body.appendChild(c);
    }
}

function mostrarToast(mensaje, tipo = 'info') {
    initToastContainer();
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = 'pointer-events-auto transform transition-all duration-300 translate-y-[-10px] opacity-0 flex items-center gap-2.5 p-3.5 rounded-2xl shadow-xl text-xs font-semibold border backdrop-blur-md';

    let iconName = 'info';
    if (tipo === 'success') {
        toast.classList.add('bg-emerald-950/95', 'text-emerald-100', 'border-emerald-700/60');
        iconName = 'check-circle-2';
    } else if (tipo === 'warning') {
        toast.classList.add('bg-amber-950/95', 'text-amber-100', 'border-amber-700/60');
        iconName = 'alert-triangle';
    } else if (tipo === 'error') {
        toast.classList.add('bg-red-950/95', 'text-red-100', 'border-red-700/60');
        iconName = 'alert-circle';
    } else {
        toast.classList.add('bg-gray-900/95', 'text-white', 'border-gray-700');
        iconName = 'info';
    }

    toast.innerHTML = `
        <i data-lucide="${iconName}" class="w-4 h-4 shrink-0"></i>
        <span class="flex-grow leading-tight">${mensaje}</span>
    `;

    container.appendChild(toast);
    lucide.createIcons();

    requestAnimationFrame(() => {
        toast.classList.remove('translate-y-[-10px]', 'opacity-0');
        toast.classList.add('translate-y-0', 'opacity-100');
    });

    setTimeout(() => {
        toast.classList.remove('translate-y-0', 'opacity-100');
        toast.classList.add('translate-y-[-10px]', 'opacity-0');
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// ==============================================================================
// 1. NAVEGACIÓN ENTRE PASOS (WIZARD 1, 2, 3)
// ==============================================================================
function actualizarBarraProgreso(paso) {
    AppState.pasoActual = paso;
    const bar1 = document.getElementById('prog-bar-1');
    const bar2 = document.getElementById('prog-bar-2');
    const bar3 = document.getElementById('prog-bar-3');
    const txt = document.getElementById('step-indicator-text');
    const badge = document.getElementById('step-badge');

    bar1.className = 'h-1 rounded-full bg-gray-200 transition-all duration-300';
    bar2.className = 'h-1 rounded-full bg-gray-200 transition-all duration-300';
    bar3.className = 'h-1 rounded-full bg-gray-200 transition-all duration-300';

    if (paso === 1) {
        bar1.classList.replace('bg-gray-200', 'bg-shalom-600');
        txt.textContent = 'Paso 1 de 3 · Tus datos';
        badge.textContent = 'Paso 1';
    } else if (paso === 2) {
        bar1.classList.replace('bg-gray-200', 'bg-shalom-600');
        bar2.classList.replace('bg-gray-200', 'bg-shalom-600');
        txt.textContent = 'Paso 2 de 3 · Agencia Shalom';
        badge.textContent = 'Paso 2';
    } else if (paso === 3) {
        bar1.classList.replace('bg-gray-200', 'bg-shalom-600');
        bar2.classList.replace('bg-gray-200', 'bg-shalom-600');
        bar3.classList.replace('bg-gray-200', 'bg-shalom-600');
        txt.textContent = 'Paso 3 de 3 · Confirmación';
        badge.textContent = 'Paso 3';
    }
}

function irAlPaso1() {
    document.getElementById('step-1-container').classList.remove('hidden');
    document.getElementById('step-2-container').classList.add('hidden');
    document.getElementById('step-3-container').classList.add('hidden');
    actualizarBarraProgreso(1);
    lucide.createIcons();
}

function irAlPaso2() {
    const docInput = document.getElementById('input_dni').value.trim();
    const nomInput = document.getElementById('input_nombre_completo').value.trim();
    const celInput = document.getElementById('input_celular').value.trim();

    if (AppState.tipoDocumento === 'DNI') {
        if (docInput.length !== 8 || !/^\d{8}$/.test(docInput)) {
            mostrarToast('Por favor ingresa un DNI peruano válido de 8 dígitos.', 'warning');
            document.getElementById('input_dni').focus();
            return;
        }
    } else {
        if (docInput.length < 8 || docInput.length > 12) {
            mostrarToast('Por favor ingresa un Carnet de Extranjería válido (8 a 12 caracteres).', 'warning');
            document.getElementById('input_dni').focus();
            return;
        }
    }

    if (!nomInput || nomInput.length < 3) {
        mostrarToast('Por favor ingresa tu nombre y apellidos completos para el rotulado del paquete.', 'warning');
        document.getElementById('input_nombre_completo').focus();
        return;
    }

    if (!celInput || celInput.length !== 9 || !celInput.startsWith('9')) {
        mostrarToast('Por favor ingresa un número de celular de 9 dígitos que inicie con 9.', 'warning');
        document.getElementById('input_celular').focus();
        return;
    }

    AppState.dni = docInput;
    AppState.nombreCompleto = nomInput;
    AppState.celular = celInput;

    document.getElementById('step-1-container').classList.add('hidden');
    document.getElementById('step-2-container').classList.remove('hidden');
    document.getElementById('step-3-container').classList.add('hidden');
    actualizarBarraProgreso(2);

    setTimeout(() => {
        initLeafletMap();
    }, 120);

    lucide.createIcons();
}

function irAlPaso3() {
    if (!AppState.agenciaSeleccionada) {
        mostrarToast('Por favor selecciona una agencia de Shalom tocando una de la lista o en el mapa.', 'warning');
        return;
    }

    document.getElementById('step-1-container').classList.add('hidden');
    document.getElementById('step-2-container').classList.add('hidden');
    document.getElementById('step-3-container').classList.remove('hidden');
    actualizarBarraProgreso(3);

    // Actualizar resumen visual del Paso 3
    const a = AppState.agenciaSeleccionada;
    document.getElementById('resumen-destinatario').textContent = AppState.nombreCompleto;
    document.getElementById('resumen-doc').textContent = `${AppState.tipoDocumento} ${AppState.dni}`;
    document.getElementById('resumen-celular').textContent = AppState.celular;

    const badgeReniec = document.getElementById('resumen-badge-reniec');
    if (AppState.estadoVerificacion === 'VERIFICADO_RENIEC_OFICIAL') {
        badgeReniec.innerHTML = `<span class="text-[9px] font-bold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800">Verificado</span>`;
    } else {
        badgeReniec.innerHTML = `<span class="text-[9px] font-medium px-2 py-0.5 rounded-full bg-gray-100 text-gray-600">Manual Válido</span>`;
    }

    document.getElementById('resumen-agencia-titulo').textContent = `${a.nombre} (${a.codigo || a.id}) · ${a.distrito}, ${a.departamento}`;
    document.getElementById('resumen-agencia-direccion').textContent = a.direccion;
    document.getElementById('resumen-agencia-ref').textContent = a.referencia ? `Ref: ${a.referencia}` : '';
    document.getElementById('resumen-agencia-horario').textContent = a.horario || 'Lunes a Sábado';
    document.getElementById('resumen-fecha-salida').textContent = AppState.fechaDespachoSeleccionada || 'Primer día hábil';

    lucide.createIcons();
}

function navAtras() {
    if (AppState.pasoActual === 3) {
        irAlPaso2();
    } else if (AppState.pasoActual === 2) {
        irAlPaso1();
    } else {
        window.history.back();
    }
}

// ==============================================================================
// 2. VALIDACIONES EN TIEMPO REAL Y VERIFICACIÓN DE IDENTIDAD
// ==============================================================================
function calcularDigitoVerificadorDNI(dniStr) {
    if (dniStr.length !== 8 || !/^\d{8}$/.test(dniStr)) return null;
    const pesos = [3, 2, 7, 6, 5, 4, 3, 2];
    let suma = 0;
    for (let i = 0; i < 8; i++) {
        suma += parseInt(dniStr[i], 10) * pesos[i];
    }
    const residuo = suma % 11;
    const digito = 11 - residuo;
    if (digito === 11) return 0;
    if (digito === 10) return 1;
    return digito;
}

function cambiarTipoDoc(tipo) {
    AppState.tipoDocumento = tipo;
    const label = document.getElementById('label-num-doc');
    const input = document.getElementById('input_dni');
    const btnVerif = document.getElementById('btn-verif-reniec-mini');
    const dvBadge = document.getElementById('dni-dv-badge');
    const counter = document.getElementById('doc-counter');

    if (tipo === 'DNI') {
        label.textContent = 'DNI (8 dígitos) *';
        input.placeholder = 'Ej: 71234567';
        input.maxLength = 8;
        btnVerif.classList.remove('hidden');
        counter.textContent = `${input.value.length}/8`;
    } else {
        label.textContent = 'Carnet de Extranjería (CE) *';
        input.placeholder = 'Ej: 001234567';
        input.maxLength = 12;
        btnVerif.classList.add('hidden');
        dvBadge.classList.add('hidden');
        counter.textContent = `${input.value.length}/12`;
    }
}

function initValidacionesPaso1() {
    const inputDni = document.getElementById('input_dni');
    const inputCel = document.getElementById('input_celular');
    const inputNom = document.getElementById('input_nombre_completo');
    const dvBadge = document.getElementById('dni-dv-badge');
    const dvVal = document.getElementById('dni-dv-val');
    const dniError = document.getElementById('dni-error-msg');
    const celError = document.getElementById('cel-error-msg');
    const docCounter = document.getElementById('doc-counter');
    const celCounter = document.getElementById('cel-counter');

    inputDni.addEventListener('input', (e) => {
        if (AppState.tipoDocumento === 'DNI') {
            e.target.value = e.target.value.replace(/\D/g, '').slice(0, 8);
            docCounter.textContent = `${e.target.value.length}/8`;
            
            if (e.target.value.length === 8) {
                const dv = calcularDigitoVerificadorDNI(e.target.value);
                AppState.digitoVerificador = dv;
                dvVal.textContent = dv;
                dvBadge.classList.remove('hidden');
                dniError.classList.add('hidden');

                // Si tiene 8 dígitos válidos, consultar automáticamente tras pausa
                clearTimeout(debounceDniTimer);
                debounceDniTimer = setTimeout(() => {
                    ejecutarVerificacionReniec();
                }, 400);
            } else {
                dvBadge.classList.add('hidden');
                if (e.target.value.length > 0 && e.target.value.length < 8) {
                    dniError.textContent = `Faltan ${8 - e.target.value.length} dígitos`;
                    dniError.classList.remove('hidden');
                } else {
                    dniError.classList.add('hidden');
                }
            }
        } else {
            e.target.value = e.target.value.replace(/[^A-Za-z0-9]/g, '').slice(0, 12).toUpperCase();
            docCounter.textContent = `${e.target.value.length}/12`;
        }
    });

    inputCel.addEventListener('input', (e) => {
        e.target.value = e.target.value.replace(/\D/g, '').slice(0, 9);
        celCounter.textContent = `${e.target.value.length}/9`;

        if (e.target.value.length > 0 && !e.target.value.startsWith('9')) {
            celError.textContent = 'El celular debe empezar con el dígito 9.';
            celError.classList.remove('hidden');
        } else if (e.target.value.length > 0 && e.target.value.length < 9) {
            celError.textContent = `Faltan ${9 - e.target.value.length} dígitos`;
            celError.classList.remove('hidden');
        } else {
            celError.classList.add('hidden');
        }
    });

    // Validar nombre
    inputNom.addEventListener('input', (e) => {
        // Normalizar a mayúsculas suaves
        if (e.target.value.length > 1) {
            e.target.classList.remove('border-red-300');
        }
    });
}

async function ejecutarVerificacionReniec() {
    const inputDni = document.getElementById('input_dni');
    const dniVal = inputDni.value.trim().padStart(8, '0');

    if (dniVal.length !== 8 || !/^\d{8}$/.test(dniVal)) {
        mostrarToast('Ingresa un DNI de 8 dígitos para consultar.', 'warning');
        inputDni.focus();
        return;
    }

    const spinner = document.getElementById('reniec-spinner-mini');
    const label = document.getElementById('reniec-btn-label');
    spinner.classList.remove('hidden');
    label.textContent = '...';

    try {
        const res = await fetch('/api/reniec/consultar', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({dni: dniVal, consentimiento_titular: true})
        });
        const data = await res.json();

        if (data.success && data.verificado_oficial) {
            const nombreCompleto = `${data.nombres} ${data.apellido_paterno} ${data.apellido_materno}`.trim();
            const nomInput = document.getElementById('input_nombre_completo');
            nomInput.value = nombreCompleto;
            nomInput.classList.add('ring-2', 'ring-emerald-500', 'bg-emerald-50/40');
            setTimeout(() => nomInput.classList.remove('ring-2', 'ring-emerald-500', 'bg-emerald-50/40'), 1800);

            AppState.estadoVerificacion = 'VERIFICADO_RENIEC_OFICIAL';
            document.getElementById('estado_verif_hidden').value = 'VERIFICADO_RENIEC_OFICIAL';
            document.getElementById('badge-verificacion-pill').innerHTML = `
                <span class="text-[10px] px-2 py-0.5 rounded-full font-bold bg-emerald-50 text-emerald-700 border border-emerald-200 flex items-center gap-1">
                    <i data-lucide="shield-check" class="w-3 h-3 text-emerald-600"></i>
                    Identidad Verificada
                </span>
            `;
            lucide.createIcons();
            mostrarToast(`Identidad verificada: ${data.nombres} ${data.apellido_paterno}`, 'success');
        } else {
            AppState.estadoVerificacion = 'MANUAL_NO_VERIFICADO';
            mostrarToast(data.mensaje || 'Puedes completar tus nombres manualmente.', 'info');
        }
    } catch (err) {
        console.error(err);
        mostrarToast('Servicio externo ocupado. Puedes completar tus datos manualmente.', 'info');
    } finally {
        spinner.classList.add('hidden');
        label.textContent = 'Verificar';
    }
}

// ==============================================================================
// 3. SELECTORES DEPENDIENTES (DEPARTAMENTO > PROVINCIA > DISTRITO)
// ==============================================================================
async function cargarArbolUbicaciones() {
    try {
        const res = await fetch('/api/agencias/arbol');
        if (res.ok) {
            const data = await res.json();
            AppState.arbolUbicaciones = data.arbol || [];
            poblarSelectDepartamentos();
        }
    } catch (e) {
        console.error('Error cargando árbol de ubicaciones:', e);
    }
}

function poblarSelectDepartamentos() {
    const selDep = document.getElementById('sel_departamento');
    selDep.innerHTML = '<option value="">Todos los Departamentos</option>';
    AppState.arbolUbicaciones.forEach(dep => {
        const opt = document.createElement('option');
        opt.value = dep.nombre;
        opt.textContent = `${dep.nombre} (${dep.total})`;
        selDep.appendChild(opt);
    });
}

function onDepartamentoChange() {
    const selDep = document.getElementById('sel_departamento');
    const selProv = document.getElementById('sel_provincia');
    const selDist = document.getElementById('sel_distrito');
    const depNombre = selDep.value;

    AppState.filtroDep = depNombre;
    AppState.filtroProv = '';
    AppState.filtroDist = '';

    selProv.innerHTML = '<option value="">Todas las Provincias</option>';
    selDist.innerHTML = '<option value="">Todos los Distritos</option>';
    selDist.disabled = true;

    if (!depNombre) {
        selProv.disabled = true;
        aplicarFiltrosYRenderizar();
        return;
    }

    const depObj = AppState.arbolUbicaciones.find(d => d.nombre === depNombre);
    if (depObj && depObj.provincias) {
        depObj.provincias.forEach(prov => {
            const opt = document.createElement('option');
            opt.value = prov.nombre;
            opt.textContent = `${prov.nombre} (${prov.total})`;
            selProv.appendChild(opt);
        });
        selProv.disabled = false;
    }

    aplicarFiltrosYRenderizar();
}

function onProvinciaChange() {
    const selDep = document.getElementById('sel_departamento');
    const selProv = document.getElementById('sel_provincia');
    const selDist = document.getElementById('sel_distrito');
    const provNombre = selProv.value;

    AppState.filtroProv = provNombre;
    AppState.filtroDist = '';
    selDist.innerHTML = '<option value="">Todos los Distritos</option>';

    if (!provNombre) {
        selDist.disabled = true;
        aplicarFiltrosYRenderizar();
        return;
    }

    const depObj = AppState.arbolUbicaciones.find(d => d.nombre === selDep.value);
    if (depObj) {
        const provObj = depObj.provincias.find(p => p.nombre === provNombre);
        if (provObj && provObj.distritos) {
            provObj.distritos.forEach(dist => {
                const opt = document.createElement('option');
                opt.value = dist.nombre;
                opt.textContent = `${dist.nombre} (${dist.total})`;
                selDist.appendChild(opt);
            });
            selDist.disabled = false;
        }
    }

    aplicarFiltrosYRenderizar();
}

function onDistritoChange() {
    const selDist = document.getElementById('sel_distrito');
    AppState.filtroDist = selDist.value;
    aplicarFiltrosYRenderizar();
}

function limpiarFiltrosUbicacion() {
    document.getElementById('sel_departamento').value = '';
    document.getElementById('sel_provincia').innerHTML = '<option value="">Todas</option>';
    document.getElementById('sel_provincia').disabled = true;
    document.getElementById('sel_distrito').innerHTML = '<option value="">Todos</option>';
    document.getElementById('sel_distrito').disabled = true;
    AppState.filtroDep = '';
    AppState.filtroProv = '';
    AppState.filtroDist = '';
    aplicarFiltrosYRenderizar();
}

function toggleModoFiltro() {
    const panel = document.getElementById('panel-selectores-dependientes');
    const btnText = document.getElementById('btn-toggle-filtros-text');
    if (panel.classList.contains('hidden')) {
        panel.classList.remove('hidden');
        btnText.textContent = 'Ocultar Selectores';
    } else {
        panel.classList.add('hidden');
        btnText.textContent = 'Ver Selectores';
    }
}

// ==============================================================================
// 4. MAPA LEAFLET Y BUSCADOR INTELIGENTE CON AUTOCOMPLETADO
// ==============================================================================
async function cargarCatalogoAgencias() {
    try {
        const res = await fetch('/api/agencias/all');
        if (res.ok) {
            const data = await res.json();
            AppState.todasLasAgencias = data.agencias || [];
            document.getElementById('lista-total-badge').textContent = `${AppState.todasLasAgencias.length} agencias`;
            document.getElementById('map-counter-text').textContent = `${AppState.todasLasAgencias.length} Agencias Shalom`;
        }
    } catch (e) {
        console.error('Error cargando catálogo:', e);
    }
}

function initLeafletMap() {
    const mapDiv = document.getElementById('mapa-leaf');
    if (!mapDiv) return;

    if (!mapInstance) {
        // Centro inicial: Lima Metrópoli o primer punto
        mapInstance = L.map('mapa-leaf', {
            zoomControl: true,
            attributionControl: false
        }).setView([-12.046374, -77.042793], 11);

        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            maxZoom: 19
        }).addTo(mapInstance);

        markersGroup = L.featureGroup().addTo(mapInstance);

        mapInstance.on('click', (e) => {
            actualizarDistanciasDesdePunto(e.latlng.lat, e.latlng.lng);
        });
    } else {
        mapInstance.invalidateSize();
    }

    aplicarFiltrosYRenderizar();
}

function aplicarFiltrosYRenderizar() {
    let filtradas = AppState.todasLasAgencias;

    if (AppState.filtroDep) {
        filtradas = filtradas.filter(a => a.departamento === AppState.filtroDep);
    }
    if (AppState.filtroProv) {
        filtradas = filtradas.filter(a => a.provincia === AppState.filtroProv);
    }
    if (AppState.filtroDist) {
        filtradas = filtradas.filter(a => a.distrito === AppState.filtroDist);
    }

    const q = document.getElementById('buscador_mapa').value.trim();
    if (q.length >= 2) {
        filtradas = filtrarPorTextoEnMemoria(filtradas, q);
    }

    AppState.agenciasFiltradas = filtradas;
    renderizarAgenciasEnMapa(filtradas);
    renderizarListaAgencias(filtradas);

    document.getElementById('lista-total-badge').textContent = `${filtradas.length} encontradas`;

    // Encuadrar mapa si hay filtros activos
    if (AppState.filtroDep && filtradas.length > 0 && mapInstance && markersGroup) {
        try {
            mapInstance.fitBounds(markersGroup.getBounds(), { padding: [30, 30], maxZoom: 14 });
        } catch (e) {}
    }
}

function filtrarPorTextoEnMemoria(lista, query) {
    const q = normalizarTextoJS(query);
    const tokens = q.split(' ').filter(t => t.length > 0);
    return lista.filter(a => {
        const corpus = normalizarTextoJS([
            a.nombre, a.distrito, a.provincia, a.departamento, a.direccion, a.referencia, a.codigo, a.id
        ].join(' '));
        return tokens.every(t => corpus.includes(t));
    });
}

function normalizarTextoJS(str) {
    if (!str) return '';
    return str.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim();
}

function renderizarAgenciasEnMapa(agencias) {
    if (!markersGroup) return;
    markersGroup.clearLayers();

    agencias.forEach(agencia => {
        if (!agencia.latitud || !agencia.longitud) return;

        const esSeleccionada = AppState.agenciaSeleccionada && AppState.agenciaSeleccionada.id === agencia.id;
        const color = esSeleccionada ? '#B91C1C' : '#DC2626';
        const size = esSeleccionada ? 22 : 18;

        const pinIcon = L.divIcon({
            className: 'custom-shalom-marker',
            html: `<div style="background-color:${color}; width:${size}px; height:${size}px; border-radius:50%; border:2.5px solid white; box-shadow:0 2px 6px rgba(0,0,0,0.35); display:flex; align-items:center; justify-content:center; color:white; font-size:9px; font-weight:bold;">${esSeleccionada ? '✓' : ''}</div>`,
            iconSize: [size, size],
            iconAnchor: [size / 2, size / 2]
        });

        const marker = L.marker([agencia.latitud, agencia.longitud], { icon: pinIcon });
        marker.on('click', () => {
            seleccionarAgencia(agencia);
        });
        marker.bindTooltip(`<b>${agencia.nombre}</b><br><span style="font-size:10px">${agencia.distrito}</span>`, { direction: 'top', offset: [0, -8] });
        markersGroup.addLayer(marker);
    });
}

function renderizarListaAgencias(agencias) {
    const container = document.getElementById('lista-agencias-container');
    container.innerHTML = '';

    if (!agencias || agencias.length === 0) {
        container.innerHTML = `
            <div class="p-6 text-center text-xs text-gray-400 bg-gray-50/50 rounded-2xl border border-dashed border-gray-200">
                <i data-lucide="map-pin-off" class="w-6 h-6 mx-auto mb-1.5 text-gray-300"></i>
                <p class="font-medium text-gray-600">No encontramos agencias activas con este criterio.</p>
                <p class="text-[11px] text-gray-400 mt-1">Prueba seleccionando otro departamento o distrito.</p>
            </div>
        `;
        lucide.createIcons();
        return;
    }

    agencias.slice(0, 80).forEach(agencia => {
        const esSeleccionada = AppState.agenciaSeleccionada && AppState.agenciaSeleccionada.id === agencia.id;
        const card = document.createElement('div');
        card.id = `card-agencia-${agencia.id}`;
        card.className = `p-3 rounded-2xl border transition-all cursor-pointer flex items-start gap-2.5 ${
            esSeleccionada 
            ? 'border-shalom-600 bg-red-50/60 shadow-sm ring-1 ring-shalom-500' 
            : 'border-gray-200 bg-white hover:border-gray-300 hover:shadow-xs'
        }`;

        const distTxt = agencia.distanciaKm !== undefined 
            ? ` · <span class="text-blue-600 font-bold">${agencia.distanciaKm.toFixed(1)} km</span>` 
            : '';

        card.innerHTML = `
            <div class="mt-0.5 text-shalom-600 shrink-0">
                <div class="w-5 h-5 rounded-full ${esSeleccionada ? 'bg-shalom-600 text-white' : 'bg-red-50 text-shalom-600'} flex items-center justify-center font-bold text-[10px]">
                    <i data-lucide="${esSeleccionada ? 'check' : 'map-pin'}" class="w-3 h-3"></i>
                </div>
            </div>
            <div class="flex-grow min-w-0">
                <div class="flex items-center justify-between gap-1">
                    <p class="text-xs font-bold text-gray-900 leading-snug truncate">${agencia.nombre}</p>
                    <span class="text-[9px] font-mono px-1.5 py-0.2 rounded bg-gray-100 text-gray-600 shrink-0">${agencia.codigo || agencia.id}</span>
                </div>
                <p class="text-[10px] text-gray-500 uppercase mt-0.5 leading-tight line-clamp-1">${agencia.direccion}${agencia.referencia ? ' · REF: ' + agencia.referencia : ''}</p>
                <div class="mt-1 flex items-center gap-1.5 text-[10px] font-semibold text-shalom-700">
                    <span>${agencia.distrito.toUpperCase()}, ${agencia.departamento.toUpperCase()}${distTxt}</span>
                </div>
            </div>
        `;

        card.addEventListener('click', () => {
            seleccionarAgencia(agencia);
        });

        container.appendChild(card);
    });

    lucide.createIcons();
}

function seleccionarAgencia(agencia) {
    AppState.agenciaSeleccionada = agencia;

    // Actualizar Ficha Detallada
    const ficha = document.getElementById('ficha-agencia-seleccionada');
    document.getElementById('ficha-nombre').textContent = agencia.nombre;
    document.getElementById('ficha-direccion').textContent = agencia.direccion;
    document.getElementById('ficha-referencia').textContent = agencia.referencia ? `Referencia: ${agencia.referencia}` : '';
    document.getElementById('ficha-horario').textContent = agencia.horario || 'Lunes a Sábado';
    document.getElementById('ficha-codigo').textContent = agencia.codigo || agencia.id;

    const telWrap = document.getElementById('ficha-telefono-wrap');
    if (agencia.telefono) {
        document.getElementById('ficha-telefono').textContent = agencia.telefono;
        telWrap.classList.remove('hidden');
    } else {
        telWrap.classList.add('hidden');
    }

    const gmapsLink = document.getElementById('ficha-gmaps-link');
    if (agencia.maps_url) {
        gmapsLink.href = agencia.maps_url;
        gmapsLink.classList.remove('hidden');
    } else {
        gmapsLink.classList.add('hidden');
    }

    ficha.classList.remove('hidden');

    if (mapInstance && agencia.latitud && agencia.longitud) {
        mapInstance.flyTo([agencia.latitud, agencia.longitud], 14, { duration: 0.8 });
    }

    renderizarAgenciasEnMapa(AppState.agenciasFiltradas.length > 0 ? AppState.agenciasFiltradas : AppState.todasLasAgencias);
    renderizarListaAgencias(AppState.agenciasFiltradas.length > 0 ? AppState.agenciasFiltradas : AppState.todasLasAgencias);

    const btn = document.getElementById('btn-continuar-paso-2');
    if (btn) btn.disabled = false;

    mostrarToast(`Agencia seleccionada: ${agencia.nombre}`, 'info');
}

function filtrarAgenciasMapa() {
    clearTimeout(debounceBuscarTimer);
    const input = document.getElementById('buscador_mapa');
    const btnLimpiar = document.getElementById('btn-limpiar-busqueda');
    const q = input.value.trim();

    if (q) {
        btnLimpiar.classList.remove('hidden');
    } else {
        btnLimpiar.classList.add('hidden');
        cerrarAutocompletado();
    }

    debounceBuscarTimer = setTimeout(async () => {
        aplicarFiltrosYRenderizar();
        if (q.length >= 2) {
            consultarAutocompletado(q);
        } else {
            cerrarAutocompletado();
        }
    }, 250);
}

function limpiarBuscador() {
    const input = document.getElementById('buscador_mapa');
    input.value = '';
    document.getElementById('btn-limpiar-busqueda').classList.add('hidden');
    cerrarAutocompletado();
    aplicarFiltrosYRenderizar();
}

async function consultarAutocompletado(q) {
    try {
        const res = await fetch(`/api/agencias/sugerencias?q=${encodeURIComponent(q)}`);
        if (!res.ok) return;
        const data = await res.json();
        mostrarMenuAutocompletado(data);
    } catch (e) {
        console.warn('Error autocompletado:', e);
    }
}

function mostrarMenuAutocompletado(data) {
    const menu = document.getElementById('autocomplete-dropdown');
    menu.innerHTML = '';

    const ubicaciones = data.ubicaciones || [];
    const agencias = data.agencias || [];

    if (ubicaciones.length === 0 && agencias.length === 0) {
        menu.classList.add('hidden');
        return;
    }

    if (ubicaciones.length > 0) {
        const titleU = document.createElement('div');
        titleU.className = 'px-3 py-1.5 text-[10px] font-bold text-gray-400 uppercase bg-gray-50';
        titleU.textContent = 'Distritos sugeridos:';
        menu.appendChild(titleU);

        ubicaciones.forEach(u => {
            const item = document.createElement('div');
            item.className = 'px-3.5 py-2 hover:bg-red-50 text-xs font-semibold text-gray-800 cursor-pointer flex items-center justify-between border-b border-gray-100 last:border-0';
            item.innerHTML = `
                <span class="flex items-center gap-1.5">
                    <i data-lucide="map-pin" class="w-3.5 h-3.5 text-shalom-600"></i>
                    ${u.distrito}, ${u.provincia} (${u.departamento})
                </span>
                <span class="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 text-gray-500 font-normal">${u.total} agencias</span>
            `;
            item.addEventListener('click', () => {
                document.getElementById('buscador_mapa').value = u.distrito;
                cerrarAutocompletado();
                aplicarFiltrosYRenderizar();
            });
            menu.appendChild(item);
        });
    }

    if (agencias.length > 0) {
        const titleA = document.createElement('div');
        titleA.className = 'px-3 py-1.5 text-[10px] font-bold text-gray-400 uppercase bg-gray-50';
        titleA.textContent = 'Agencias coincidentes:';
        menu.appendChild(titleA);

        agencias.slice(0, 5).forEach(a => {
            const item = document.createElement('div');
            item.className = 'px-3.5 py-2 hover:bg-red-50 text-xs font-semibold text-gray-800 cursor-pointer flex items-center justify-between border-b border-gray-100 last:border-0';
            item.innerHTML = `
                <div class="truncate">
                    <span class="font-bold text-gray-900 block truncate">${a.nombre}</span>
                    <span class="text-[10px] text-gray-400 font-normal block truncate">${a.direccion}</span>
                </div>
                <span class="text-[10px] text-shalom-700 font-mono font-bold shrink-0 ml-2">${a.codigo || a.id}</span>
            `;
            item.addEventListener('click', () => {
                seleccionarAgencia(a);
                cerrarAutocompletado();
            });
            menu.appendChild(item);
        });
    }

    menu.classList.remove('hidden');
    lucide.createIcons();
}

function cerrarAutocompletado() {
    const menu = document.getElementById('autocomplete-dropdown');
    if (menu) menu.classList.add('hidden');
}

// Cerrar autocompletado si hace clic afuera
document.addEventListener('click', (e) => {
    if (!e.target.closest('#buscador_mapa') && !e.target.closest('#autocomplete-dropdown')) {
        cerrarAutocompletado();
    }
});

function centrarMapaVerTodas() {
    if (mapInstance && markersGroup && markersGroup.getLayers().length > 0) {
        mapInstance.fitBounds(markersGroup.getBounds(), { padding: [25, 25] });
    }
}

function obtenerUbicacionUsuario() {
    if (!navigator.geolocation) {
        mostrarToast('La geolocalización no está soportada por tu navegador.', 'warning');
        return;
    }

    const btn = document.getElementById('btn-ubicarme');
    btn.innerHTML = `<i data-lucide="loader-2" class="w-3.5 h-3.5 animate-spin"></i><span>...</span>`;
    lucide.createIcons();

    navigator.geolocation.getCurrentPosition(
        (position) => {
            const lat = position.coords.latitude;
            const lng = position.coords.longitude;
            AppState.ubicacionUsuario = { lat, lng };

            if (mapInstance) {
                if (userMarker) mapInstance.removeLayer(userMarker);

                const userIcon = L.divIcon({
                    className: 'custom-user-marker',
                    html: `<div style="background-color:#3B82F6; width:16px; height:16px; border-radius:50%; border:2.5px solid white; box-shadow:0 0 10px rgba(59,130,246,0.7);"></div>`,
                    iconSize: [16, 16]
                });

                userMarker = L.marker([lat, lng], { icon: userIcon }).addTo(mapInstance);
                mapInstance.setView([lat, lng], 13);
            }

            actualizarDistanciasDesdePunto(lat, lng);
            btn.innerHTML = `<i data-lucide="check" class="w-3.5 h-3.5 text-emerald-600"></i><span>Ubicado</span>`;
            lucide.createIcons();
            mostrarToast('Ubicación detectada. Agencias ordenadas por proximidad.', 'success');
        },
        (error) => {
            mostrarToast('No se pudo obtener el GPS. Puedes elegir tu agencia en el mapa o lista.', 'info');
            btn.innerHTML = `<i data-lucide="crosshair" class="w-3.5 h-3.5 text-shalom-600"></i><span>Ubicarme</span>`;
            lucide.createIcons();
        }
    );
}

function calcularDistanciaHaversine(lat1, lon1, lat2, lon2) {
    const R = 6371; // Radio de la Tierra en km
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLon = (lon2 - lon1) * Math.PI / 180;
    const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
              Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
              Math.sin(dLon/2) * Math.sin(dLon/2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
    return R * c;
}

function actualizarDistanciasDesdePunto(lat, lng) {
    AppState.todasLasAgencias.forEach(a => {
        if (a.latitud && a.longitud) {
            a.distanciaKm = calcularDistanciaHaversine(lat, lng, a.latitud, a.longitud);
        }
    });

    AppState.todasLasAgencias.sort((a, b) => (a.distanciaKm || 9999) - (b.distanciaKm || 9999));
    aplicarFiltrosYRenderizar();
}

// ==============================================================================
// 5. SELECTOR DE FECHAS DE DESPACHO (PASO 3)
// ==============================================================================
function initFechasDespacho() {
    const scrollContainer = document.getElementById('fechas-despacho-scroll');
    if (!scrollContainer) return;
    scrollContainer.innerHTML = '';

    const diasSemana = ['dom', 'lun', 'mar', 'mié', 'jue', 'vie', 'sáb'];
    const hoy = new Date();

    for (let i = 0; i < 7; i++) {
        const fecha = new Date(hoy);
        fecha.setDate(hoy.getDate() + i);

        const diaNombre = i === 0 ? 'hoy' : diasSemana[fecha.getDay()];
        const diaNum = fecha.getDate();
        const mesNum = fecha.getMonth() + 1;
        const textoPill = `${diaNombre} ${diaNum}/${mesNum}`;

        const btn = document.createElement('button');
        btn.type = 'button';
        btn.dataset.fecha = textoPill;
        btn.className = `px-3.5 py-1.5 rounded-full text-xs font-bold whitespace-nowrap transition-all cursor-pointer ${
            i === 0 
            ? 'bg-shalom-600 text-white shadow-sm' 
            : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
        }`;
        btn.textContent = textoPill;

        if (i === 0) AppState.fechaDespachoSeleccionada = textoPill;

        btn.addEventListener('click', () => {
            scrollContainer.querySelectorAll('button').forEach(b => {
                b.className = 'px-3.5 py-1.5 rounded-full text-xs font-bold whitespace-nowrap bg-gray-100 text-gray-700 hover:bg-gray-200 transition-all cursor-pointer';
            });
            btn.className = 'px-3.5 py-1.5 rounded-full text-xs font-bold whitespace-nowrap bg-shalom-600 text-white shadow-sm transition-all cursor-pointer';
            AppState.fechaDespachoSeleccionada = textoPill;
            const resFecha = document.getElementById('resumen-fecha-salida');
            if (resFecha) resFecha.textContent = textoPill;
        });

        scrollContainer.appendChild(btn);
    }
}

// ==============================================================================
// 6. ENVÍO FINAL DEL FORMULARIO Y CONFIRMACIÓN CON IDEMPOTENCIA
// ==============================================================================
async function enviarFormularioFinal() {
    if (AppState.enviando) {
        mostrarToast('Tu registro ya está en proceso...', 'info');
        return;
    }

    const btn = document.getElementById('btn-confirmar-despacho');
    const spinner = document.getElementById('btn-confirmar-spinner');
    const label = document.getElementById('btn-confirmar-text');

    AppState.enviando = true;
    btn.disabled = true;
    spinner.classList.remove('hidden');
    label.textContent = 'Registrando envío...';

    const partesNombre = AppState.nombreCompleto.split(' ').filter(p => p.length > 0);
    const nombres = partesNombre.slice(0, Math.max(1, partesNombre.length - 2)).join(' ') || partesNombre[0];
    const apellidoPaterno = partesNombre.length > 1 ? partesNombre[partesNombre.length - 2] : 'NO_ESPECIFICADO';
    const apellidoMaterno = partesNombre.length > 2 ? partesNombre[partesNombre.length - 1] : 'NO_ESPECIFICADO';

    const payload = {
        tipo_documento: AppState.tipoDocumento,
        dni: AppState.dni,
        nombres: nombres,
        apellido_paterno: apellidoPaterno,
        apellido_materno: apellidoMaterno,
        celular: AppState.celular,
        departamento: AppState.agenciaSeleccionada.departamento,
        provincia: AppState.agenciaSeleccionada.provincia,
        distrito: AppState.agenciaSeleccionada.distrito,
        codigo_agencia: AppState.agenciaSeleccionada.id,
        nombre_agencia: AppState.agenciaSeleccionada.nombre,
        direccion_agencia: AppState.agenciaSeleccionada.direccion,
        referencia_agencia: AppState.agenciaSeleccionada.referencia || '',
        fecha_despacho: AppState.fechaDespachoSeleccionada || '',
        estado_verificacion_identidad: AppState.estadoVerificacion,
        idempotency_key: AppState.idempotencyKey
    };

    try {
        const res = await fetch('/api/envios/registrar', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });

        const data = await res.json();
        if (res.ok && data.success) {
            window.location.href = data.redirect_url;
        } else {
            mostrarToast(data.detail || data.mensaje || 'Error al procesar el registro.', 'error');
            AppState.enviando = false;
            btn.disabled = false;
            spinner.classList.add('hidden');
            label.textContent = 'Confirmar y Registrar Envío';
        }
    } catch (err) {
        console.error('Error en envío:', err);
        mostrarToast('Error de red al conectar con el servidor. Intenta de nuevo.', 'error');
        AppState.enviando = false;
        btn.disabled = false;
        spinner.classList.add('hidden');
        label.textContent = 'Confirmar y Registrar Envío';
    }
}
