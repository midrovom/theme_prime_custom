/* Offline app shell. No customer content is interpolated into HTML strings. */
(function () {
  'use strict';
  document.addEventListener('DOMContentLoaded', async function () {
    var tc = self.TranscashOffline;
    if ('serviceWorker' in navigator && self.isSecureContext) {
      navigator.serviceWorker.register('/transcash/sw.js', { scope: '/transcash/' }).catch(function () {});
    }
    var userId = localStorage.getItem('tcMobileUser');
    var guides = [];
    var selected = null;
    var mode = 'evidencia';
    var form = document.getElementById('tc-offline-form');
    var box = document.getElementById('tc-offline-type-fields');
    var report = document.getElementById('tc-offline-error');
    function node(tag, className, text) {
      var el = document.createElement(tag);
      if (className) el.className = className;
      if (text != null) el.textContent = String(text);
      return el;
    }
    function showError(message) { report.hidden = !message; report.textContent = message || ''; }
    function connection() {
      var pill = document.getElementById('tc-network-pill');
      pill.textContent = navigator.onLine ? '● Con señal' : '● Sin señal';
      pill.classList.toggle('is-offline', !navigator.onLine);
      pill.classList.toggle('is-online', navigator.onLine);
    }
    async function currentUser() {
      if (navigator.onLine) {
        try {
          var res = await tc.session();
          userId = String(res.user_id);
          localStorage.setItem('tcMobileUser', userId);
        } catch (_) { /* Offline shell remains readable without a login request. */ }
      }
      return userId;
    }
    function opt(select, value, text, selectedValue) {
      var option = node('option', '', text); option.value = value;
      if (String(value) === String(selectedValue)) option.selected = true;
      select.appendChild(option);
    }
    function labeledInput(labelText, input) {
      var wrap = node('div', 'tc-offline-control');
      var label = node('label', 'tc-label', labelText);
      wrap.appendChild(label); wrap.appendChild(input); return wrap;
    }
    function chooseGuide(guide) {
      selected = guide;
      document.getElementById('tc-offline-compose').hidden = false;
      document.getElementById('tc-offline-compose-title').textContent = 'Reporte · Guía ' + guide.name;
      mode = (guide.types || []).length ? 'evidencia' : 'rotura';
      tabs(); fields();
      document.getElementById('tc-offline-compose').scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
    function tabs() {
      document.querySelectorAll('[data-offline-tab]').forEach(function (b) {
        b.classList.toggle('active', b.dataset.offlineTab === mode);
      });
    }
    function fields() {
      box.replaceChildren();
      if (mode === 'evidencia') {
        var select = node('select', 'tc-input'); select.name = 'tipo'; select.required = true;
        var labels = { carga: 'Carga / embarque', llegada: 'Llegada / descarga', novedad: 'Novedad en ruta', cliente: 'Evidencia del destinatario' };
        (selected.types || []).forEach(function (value) { opt(select, value, labels[value] || value); });
        box.appendChild(labeledInput('Tipo de evidencia', select));
        var novelty = node('select', 'tc-input'); novelty.name = 'tipo_novedad';
        opt(novelty, 'ninguna', 'Sin novedad adicional');
        opt(novelty, 'faltante', 'Faltantes'); opt(novelty, 'otro', 'Otra observación');
        box.appendChild(labeledInput('¿Hay otra novedad?', novelty));
        if (!(selected.types || []).length) box.appendChild(node('p', 'tc-note tc-note-warning', 'No hay tipos disponibles para esta guía. Ábrela con conexión para actualizar sus permisos.'));
      } else {
        var product = node('select', 'tc-input'); product.name = 'linea_id'; product.required = true;
        opt(product, '', 'Seleccionar producto…');
        (selected.products || []).forEach(function (p) {
          opt(product, p.id, p.label + ' · máx. ' + p.max + ' ' + p.unit);
        });
        box.appendChild(labeledInput('Producto afectado', product));
        var qty = node('input', 'tc-input'); qty.name = 'cantidad_rota'; qty.type = 'number';
        qty.step = '0.001'; qty.min = '0.001'; qty.inputMode = 'decimal'; qty.required = true;
        box.appendChild(labeledInput('Cantidad rota (según unidad del producto)', qty));
        product.addEventListener('change', function () {
          var p = (selected.products || []).find(function (x) { return String(x.id) === product.value; });
          if (p) qty.max = p.max; else qty.removeAttribute('max');
        });
        if (!(selected.products || []).length) box.appendChild(node('p', 'tc-note tc-note-warning', 'Debes abrir el detalle de esta guía con Internet una vez para guardar sus productos.'));
      }
      form.querySelector('button[type=submit]').disabled = mode === 'rotura' ? !(selected.products || []).length : !(selected.types || []).length;
    }
    function guideCard(g) {
      var btn = node('button', 'tc-guide-card tc-offline-guide'); btn.type = 'button';
      var top = node('div', 'tc-guide-top'); top.appendChild(node('span', 'tc-guide-number', 'GUÍA ' + g.name));
      top.appendChild(node('span', 'tc-status', g.state || 'Registrada'));
      btn.appendChild(top);
      var route = node('div', 'tc-guide-route');
      route.appendChild(node('span', 'tc-route-node'));
      var content = node('div'); content.appendChild(node('div', 'tc-route-city', g.origin || 'Origen'));
      content.appendChild(node('div', 'tc-route-line', '↓ DESTINO'));
      content.appendChild(node('div', 'tc-route-city', g.destination || 'Destino'));
      route.appendChild(content); btn.appendChild(route);
      btn.appendChild(node('div', 'tc-mini-meta', (g.products || []).length + ' productos preparados · ' + (g.types || []).length + ' tipos de evidencia'));
      btn.addEventListener('click', function () { chooseGuide(g); });
      return btn;
    }
    async function paint() {
      guides = userId ? await tc.guidesFor(userId) : [];
      var list = document.getElementById('tc-offline-guides'); list.replaceChildren();
      document.getElementById('tc-offline-guide-count').textContent = guides.length;
      guides.forEach(function (g) { list.appendChild(guideCard(g)); });
      if (!guides.length) list.appendChild(node('p', 'tc-empty-inline', 'No hay guías preparadas. Entra a Mis guías con conexión y abre cada guía antes de trabajar sin señal.'));
      var params = new URLSearchParams(location.search);
      var guideId = params.get('guide') || ((location.pathname.match(/\/transcash\/guias\/(\d+)/) || [])[1]);
      if (guideId && (!selected || String(selected.guideId) !== String(guideId))) {
        var match = guides.find(function (g) { return String(g.guideId) === String(guideId); });
        if (match) chooseGuide(match);
      }
      var queue = userId ? await tc.queueFor(userId) : [];
      document.getElementById('tc-pending-total').textContent = queue.length + ' pendientes';
      var outbox = document.getElementById('tc-offline-outbox'); outbox.replaceChildren();
      queue.forEach(function (item) {
        var card = node('article', 'tc-outbox-item');
        var title = node('strong', '', (item.kind === 'rotura' ? '⚠ Rotura' : '📷 Evidencia') + ' · ' + item.guideName);
        card.appendChild(title);
        card.appendChild(node('span', 'tc-outbox-status' + (item.status === 'needs_review' ? ' tc-red' : ''),
          item.status === 'needs_review' ? 'Requiere revisión' : 'Pendiente de envío'));
        card.appendChild(node('small', '', new Date(item.createdAt).toLocaleString('es-EC') + ' · ' + item.files.length + ' archivo(s)'));
        card.dataset.tcQueueId = item.id;
        card.appendChild(node('small', 'tc-upload-progress', item.status === 'needs_review' ? 'Revisar motivo del rechazo' : 'Guardado en el teléfono · sin confirmar por Odoo'));
        if (item.error) card.appendChild(node('p', 'tc-outbox-error', item.error));
        var actions = node('div', 'tc-outbox-actions');
        if (item.status === 'needs_review') {
          var again = node('button', 'tc-text-button', 'Reintentar'); again.type = 'button';
          again.addEventListener('click', async function () { item.status = 'pending'; item.error = ''; await tc.update(item); await send(); });
          actions.appendChild(again);
        }
        var del = node('button', 'tc-text-button tc-red', 'Descartar'); del.type = 'button';
        del.addEventListener('click', async function () {
          if (!confirm('Esta evidencia pendiente se eliminará del teléfono. Si aún no se envió, se perderá. ¿Continuar?')) return;
          await tc.remove(item.id); await paint();
        }); actions.appendChild(del); card.appendChild(actions); outbox.appendChild(card);
      });
      if (!queue.length) outbox.appendChild(node('p', 'tc-empty-inline', 'No tienes registros pendientes en este teléfono.'));
    }
    window.addEventListener('transcash-upload-progress', function (event) {
      var card = Array.from(document.querySelectorAll('[data-tc-queue-id]')).find(function (n) { return n.dataset.tcQueueId === event.detail.id; });
      if (card) {
        var label = card.querySelector('.tc-upload-progress');
        if (label) label.textContent = 'Enviando bloques ' + event.detail.done + '/' + event.detail.total + ' · no cierres la app';
      }
    });
    async function send() {
      if (!navigator.onLine) { connection(); return; }
      var button = document.getElementById('tc-force-sync'); button.disabled = true;
      button.textContent = 'Sincronizando…';
      var result = await tc.sync();
      button.disabled = false; button.textContent = '↻ Sincronizar';
      showError(result.error || '');
      await paint();
      if (result.sent) document.getElementById('tc-offline-subtitle').textContent = result.sent + ' registro(s) enviado(s). Los pendientes restantes siguen en el dispositivo.';
    }
    document.querySelectorAll('[data-offline-tab]').forEach(function (b) {
      b.addEventListener('click', function () { mode = b.dataset.offlineTab; tabs(); fields(); });
    });
    function allFiles() {
      return Array.from(form.querySelectorAll('input[type="file"]')).reduce(function (acc, el) { return acc.concat(Array.from(el.files || [])); }, []);
    }
    form.querySelectorAll('input[type=file]').forEach(function (input) { input.addEventListener('change', function () {
      var files = allFiles(); document.getElementById('tc-offline-file-preview').textContent = files.length ? files.map(function (f) { return f.name + ' (' + (f.size / 1048576).toFixed(1) + ' MB)'; }).join(' · ') : 'Sin archivos seleccionados';
    }); });
    form.addEventListener('submit', async function (event) {
      event.preventDefault(); showError('');
      if (!selected || !userId) return showError('No hay guía preparada en este dispositivo.');
      var button = form.querySelector('button[type=submit]');
      button.disabled = true;
      try {
        // A persistence request reduces the chance of browser quota eviction,
        // but the browser may decline it; a local copy is never an ERP receipt.
        if (navigator.storage && navigator.storage.persist) {
          await navigator.storage.persist().catch(function () { return false; });
        }
        var fields = {};
        new FormData(form).forEach(function (value, name) { if (name !== 'archivos') fields[name] = value; });
        await tc.enqueue({ userId: userId, guideId: selected.guideId, guideName: selected.name,
          kind: mode, fields: fields, files: allFiles() });
        form.reset();
        document.getElementById('tc-offline-file-preview').textContent = 'Guardado en este teléfono';
        document.getElementById('tc-offline-subtitle').textContent = 'Tu nuevo registro quedó pendiente. No borres los datos del navegador.';
        await paint();
        if (navigator.onLine) send();
      } catch (error) { showError(error.message || 'No se pudo guardar localmente. Conserve los archivos originales.'); }
      finally { button.disabled = false; }
    });
    document.getElementById('tc-force-sync').addEventListener('click', send);
    document.getElementById('tc-forget-device').addEventListener('click', async function () {
      if (!userId || !confirm('Se borrarán las guías y todas las fotos y videos PENDIENTES de este dispositivo. ¿Estás seguro?')) return;
      await tc.clearAll(); localStorage.removeItem('tcMobileUser'); userId = null; selected = null;
      document.getElementById('tc-offline-compose').hidden = true;
      await paint();
    });
    window.addEventListener('online', function () { connection(); send(); });
    window.addEventListener('offline', connection);
    document.addEventListener('visibilitychange', function () { if (!document.hidden && navigator.onLine) send(); });
    connection(); await currentUser(); await paint();
    if (navigator.onLine) send();
  });
}());
