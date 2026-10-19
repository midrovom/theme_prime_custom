// Aislamiento: este Service Worker sirve SOLO las páginas de Catastro PWA.
// No registra redirecciones ni intercepta la navegación del escritorio Odoo (/web).
const CACHE = "conedera-field-v4";
const APP_PATH = "/conedera/app";
const SHELL = [
  "/conedera/manifest.webmanifest?v=18.0.1.3.0",
  "/conedera_odoo_census_mobile/static/src/pwa/app.css?v=18.0.1.3.0",
  "/conedera_odoo_census_mobile/static/src/pwa/app.js?v=18.0.1.3.0",
  "/conedera_odoo_census_mobile/static/description/icon.svg",
  "/conedera_odoo_census_mobile/static/description/icon-192.png",
  "/conedera_odoo_census_mobile/static/description/icon-512.png",
  "/conedera_odoo_census_mobile/static/description/icon-maskable-512.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then(async (cache) => {
      await cache.addAll(SHELL);
      // Nunca guardar en caché una redirección a login como si fuera Catastro.
      const response = await fetch(APP_PATH, { credentials: "same-origin", cache: "no-store" });
      if (!response.ok || response.redirected || new URL(response.url).pathname !== APP_PATH
          || !(response.headers.get("Content-Type") || "").includes("text/html")) {
        throw new Error("No se pudo precargar Catastro PWA con una sesión válida");
      }
      await cache.put(APP_PATH, response);
      await self.skipWaiting();
    })
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(
      keys.filter((key) => key.startsWith("conedera-field-") && key !== CACHE)
        .map((key) => caches.delete(key))
    )).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  // Se permite el fallback offline SOLO en la URL exacta del catastro.
  if (req.mode === "navigate" && url.pathname === APP_PATH) {
    event.respondWith(
      fetch(req).then((res) => {
        if (res.ok && !res.redirected && new URL(res.url).pathname === APP_PATH
            && (res.headers.get("Content-Type") || "").includes("text/html")) {
          const copy = res.clone();
          event.waitUntil(caches.open(CACHE).then((cache) => cache.put(APP_PATH, copy)));
        }
        return res;
      }).catch(async () => (await caches.match(APP_PATH)) || Response.error())
    );
    return;
  }

  // Solo caché de recursos propios del complemento, nunca assets de otros módulos.
  if (url.pathname.startsWith("/conedera_odoo_census_mobile/static/")
      || url.pathname === "/conedera/manifest.webmanifest") {
    event.respondWith(
      caches.match(req).then((cached) => cached || fetch(req).then((res) => {
        if (res.ok && !res.redirected) {
          const copy = res.clone();
          event.waitUntil(caches.open(CACHE).then((cache) => cache.put(req, copy)));
        }
        return res;
      }))
    );
  }
});
