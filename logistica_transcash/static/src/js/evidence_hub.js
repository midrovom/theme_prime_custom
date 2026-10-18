/* V5.25: visor móvil sin dialog/showModal (evita documento inert en iOS/WebView). */
(function () {
  'use strict';
  var overlay = null;
  var previousFocus = null;
  var oldOverflow = '';
  function close() {
    if (!overlay) return;
    var current = overlay;
    overlay = null;  // Guard against repeated close/cancel events.
    var video = current.querySelector('video');
    if (video) {
      try { video.pause(); video.removeAttribute('src'); video.load(); } catch (ignored) {}
    }
    var img = current.querySelector('img');
    if (img) img.removeAttribute('src');
    current.remove();
    document.body.classList.remove('tc-hub-modal-open');
    document.body.style.overflow = oldOverflow;
    if (previousFocus && document.contains(previousFocus)) previousFocus.focus();
    previousFocus = null;
  }
  function open(link) {
    close();
    var url = link.getAttribute('href');
    if (!url || url.charAt(0) === '#') return;
    previousFocus = link;
    oldOverflow = document.body.style.overflow;
    var view = document.createElement('div');
    view.id = 'tc-evidence-lightbox';
    view.className = 'tc-hub-lightbox tc-hub-overlay';
    view.setAttribute('role', 'dialog');
    view.setAttribute('aria-modal', 'true');
    view.setAttribute('aria-label', 'Visor de evidencias');
    var head = document.createElement('div'); head.className = 'tc-hub-modal-head';
    var title = document.createElement('strong'); title.textContent = link.getAttribute('aria-label') || 'Evidencia';
    var exit = document.createElement('button'); exit.type = 'button';
    exit.className = 'tc-hub-modal-close'; exit.textContent = '✕ Cerrar';
    exit.setAttribute('aria-label', 'Cerrar foto o video y volver al viaje');
    exit.addEventListener('click', close);
    head.appendChild(title); head.appendChild(exit);
    var slot = document.createElement('div'); slot.className = 'tc-hub-modal-media';
    var isVideo = link.getAttribute('data-hub-kind') === 'video';
    var media = document.createElement(isVideo ? 'video' : 'img');
    if (isVideo) {
      media.controls = true; media.playsInline = true; media.preload = 'metadata';
      media.setAttribute('aria-label', 'Video de evidencia');
    } else {
      media.alt = title.textContent; media.decoding = 'async';
    }
    // Do not play or download the full video before the user requests it.
    media.src = url;
    slot.appendChild(media); view.appendChild(head); view.appendChild(slot);
    view.addEventListener('click', function (event) { if (event.target === view || event.target === slot) close(); });
    overlay = view;
    document.body.appendChild(view);
    document.body.classList.add('tc-hub-modal-open');
    document.body.style.overflow = 'hidden';
    exit.focus();
  }
  document.addEventListener('click', function (event) {
    var link = event.target.closest && event.target.closest('[data-tc-hub-open]');
    if (!link) return;
    event.preventDefault(); open(link);
  });
  document.addEventListener('keydown', function (event) {
    if (!overlay) return;
    if (event.key === 'Escape' || event.key === 'Backspace') {
      event.preventDefault(); close();
    }
    // Keep keyboard navigation inside the evidence panel.
    if (event.key === 'Tab') {
      var focusables = overlay.querySelectorAll('button, video[controls]');
      if (!focusables.length) return;
      var first = focusables[0], last = focusables[focusables.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    }
  });
  window.addEventListener('pagehide', close);
})();
