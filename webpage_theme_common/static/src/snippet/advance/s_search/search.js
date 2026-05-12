odoo.define('webpage_theme_common.search_placeholder', function (require) {
    "use strict";

    const publicWidget = require('web.public.widget');

    publicWidget.registry.SearchPlaceholderTyping = publicWidget.Widget.extend({
        selector: '.tp-search-input',
        start: function () {
            const frases = document.querySelectorAll(".tp-fake-placeholder.typing");
            if (!frases.length) {
                return;
            }
            let index = 0;

            // Duración en segundos desde el CSS variable
            const duracion = parseInt(frases[0].style.getPropertyValue("--anim-duration") || 5, 10) * 1000;

            function mostrarFrase() {
                // Ocultar todas
                frases.forEach(f => f.style.display = "none");

                // Mostrar solo la actual
                frases[index].style.display = "inline-block";

                // Reiniciar animación
                frases[index].classList.remove("typing");
                void frases[index].offsetWidth; // forzar reflow
                frases[index].classList.add("typing");

                // Pasar a la siguiente
                index = (index + 1) % frases.length;
            }

            // Mostrar la primera inmediatamente
            mostrarFrase();

            // Cambiar cada X segundos
            setInterval(mostrarFrase, duracion);
        },
    });
});
