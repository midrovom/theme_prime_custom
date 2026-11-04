/* PWA Solicitud de crédito — únicamente recursos estáticos, nunca páginas privadas.
 * Al recuperar conectividad reintenta un formulario que el usuario puso en cola.
 * Las solicitudes se identifican por UUID y siempre se validan en Odoo.
 */
'use strict';
const CACHE = 'credit-safe-static-v1844';
const BASE = '/custom_web_credito_conedera/static/';
const STATIC = [
    BASE + 'pwa/offline-shell.html',
    BASE + 'src/js/credit_portal.js',
    BASE + 'src/js/credit_offline.js',
    BASE + 'src/js/credit_offline_operations.js',
    BASE + 'src/css/credit_offline.css',
    BASE + 'src/css/credit_pwa.css',
    BASE + 'src/css/credit_portal.css',
    BASE + 'pwa/icon-192.png',
];
self.addEventListener('install', function (event) {
    event.waitUntil(caches.open(CACHE).then(function (cache) { return cache.addAll(STATIC); }).then(function () { return self.skipWaiting(); }));
});
self.addEventListener('activate', function (event) {
    event.waitUntil(Promise.all([
        caches.keys().then(function (keys) { return Promise.all(keys.filter(function (k) { return k.startsWith('credit-safe-static-') && k !== CACHE; }).map(function (k) { return caches.delete(k); })); }),
        self.clients.claim()
    ]));
});
self.addEventListener('message', function (event) {
    if (!event.data || event.data.type !== 'CREDIT_CACHE_ASSETS') { return; }
    var urls = (event.data.urls || []).filter(function (url) {
        try { var parsed = new URL(url, self.location.href);
            return parsed.origin === self.location.origin && (/^\/web\/assets\//.test(parsed.pathname) || parsed.pathname.startsWith(BASE));
        } catch (_) { return false; }
    }).slice(0, 24);
    event.waitUntil(caches.open(CACHE).then(function (cache) {
        return Promise.all(urls.map(function (url) { return cache.add(url).catch(function () {}); }));
    }));
});
const OFFLINE_PAGE = '<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head><body style="font:16px system-ui;padding:24px;background:#fafafa"><h1>Sin conexión</h1><p>Puede registrar una solicitud offline si abrió previamente el formulario desde este dispositivo.</p><a href="/my/credito/nueva">Abrir formulario guardado</a></body></html>';
self.addEventListener('fetch', function (event) {
    var req = event.request;
    if (req.method !== 'GET') { return; }
    var url = new URL(req.url);
    if (url.origin !== self.location.origin) { return; }
    if (url.pathname.startsWith('/web/assets/') || url.pathname.startsWith(BASE)) {
        if (req.destination !== 'style' && req.destination !== 'script' && req.destination !== 'image' && url.pathname !== BASE + 'pwa/offline-shell.html') { return; }
        event.respondWith(caches.match(req).then(function (hit) {
            return hit || fetch(req).then(function (res) {
                if (res.ok && res.type === 'basic') {
                    var clone = res.clone(); caches.open(CACHE).then(function (cache) { cache.put(req, clone); });
                }
                return res;
            });
        }));
        return;
    }
    if (req.mode !== 'navigate' || !url.pathname.startsWith('/my/credito/')) { return; }
    event.respondWith(fetch(req).catch(async function () {
        if (url.pathname === '/my/credito/nueva') {
            return (await caches.match(BASE + 'pwa/offline-shell.html')) || new Response(OFFLINE_PAGE, {headers:{'Content-Type':'text/html; charset=utf-8'}});
        }
        return new Response(OFFLINE_PAGE, {status:503,headers:{'Content-Type':'text/html; charset=utf-8','Cache-Control':'no-store'}});
    }));
});
function offlineDB() {
    return new Promise(function (resolve, reject) {
        var r = indexedDB.open('solicitud-credito-offline-v1', 1);
        r.onupgradeneeded = function () { if (!r.result.objectStoreNames.contains('drafts')) { r.result.createObjectStore('drafts', {keyPath:'key'}); } if (!r.result.objectStoreNames.contains('templates')) { r.result.createObjectStore('templates', {keyPath:'key'}); } };
        r.onsuccess = function () { resolve(r.result); }; r.onerror = function () { reject(r.error); };
    });
}
async function dbOperation(mode, action) {
    var db = await offlineDB();
    try { return await new Promise(function (resolve,reject) {
        var transaction = db.transaction('drafts',mode);
        var req = action(transaction.objectStore('drafts'));
        req.onsuccess = function () { resolve(req.result); };
        req.onerror = function () { reject(req.error); };
        transaction.onabort = function () { reject(transaction.error); };
    }); } finally { db.close(); }
}
async function syncPending() {
    var drafts = await dbOperation('readonly', function (store) { return store.getAll(); });
    for (var i = 0; i < drafts.length; i++) {
        var draft = drafts[i];
        if (draft.status !== 'pending' || !draft.key.startsWith(self.location.origin + '|')) { continue; }
        try {
            var contextResponse = await fetch('/my/credito/offline/context', {credentials:'same-origin',cache:'no-store'});
            if (!contextResponse.ok || !(contextResponse.headers.get('content-type') || '').includes('application/json')) { continue; }
            var context = await contextResponse.json();
            var expectedKey = [self.location.origin,context.website_id,context.company_id,context.user_id].join('|');
            if ((draft.mode === 'update' || draft.mode === 'documents') ?
                !(draft.key.startsWith(expectedKey + '|') &&
                  draft.identity.user_id === context.user_id &&
                  draft.identity.company_id === context.company_id &&
                  draft.identity.website_id === context.website_id) : expectedKey !== draft.key) { continue; }
            var data = new FormData();
            draft.entries.forEach(function (entry) {
                if (entry.value instanceof Blob) { data.append(entry.name,entry.value,entry.filename || entry.value.name || 'imagen'); }
                else { data.append(entry.name,entry.value); }
            });
            data.set('csrf_token',context.csrf_token);
            if (draft.mode === 'update' || draft.mode === 'documents') {
                data.set('offline_operation', draft.mode);
                data.set('offline_application_id', String(draft.applicationId));
                data.set('offline_operation_uuid', draft.operation_uuid);
                data.set('offline_website_id', String(draft.identity.website_id));
                data.set('offline_company_id', String(draft.identity.company_id));
            }
            var endpoint = (draft.mode === 'update' || draft.mode === 'documents') ? 'dispatch' : 'submit';
            var response = await fetch('/my/credito/offline/' + endpoint,
                {method:'POST',body:data,credentials:'same-origin',cache:'no-store'});
            if (!response.ok || !(response.headers.get('content-type')||'').includes('application/json')) { continue; }
            var result = await response.json();
            if (result.status === 'sent') {
                await dbOperation('readwrite',function (store) {return store.delete(draft.key);});
                var clients = await self.clients.matchAll({type:'window',includeUncontrolled:true});
                clients.forEach(function (client) {
                    if (draft.mode === 'update' || draft.mode === 'documents') {
                        client.postMessage({type:'CREDIT_OPERATION_SENT',application_id:result.application_id,key:draft.key});
                    } else {
                        client.postMessage({type:'CREDIT_SENT',application_id:result.application_id});
                    }
                });
            } else if (draft.mode && (result.status === 'review' || result.status === 'blocked')) {
                // Retener archivos pero no repetir infinitamente una operación rechazada.
                draft.status = 'draft';
                await dbOperation('readwrite',function (store) {return store.put(draft);});
            }
        } catch (error) { /* Mantener el borrador para otro intento seguro. */ }
    }
}
self.addEventListener('sync',function (event) {
    if (event.tag === 'credit-send-pending') { event.waitUntil(syncPending()); }
});
