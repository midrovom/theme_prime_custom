/* Progressive enhancement only. The forms work server-side without JS. */
(function () {
  'use strict';
  document.addEventListener('DOMContentLoaded', function () {
    var modal = document.getElementById('tc-action-modal');
    var selectedPanel = 'resumen';
    var available = Array.from(document.querySelectorAll('[data-panel]'));
    function showTab(name) {
      if (!available.some(function (p) { return p.dataset.panel === name; })) return;
      selectedPanel = name;
      available.forEach(function (p) { p.hidden = p.dataset.panel !== name; });
      document.querySelectorAll('[data-tab]').forEach(function (b) {
        b.classList.toggle('active', b.dataset.tab === name);
        b.setAttribute('aria-selected', String(b.dataset.tab === name));
      });
      document.querySelectorAll('[data-go-tab]').forEach(function (b) {
        b.classList.toggle('active', b.dataset.goTab === name);
      });
    }
    document.querySelectorAll('[data-tab], [data-go-tab]').forEach(function (button) {
      button.addEventListener('click', function () {
        showTab(button.dataset.tab || button.dataset.goTab);
        if (button.dataset.goTab) window.scrollTo({ top: 245, behavior: 'smooth' });
      });
    });
    if (available.length) showTab(['resumen','productos','evidencias','roturas','historial'].indexOf(window.location.hash.slice(1)) >= 0 ? window.location.hash.slice(1) : selectedPanel);

    function selectForm(name) {
      if (!modal) return;
      modal.querySelectorAll('[data-form-panel]').forEach(function (p) { p.hidden = p.dataset.formPanel !== name; });
      modal.querySelectorAll('[data-form-tab]').forEach(function (b) { b.classList.toggle('active', b.dataset.formTab === name); });
    }
    function openModal(form) {
      if (!modal) return;
      selectForm(form || (modal.querySelector('[data-form-panel="evidencia"]') ? 'evidencia' : 'rotura'));
      modal.classList.add('is-open');
      modal.setAttribute('aria-hidden', 'false');
      document.body.classList.add('tc-modal-open');
      modal.querySelector('.tc-modal-close').focus();
    }
    function closeModal() {
      if (!modal) return;
      modal.classList.remove('is-open');
      modal.setAttribute('aria-hidden', 'true');
      document.body.classList.remove('tc-modal-open');
    }
    document.querySelectorAll('[data-modal-open]').forEach(function (b) { b.addEventListener('click', function () { openModal(); }); });
    document.querySelectorAll('[data-modal-close]').forEach(function (b) { b.addEventListener('click', closeModal); });
    document.querySelectorAll('[data-form-tab]').forEach(function (b) { b.addEventListener('click', function () { selectForm(b.dataset.formTab); }); });
    document.querySelectorAll('[data-damage-line]').forEach(function (b) {
      b.addEventListener('click', function () {
        openModal('rotura');
        var choice = document.getElementById('tc-damage-product');
        if (choice) { choice.value = b.dataset.damageLine; choice.dispatchEvent(new Event('change')); }
      });
    });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') closeModal(); });
    var choice = document.getElementById('tc-damage-product');
    if (choice) choice.addEventListener('change', function () {
      var o = this.options[this.selectedIndex];
      var max = o ? o.dataset.max : '';
      var unit = o ? o.dataset.unit : '';
      document.getElementById('tc-quantity-help').textContent = max ? 'Embarcado: ' + max + ' ' + unit + ' (máximo teórico; descuenta reportes previos).' : 'Selecciona un producto para conocer su cantidad.';
      document.getElementById('tc-unit-label').textContent = unit || 'UND.';
      var qty = modal.querySelector('[name="cantidad_rota"]');
      if (qty) { if (max) qty.max = max; else qty.removeAttribute('max'); }
    });
    document.querySelectorAll('.tc-form-panel').forEach(function (form) {
      var inputs = Array.from(form.querySelectorAll('input[type="file"]'));
      var preview = form.querySelector('[data-file-preview]');
      function showFiles() {
        if (!preview) return;
        preview.textContent = '';
        var files = inputs.reduce(function (all, input) { return all.concat(Array.from(input.files || [])); }, []);
        if (!files.length) { preview.textContent = 'Sin archivos seleccionados'; return; }
        files.forEach(function (file) {
          var item = document.createElement('span'); item.className = 'tc-file-tag';
          item.textContent = (file.type.indexOf('video/') === 0 ? '🎥 ' : '📷 ') + file.name + ' · ' + (file.size / (1024 * 1024)).toFixed(1) + ' MB';
          preview.appendChild(item);
        });
        if (files.length > 6) { var warning = document.createElement('b'); warning.className = 'tc-red'; warning.textContent = 'Máximo 6 archivos.'; preview.appendChild(warning); }
      }
      inputs.forEach(function (input) { input.addEventListener('change', showFiles); });
      form.addEventListener('submit', function (event) {
        var files = inputs.reduce(function (all, input) { return all.concat(Array.from(input.files || [])); }, []);
        if (form.dataset.formPanel === 'rotura' && files.length === 0) { event.preventDefault(); window.alert('Adjunta una fotografía o video de la rotura.'); return; }
        if (files.length > 6 || files.reduce(function (total, f) { return total + f.size; }, 0) > 110 * 1024 * 1024) { event.preventDefault(); window.alert('Máximo 6 archivos y 110 MB en total.'); return; }
        var button = form.querySelector('button[type="submit"]');
        if (button) { button.disabled = true; button.textContent = 'Subiendo archivos…'; }
      });
    });
  });
}());

/* Offline-first enhancement for evidence and damage forms. Normal POST remains a fallback
 * if IndexedDB/service workers are unavailable. Never claim delivery before server ACK.
 */
(function () {
  'use strict';
  document.addEventListener('DOMContentLoaded', function () {
    var tc = self.TranscashOffline;
    if (!tc) return;
    var body = document.body;
    var userId = body.dataset.tcUserId;
    var guideId = body.dataset.tcGuideId;
    if (!userId) return;
    localStorage.setItem('tcMobileUser', String(userId));
    var pendingLink = document.querySelectorAll('[data-tc-pending-link]');
    var banner = document.createElement('div');
    banner.className = 'tc-live-status'; banner.setAttribute('role', 'status');
    var note = document.createElement('span');
    var go = document.createElement('a'); go.href = '/transcash/offline'; go.textContent = 'Ver pendientes →';
    banner.appendChild(note); banner.appendChild(go);
    window.addEventListener('transcash-upload-progress', function (ev) {
      if (ev.detail && ev.detail.total) note.textContent = '↑ Video: ' + Math.round(100 * ev.detail.done / ev.detail.total) + '% enviado · ' + ev.detail.done + '/' + ev.detail.total + ' bloques';
    });
    var header = document.querySelector('.tc-top');
    if (header) header.insertAdjacentElement('afterend', banner);
    async function refresh() {
      var pending = await tc.queueFor(userId);
      note.textContent = (navigator.onLine ? '● Con señal' : '● Sin señal') + ' · ' + pending.length + ' por sincronizar';
      banner.classList.toggle('no-signal', !navigator.onLine);
      pendingLink.forEach(function (a) { a.textContent = '⇅ Pendientes' + (pending.length ? ' (' + pending.length + ')' : ''); });
    }
    function fromCard(card) {
      return { userId: String(userId), guideId: Number(card.dataset.tcCardId),
        name: card.dataset.tcCardName, state: card.dataset.tcCardState,
        origin: card.dataset.tcCardOrigin, destination: card.dataset.tcCardDestination,
        types: [], products: [] };
    }
    async function saveGuideSnapshots() {
      var cards = document.querySelectorAll('[data-tc-card-id]');
      for (var i = 0; i < cards.length; i++) await tc.rememberGuide(fromCard(cards[i]));
      if (!guideId) return;
      var select = document.getElementById('tc-damage-product');
      var typeSelect = document.querySelector('.tc-form-panel[data-form-panel="evidencia"] [name="tipo"]');
      var products = select ? Array.from(select.options).filter(function (o) { return o.value; }).map(function (o) {
        return { id: Number(o.value), label: o.textContent.trim(), max: o.dataset.max, unit: o.dataset.unit };
      }) : [];
      var types = typeSelect ? Array.from(typeSelect.options).filter(function (o) { return o.value; }).map(function (o) { return o.value; }) : [];
      await tc.rememberGuide({ userId: String(userId), guideId: Number(guideId), name: body.dataset.tcGuideName,
        origin: body.dataset.tcGuideOrigin, destination: body.dataset.tcGuideDestination,
        state: body.dataset.tcGuideState, products: products, types: types });
    }
    async function requestSync() {
      if (!navigator.onLine) return;
      var result = await tc.sync();
      await refresh();
      if (result.sent) notify('✓ ' + result.sent + ' registro(s) sincronizados con Transcash', false);
      if (result.error && result.error.indexOf('sesión') === -1) console.warn('Transcash sync:', result.error);
    }
    async function scheduleBackground() {
      if (!('serviceWorker' in navigator)) return;
      try {
        var registration = await navigator.serviceWorker.ready;
        if (registration.sync && registration.sync.register) await registration.sync.register('transcash-outbox');
      } catch (_) { /* Safari/iOS: retry when the app is opened or reconnects. */ }
    }
    var toast;
    function notify(message, bad) {
      if (!toast) { toast = document.createElement('div'); toast.className = 'tc-toast'; toast.setAttribute('role', 'status'); document.body.appendChild(toast); }
      toast.textContent = message; toast.classList.toggle('tc-toast-error', !!bad); toast.classList.add('show');
      if (toast._timeout) clearTimeout(toast._timeout);
      toast._timeout = setTimeout(function () { toast.classList.remove('show'); }, 5500);
    }
    if ('serviceWorker' in navigator && window.isSecureContext) {
      navigator.serviceWorker.register('/transcash/sw.js', { scope: '/transcash/' }).catch(function (error) { console.warn('PWA no disponible:', error); });
    }
    saveGuideSnapshots().catch(function (e) { console.warn('No se pudo preparar la guía offline:', e); });
    refresh().catch(function () {});
    // Forms are always committed to IndexedDB BEFORE attempting network upload.
    document.querySelectorAll('.tc-form-panel').forEach(function (form) {
      form.addEventListener('submit', async function (event) {
        if (!guideId || !window.isSecureContext || !('indexedDB' in window)) return;
        event.preventDefault(); event.stopImmediatePropagation();
        var submit = form.querySelector('button[type="submit"]');
        if (submit) { submit.disabled = true; submit.textContent = 'Guardando en este teléfono…'; }
        try {
          if (navigator.storage && navigator.storage.persist) {
            await navigator.storage.persist().catch(function () { return false; });
          }
          var fields = {};
          new FormData(form).forEach(function (value, key) {
            if (key !== 'archivos' && key !== 'csrf_token') fields[key] = value;
          });
          var files = Array.from(form.querySelectorAll('input[type=file]')).reduce(function (all, input) {
            return all.concat(Array.from(input.files || []));
          }, []);
          var kind = form.dataset.formPanel;
          var record = await tc.enqueue({ userId: userId, guideId: guideId,
            guideName: body.dataset.tcGuideName, kind: kind, fields: fields, files: files });
          form.reset();
          var preview = form.querySelector('[data-file-preview]');
          if (preview) preview.textContent = 'Archivos guardados en este teléfono';
          notify('✓ Guardado en el dispositivo. Pendiente de sincronizar.', false);
          var modal = document.getElementById('tc-action-modal');
          if (modal) { modal.classList.remove('is-open'); modal.setAttribute('aria-hidden', 'true'); document.body.classList.remove('tc-modal-open'); }
          await refresh();
          await scheduleBackground();
          if (navigator.onLine) requestSync();
        } catch (error) {
          notify('No se guardó: ' + (error.message || 'revisa el espacio disponible'), true);
          // Files remain in the form so they can be retried without losing the selection.
        } finally { if (submit) { submit.disabled = false; submit.textContent = form.dataset.formPanel === 'rotura' ? 'Registrar rotura →' : 'Guardar evidencia →'; } }
      }, true);
    });
    window.addEventListener('online', function () { refresh(); requestSync(); });
    window.addEventListener('offline', refresh);
    document.addEventListener('visibilitychange', function () { if (!document.hidden) requestSync(); });
    if (navigator.onLine) requestSync();
  });
}());

/* Escritorio: búsqueda instantánea de guías ya autorizadas por el servidor. */
document.addEventListener('DOMContentLoaded', function () {
  var field = document.getElementById('tc-guide-search');
  if (!field) return;
  var cards = Array.from(document.querySelectorAll('.tc-guide-card'));
  field.addEventListener('input', function () {
    var query = (field.value || '').trim().toLocaleLowerCase();
    cards.forEach(function (card) {
      var haystack = [card.dataset.tcCardName, card.dataset.tcCardOrigin,
                      card.dataset.tcCardDestination].join(' ').toLocaleLowerCase();
      card.hidden = Boolean(query) && haystack.indexOf(query) === -1;
    });
  });
});
