/**
 * LÓGICA DEL PANEL ADMINISTRATIVO PRIVADO DE ENVÍOS Y AGENCIAS SHALOM
 */

let filtroEstadoActual = 'TODOS';
let filtroAgenciasActual = 'todas';
let adminDebounceTimer = null;
let agenciasDebounceTimer = null;
let contenidoImportarCargado = '';

document.addEventListener('DOMContentLoaded', () => {
    // Carga inicial
});

function cambiarPestana(tab) {
    const btnEnvios = document.getElementById('tab-btn-envios');
    const btnAgencias = document.getElementById('tab-btn-agencias');
    const secEnvios = document.getElementById('seccion-envios');
    const secAgencias = document.getElementById('seccion-agencias');

    if (tab === 'envios') {
        btnEnvios.className = 'px-4 py-2 rounded-xl text-xs font-bold bg-shalom-600 text-white shadow-sm transition-all cursor-pointer';
        btnAgencias.className = 'px-4 py-2 rounded-xl text-xs font-semibold bg-gray-100 hover:bg-gray-200 text-gray-700 transition-all cursor-pointer';
        secEnvios.classList.remove('hidden');
        secAgencias.classList.add('hidden');
    } else {
        btnAgencias.className = 'px-4 py-2 rounded-xl text-xs font-bold bg-shalom-600 text-white shadow-sm transition-all cursor-pointer';
        btnEnvios.className = 'px-4 py-2 rounded-xl text-xs font-semibold bg-gray-100 hover:bg-gray-200 text-gray-700 transition-all cursor-pointer';
        secAgencias.classList.remove('hidden');
        secEnvios.classList.add('hidden');
        cargarTablaAgenciasAdmin();
    }
    lucide.createIcons();
}

// ==============================================================================
// 1. GESTIÓN DE ENVÍOS
// ==============================================================================
function setFiltroEstado(estado) {
    filtroEstadoActual = estado;
    document.querySelectorAll('.filtro-btn').forEach(btn => {
        if (btn.dataset.estado === estado) {
            btn.className = 'filtro-btn px-3 py-1.5 rounded-lg text-xs font-bold bg-shalom-600 text-white transition-colors';
        } else {
            btn.className = 'filtro-btn px-3 py-1.5 rounded-lg text-xs font-semibold bg-gray-100 hover:bg-gray-200 text-gray-700 transition-colors';
        }
    });
    recargarTablaEnvios();
}

function debounceAdminFilter() {
    clearTimeout(adminDebounceTimer);
    adminDebounceTimer = setTimeout(() => {
        recargarTablaEnvios();
    }, 250);
}

async function recargarTablaEnvios() {
    const busqueda = document.getElementById('admin-search-input').value.trim();
    const url = `/api/admin/envios?estado=${encodeURIComponent(filtroEstadoActual)}&q=${encodeURIComponent(busqueda)}`;
    
    try {
        const res = await fetch(url);
        if (res.status === 401) {
            window.location.href = '/admin/login';
            return;
        }
        const data = await res.json();
        renderizarTablaAdmin(data.envios);
    } catch (err) {
        console.error('Error al consultar envíos:', err);
    }
}

function renderizarTablaAdmin(envios) {
    const tbody = document.getElementById('tabla-envios-body');
    tbody.innerHTML = '';

    if (!envios || envios.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="9" class="px-4 py-8 text-center text-gray-400 text-xs">
                    No se encontraron envíos con los filtros aplicados.
                </td>
            </tr>
        `;
        return;
    }

    envios.forEach(e => {
        const tr = document.createElement('tr');
        tr.className = 'hover:bg-gray-50/80 transition-colors';
        tr.dataset.id = e.id;

        const fechaFormateada = e.fecha_registro ? e.fecha_registro.substring(0, 16).replace('T', ' ') : '';
        const badgeReniec = e.estado_verificacion_identidad === 'VERIFICADO_RENIEC_OFICIAL'
            ? `<span class="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
                 <i data-lucide="check" class="w-3 h-3"></i> Oficial RENIEC
               </span>`
            : `<span class="inline-flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded-full bg-gray-100 text-gray-600 border border-gray-200">
                 Manual Válido
               </span>`;

        let estadoColor = 'bg-gray-50 text-gray-700 border-gray-300';
        if (e.estado_registro === 'PENDIENTE') estadoColor = 'bg-amber-50 text-amber-700 border-amber-300';
        else if (e.estado_registro === 'ENVIADO') estadoColor = 'bg-blue-50 text-blue-700 border-blue-300';
        else if (e.estado_registro === 'ENTREGADO') estadoColor = 'bg-emerald-50 text-emerald-700 border-emerald-300';

        const despachoBadge = e.fecha_despacho ? `<span class="text-[9px] px-1.5 py-0.2 rounded bg-amber-50 text-amber-700 font-semibold block mt-0.5">Despacho: ${e.fecha_despacho}</span>` : '';

        // Celda Tamaño de Paquete
        const tamanoActual = e.tamano_paquete || 'PAQUETE XS';
        const celdaTamano = `
            <select 
                onchange="cambiarTamanoPaquete('${e.id}', this.value, this)" 
                class="text-[11px] font-bold rounded-lg px-2.5 py-1 border transition-all cursor-pointer bg-amber-50 text-amber-900 border-amber-300 hover:bg-amber-100"
                title="Selecciona el tamaño del paquete para Shalom Pro"
            >
                <option value="PAQUETE XS" ${tamanoActual === 'PAQUETE XS' ? 'selected' : ''}>📦 XS (0.5 kg)</option>
                <option value="PAQUETE XXS" ${tamanoActual === 'PAQUETE XXS' ? 'selected' : ''}>📦 XXS (0.25 kg)</option>
                <option value="SOBRE" ${tamanoActual === 'SOBRE' ? 'selected' : ''}>✉️ SOBRE (0 kg)</option>
                <option value="PAQUETE S" ${tamanoActual === 'PAQUETE S' ? 'selected' : ''}>📦 S (2 kg)</option>
                <option value="PAQUETE M" ${tamanoActual === 'PAQUETE M' ? 'selected' : ''}>📦 M (5 kg)</option>
                <option value="PAQUETE L" ${tamanoActual === 'PAQUETE L' ? 'selected' : ''}>📦 L (10 kg)</option>
            </select>
        `;

        // Celda Guía Shalom Pro
        let celdaShalomPro = '';
        if (e.numero_guia_shalom) {
            celdaShalomPro = `
                <div>
                    <span class="inline-flex items-center gap-1 font-mono font-bold text-[11px] text-shalom-800 bg-shalom-50 px-2 py-0.5 rounded-md border border-shalom-200">
                        <i data-lucide="package-check" class="w-3 h-3 text-shalom-600"></i>
                        ${e.numero_guia_shalom}
                    </span>
                    ${e.monto_flete ? `<span class="text-[10px] text-gray-500 block mt-0.5 font-medium">Flete: S/ ${Number(e.monto_flete).toFixed(2)}</span>` : ''}
                    ${e.url_guia_pdf ? `<a href="${e.url_guia_pdf}" target="_blank" class="inline-flex items-center gap-1 text-[10px] text-shalom-600 hover:text-shalom-800 font-bold mt-0.5 underline"><i data-lucide="external-link" class="w-2.5 h-2.5"></i> Rastrear / PDF</a>` : ''}
                </div>
            `;
        } else {
            const nombreDest = `${e.nombres} ${e.apellido_paterno}`.replace(/'/g, "\\'");
            const agDest = (e.nombre_agencia || '').replace(/'/g, "\\'");
            celdaShalomPro = `
                <button 
                    type="button" 
                    onclick="abrirModalEmitirShalomPro('${e.codigo_registro}', '${e.codigo_registro}', '${nombreDest}', '${agDest}')" 
                    class="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-xl bg-gradient-to-r from-shalom-700 to-red-600 hover:from-shalom-800 hover:to-red-700 text-white font-bold text-[10px] shadow-sm transition-all cursor-pointer"
                    title="Generar guía oficial en Shalom Pro con 1 solo clic"
                >
                    <i data-lucide="zap" class="w-3 h-3"></i>
                    <span>Emitir Guía</span>
                </button>
            `;
        }

        tr.innerHTML = `
            <td class="px-4 py-3 whitespace-nowrap">
                <span class="font-mono font-bold text-shalom-700 block">${e.codigo_registro}</span>
                <span class="text-[10px] text-gray-400">${fechaFormateada}</span>
                ${despachoBadge}
            </td>
            <td class="px-4 py-3">
                <span class="font-bold text-gray-900 block">${e.nombres} ${e.apellido_paterno}</span>
                <span class="text-[11px] text-gray-500">${e.apellido_materno}</span>
            </td>
            <td class="px-4 py-3 whitespace-nowrap">
                <span class="font-mono text-gray-800 block">${e.tipo_documento || 'DNI'}: ${e.dni}</span>
                <span class="font-mono text-gray-500">Cel: +51 ${e.celular}</span>
            </td>
            <td class="px-4 py-3 whitespace-nowrap">
                ${badgeReniec}
            </td>
            <td class="px-4 py-3">
                <span class="font-semibold text-gray-900 block">${e.nombre_agencia}</span>
                <span class="text-[10px] text-gray-400 block">${e.distrito}, ${e.departamento}</span>
            </td>
            <td class="px-4 py-3 whitespace-nowrap">
                ${celdaTamano}
            </td>
            <td class="px-4 py-3 whitespace-nowrap" id="col-guia-${e.id}">
                ${celdaShalomPro}
            </td>
            <td class="px-4 py-3 whitespace-nowrap">
                <select 
                    onchange="cambiarEstado('${e.id}', this.value)" 
                    class="text-[11px] font-bold rounded-lg px-2.5 py-1 border transition-colors cursor-pointer ${estadoColor}"
                >
                    <option value="PENDIENTE" ${e.estado_registro === 'PENDIENTE' ? 'selected' : ''}>PENDIENTE</option>
                    <option value="EN_PREPARACION" ${e.estado_registro === 'EN_PREPARACION' ? 'selected' : ''}>EN PREPARACIÓN</option>
                    <option value="ENVIADO" ${e.estado_registro === 'ENVIADO' ? 'selected' : ''}>ENVIADO</option>
                    <option value="ENTREGADO" ${e.estado_registro === 'ENTREGADO' ? 'selected' : ''}>ENTREGADO</option>
                    <option value="CANCELADO" ${e.estado_registro === 'CANCELADO' ? 'selected' : ''}>CANCELADO</option>
                </select>
            </td>
            <td class="px-4 py-3 text-right whitespace-nowrap">
                <button 
                    type="button" 
                    class="btn-ver-detalle p-1.5 rounded-lg border border-gray-200 hover:bg-gray-100 text-gray-600 hover:text-gray-900 transition-colors" 
                    title="Ver detalle completo"
                >
                    <i data-lucide="eye" class="w-4 h-4"></i>
                </button>
            </td>
        `;

        tr.querySelector('.btn-ver-detalle').addEventListener('click', () => {
            abrirDetalleEnvio(e);
        });

        tbody.appendChild(tr);
    });

    lucide.createIcons();
}

async function cambiarEstado(idEnvio, nuevoEstado) {
    try {
        const res = await fetch(`/api/admin/envios/${idEnvio}/estado`, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({estado_registro: nuevoEstado})
        });
        const data = await res.json();
        if (!res.ok) {
            alert(data.detail || 'Error al actualizar estado');
        } else {
            recargarTablaEnvios();
        }
    } catch (err) {
        console.error('Error al cambiar estado:', err);
    }
}

async function cambiarTamanoPaquete(idEnvio, nuevoTamano, selectEl) {
    if (!selectEl) return;
    const originalClasses = selectEl.className;
    selectEl.disabled = true;
    try {
        const res = await fetch(`/api/admin/envios/${idEnvio}/tamano`, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({tamano_paquete: nuevoTamano})
        });
        const data = await res.json();
        if (!res.ok) {
            alert(data.detail || 'Error al actualizar el tamaño del paquete');
        } else {
            // Visual feedback: green border/bg flash to confirm save
            selectEl.className = 'text-[11px] font-bold rounded-lg px-2.5 py-1 border transition-all cursor-pointer bg-emerald-100 text-emerald-900 border-emerald-400';
            setTimeout(() => {
                selectEl.className = originalClasses;
            }, 800);
        }
    } catch (err) {
        console.error('Error al cambiar tamaño de paquete:', err);
        alert('Error de conexión al guardar el tamaño.');
    } finally {
        selectEl.disabled = false;
    }
}

function abrirDetalleEnvio(envio) {
    const modal = document.getElementById('modal-admin-detalle');
    const box = document.getElementById('detalle-modal-contenido');
    document.getElementById('detalle-modal-titulo').textContent = `Envío ${envio.codigo_registro}`;

    box.innerHTML = `
        <div class="bg-gray-50 p-3.5 rounded-2xl border border-gray-200 space-y-2">
            <div class="flex justify-between border-b pb-1.5">
                <span class="text-gray-500 font-semibold">Destinatario:</span>
                <span class="font-bold text-gray-900">${envio.nombres} ${envio.apellido_paterno} ${envio.apellido_materno}</span>
            </div>
            <div class="flex justify-between border-b pb-1.5">
                <span class="text-gray-500 font-semibold">${envio.tipo_documento || 'DNI'}:</span>
                <span class="font-mono font-bold">${envio.dni}</span>
            </div>
            <div class="flex justify-between border-b pb-1.5">
                <span class="text-gray-500 font-semibold">Celular WhatsApp:</span>
                <span class="font-mono font-bold text-emerald-700">+51 ${envio.celular}</span>
            </div>
            <div class="flex justify-between border-b pb-1.5">
                <span class="text-gray-500 font-semibold">Agencia Shalom:</span>
                <span class="font-bold text-shalom-700 text-right">${envio.nombre_agencia} (${envio.codigo_agencia})</span>
            </div>
            <div class="flex justify-between border-b pb-1.5">
                <span class="text-gray-500 font-semibold">Ubicación:</span>
                <span class="text-right text-gray-800">${envio.distrito}, ${envio.provincia}, ${envio.departamento}</span>
            </div>
            <div class="flex justify-between border-b pb-1.5">
                <span class="text-gray-500 font-semibold">Tamaño Shalom Pro:</span>
                <span class="font-bold text-amber-800">${envio.tamano_paquete || 'PAQUETE XS'}</span>
            </div>
            <div class="flex justify-between border-b pb-1.5">
                <span class="text-gray-500 font-semibold">Dirección:</span>
                <span class="text-right text-gray-700 text-[11px]">${envio.direccion_agencia}</span>
            </div>
            ${envio.referencia_agencia ? `
            <div class="flex justify-between border-b pb-1.5">
                <span class="text-gray-500 font-semibold">Referencia:</span>
                <span class="text-right italic text-gray-600 text-[11px]">${envio.referencia_agencia}</span>
            </div>` : ''}
            <div class="flex justify-between border-b pb-1.5">
                <span class="text-gray-500 font-semibold">Fecha Programada:</span>
                <span class="font-bold text-shalom-700">${envio.fecha_despacho || 'No especificada'}</span>
            </div>
            <div class="flex justify-between border-b pb-1.5">
                <span class="text-gray-500 font-semibold">Verificación Identidad:</span>
                <span class="font-bold">${envio.estado_verificacion_identidad}</span>
            </div>
            <div class="flex justify-between border-b pb-1.5">
                <span class="text-gray-500 font-semibold">Fecha Registro:</span>
                <span>${envio.fecha_registro}</span>
            </div>
            <div class="flex justify-between">
                <span class="text-gray-500 font-semibold">Idempotency Key:</span>
                <span class="font-mono text-[10px] text-gray-400 truncate max-w-[200px]">${envio.idempotency_key}</span>
            </div>
        </div>
    `;

    modal.classList.remove('hidden');
    lucide.createIcons();
}

function cerrarDetalleEnvio() {
    const modal = document.getElementById('modal-admin-detalle');
    if (modal) modal.classList.add('hidden');
}

// ------------------------------------------------------------------------------
// MODAL EMISIÓN SHALOM PRO
// ------------------------------------------------------------------------------
function abrirModalEmitirShalomPro(idEnvio, codigo, cliente, agencia) {
    document.getElementById('shalom-pro-id-envio').value = idEnvio;
    document.getElementById('modal-shalom-cliente').textContent = cliente;
    document.getElementById('modal-shalom-agencia').textContent = agencia;
    document.getElementById('modal-shalom-subtitulo').textContent = `Orden para envío ${codigo}`;
    
    // Reset defaults
    document.getElementById('shalom-pro-bultos').value = 1;
    document.getElementById('shalom-pro-peso').value = 1.0;
    document.getElementById('shalom-pro-tipo-pago').value = 'PAGO_EN_DESTINO';
    document.getElementById('shalom-pro-contenido').value = 'PAQUETE / MERCADERÍA';
    document.getElementById('shalom-pro-observaciones').value = '';

    const btn = document.getElementById('btn-confirmar-shalom-pro');
    if (btn) btn.disabled = false;
    const btnText = document.getElementById('btn-text-shalom-pro');
    if (btnText) btnText.textContent = 'Confirmar y Emitir Guía';

    const modal = document.getElementById('modal-emitir-shalom-pro');
    if (modal) modal.classList.remove('hidden');
    lucide.createIcons();
}

function cerrarModalEmitirShalomPro() {
    const modal = document.getElementById('modal-emitir-shalom-pro');
    if (modal) modal.classList.add('hidden');
}

async function confirmarEmisionShalomPro() {
    const idEnvio = document.getElementById('shalom-pro-id-envio').value;
    const bultos = parseInt(document.getElementById('shalom-pro-bultos').value) || 1;
    const pesoKg = parseFloat(document.getElementById('shalom-pro-peso').value) || 1.0;
    const tipoPago = document.getElementById('shalom-pro-tipo-pago').value;
    const contenido = document.getElementById('shalom-pro-contenido').value.trim() || 'PAQUETE / MERCADERÍA';
    const observaciones = document.getElementById('shalom-pro-observaciones').value.trim();

    const btn = document.getElementById('btn-confirmar-shalom-pro');
    const btnText = document.getElementById('btn-text-shalom-pro');
    if (btn) btn.disabled = true;
    if (btnText) btnText.textContent = 'Conectando con Shalom Pro...';

    try {
        const res = await fetch(`/api/admin/envios/${idEnvio}/emitir-shalom-pro`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                bultos: bultos,
                peso_kg: pesoKg,
                tipo_pago: tipoPago,
                contenido_paquete: contenido,
                observaciones: observaciones
            })
        });

        const data = await res.json();
        if (!res.ok) {
            alert(`Error de Shalom Pro: ${data.detail || 'No se pudo generar la guía'}`);
            if (btn) btn.disabled = false;
            if (btnText) btnText.textContent = 'Confirmar y Emitir Guía';
            return;
        }

        cerrarModalEmitirShalomPro();
        alert(`🎉 ¡Guía generada exitosamente!\n\nNúmero de Guía: ${data.numero_guia}\nModo: ${data.modo}\nMonto Flete: S/ ${Number(data.monto_flete).toFixed(2)}\n\nEl estado cambió automáticamente a "EN PREPARACIÓN".`);
        recargarTablaEnvios();
    } catch (e) {
        console.error('Error emitiendo guía Shalom Pro:', e);
        alert('Ocurrió un error inesperado al conectar con Shalom Pro.');
        if (btn) btn.disabled = false;
        if (btnText) btnText.textContent = 'Confirmar y Emitir Guía';
    }
}

// ------------------------------------------------------------------------------
// MODAL CARGA MASIVA SHALOM PRO (SIN API)
// ------------------------------------------------------------------------------
function abrirModalCargaMasivaShalomPro() {
    const modal = document.getElementById('modal-carga-masiva-shalom');
    if (modal) modal.classList.remove('hidden');
    lucide.createIcons();
}

function cerrarModalCargaMasivaShalomPro() {
    const modal = document.getElementById('modal-carga-masiva-shalom');
    if (modal) modal.classList.add('hidden');
}

function descargarPlantillaShalomPro() {
    const chk = document.getElementById('check-solo-pendientes-masivo');
    const soloPendientes = chk ? chk.checked : true;
    const tamanoSel = document.getElementById('select-tamano-defecto-masivo');
    const tamanoDefecto = tamanoSel ? tamanoSel.value : 'PAQUETE XS';
    window.location.href = `/api/admin/envios/exportar-shalom-pro?solo_pendientes=${soloPendientes}&tamano_defecto=${encodeURIComponent(tamanoDefecto)}`;
}

// ==============================================================================
// 2. GESTIÓN DEL CATÁLOGO DE AGENCIAS
// ==============================================================================
function setFiltroAgencias(estado) {
    filtroAgenciasActual = estado;
    document.querySelectorAll('.filtro-agencia-btn').forEach(btn => {
        if (btn.dataset.estado === estado) {
            btn.className = 'filtro-agencia-btn px-2.5 py-1 rounded-lg text-xs font-bold bg-shalom-600 text-white';
        } else {
            btn.className = 'filtro-agencia-btn px-2.5 py-1 rounded-lg text-xs font-medium bg-gray-100 text-gray-700';
        }
    });
    cargarTablaAgenciasAdmin();
}

function debounceAgenciasFilter() {
    clearTimeout(agenciasDebounceTimer);
    agenciasDebounceTimer = setTimeout(() => {
        cargarTablaAgenciasAdmin();
    }, 250);
}

async function cargarTablaAgenciasAdmin() {
    const q = document.getElementById('agencias-search-input').value.trim();
    const url = `/api/admin/shalom/agencias?estado=${encodeURIComponent(filtroAgenciasActual)}&q=${encodeURIComponent(q)}`;

    try {
        const res = await fetch(url);
        if (!res.ok) return;
        const data = await res.json();
        renderizarTablaAgenciasAdmin(data.agencias || []);
    } catch (e) {
        console.error('Error cargando agencias:', e);
    }
}

function renderizarTablaAgenciasAdmin(agencias) {
    const tbody = document.getElementById('tabla-agencias-body');
    tbody.innerHTML = '';

    if (!agencias || agencias.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" class="px-4 py-6 text-center text-gray-400 text-xs">No se encontraron agencias.</td></tr>`;
        return;
    }

    agencias.forEach(a => {
        const tr = document.createElement('tr');
        tr.className = 'hover:bg-gray-50/80 transition-colors';

        const badgeActivo = a.activo
            ? `<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">Activa</span>`
            : `<span class="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-gray-100 text-gray-600 border border-gray-200" title="${a.motivo_inactiva || ''}">Inactiva</span>`;

        const overrideBadge = a.override_manual 
            ? `<span class="text-[9px] text-amber-600 block font-semibold">(Manual)</span>` 
            : '';

        tr.innerHTML = `
            <td class="px-4 py-2.5 whitespace-nowrap">
                <span class="font-mono font-bold text-gray-900 block">${a.codigo || a.id}</span>
                <span class="text-[10px] text-gray-400">ID: ${a.id}</span>
            </td>
            <td class="px-4 py-2.5 font-bold text-gray-900">${a.nombre}</td>
            <td class="px-4 py-2.5">
                <span class="text-gray-800 font-semibold block">${a.distrito}</span>
                <span class="text-[10px] text-gray-400 block">${a.provincia}, ${a.departamento}</span>
            </td>
            <td class="px-4 py-2.5">
                <p class="text-[11px] text-gray-600 truncate max-w-xs">${a.direccion}</p>
                <p class="text-[10px] text-gray-400 mt-0.5 truncate max-w-xs">${a.horario || 'N/D'}</p>
            </td>
            <td class="px-4 py-2.5 whitespace-nowrap">
                ${badgeActivo}
                ${overrideBadge}
            </td>
            <td class="px-4 py-2.5 text-right whitespace-nowrap">
                <button 
                    type="button" 
                    onclick="toggleEstadoAgencia('${a.id}', ${!a.activo})"
                    class="px-2.5 py-1 rounded-lg text-[10px] font-bold ${a.activo ? 'bg-red-50 hover:bg-red-100 text-red-700' : 'bg-emerald-50 hover:bg-emerald-100 text-emerald-700'} transition-colors cursor-pointer"
                >
                    ${a.activo ? 'Desactivar' : 'Activar'}
                </button>
            </td>
        `;

        tbody.appendChild(tr);
    });

    lucide.createIcons();
}

async function toggleEstadoAgencia(agenciaId, nuevoEstado) {
    const motivo = nuevoEstado ? 'Reactivada manualmente por admin' : prompt('Motivo de desactivación (ej: Cierre temporal por obras):', 'Desactivada por admin');
    if (motivo === null) return; // cancelado

    try {
        const res = await fetch(`/api/admin/shalom/agencias/${agenciaId}/estado`, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({activo: nuevoEstado, motivo: motivo})
        });
        const data = await res.json();
        if (res.ok) {
            cargarTablaAgenciasAdmin();
        } else {
            alert(data.detail || 'Error al actualizar agencia');
        }
    } catch (e) {
        alert('Error al conectar con el servidor.');
    }
}

// Modales de Catálogo / Importación
function abrirModalCatalogo() {
    cambiarPestana('agencias');
}

function abrirModalImportar() {
    document.getElementById('modal-importar-catalogo').classList.remove('hidden');
    document.getElementById('import-preview-box').classList.add('hidden');
    document.getElementById('btn-aplicar-import').classList.add('hidden');
    lucide.createIcons();
}

function cerrarModalImportar() {
    document.getElementById('modal-importar-catalogo').classList.add('hidden');
}

function leerArchivoImportacion(input) {
    if (input.files && input.files[0]) {
        const file = input.files[0];
        const reader = new FileReader();
        reader.onload = (e) => {
            contenidoImportarCargado = e.target.result;
            document.getElementById('import-contenido').value = contenidoImportarCargado.substring(0, 3000);
            if (!document.getElementById('import-fuente').value) {
                document.getElementById('import-fuente').value = `Archivo ${file.name}`;
            }
        };
        reader.readAsText(file);
    }
}

async function ejecutarImportacion(dryRun) {
    const contenido = contenidoImportarCargado || document.getElementById('import-contenido').value.trim();
    const fuente = document.getElementById('import-fuente').value.trim() || 'Importación manual oficial';

    if (!contenido) {
        alert('Debes ingresar o cargar el contenido del catálogo.');
        return;
    }

    const previewBox = document.getElementById('import-preview-box');
    const btnAplicar = document.getElementById('btn-aplicar-import');

    try {
        const res = await fetch('/api/admin/shalom/importar', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                contenido: contenido,
                fuente: fuente,
                dry_run: dryRun,
                forzar: false
            })
        });

        const data = await res.json();

        if (!data.success) {
            alert(data.mensaje || 'Error al procesar el archivo.');
            return;
        }

        const rep = data.reporte || {};
        const dif = data.diferencias || {};

        previewBox.innerHTML = `
            <h4 class="font-bold text-gray-900 border-b pb-1">Resultado de la verificación:</h4>
            <p><strong>Recibidos:</strong> ${rep.recibidos} | <strong>Válidos:</strong> ${rep.total} | <strong>Activos:</strong> ${rep.activas} | <strong>Disponibles para clientes:</strong> ${rep.publicables}</p>
            <p class="text-gray-500">Nuevas: ${dif.nuevas} · Modificadas: ${dif.modificadas} · Retiradas: ${dif.retiradas} · Desactivadas: ${dif.desactivadas} · Reactivadas: ${dif.reactivadas}</p>
            ${data.advertencia ? `<p class="p-2 bg-amber-50 text-amber-800 rounded font-semibold">${data.advertencia}</p>` : ''}
        `;
        previewBox.classList.remove('hidden');

        if (dryRun) {
            btnAplicar.classList.remove('hidden');
        } else {
            alert(data.mensaje || 'Catálogo aplicado con éxito.');
            cerrarModalImportar();
            window.location.reload();
        }
    } catch (e) {
        alert('Error de conexión al importar catálogo.');
    }
}

async function sincronizarAPIOficial() {
    const btn = document.getElementById('btn-sync-api');
    btn.disabled = true;
    btn.innerHTML = `<i data-lucide="loader-2" class="w-3.5 h-3.5 animate-spin"></i> Sincronizando...`;
    lucide.createIcons();

    try {
        const res = await fetch('/api/admin/shalom/sincronizar', {method: 'POST'});
        const data = await res.json();
        alert(data.mensaje || 'Proceso completado.');
        if (data.aplicado) {
            window.location.reload();
        }
    } catch (err) {
        alert('Error al conectar con el servidor.');
    } finally {
        btn.disabled = false;
        btn.innerHTML = `<i data-lucide="refresh-cw" class="w-3.5 h-3.5"></i> Sincronizar API`;
        lucide.createIcons();
    }
}
