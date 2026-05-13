odoo.define('webpage_theme_common.search', function (require) {
    "use strict";

    const publicWidget = require('web.public.widget');

    publicWidget.registry.SearchPlaceholderTyping = publicWidget.Widget.extend({
        selector: '.tp-search-input',

        start: function () {
            const frases = document.querySelectorAll('.tp-fake-placeholder');

            if (!frases.length) {
                return this._super.apply(this, arguments);
            }

            let index = 0;

            function mostrarFrase() {

                // ocultar todas
                frases.forEach(f => {
                    f.classList.remove('active');
                });

                const actual = frases[index];

                // forzar reinicio animación
                void actual.offsetWidth;

                actual.classList.add('active');

                // duración desde CSS variable
                const duration =
                    parseFloat(
                        getComputedStyle(actual)
                        .getPropertyValue('--anim-duration')
                    ) * 1000;

                // siguiente frase
                setTimeout(() => {
                    index = (index + 1) % frases.length;
                    mostrarFrase();
                }, duration + 1000); // pausa extra
            }

            mostrarFrase();

            return this._super.apply(this, arguments);
        },
    });
});