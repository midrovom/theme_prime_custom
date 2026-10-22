/* Transcash: seleccionar todas las guías que coinciden con transporte, chofer y destino.
   No se transmiten IDs adicionales, ni se omite la validación del servidor. */
(function () {
    'use strict';
    var MAX_GUIAS = 100; // límite original del controller de Logística

    function inicializar() {
        var form = document.querySelector('form[data-tc-guide-bulk-form="1"]');
        if (!form) return;
        var master = form.querySelector('input[data-tc-select-all="1"]');
        var contador = form.querySelector('[data-tc-select-all-count="1"]');
        // La PWA v2.6 no autoriza reasignaciones; el servidor impone el filtro.
        if (!master) return;
        var guias = Array.prototype.slice.call(
            form.querySelectorAll('input[type="checkbox"][name="guias"]')
        );

        function esElegible(chk) {
            return !chk.disabled;
        }
        function refrescar() {
            var elegibles = guias.filter(esElegible);
            var marcadas = guias.filter(function (c) { return c.checked; }).length;
            master.checked = elegibles.length > 0 &&
                elegibles.every(function (c) { return c.checked; }) && marcadas <= MAX_GUIAS;
            master.indeterminate = marcadas > 0 && !master.checked;
            master.disabled = elegibles.length === 0;
            if (contador) {
                contador.textContent = marcadas + ' guía(s) seleccionada(s) · ' +
                    elegibles.length + ' guía(s) del filtro visible · límite ' +
                    MAX_GUIAS + ' por embarque.';
            }
        }
        function marcarTodas() {
            if (!master.checked) {
                guias.forEach(function (c) { c.checked = false; });
                refrescar();
                return;
            }
            // Mantener primero las selecciones previas para evitar sorpresas.
            var orden = guias.filter(function (c) { return c.checked && esElegible(c); })
                .concat(guias.filter(function (c) { return !c.checked && esElegible(c); }));
            guias.forEach(function (c) { c.checked = false; });
            orden.slice(0, MAX_GUIAS).forEach(function (c) { c.checked = true; });
            refrescar();
            if (contador && orden.length > MAX_GUIAS) {
                contador.textContent += ' Hay más guías visibles; seleccione otro lote para el siguiente viaje.';
            }
        }
        master.addEventListener('change', marcarTodas);
        guias.forEach(function (c) {
            c.addEventListener('change', function () {
                if (guias.filter(function (g) { return g.checked; }).length > MAX_GUIAS) {
                    c.checked = false;
                    if (contador) contador.textContent = 'Solo puede seleccionar hasta 100 guías por ruta.';
                } else {
                    refrescar();
                }
            });
        });
        refrescar();
    }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', inicializar);
    } else {
        inicializar();
    }
}());
