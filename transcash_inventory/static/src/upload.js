(function () {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const form = $('uploadForm'), picker = $('excelFile'), submit = $('uploadBtn');
  const token = document.querySelector('meta[name="transcash-csrf"]').content;
  const CHUNK_BYTES = 384 * 1024;
  const MAX_FILE = 45 * 1024 * 1024;
  let uploading = false;
  let currentToken = null;
  let destinationTimer = null;

  function humanSize(size) {return (size / 1024 / 1024).toFixed(2).replace('.', ',') + ' MB';}
  function message(text, kind) {
    const box = $('message'); box.textContent = text;
    box.className = 'message ' + kind; box.hidden = false;
  }
  function clearMessage() { $('message').hidden = true; $('message').textContent = ''; }
  function validSelection() {
    const file = picker.files && picker.files[0];
    if (!file) return null;
    if (!file.name.toLowerCase().endsWith('.xlsx')) { message('Solo se admite Excel con extensión .xlsx.', 'error'); return null; }
    if (!file.size || file.size > MAX_FILE) { message('El archivo debe tener contenido y ser menor de 45 MB.', 'error'); return null; }
    return file;
  }
  function fileSelected() {
    clearMessage();
    const file = validSelection();
    $('dropZone').classList.toggle('valid', Boolean(file));
    $('selectedName').textContent = file ? file.name : 'Haz clic aquí para elegir un Excel';
    $('selectedInfo').textContent = file ? humanSize(file.size) + ' · Listo para cargar' : 'Archivo .xlsx — máximo 45 MB';
    submit.disabled = uploading || !file;
    if (file) $('validation').textContent = 'Archivo seleccionado. Pulsa «Cargar y procesar Excel» para enviar y analizar el contenido.';
  }
  function progress(part, total, text, processing) {
    $('progressBox').hidden = false;
    const p = processing ? 100 : Math.max(0, Math.min(99, Math.round(part * 100 / total)));
    $('progressBar').style.width = p + '%';
    $('progressPercent').textContent = processing ? '100% transferido' : p + '%';
    $('progressStage').textContent = text;
    $('progressDetail').textContent = processing ? 'El servidor está validando el Excel y actualizando los indicadores. No cierres la ventana.' :
      'Fragmento ' + part + ' de ' + total + ' transferidos correctamente.';
  }
  async function post(path, data) {
    const response = await fetch(path, {method: 'POST', credentials: 'same-origin', cache: 'no-store', body: data});
    const contentType = response.headers.get('content-type') || '';
    let result;
    if (contentType.includes('application/json')) {
      result = await response.json();
    } else {
      const body = await response.text();
      if (response.status === 413) throw new Error('El servidor rechazó el tamaño del fragmento (HTTP 413). Revisa el límite de carga de Nginx/Odoo.');
      if (response.status === 403) throw new Error('Sesión sin permisos o token CSRF vencido (HTTP 403). Actualiza la página e inténtalo de nuevo.');
      if (response.redirected || /login|signin/i.test(body.slice(0, 150))) throw new Error('La sesión de Odoo ha expirado. Inicia sesión otra vez y reintenta.');
      throw new Error('Respuesta inesperada del servidor (HTTP ' + response.status + '). Revisa el registro de Odoo.');
    }
    if (!response.ok || !result.ok) throw new Error(result.error || 'Error HTTP ' + response.status);
    return result;
  }
  function body(values) {
    const form = new FormData(); form.append('csrf_token', token);
    Object.entries(values).forEach(([key, val]) => form.append(key, val));
    return form;
  }
  function navigateDashboard() {
    // Se envía una señal al componente Odoo padre para cambiar de menú sin cerrar la sesión.
    if (window.parent !== window) window.parent.postMessage({type: 'transcash_inventory:view_dashboard'}, window.location.origin);
    else window.location.assign('/transcash_inventory/dashboard');
  }
  async function cancelOldToken() {
    if (!currentToken) return;
    const previous = currentToken; currentToken = null;
    try {await post('/transcash_inventory/upload/cancel', body({token: previous}));} catch (err) {console.warn('No se pudo cerrar la sesión temporal de carga.', err);}
  }
  async function upload(file) {
    const count = Math.ceil(file.size / CHUNK_BYTES);
    progress(0, count, 'Iniciando transferencia...');
    const started = await post('/transcash_inventory/upload/start', body({filename: file.name, size: file.size, parts: count}));
    currentToken = started.token;
    if (started.chunk_size !== CHUNK_BYTES || started.parts !== count) throw new Error('El tamaño de fragmentos del servidor no coincide. Actualiza el módulo.');
    for (let i = 0; i < count; i++) {
      const fragment = file.slice(i * CHUNK_BYTES, Math.min((i + 1) * CHUNK_BYTES, file.size));
      await post('/transcash_inventory/upload/chunk', body({token: currentToken, index: i, chunk: fragment}));
      progress(i + 1, count, 'Subiendo Excel...');
    }
    progress(count, count, 'Transferencia completa. Procesando datos...', true);
    const done = await post('/transcash_inventory/upload/finish', body({token: currentToken}));
    currentToken = null;
    $('progressStage').textContent = 'Archivo importado correctamente';
    $('progressDetail').textContent = 'La nueva versión del inventario está guardada en Odoo.';
    message('Importación completada. Se procesaron ' + done.products.toLocaleString('es-EC') +
      ' productos. Periodo final: ' + done.period + '. Versión: #' + done.snapshot_id + '. Abriendo dashboard...', 'success');
    destinationTimer = window.setTimeout(navigateDashboard, 2200);
  }
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (uploading) return;
    const file = validSelection(); if (!file) return;
    uploading = true;
    submit.disabled = true; picker.disabled = true; $('resetBtn').disabled = true;
    clearMessage();
    try { await upload(file); }
    catch (error) {
      message('No se pudo completar la importación.\n' + (error.message || String(error)) +
        '\nSi el problema continúa, revisa Odoo → Registro del servidor o informa el mensaje exacto al administrador.', 'error');
      await cancelOldToken();
    } finally {
      uploading = false; picker.disabled = false; $('resetBtn').disabled = false;
      submit.disabled = !validSelection();
    }
  });
  picker.addEventListener('change', fileSelected);
  $('resetBtn').addEventListener('click', () => {
    if (uploading) return;
    if (destinationTimer) window.clearTimeout(destinationTimer);
    picker.value = ''; clearMessage();
    $('progressBox').hidden = true;
    $('validation').textContent = 'La selección del archivo no inicia la carga. Después pulsa «Cargar y procesar Excel».';
    fileSelected();
  });
  const zone = $('dropZone');
  ['dragenter', 'dragover'].forEach(name => zone.addEventListener(name, e => {e.preventDefault();zone.classList.add('dragover');}));
  ['dragleave', 'drop'].forEach(name => zone.addEventListener(name, e => {e.preventDefault();zone.classList.remove('dragover');}));
  zone.addEventListener('drop', (e) => {
    if (uploading) return;
    if (e.dataTransfer && e.dataTransfer.files.length) {
      try {picker.files = e.dataTransfer.files;fileSelected();}
      catch (err) {message('Selecciona el archivo usando el botón para evitar restricciones del navegador.', 'error');}
    }
  });
  $('goDashboard').addEventListener('click', navigateDashboard);
}());
