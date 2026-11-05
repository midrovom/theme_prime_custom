const CACHE = "catastro-field-v20";
const ASSETS = [
  "/catastro/app",
  "/catastro/manifest.webmanifest",
  "/conedera_odoo_census_mobile/static/src/pwa/app.css?v=18.0.1.5.14",
  "/conedera_odoo_census_mobile/static/src/pwa/app.js?v=18.0.1.5.14",
  "/conedera_odoo_census_mobile/static/src/pwa/boot_guard.js?v=18.0.1.5.14",
  "/conedera_odoo_census_mobile/static/description/icon.svg",
];

function safeToCache(response, expectedHtml = false) {
  if (!response || !response.ok || response.redirected) return false;
  const type = response.headers.get("content-type") || "";
  if (expectedHtml && !type.includes("text/html")) return false;
  return true;
}

self.addEventListener("install", (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE);
    const outcomes = await Promise.allSettled(ASSETS.map(async (url) => {
      const response = await fetch(new Request(url, { credentials: "same-origin", cache: "reload" }));
      if (!safeToCache(response, url === "/catastro/app")) throw new Error(`Recurso no disponible: ${url}`);
      await cache.put(url, response);
    }));
    // El HTML es opcional (puede requerir inicio de sesión), pero el JS y CSS no lo son.
    for (const index of [2, 3, 4]) {
      if (outcomes[index].status !== "fulfilled") throw new Error(`No se pudo instalar el recurso ${ASSETS[index]}`);
    }
    await self.skipWaiting();
  })());
});

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter(key =>
      (key.startsWith("conedera-field-") || key.startsWith("catastro-field-")) && key !== CACHE
    ).map(key => caches.delete(key)));
    await self.clients.claim();
  })());
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  if (request.mode === "navigate" && url.pathname === "/catastro/app") {
    event.respondWith((async () => {
      try {
        const response = await fetch(request);
        if (safeToCache(response, true)) {
          const cache = await caches.open(CACHE);
          await cache.put("/catastro/app", response.clone());
        }
        return response;
      } catch (error) {
        const cached = await caches.match("/catastro/app");
        if (cached) return cached;
        throw error;
      }
    })());
    return;
  }

  if (url.pathname.startsWith("/conedera_odoo_census_mobile/static/src/pwa/") || url.pathname === "/catastro/manifest.webmanifest") {
    event.respondWith((async () => {
      try {
        const response = await fetch(request);
        if (safeToCache(response)) {
          const cache = await caches.open(CACHE);
          await cache.put(request, response.clone());
        }
        return response;
      } catch (error) {
        const cached = await caches.match(request);
        if (cached) return cached;
        throw error;
      }
    })());
    return;
  }

  if (url.pathname === "/conedera_odoo_census_mobile/static/description/icon.svg") {
    event.respondWith(caches.match(request).then(cached => cached || fetch(request)));
  }
});
