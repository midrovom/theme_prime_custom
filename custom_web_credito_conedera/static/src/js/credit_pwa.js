/** PWA del portal de crédito: aviso de instalación contextual y respetuoso. */
(function () {
    'use strict';
    // Evita mostrar avisos en el backend o en otras aplicaciones del mismo Odoo.
    if (!window.location.pathname.startsWith('/my/credito/')) { return; }

    var promptEvent = null;
    var banner = null;
    var message = null;
    var installButton = null;
    var dismissButton = null;
    var mobile = /Android|iPhone|iPad|iPod/i.test(navigator.userAgent || '');
    var ios = /iPhone|iPad|iPod/i.test(navigator.userAgent || '');
    var dismissalKey = 'credit-pwa-install-dismissed-v1';
    var dismissalDuration = 7 * 24 * 60 * 60 * 1000;

    function isInstalled() {
        return window.matchMedia('(display-mode: standalone)').matches || Boolean(navigator.standalone);
    }
    function dismissedRecently() {
        try {
            return (Date.now() - Number(localStorage.getItem(dismissalKey) || 0)) < dismissalDuration;
        } catch (_) { return false; }
    }
    function reveal() {
        if (!banner || !mobile || isInstalled() || dismissedRecently()) { return; }
        banner.hidden = false;
    }
    function hide() { if (banner) { banner.hidden = true; } }
    function showInstructions() {
        if (!banner) { return; }
        if (!window.isSecureContext) {
            message.textContent = 'Para instalar el portal, ábrelo mediante HTTPS y vuelve a ingresar.';
            installButton.hidden = true;
        } else if (ios) {
            message.textContent = 'En iPhone, toca Compartir y luego «Añadir a pantalla de inicio».';
            installButton.hidden = true;
        } else if (promptEvent) {
            message.textContent = 'Instala el portal y ábrelo desde el ícono de tu teléfono.';
            installButton.hidden = false;
        } else {
            message.textContent = 'Abre el menú del navegador (⋮) y selecciona «Instalar aplicación» o «Añadir a pantalla de inicio».';
            installButton.hidden = true;
        }
        reveal();
    }

    window.addEventListener('beforeinstallprompt', function (event) {
        if (!mobile || isInstalled()) { return; }
        event.preventDefault();
        promptEvent = event;
        showInstructions();
    });
    window.addEventListener('appinstalled', function () {
        promptEvent = null;
        hide();
    });

    function initialize() {
        banner = document.getElementById('credit-pwa-install');
        if (!banner) { return; }
        message = document.getElementById('credit-pwa-install-message');
        installButton = document.getElementById('credit-pwa-install-button');
        dismissButton = document.getElementById('credit-pwa-dismiss-button');
        if (!message || !installButton || !dismissButton) { return; }

        if ('serviceWorker' in navigator && window.isSecureContext) {
            navigator.serviceWorker.register('/my/credito/sw.js', {scope: '/my/credito/', updateViaCache: 'none'})
                .catch(function (error) { console.warn('PWA de crédito no disponible:', error); });
        }
        installButton.addEventListener('click', async function () {
            if (!promptEvent) { return; }
            var event = promptEvent;
            promptEvent = null;
            installButton.hidden = true;
            try {
                await event.prompt();
                var result = await event.userChoice;
                if (result && result.outcome === 'accepted') { hide(); }
                else { showInstructions(); }
            } catch (_) { showInstructions(); }
        });
        dismissButton.addEventListener('click', function () {
            try { localStorage.setItem(dismissalKey, String(Date.now())); } catch (_) { /* opcional */ }
            hide();
        });
        showInstructions();
    }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initialize, {once: true});
    } else { initialize(); }
}());
