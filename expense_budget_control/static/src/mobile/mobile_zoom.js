/** @odoo-module **/

/**
 * Odoo 18's backend viewport usually contains `user-scalable=no`.
 * Enable native two-finger zoom for the PWA without intercepting touch events,
 * changing the app's menus or scaling elements manually.
 *
 * The change is intentionally limited to the browser viewport meta tag.
 * It does not affect data, permissions, business logic or event handlers.
 */
function enableNativePinchZoom() {
    const meta = document.querySelector('meta[name="viewport"]');
    if (!meta) {
        return;
    }
    const original = meta.getAttribute("content") || "width=device-width, initial-scale=1";
    const settings = original
        .split(",")
        .map((setting) => setting.trim())
        .filter((setting) => setting && !/^(user-scalable|maximum-scale)\s*=/i.test(setting));
    settings.push("maximum-scale=5", "user-scalable=yes");
    meta.setAttribute("content", settings.join(", "));
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", enableNativePinchZoom, { once: true });
} else {
    enableNativePinchZoom();
}
