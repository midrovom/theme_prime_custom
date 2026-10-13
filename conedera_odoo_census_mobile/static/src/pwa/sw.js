const CACHE = "conedera-field-v1";
const SHELL = [
  "/conedera/app",
  "/conedera/manifest.webmanifest",
  "/conedera_odoo_census_mobile/static/src/pwa/app.css",
  "/conedera_odoo_census_mobile/static/src/pwa/app.js",
  "/conedera_odoo_census_mobile/static/description/icon.svg",
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((key) => key.startsWith("conedera-field-") && key !== CACHE).map((key) => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  if (req.mode === "navigate" && url.pathname.startsWith("/conedera/")) {
    event.respondWith(
      fetch(req).then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((cache) => cache.put("/conedera/app", copy));
        return res;
      }).catch(() => caches.match("/conedera/app"))
    );
    return;
  }

  if (url.pathname.includes("/conedera_odoo_census_mobile/static/") || url.pathname === "/conedera/manifest.webmanifest") {
    event.respondWith(caches.match(req).then((cached) => cached || fetch(req).then((res) => {
      const copy = res.clone();
      caches.open(CACHE).then((cache) => cache.put(req, copy));
      return res;
    })));
  }
});
