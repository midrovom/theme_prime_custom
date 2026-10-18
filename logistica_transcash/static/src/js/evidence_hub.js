/* Transcash V5.20 - Visor accesible, sin permisos ni datos guardados en el navegador. */
(function () {
  'use strict';
  function closeHub(dialog) {
    if (!dialog) return;
    var player = dialog.querySelector('video');
    if (player) { player.pause(); player.removeAttribute('src'); player.load(); }
    if (dialog.open && typeof dialog.close === 'function') dialog.close();
    else { dialog.removeAttribute('open'); dialog.style.display = 'none'; }
    document.body.classList.remove('tc-hub-modal-open');
  }
  function openHub(anchor) {
    var modal = document.querySelector('#tc-evidence-lightbox');
    if (!modal) {
      modal = document.createElement('dialog');
      modal.id = 'tc-evidence-lightbox';
      modal.className = 'tc-hub-lightbox';
      modal.innerHTML = '<div class="tc-hub-modal-head"><strong>Transcash · Evidencia</strong><button type="button" class="tc-hub-modal-close" aria-label="Cerrar evidencia">✕ Cerrar</button></div><div class="tc-hub-modal-media"></div>';
      document.body.appendChild(modal);
      modal.querySelector('button').addEventListener('click', function () { closeHub(modal); });
      modal.addEventListener('click', function (event) { if (event.target === modal) closeHub(modal); });
      modal.addEventListener('close', function () { closeHub(modal); });
    }
    var mediaSlot = modal.querySelector('.tc-hub-modal-media');
    mediaSlot.replaceChildren();
    var type = anchor.getAttribute('data-hub-kind');
    var element = document.createElement(type === 'video' ? 'video' : 'img');
    element.src = anchor.getAttribute('href');
    element.setAttribute('aria-label', anchor.getAttribute('aria-label') || 'Evidencia');
    if (type === 'video') { element.controls = true; element.playsInline = true; element.preload = 'metadata'; }
    else { element.alt = anchor.getAttribute('aria-label') || 'Evidencia'; }
    mediaSlot.appendChild(element);
    if (typeof modal.showModal === 'function') modal.showModal();
    else { modal.style.display = 'grid'; modal.setAttribute('open', ''); }
    document.body.classList.add('tc-hub-modal-open');
  }
  document.addEventListener('click', function (event) {
    var anchor = event.target.closest('[data-tc-hub-open]');
    if (!anchor) return;
    event.preventDefault();
    openHub(anchor);
  });
  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape') closeHub(document.getElementById('tc-evidence-lightbox'));
  });
})();
