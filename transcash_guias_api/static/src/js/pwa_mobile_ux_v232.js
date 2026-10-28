/* v2.32 · Mejora progresiva de los formularios de evidencia.
 * La carga sigue siendo POST nativo; el loading y anti doble envío v2.22
 * no se sustituyen, y los formularios offline de guías no se interceptan.
 */
(function () {
  'use strict';
  function ready() {
    document.querySelectorAll('[data-tc-evidence-upload]').forEach(function (form) {
      var input = form.querySelector('input[type="file"][name="archivo"]');
      var message = form.querySelector('.tc-evidence-file-status');
      var submit = form.querySelector('button[type="submit"]');
      if (!input || !message || !submit) return;
      // Sin JS el botón está activo y la validación nativa sigue operando.
      submit.disabled = true;
      var sending = false;
      function display(value, kind) {
        message.textContent = value;
        message.classList.toggle('is-ready', kind === 'ready');
        message.classList.toggle('is-error', kind === 'error');
        form.classList.toggle('is-selected', kind === 'ready');
        form.classList.toggle('is-invalid', kind === 'error');
      }
      function check() {
        var file = input.files && input.files[0];
        if (!file) { display('Selecciona un archivo para continuar.', 'idle'); submit.disabled = true; return false; }
        var ext = (file.name || '').toLowerCase();
        var isVideo = (file.type || '').indexOf('video/') === 0 || /\.(mp4|mov|webm)$/.test(ext);
        var max = (isVideo ? 75 : 20) * 1024 * 1024;
        var allowed = /\.(jpe?g|png|webp|heic|heif|mp4|webm|mov)$/.test(ext) ||
                      /^(image\/(jpeg|png|webp|heic|heif)|video\/(mp4|webm|quicktime))$/.test(file.type || '');
        if (!allowed || file.size > max || file.size === 0) {
          display(!allowed ? 'Formato no admitido. Usa foto JPG/PNG/HEIC o video MP4/MOV/WebM.' :
                  file.size === 0 ? 'Este archivo está vacío. Elige otro.' :
                  'Archivo demasiado grande. Máximo ' + (isVideo ? '75 MB por video.' : '20 MB por foto.'), 'error');
          submit.disabled = true; return false;
        }
        display('✓ ' + file.name + ' · ' + (file.size / (1024 * 1024)).toFixed(1) + ' MB · Listo para enviar', 'ready');
        submit.disabled = false;
        return true;
      }
      input.addEventListener('change', check);
      form.addEventListener('submit', function (event) {
        if (sending || !check()) { event.preventDefault(); return; }
        sending = true;
        // Mantener el POST nativo; bloquear siguientes pulsaciones.
        window.setTimeout(function () { submit.disabled = true; }, 0);
      });
      window.addEventListener('pageshow', function () { sending = false; check(); });
    });

    // Los modales de guía ya guardan evidencias offline y tienen su propia
    // validación; solo añadimos una indicación de selección, sin intervenir POST.
    document.querySelectorAll('.tc-form-panel[data-form-panel]').forEach(function (panel) {
      var preview = panel.querySelector('[data-file-preview]');
      if (!preview) return;
      var hint = document.createElement('div');
      hint.className = 'tc-mobile-selected-hint';
      hint.setAttribute('role', 'status');
      hint.setAttribute('aria-live', 'polite');
      hint.textContent = 'Elige archivos y verifica los nombres antes de guardar.';
      preview.insertAdjacentElement('afterend', hint);
      panel.querySelectorAll('input[type="file"]').forEach(function (input) {
        input.addEventListener('change', function () {
          var files = Array.from(panel.querySelectorAll('input[type="file"]'))
            .reduce(function (all, current) { return all.concat(Array.from(current.files || [])); }, []);
          hint.textContent = files.length ?
            '✓ ' + files.length + ' archivo(s) seleccionado(s). Revisa los nombres y pulsa el botón Guardar.' :
            'Elige archivos y verifica los nombres antes de guardar.';
        });
      });
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', ready);
  else ready();
}());
