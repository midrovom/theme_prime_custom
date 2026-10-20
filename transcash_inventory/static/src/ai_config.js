/* Configuración admin autónoma, sin asistente TransientModel. */
(function () {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const csrf = document.querySelector('meta[name="transcash-csrf"]').content;
  let busy = false;
  const buttons = [$('saveBtn'), $('verifyBtn'), $('testBtn')];
  function setBusy(flag) { busy = flag; buttons.forEach(b => b.disabled = flag); }
  function notify(message, kind) {
    const el = $('banner'); el.textContent = message; el.className = kind || '';
    el.hidden = false;
  }
  function renderStatus(s) {
    $('currentState').textContent = s.ready ? 'IA lista para consultas' : (s.key_saved ? 'Clave guardada · IA no activa' : 'API Key pendiente');
    $('currentState').className = 'chip ' + (s.ready ? 'ready' : 'warn');
    $('statusEnabled').textContent = s.enabled ? 'Sí' : 'No';
    $('statusKey').textContent = s.key_saved ? 'Sí (clave protegida)' : 'No';
    $('statusModel').textContent = s.model || 'No definido';
    $('keyHint').textContent = s.key_saved ? 'Ya existe una clave guardada. Deje vacío para conservarla.' : 'No hay una clave guardada; ingrésela antes de activar.';
    $('aiEnabled').checked = !!s.enabled;
    $('aiModel').value = s.model || 'gpt-5-mini';
    $('apiKey').value = '';
    $('removeKey').checked = false;
  }
  async function api(url, data) {
    const options = {credentials: 'same-origin', cache: 'no-store'};
    if (data) {
      options.method = 'POST'; options.body = data;
    }
    let response;
    try {response = await fetch(url, options);} catch (_) {throw new Error('No fue posible contactar con Odoo. Compruebe la sesión y la red.');}
    const type = response.headers.get('content-type') || '';
    if (!type.includes('application/json')) {
      throw new Error(response.status === 404 ? 'La actualización del módulo no está aplicada. Reinicie Odoo y actualice el módulo.' :
        'Odoo no devolvió JSON (HTTP ' + response.status + '). Compruebe la sesión y el log.');
    }
    const payload = await response.json();
    if (!response.ok || payload.error) throw new Error(payload.error || 'Error HTTP ' + response.status);
    return payload;
  }
  async function state({updateForm = true} = {}) {
    const r = await api('/transcash_inventory/ai/configuration/state?t=' + Date.now());
    if (updateForm) renderStatus(r.config);
    return r.config;
  }
  $('settingsForm').addEventListener('submit', async (event) => {
    event.preventDefault();
    if (busy) return;
    const enabled = $('aiEnabled').checked, remove = $('removeKey').checked;
    const key = $('apiKey').value.trim(), model = $('aiModel').value.trim();
    if (remove && key) {notify('Desmarque eliminar clave si desea reemplazarla.', 'error');return;}
    const data = new FormData();
    data.append('csrf_token', csrf);
    data.append('ai_enabled', enabled ? '1':'0');
    data.append('ai_model', model);
    data.append('api_key_new', key);
    data.append('remove_key', remove ? '1':'0');
    setBusy(true); notify('Guardando la configuración en Odoo...', 'info');
    try {
      const saved = await api('/transcash_inventory/ai/configuration/save', data);
      // Nueva transacción después del guardado. No confundir un ACK con persistencia.
      const confirmed = await state({updateForm: false});
      if (confirmed.enabled !== enabled || confirmed.model !== model ||
          confirmed.key_saved !== saved.config.key_saved) {
        throw new Error('Odoo respondió al guardado, pero otra petición encontró valores diferentes. Revise los logs, la base de datos y los workers.');
      }
      renderStatus(confirmed);
      notify('Configuración guardada y verificada en una nueva petición. ' +
             (confirmed.ready ? 'ChatGPT está listo para consultas.' : 'La IA está desactivada o sin clave.'), 'success');
    } catch (error) {notify(error.message, 'error');}
    finally {setBusy(false);}
  });
  $('verifyBtn').addEventListener('click', async () => {
    if (busy) return;setBusy(true);
    try { const c = await state(); notify('Configuración leída de la base de Odoo: ' +
      (c.enabled ? 'activa' : 'inactiva') + ', API Key ' + (c.key_saved ? 'guardada' : 'no guardada') + '.', 'info'); }
    catch (e) {notify(e.message, 'error');}finally {setBusy(false);}
  });
  $('testBtn').addEventListener('click', async () => {
    if (busy) return;setBusy(true);notify('Comprobando conexión con OpenAI. Espere...', 'info');
    const data = new FormData();data.append('csrf_token', csrf);
    try {const resp = await api('/transcash_inventory/ai/configuration/test', data);
      $('statusConnection').textContent = 'Correcta';notify(resp.message || 'Conexión correcta.', 'success');}
    catch (e) {$('statusConnection').textContent = 'No confirmada';notify(e.message, 'error');}
    finally {setBusy(false);}
  });
  setBusy(true);
  state().then(() => {}).catch(e => notify(e.message, 'error')).finally(() => setBusy(false));
})();
