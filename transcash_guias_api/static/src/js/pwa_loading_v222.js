/* Transcash PWA: feedback real de navegación y prevención de doble envío.
 * No simula un porcentaje. Solo actúa sobre formularios y enlaces internos.
 * Sin JavaScript, el envío nativo del formulario continúa funcionando.
 */
(function () {
    'use strict';

    var activeForm = null;
    var overlay = null;
    var label = null;
    var detail = null;

    function isPwa() {
        return window.location.pathname.indexOf('/transcash/') === 0 ||
               window.location.pathname === '/transcash';
    }

    function makeOverlay() {
        if (overlay) return overlay;
        overlay = document.createElement('div');
        overlay.className = 'tc-pwa-loading';
        overlay.id = 'tc-pwa-loading';
        overlay.hidden = true;
        overlay.setAttribute('role', 'status');
        overlay.setAttribute('aria-live', 'polite');
        overlay.setAttribute('aria-atomic', 'true');
        overlay.innerHTML =
            '<div class="tc-pwa-loading__card">' +
              '<div class="tc-pwa-loading__spinner" aria-hidden="true"></div>' +
              '<strong class="tc-pwa-loading__title"></strong>' +
              '<p class="tc-pwa-loading__detail"></p>' +
              '<div class="tc-pwa-loading__track" role="progressbar" ' +
                  'aria-label="Procesando solicitud" aria-valuetext="En proceso">' +
                '<span class="tc-pwa-loading__bar"></span>' +
              '</div>' +
              '<small>No vuelvas a pulsar. La operación se enviará una sola vez.</small>' +
            '</div>';
        document.body.appendChild(overlay);
        label = overlay.querySelector('.tc-pwa-loading__title');
        detail = overlay.querySelector('.tc-pwa-loading__detail');
        return overlay;
    }

    function messageFor(form) {
        var target = (form.getAttribute('action') || window.location.pathname).toLowerCase();
        if (/\/operacion\/guias\/sincronizar(?:\?|$)/.test(target)) {
            return ['Sincronizando guías ERP',
                    'Consultando API Administrator e importando los registros…'];
        }
        if (/\/embarques\/\d+\/rutas\/agregar(?:\?|$)/.test(target)) {
            return ['Agregando hoja de ruta', 'Comprobando compatibilidad y guardando el viaje…'];
        }
        if (/\/(?:embarques|rutas)\/\d+\/eliminar(?:\?|$)/.test(target)) {
            return ['Eliminando planificación', 'Liberando las guías sin borrar su información…'];
        }
        if (/\/rutas\/\d+\/guias(?:\?|$)/.test(target)) {
            return ['Guardando selección de guías', 'Validando guías, chofer, transportista y destino…'];
        }
        if (/\/rutas\/\d+\/confirmar/.test(target)) {
            return ['Confirmando hoja de ruta', 'Comprobando las guías seleccionadas…'];
        }
        if (/\/rutas\/\d+\/evidencia/.test(target) || form.enctype === 'multipart/form-data') {
            return ['Enviando archivos', 'No cierres esta pantalla durante el envío…'];
        }
        if (/\/rutas\/nueva/.test(target)) {
            return ['Creando hoja de ruta', 'Preparando el siguiente paso…'];
        }
        if (/\/embarques\/nuevo/.test(target)) {
            return ['Procesando embarque', 'Validando rutas y carga…'];
        }
        if (/\/aprobar/.test(target)) {
            return ['Registrando aprobación', 'Comprobando las autorizaciones…'];
        }
        if (/\/negociar/.test(target)) {
            return ['Guardando el flete', 'Registrando el acuerdo autorizado…'];
        }
        if (/\/liberar|\/aceptar-salir/.test(target)) {
            return ['Actualizando el viaje', 'Validando el estado de la operación…'];
        }
        if ((form.method || 'get').toLowerCase() === 'get') {
            return ['Buscando información', 'Consultando los registros disponibles…'];
        }
        return ['Procesando solicitud', 'Verificando y registrando la información…'];
    }

    function show(title, description) {
        var el = makeOverlay();
        label.textContent = title;
        detail.textContent = description;
        el.hidden = false;
        document.documentElement.classList.add('tc-pwa-is-loading');
    }

    function clear() {
        activeForm = null;
        if (overlay) overlay.hidden = true;
        document.documentElement.classList.remove('tc-pwa-is-loading');
        document.querySelectorAll('[data-tc-submitting="1"]').forEach(function (el) {
            el.removeAttribute('data-tc-submitting');
            el.removeAttribute('aria-busy');
        });
    }

    // Bubbling phase: upload/offline handlers have a chance to preventDefault
    // before this runs. Do not interfere with IndexedDB queue submissions.
    document.addEventListener('submit', function (ev) {
        if (!isPwa() || ev.defaultPrevented) return;
        var form = ev.target;
        if (!form || form.tagName !== 'FORM') return;
        if (activeForm || form.dataset.tcSubmitting === '1') {
            ev.preventDefault();
            ev.stopPropagation();
            return;
        }
        // Native validity is checked before submit events. Additional custom
        // handlers can still cancel the event before it reaches document.
        var text = messageFor(form);
        activeForm = form;
        form.dataset.tcSubmitting = '1';
        form.setAttribute('aria-busy', 'true');
        show(text[0], text[1]);
    }, false);

    // Navigation GET pages may take time to load on mobile. Skip same-page,
    // files, external links, downloads and newly opened tabs.
    document.addEventListener('click', function (ev) {
        if (!isPwa() || ev.defaultPrevented || ev.button !== 0 ||
                ev.metaKey || ev.ctrlKey || ev.shiftKey || ev.altKey) return;
        var a = ev.target.closest('a[href]');
        if (!a || a.hasAttribute('download') ||
                (a.target && a.target.toLowerCase() !== '_self')) return;
        var url;
        try { url = new URL(a.href, window.location.href); } catch (_) { return; }
        if (url.origin !== window.location.origin ||
                !url.pathname.startsWith('/transcash/') ||
                url.pathname === window.location.pathname &&
                url.search === window.location.search && url.hash) return;
        if (/\.(?:jpg|jpeg|png|webp|gif|pdf|mp4|webm|xlsx|zip)$/i.test(url.pathname)) return;
        // Allow native click handling first. Only show for an actual navigation.
        window.setTimeout(function () {
            if (!ev.defaultPrevented && !activeForm && document.visibilityState === 'visible') {
                show('Abriendo pantalla', 'Cargando información de Logística…');
            }
        }, 180);
    }, false);

    // Browser back/forward cache restores the old DOM; unlock it immediately.
    window.addEventListener('pageshow', clear);
    // Inputs remain usable when the browser rejects navigation (e.g. offline).
    window.addEventListener('online', function () {
        if (!activeForm && overlay && !overlay.hidden) clear();
    });
}());
