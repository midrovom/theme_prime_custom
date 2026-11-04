/** Solicitud de crédito: borrador local y envío diferido por dominio/usuario/empresa.
 * Datos personales y archivos permanecen SOLO en este dispositivo hasta el envío.
 * No se cachean respuestas autenticadas de Odoo ni documentos del servidor.
 */
(function () {
    'use strict';
    var PREFIX = '/my/credito/';
    if (!location.pathname.startsWith(PREFIX)) { return; }
    var DB_NAME = 'solicitud-credito-offline-v1';
    var DB_VERSION = 1;
    var ASSET_BASE = '/custom_web_credito_conedera/static/';
    var form = null, key = null, userInfo = null, timer = null, saving = false;
    var restoring = false;
    var currentRecord = null, sendingRequest = false;
    var maxBytes = 15 * 1024 * 1024;

    function openDB() {
        return new Promise(function (resolve, reject) {
            var r = indexedDB.open(DB_NAME, DB_VERSION);
            r.onupgradeneeded = function () {
                if (!r.result.objectStoreNames.contains('drafts')) { r.result.createObjectStore('drafts', {keyPath: 'key'}); }
                if (!r.result.objectStoreNames.contains('templates')) { r.result.createObjectStore('templates', {keyPath: 'key'}); }
            };
            r.onsuccess = function () { resolve(r.result); };
            r.onerror = function () { reject(r.error); };
        });
    }
    async function store(name, mode, operation) {
        var db = await openDB();
        try {
            return await new Promise(function (resolve, reject) {
                var tx = db.transaction(name, mode);
                var request = operation(tx.objectStore(name));
                request.onsuccess = function () { resolve(request.result); };
                request.onerror = function () { reject(request.error); };
                tx.onabort = function () { reject(tx.error); };
            });
        } finally { db.close(); }
    }
    function get(name, id) { return store(name, 'readonly', function (s) { return s.get(id); }); }
    function put(name, value) { return store(name, 'readwrite', function (s) { return s.put(value); }); }
    function del(name, id) { return store(name, 'readwrite', function (s) { return s.delete(id); }); }
    function generatedUUID() {
        return (crypto.randomUUID && crypto.randomUUID()) || 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
            var r = crypto.getRandomValues(new Uint8Array(1))[0] & 15;
            return (c === 'x' ? r : (r & 3 | 8)).toString(16);
        });
    }
    function userKey(u) { return [location.origin, u.website_id, u.company_id, u.user_id].join('|'); }
    function show(message, type) {
        var bar = document.getElementById('credit-offline-bar');
        if (!bar) { return; }
        bar.hidden = false;
        bar.textContent = message;
        bar.className = 'credit-offline-bar credit-offline-' + (type || 'info');
    }
    function identityFromForm() {
        return {
            user_id: Number(form.dataset.creditUser),
            website_id: Number(form.dataset.creditWebsite),
            company_id: Number(form.dataset.creditCompany)
        };
    }
    function gather() {
        var entries = [];
        var bytes = 0;
        new FormData(form).forEach(function (value, name) {
            if (name === 'csrf_token') { return; }
            if (value instanceof File) {
                if (!value.name || !value.size) { return; }
                bytes += value.size;
                entries.push({name: name, value: value, filename: value.name});
            } else {
                entries.push({name: name, value: String(value)});
            }
        });
        if (bytes > maxBytes) { throw new Error('Los archivos del borrador superan 15 MB. Reduzca su tamaño.'); }
        return entries;
    }
    function ensureUUID() {
        var input = form.querySelector('[name="credit_submission_uuid"]');
        if (input && !input.value) { input.value = generatedUUID(); }
    }
    function generateBlankTemplate() {
        var clone = form.cloneNode(true);
        // Ni la información personal ni el token CSRF se almacenan en la plantilla.
        clone.removeAttribute('data-credit-wizard-initialized');
        clone.classList.remove('credit-wizard-ready');
        clone.querySelectorAll('[name="csrf_token"], [name="credit_edit_mode"]').forEach(function (node) { node.remove(); });
        clone.querySelectorAll('input,textarea').forEach(function (input) {
            var type = (input.type || '').toLowerCase();
            if (type === 'file') { input.removeAttribute('value'); return; }
            if (type === 'checkbox' || type === 'radio') { input.removeAttribute('checked'); return; }
            var name = input.name || '';
            if (/_count$/.test(name)) { return; }
            if (name === 'business_location_method') { input.setAttribute('value', 'manual'); return; }
            input.removeAttribute('value');
            if (input.tagName === 'TEXTAREA') { input.textContent = ''; }
        });
        clone.querySelectorAll('option').forEach(function (o) { o.removeAttribute('selected'); });
        clone.querySelectorAll('img[src*="/my/credito/"],iframe[src*="/my/credito/"]').forEach(function (n) { n.remove(); });
        clone.querySelectorAll('.credit-sketch-review-frame').forEach(function (n) { n.replaceChildren(); });
        clone.querySelectorAll('.credit-offline-bar').forEach(function (n) { n.replaceChildren(); });
        return clone.outerHTML;
    }
    async function rememberTemplate() {
        if (!navigator.onLine) { return; }
        var css = Array.from(document.querySelectorAll('link[rel="stylesheet"][href]'))
            .map(function (link) { return link.href; })
            .filter(function (url) { return new URL(url, location.href).origin === location.origin; });
        css.push(location.origin + ASSET_BASE + 'src/css/credit_pwa.css');
        css.push(location.origin + ASSET_BASE + 'src/css/credit_offline.css');
        var theme = Array.from(document.querySelectorAll('style')).map(function (n) { return n.textContent || ''; })
            .filter(function (s) { return s.includes('--credit-'); }).join('\n').slice(0, 12000);
        await put('templates', {key: key, html: generateBlankTemplate(), css: Array.from(new Set(css)),
            theme: theme, identity: userInfo, companyName: (document.querySelector('.credit-kicker') || {}).textContent || '',
            updatedAt: Date.now()});
        if (navigator.serviceWorker && navigator.serviceWorker.ready) {
            navigator.serviceWorker.ready.then(function (registration) {
                var worker = navigator.serviceWorker.controller || registration.active;
                if (worker) { worker.postMessage({type: 'CREDIT_CACHE_ASSETS', urls: css}); }
            }).catch(function () {});
        }
    }
    async function saveDraft(queue, quiet) {
        if (restoring || !form || !key) { return; }
        while (saving) { await new Promise(function (resolve) { setTimeout(resolve, 35); }); }
        saving = true;
        try {
            ensureUUID();
            // Una modificación posterior a Enviar crea un borrador que necesita nueva confirmación.
            var record = {key: key, identity: userInfo, updatedAt: Date.now(),
                entries: gather(), status: (queue || (currentRecord && currentRecord.status === 'pending')) ? 'pending' : 'draft'};
            await put('drafts', record);
            currentRecord = record;
            if (!quiet) {
                show(queue ? 'Sin conexión: solicitud guardada en este dispositivo, pendiente de sincronización.' :
                    'Borrador guardado en este dispositivo' + (navigator.onLine ? '.' : ' · Sin conexión.'),
                    queue ? 'pending' : 'info');
            }
            var clear = document.getElementById('credit-clear-offline');
            if (clear) { clear.hidden = false; }
            return record;
        } catch (error) {
            show('No se pudo guardar el borrador: ' + error.message, 'error');
            throw error;
        } finally { saving = false; }
    }
    function scheduleSave() {
        if (restoring || sendingRequest) { return; }
        window.clearTimeout(timer);
        timer = window.setTimeout(function () { saveDraft(false).catch(function () {}); }, 650);
    }
    async function restoreDraft(record) {
        if (!record || !record.entries) { return; }
        restoring = true;
        try {
            var counts = {};
            record.entries.forEach(function (entry) { if (/_count$/.test(entry.name)) { counts[entry.name] = Number(entry.value); } });
            // Recrear vehículos y referencias antes de recuperar valores.
            var vehicleTarget = Math.min(30, counts.vehicle_count || 1);
            var vehicleButton = document.getElementById('credit-add-vehicle');
            for (var i = 1; i < vehicleTarget && vehicleButton; i++) { vehicleButton.click(); }
            ['commercial','personal','bank'].forEach(function (kind) {
                var target = Math.min(30, counts[kind + '_count'] || 1);
                var add = form.querySelector('[data-credit-add-reference="' + kind + '"]');
                var body = form.querySelector('[data-credit-reference-body="' + kind + '"]');
                for (var j = body ? body.children.length : 0; j < target && add; j++) { add.click(); }
            });
            var fileGroups = {};
            record.entries.forEach(function (entry) {
                // La fecha de solicitud siempre es la asignada por el servidor.
                if (entry.name === 'application_date') { return; }
                var field = form.elements.namedItem(entry.name);
                if (!field) { return; }
                if (entry.value instanceof Blob) {
                    (fileGroups[entry.name] || (fileGroups[entry.name] = [])).push(entry);
                } else if (field instanceof RadioNodeList && field.length && !field.tagName) {
                    Array.from(field).forEach(function (n) { if (n.type === 'radio') { n.checked = n.value === entry.value; } });
                } else if (field.type === 'checkbox') { field.checked = true; }
                else if (field.tagName === 'SELECT' || field.tagName === 'TEXTAREA' || field.tagName === 'INPUT') { field.value = entry.value; }
            });
            Object.keys(fileGroups).forEach(function (name) {
                var input = form.elements.namedItem(name);
                if (!input || input.type !== 'file') { return; }
                try {
                    var transfer = new DataTransfer();
                    fileGroups[name].forEach(function (entry) {
                        var value = entry.value;
                        var file = value instanceof File ? value : new File([value], entry.filename || 'croquis.png', {type: value.type});
                        transfer.items.add(file);
                    });
                    input.files = transfer.files;
                    input.dispatchEvent(new Event('change', {bubbles: true}));
                } catch (error) { show('No se pudieron restaurar todos los archivos. Vuelva a seleccionarlos.', 'error'); }
            });
            document.getElementById('credit-applicant-type')?.dispatchEvent(new Event('change', {bubbles:true}));
            ['credit-identification-type','credit-employment-relationship','credit-employer-type'].forEach(function (id) {
                var f = document.getElementById(id); if (f) { f.dispatchEvent(new Event('change', {bubbles:true})); }
            });
            var finalStep = record.entries.some(function (entry) { return entry.name === 'declaration_accepted'; }) ? 6 : 1;
            if (window.creditWizardGoto) { window.creditWizardGoto(finalStep); }
            show(record.status === 'pending' ? 'Envío pendiente. Se intentará enviar al recuperar conexión y sesión válida.' :
                'Borrador recuperado de este dispositivo. Compruebe sus datos antes de enviarlo.', record.status);
            var clear = document.getElementById('credit-clear-offline'); if (clear) { clear.hidden = false; }
        } finally { restoring = false; }
    }
    async function fetchWithTimeout(url, options, timeoutMs) {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), timeoutMs);
        try { return await fetch(url, Object.assign({}, options, {signal: controller.signal})); }
        catch (error) {
            if (error && (error.name === 'TypeError' || error.name === 'AbortError')) {
                error.creditNetworkFailure = true;
            }
            throw error;
        }
        finally { clearTimeout(timeout); }
    }
    function isConnectivityFailure(error) {
        // HTTP 4xx/5xx, HTML de login y JSON de validación NO son pérdida de red.
        return Boolean(error && error.creditNetworkFailure === true);
    }
    async function sendQueued(force = false) {
        if (sendingRequest || !key) { return; }
        var record = await get('drafts', key);
        if (!record || (record.status !== 'pending' && !(force && record.status === 'draft'))) { return; }
        sendingRequest = true;
        show('Enviando la solicitud a Odoo…', 'info');
        try {
            var check = await fetchWithTimeout(PREFIX + 'offline/context', {credentials:'same-origin', cache:'no-store'}, 20000);
            if (!check.ok) { throw new Error('No se verificó la sesión (HTTP ' + check.status + '). Inicie sesión de nuevo.'); }
            if (!(check.headers.get('Content-Type') || '').includes('application/json')) {
                throw new Error('Odoo devolvió una página en lugar de los datos de sesión. Vuelva a iniciar sesión.');
            }
            var context = await check.json();
            if (userKey(context) !== record.key) {
                throw new Error('La sesión no corresponde a la empresa y usuario de este borrador.');
            }
            var data = new FormData();
            record.entries.forEach(function (e) {
                if (e.value instanceof Blob) { data.append(e.name, e.value, e.filename || e.value.name || 'archivo'); }
                else { data.append(e.name, e.value); }
            });
            data.set('csrf_token', context.csrf_token);
            var response = await fetchWithTimeout(PREFIX + 'offline/submit', {
                method:'POST', credentials:'same-origin', body:data, cache:'no-store'
            }, 120000);
            if (!response.ok) { throw new Error('Odoo rechazó el envío (HTTP ' + response.status + '). Compruebe la sesión o el registro del servidor.'); }
            if (!(response.headers.get('Content-Type') || '').includes('application/json')) {
                throw new Error('Respuesta inesperada de Odoo. Compruebe la sesión y vuelva a intentar.');
            }
            var answer = await response.json();
            if (answer.status === 'sent') {
                await del('drafts', record.key);
                currentRecord = null;
                show('Solicitud registrada correctamente en Odoo.', 'success');
                if (form && !document.getElementById('credit-offline-root')) {
                    location.assign(PREFIX + answer.application_id + '?sent=1');
                } else {
                    location.assign(PREFIX + 'historial');
                }
                return;
            }
            // La API respondió: NO hay motivo para dejar la operación esperando internet.
            record.status = 'draft';
            await put('drafts', record);
            currentRecord = record;
            var explanation = answer.message || 'La solicitud no se guardó. Revise los datos.';
            if (Array.isArray(answer.errors) && answer.errors.length) {
                explanation += ' ' + answer.errors.join(' • ');
            }
            show(explanation, 'error');
        } catch (error) {
            if (isConnectivityFailure(error)) {
                record.status = 'pending';
                await put('drafts', record);
                currentRecord = record;
                show('No hubo respuesta de red. Solicitud guardada localmente, pendiente de sincronización.', 'pending');
                askSync();
            } else {
                record.status = 'draft';
                await put('drafts', record);
                currentRecord = record;
                show('La solicitud no se guardó en Odoo: ' + error.message + ' Los datos permanecen en este dispositivo para reintentar.', 'error');
            }
        } finally { sendingRequest = false; }
    }
    function askSync() {
        if (navigator.serviceWorker && navigator.serviceWorker.ready) {
            navigator.serviceWorker.ready.then(function (registration) {
                if (registration.sync && registration.sync.register) {
                    registration.sync.register('credit-send-pending').catch(function () {});
                }
            }).catch(function () {});
        }
    }
    function addAppChrome() {
        if (document.querySelector('.credit-appbar')) { return; }
        var target = document.querySelector('.credit-application-container') || document.querySelector('.credit-history-responsive')?.closest('.container') ||
            document.querySelector('main .container.py-4') || document.querySelector('#credit-offline-root:has(form)');
        if (!target) { return; }
        var header = document.createElement('div');
        header.className = 'credit-appbar';
        var company = (document.querySelector('.credit-kicker') || {}).textContent || 'Solicitud de crédito';
        var title = document.createElement('strong'); title.textContent = company;
        var status = document.createElement('span'); status.textContent = navigator.onLine ? 'En línea' : 'Sin conexión';
        status.className = 'credit-appbar-status';
        header.appendChild(title); header.appendChild(status);
        target.insertBefore(header, target.firstChild);
        var nav = document.createElement('nav'); nav.className = 'credit-appnav'; nav.setAttribute('aria-label', 'Navegación de solicitud de crédito');
        [['historial','Historial','fa fa-list-ul'],['nueva','Nueva solicitud','fa fa-file-text-o']].forEach(function (item) {
            var link = document.createElement('a'); link.href = PREFIX + item[0];
            var icon = document.createElement('i'); icon.className = item[2]; icon.setAttribute('aria-hidden','true');
            var caption = document.createElement('span'); caption.textContent = item[1];
            link.appendChild(icon); link.appendChild(caption); nav.appendChild(link);
        });
        document.body.appendChild(nav);
        window.addEventListener('online', function () { status.textContent = 'En línea'; });
        window.addEventListener('offline', function () { status.textContent = 'Sin conexión'; });
    }
    async function initialize() {
        addAppChrome();
        var offlineRoot = document.getElementById('credit-offline-root');
        if (offlineRoot && location.pathname !== '/my/credito/nueva') { return; }
        if (offlineRoot) {
            // Sin conexión se reconstruye SOLO una plantilla vacía preparada online.
            var records = await store('templates', 'readonly', function (s) { return s.getAll(); });
            var candidate = records.filter(function (r) { return r.key.startsWith(location.origin + '|'); })
                .sort(function (a,b) { return b.updatedAt-a.updatedAt; })[0];
            if (candidate) {
                candidate.css.forEach(function (url) {
                    var link = document.createElement('link'); link.rel='stylesheet'; link.href=url; document.head.appendChild(link);
                });
                if (candidate.theme) { var style = document.createElement('style'); style.textContent = candidate.theme; document.head.appendChild(style); }
                offlineRoot.innerHTML = '<div class="credit-offline-heading"><h1>Solicitud de crédito · Sin conexión</h1><p>Los datos se guardarán únicamente en este dispositivo. Evite equipos compartidos. Cuando vuelva internet se enviarán las solicitudes que dejó pendientes.</p></div>' + candidate.html;
                addAppChrome();
                form = offlineRoot.querySelector('form.credit-form');
                userInfo = candidate.identity; key = candidate.key;
                if (window.creditInitPortal) { window.creditInitPortal(); }
            } else {
                offlineRoot.textContent = 'Para completar la solicitud sin internet, abra una vez el formulario conectado desde este dispositivo.';
                return;
            }
        } else {
            form = document.querySelector('form.credit-form[data-credit-wizard="1"]:not(:has([name="credit_edit_mode"]))');
            if (!form) {
                // Al volver del envío online, quitar borradores ya confirmados.
                if (new URLSearchParams(location.search).get('sent') === '1') {
                    var portalIdentity = document.querySelector('meta[name="credit-portal-identity"]');
                    if (portalIdentity) {
                        var ownKey = [location.origin, portalIdentity.dataset.website,
                            portalIdentity.dataset.company, portalIdentity.dataset.user].join('|');
                        await del('drafts', ownKey).catch(function () {});
                    }
                }
                return;
            }
            userInfo = identityFromForm(); key = userKey(userInfo);
            await rememberTemplate();
        }
        ensureUUID();
        var record = await get('drafts', key);
        if (record) { await restoreDraft(record); }
        else if (!navigator.onLine) { show('Sin conexión. Complete el formulario; se guardará en este dispositivo.', 'pending'); }
        form.addEventListener('input', scheduleSave);
        form.addEventListener('change', scheduleSave);
        form.addEventListener('submit', function (event) {
            // Si falló la validación de los seis pasos, no enviar ni crear un pendiente.
            if (event.defaultPrevented) { return; }
            event.preventDefault();
            if (sendingRequest) { return; }
            window.clearTimeout(timer);
            var button = form.querySelector('[data-credit-submit]');
            (async function () {
                // Guardado de seguridad; NO marcar pendiente estando online.
                var draft = await saveDraft(false, true);
                if (!draft) { return; }
                // Intentar el servidor incluso si navigator.onLine indica desconexión:
                // ese indicador no demuestra que Odoo sea inalcanzable.
                // Solo una petición fallida deja un pendiente offline.
                await sendQueued(true);
            })().catch(function (error) {
                show('No se pudo preparar el envío: ' + error.message, 'error');
            }).finally(function () {
                if (button) { button.disabled = false; button.textContent = 'Enviar solicitud de crédito'; }
            });
        });
        var clearButton = document.getElementById('credit-clear-offline');
        if (clearButton) {
            clearButton.addEventListener('click', async function () {
                if (!window.confirm('¿Eliminar el borrador de crédito guardado en este dispositivo?')) { return; }
                await del('drafts', key); currentRecord = null; clearButton.hidden = true;
                show('Borrador local eliminado. Los archivos no se enviaron a Odoo.', 'info');
            });
        }
        if (navigator.serviceWorker) {
            navigator.serviceWorker.addEventListener('message', function (event) {
                if (event.data && event.data.type === 'CREDIT_SENT') {
                    del('drafts', key).catch(function () {});
                    show('La solicitud se envió correctamente al recuperar internet.', 'success');
                    location.assign(PREFIX + event.data.application_id + '?sent=1');
                }
            });
        }
        window.addEventListener('online', function () { sendQueued(); });
        document.addEventListener('visibilitychange', function () { if (!document.hidden && navigator.onLine) { sendQueued(); } });
        window.addEventListener('offline', function () { show('Sin conexión. Los cambios se guardan en este dispositivo.', 'pending'); });
        if (record && record.status === 'pending') { askSync(); await sendQueued(); }
    }
    if (document.readyState === 'loading') { document.addEventListener('DOMContentLoaded', function () { initialize().catch(console.error); }, {once:true}); }
    else { initialize().catch(console.error); }
}());
