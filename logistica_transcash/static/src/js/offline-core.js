/* Transcash PWA v4. Shared IndexedDB outbox used by document and service worker.
 * No Odoo cookies, CSRF tokens or personal data are put into Cache Storage.
 */
(function (root) {
  'use strict';
  var NAME = 'transcash-mobile-v3';
  var VERSION = 1;
  var inFlight = null;
  function open() {
    return new Promise(function (resolve, reject) {
      if (!root.indexedDB) return reject(new Error('Almacenamiento offline no disponible.'));
      var req = root.indexedDB.open(NAME, VERSION);
      req.onupgradeneeded = function () {
        var db = req.result;
        if (!db.objectStoreNames.contains('queue')) db.createObjectStore('queue', { keyPath: 'id' });
        if (!db.objectStoreNames.contains('guides')) db.createObjectStore('guides', { keyPath: 'key' });
      };
      req.onsuccess = function () { resolve(req.result); };
      req.onerror = function () { reject(req.error); };
    });
  }
  async function store(name, mode, run) {
    var db = await open();
    return new Promise(function (resolve, reject) {
      var tx = db.transaction(name, mode), os = tx.objectStore(name), value;
      try { value = run(os); } catch (err) { db.close(); reject(err); return; }
      tx.oncomplete = function () { db.close(); resolve(value); };
      tx.onerror = function () { db.close(); reject(tx.error || new Error('No se pudo guardar en el teléfono.')); };
      tx.onabort = function () { db.close(); reject(tx.error || new Error('El teléfono rechazó el almacenamiento.')); };
    });
  }
  function getAll(name) {
    return new Promise(async function (resolve, reject) {
      try {
        var db = await open(), tx = db.transaction(name, 'readonly'), req = tx.objectStore(name).getAll();
        req.onsuccess = function () { resolve(req.result || []); };
        req.onerror = function () { reject(req.error); };
        tx.oncomplete = function () { db.close(); };
      } catch (error) { reject(error); }
    });
  }
  function id() {
    if (root.crypto && root.crypto.randomUUID) return root.crypto.randomUUID();
    if (!root.crypto || !root.crypto.getRandomValues) throw new Error('Se requiere HTTPS para guardar evidencias offline.');
    var array = new Uint8Array(16);
    root.crypto.getRandomValues(array);
    array[6] = array[6] & 15 | 64;
    array[8] = array[8] & 63 | 128;
    var s = Array.from(array, function (b) { return b.toString(16).padStart(2, '0'); }).join('');
    return s.slice(0, 8) + '-' + s.slice(8, 12) + '-' + s.slice(12, 16) + '-' + s.slice(16, 20) + '-' + s.slice(20);
  }
  async function rememberGuide(snapshot) {
    if (!snapshot || !snapshot.userId || !snapshot.guideId) return;
    snapshot.key = String(snapshot.userId) + ':' + String(snapshot.guideId);
    // A lightweight list refresh must not erase product details captured on a guide page.
    var earlier = (await guidesFor(snapshot.userId)).find(function (g) { return g.key === snapshot.key; });
    if (earlier && (!snapshot.products || !snapshot.products.length)) snapshot.products = earlier.products || [];
    if (earlier && (!snapshot.types || !snapshot.types.length)) snapshot.types = earlier.types || [];
    snapshot.updatedAt = Date.now();
    await store('guides', 'readwrite', function (os) { os.put(snapshot); });
  }
  async function guidesFor(userId) {
    var all = await getAll('guides');
    return all.filter(function (g) { return String(g.userId) === String(userId); }).sort(function (a, b) { return b.updatedAt - a.updatedAt; });
  }
  function validateFiles(files) {
    if (files.length > 6) throw new Error('Máximo 6 archivos por registro.');
    var total = 0;
    files.forEach(function (f) {
      var isImage = f.type.indexOf('image/') === 0;
      var isVideo = f.type.indexOf('video/') === 0;
      if (!isImage && !isVideo) throw new Error('Solo se admiten imágenes y videos.');
      if (isImage && f.size > 12 * 1048576) throw new Error('Cada foto admite hasta 12 MB.');
      if (isVideo && f.size > 75 * 1048576) throw new Error('Cada video admite hasta 75 MB.');
      total += f.size;
    });
    if (total > 110 * 1048576) throw new Error('Máximo 110 MB por registro.');
  }
  async function enqueue(draft) {
    var files = draft.files || [];
    validateFiles(files);
    if (!draft.userId || !draft.guideId || ['evidencia', 'rotura'].indexOf(draft.kind) === -1) throw new Error('Guía y usuario requeridos.');
    if (!(draft.fields.observacion || '').trim() && draft.kind === 'evidencia' && draft.fields.tipo === 'llegada') {
      draft.fields.observacion = 'Evidencia de descarga sin novedades declaradas por el chofer';
    }
    if (!(draft.fields.observacion || '').trim()) throw new Error('Escribe una observación.');
    if (draft.kind === 'rotura' && (!files.length || !draft.fields.linea_id || !(Number(String(draft.fields.cantidad_rota || '').replace(',', '.')) > 0))) {
      throw new Error('La rotura requiere un producto, cantidad y una foto o video.');
    }
    if (draft.kind === 'evidencia' && ['carga', 'llegada'].indexOf(draft.fields.tipo) >= 0 && !files.length) {
      throw new Error('Agrega una foto o video de carga o llegada.');
    }
    var data = {
      id: id(), userId: String(draft.userId), guideId: Number(draft.guideId), guideName: String(draft.guideName || ''),
      kind: draft.kind, fields: draft.fields, files: files.map(function (f) { return { blob: f, name: f.name || 'archivo', type: f.type, size: f.size }; }),
      status: 'pending', attempts: 0, error: '', createdAt: Date.now(), capturedAt: new Date().toISOString(), lastTryAt: 0
    };
    await store('queue', 'readwrite', function (os) { os.add(data); });
    return data;
  }
  async function queueFor(userId) {
    var all = await getAll('queue');
    return all.filter(function (x) { return String(x.userId) === String(userId); }).sort(function (a, b) { return a.createdAt - b.createdAt; });
  }
  function remove(id) { return store('queue', 'readwrite', function (os) { os.delete(id); }); }
  function update(item) { return store('queue', 'readwrite', function (os) { os.put(item); }); }
  async function clearAll() {
    await store('queue', 'readwrite', function (os) { os.clear(); });
    await store('guides', 'readwrite', function (os) { os.clear(); });
  }
  async function clearUser(userId) {
    var q = await queueFor(userId), g = await guidesFor(userId);
    await store('queue', 'readwrite', function (os) { q.forEach(function (x) { os.delete(x.id); }); });
    await store('guides', 'readwrite', function (os) { g.forEach(function (x) { os.delete(x.key); }); });
  }
  async function session() {
    var res = await root.fetch('/transcash/sync/session', {
      credentials: 'same-origin', cache: 'no-store', redirect: 'follow', headers: { 'Accept': 'application/json' }
    });
    if (!res.ok || !(res.headers.get('content-type') || '').includes('application/json')) throw new Error('Inicia sesión en Transcash para sincronizar.');
    var body = await res.json();
    if (!body.ok || !body.csrf_token || !body.user_id) throw new Error('Sesión no válida.');
    return body;
  }
  // 1 MiB resumable transfer. The server, not IndexedDB, is the source
  // of truth for acknowledged chunks; a restarted phone never repeats them.
  var CHUNK = 1024 * 1024;
  function progress(item, done, total) {
    if (root.document && typeof root.CustomEvent !== 'undefined') {
      root.dispatchEvent(new root.CustomEvent('transcash-upload-progress', {
        detail: { id: item.id, done: done, total: total }
      }));
    }
  }
  async function jsonRequest(path, options) {
    var res = await root.fetch(path, options || {});
    if (!(res.headers.get('content-type') || '').includes('application/json')) {
      throw new Error('Se requiere iniciar sesión nuevamente o revisar la conexión.');
    }
    var body = await res.json();
    if (!res.ok || !body.ok) {
      var err = new Error(body.error || ('Error HTTP ' + res.status));
      err.permanent = [400, 403, 409, 413, 422].indexOf(res.status) >= 0;
      throw err;
    }
    return body;
  }
  async function sha256(blob) {
    if (!root.crypto || !root.crypto.subtle) throw new Error('La subida segura requiere HTTPS.');
    var bytes = await blob.arrayBuffer();
    var hash = await root.crypto.subtle.digest('SHA-256', bytes);
    return Array.from(new Uint8Array(hash), function (b) { return b.toString(16).padStart(2, '0'); }).join('');
  }
  function fileParams(item, file, index, checksum) {
    return {
      client_uuid: item.id, guide_id: String(item.guideId), kind: item.kind,
      file_index: String(index), file_count: String(item.files.length),
      file_size: String(file.size), file_sha256: checksum,
      file_name: file.name, file_mime: file.type,
      total_chunks: String(Math.ceil(file.size / CHUNK))
    };
  }
  function append(data, values) {
    Object.keys(values).forEach(function (key) { data.append(key, String(values[key])); });
  }
  async function stageFiles(item, token) {
    var files = item.files || [];
    var done = 0;
    var total = files.reduce(function (a, f) { return a + Math.ceil(f.size / CHUNK); }, 0);
    progress(item, done, total);
    for (var i = 0; i < files.length; i++) {
      var file = files[i];
      var checksum = await sha256(file.blob);
      var fields = fileParams(item, file, i, checksum);
      var query = new URLSearchParams(fields);
      var response = await jsonRequest('/transcash/sync/chunk/status?' + query.toString(), {
        credentials: 'same-origin', cache: 'no-store', headers: { Accept: 'application/json' }
      });
      if (response.complete) { progress(item, total, total); return; }
      var received = new Set(response.received || []);
      done += received.size;
      progress(item, done, total);
      for (var k = 0; k < Number(fields.total_chunks); k++) {
        if (received.has(k)) continue;
        var start = k * CHUNK;
        var form = new FormData();
        append(form, fields);
        form.append('csrf_token', token);
        form.append('chunk_index', String(k));
        form.append('chunk', file.blob.slice(start, Math.min(file.size, start + CHUNK)), 'bloque.bin');
        await jsonRequest('/transcash/sync/chunk/part', {
          method: 'POST', credentials: 'same-origin', body: form, cache: 'no-store'
        });
        done += 1;
        progress(item, done, total);
      }
    }
  }
  async function upload(item, token) {
    var data = new FormData();
    data.append('csrf_token', token);
    data.append('client_uuid', item.id);
    data.append('guide_id', String(item.guideId));
    data.append('kind', item.kind);
    data.append('captured_at', item.capturedAt || '');
    Object.keys(item.fields).forEach(function (key) { data.append(key, String(item.fields[key] || '')); });
    if (item.files.length) {
      await stageFiles(item, token);
      data.append('chunked', '1');
      data.append('file_count', String(item.files.length));
    } else {
      data.append('chunked', '1');
      data.append('file_count', '0');
    }
    try {
      var body = await jsonRequest('/transcash/sync/upload', {
        method: 'POST', body: data, cache: 'no-store', credentials: 'same-origin'
      });
      return { ok: true, permanent: false, id: body.id };
    } catch (error) {
      return { ok: false, permanent: !!error.permanent, error: error.message };
    }
  }
  async function sync() {
    if (inFlight) return inFlight;
    inFlight = (async function () {
      var state = { sent: 0, pending: 0, blocked: 0, error: '' };
      try {
        var onlineSession = await session();
        var items = await queueFor(onlineSession.user_id);
        for (var i = 0; i < items.length; i++) {
          var item = items[i];
          if (item.status === 'needs_review') { state.blocked++; continue; }
          // Retry pending requests; same UUID guarantees safe recovery if last response was lost.
          item.attempts += 1;
          item.lastTryAt = Date.now();
          try {
            var result = await upload(item, onlineSession.csrf_token);
            if (result.ok) { await remove(item.id); state.sent++; continue; }
            item.error = result.error;
            item.status = result.permanent ? 'needs_review' : 'pending';
            await update(item);
            if (result.permanent) state.blocked++;
            else { state.error = result.error; break; }
          } catch (error) {
            item.error = String(error.message || 'Sin conexión.');
            if (error.permanent) item.status = 'needs_review';
            await update(item);
            state.error = item.error;
            break;
          }
        }
        state.pending = (await queueFor(onlineSession.user_id)).length;
      } catch (error) { state.error = String(error.message || error); }
      return state;
    })();
    try { return await inFlight; } finally { inFlight = null; }
  }
  root.TranscashOffline = { enqueue: enqueue, rememberGuide: rememberGuide, guidesFor: guidesFor,
    queueFor: queueFor, remove: remove, clearUser: clearUser, clearAll: clearAll, sync: sync, update: update,
    validateFiles: validateFiles, session: session };
}(self));
