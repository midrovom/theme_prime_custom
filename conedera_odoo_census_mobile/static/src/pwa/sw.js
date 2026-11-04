const CACHE = "catastro-field-v7";
const SHELL = [
  "/catastro/app",
  "/catastro/manifest.webmanifest",
  "/conedera_odoo_census_mobile/static/src/pwa/app.css?v=18.0.1.5.1",
  "/conedera_odoo_census_mobile/static/src/pwa/app.js?v=18.0.1.5.1",
  "/conedera_odoo_census_mobile/static/description/icon.svg",
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((key) => (key.startsWith("conedera-field-") || key.startsWith("catastro-field-")) && key !== CACHE).map((key) => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  if (req.mode === "navigate" && url.pathname === "/catastro/app") {
    event.respondWith(
      fetch(req).then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((cache) => cache.put("/catastro/app", copy));
        return res;
      }).catch(() => caches.match("/catastro/app"))
    );
    return;
  }

  if (url.pathname.startsWith("/conedera_odoo_census_mobile/static/src/pwa/") || url.pathname === "/catastro/manifest.webmanifest") {
    event.respondWith(fetch(req).then((res) => {
      if (res.ok) { const copy = res.clone(); caches.open(CACHE).then((cache) => cache.put(req, copy)); }
      return res;
    }).catch(() => caches.match(req)));
    return;
  }
  if (url.pathname === "/conedera_odoo_census_mobile/static/description/icon.svg") {
    event.respondWith(caches.match(req).then((cached) => cached || fetch(req)));
  }
});
