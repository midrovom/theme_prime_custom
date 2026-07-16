/** @odoo-module **/

export function initDatafast() {
    if (typeof window.wpwlOptions?.onReady === "function") {
        window.wpwlOptions.onReady();
    }
}

// Ejecutar inmediatamente
initDatafast();

