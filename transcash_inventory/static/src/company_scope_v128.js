/* The parent Odoo OWL action supplies the selected company, never the user default. */
(() => {
  'use strict';
  const id = new URLSearchParams(window.location.search).get('company_id');
  if (!id || !/^\d+$/.test(id)) return;
  const nativeFetch = window.fetch.bind(window);
  window.fetch = function(input, options) {
    const original = input instanceof Request ? input.url : String(input);
    const url = new URL(original, window.location.href);
    if (url.origin === window.location.origin &&
        url.pathname.startsWith('/transcash_inventory/') &&
        !url.searchParams.has('company_id')) {
      url.searchParams.set('company_id', id);
      if (input instanceof Request) input = new Request(url.href, input);
      else input = url.href;
    }
    return nativeFetch(input, options).then(response => {
      const actual = response.headers.get('X-Transcash-Company-ID');
      if (actual && actual !== id && response.ok) {
        throw new Error('La empresa activa cambió; vuelva a abrir el panel.');
      }
      return response;
    });
  };
})();
