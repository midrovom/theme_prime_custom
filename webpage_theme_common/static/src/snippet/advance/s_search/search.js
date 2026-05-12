/** @odoo-module **/

odoo.define('@webpage_theme_common/snippet/advance/s_search/search', function (require) {

    "use strict";

    const publicWidget = require('web.public.widget');

    publicWidget.registry.SearchPlaceholderTyping = publicWidget.Widget.extend({
        selector: '.tp-search-wrapper',

        start: function () {
            const frases = this.el.querySelectorAll('.tp-fake-placeholder');

            if (!frases.length) {
                return this._super.apply(this, arguments);
            }

            let index = 0;

            const mostrarFrase = () => {

                frases.forEach(f => {
                    f.classList.remove('active');
                });

                const actual = frases[index];

                // reiniciar animación
                actual.style.animation = 'none';
                void actual.offsetWidth;
                actual.style.animation = '';

                actual.classList.add('active');

                const duration =
                    parseFloat(
                        getComputedStyle(actual)
                        .getPropertyValue('--anim-duration')
                    ) * 1000;

                setTimeout(() => {
                    index = (index + 1) % frases.length;
                    mostrarFrase();
                }, duration + 1000);
            };

            mostrarFrase();

            return this._super.apply(this, arguments);
        },
    });
});