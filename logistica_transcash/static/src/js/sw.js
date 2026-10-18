/* Versioned app shell ONLY. Authenticated guide HTML and media are never cached. */
importScripts('/logistica_transcash/static/src/js/offline-core.js');
var STATIC = 'transcash-pwa-v5.23-shell-1';
var APP_ASSETS = [
  '/transcash/offline',
  '/transcash/manifest.webmanifest',
  '/logistica_transcash/static/src/css/mobile.css',
  '/logistica_transcash/static/src/js/offline-core.js',
  '/logistica_transcash/static/src/js/offline-app.js',
  '/logistica_transcash/static/src/js/mobile.js',
  '/logistica_transcash/static/src/img/icon-192.png',
  '/logistica_transcash/static/src/img/icon-512.png'
];
self.addEventListener('install', function (event) {
  event.waitUntil(caches.open(STATIC).then(function (cache) { return cache.addAll(APP_ASSETS); }).then(function () { return self.skipWaiting(); }));
});
self.addEventListener('activate', function (event) {
  event.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.filter(function (k) { return k.indexOf('transcash-pwa-') === 0 && k !== STATIC; }).map(function (k) { return caches.delete(k); }));
  }).then(function () { return self.clients.claim(); }));
});
self.addEventListener('fetch', function (event) {
  var req = event.request, url = new URL(req.url);
  if (req.method !== 'GET' || url.origin !== self.location.origin) return;
  if (req.mode === 'navigate' && url.pathname.indexOf('/transcash/') === 0) {
    // A stale private HTML page would expose customer details after account logout.
    event.respondWith(fetch(req).catch(function () { return caches.match('/transcash/offline'); }));
    return;
  }
  if (APP_ASSETS.indexOf(url.pathname) !== -1) {
    event.respondWith(caches.match(url.pathname).then(function (cached) { return cached || fetch(req); }));
  }
});
self.addEventListener('sync', function (event) {
  if (event.tag === 'transcash-outbox') {
    event.waitUntil(self.TranscashOffline.sync().then(function (result) {
      // Tell compatible browsers to retry transient failures. Permanent business
      // validation errors require the user's review, not automatic retries.
      if (result.error && result.error.indexOf('Inicia sesión') === -1) throw new Error(result.error);
    }));
  }
});
self.addEventListener('message', function (event) {
  if (event.data && event.data.type === 'SYNC_OUTBOX') {
    event.waitUntil(self.TranscashOffline.sync());
  }
});
