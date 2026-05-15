/** @odoo-module **/

import publicWidget from '@web/legacy/js/public/public_widget';

publicWidget.registry.searchPlaceholderRotator = publicWidget.Widget.extend({
    selector: '.o_searchbar_form',

    start: function () {

        // Buscar únicamente los spans dentro de este buscador
        const spans = this.el.querySelectorAll('.tp-fake-placeholder');

        if (!spans.length) {
            return;
        }

        let index = 0;

        // Leer duración desde CSS variable
        const duration =
            parseFloat(
                getComputedStyle(spans[0])
                    .getPropertyValue('--anim-duration')
            ) * 1000 || 2000;

        // Ocultar todos
        spans.forEach(span => {
            span.classList.remove('active');
        });

        // Mostrar primero
        spans[0].classList.add('active');

        setInterval(() => {

            // ocultar actual
            spans[index].classList.remove('active');

            // siguiente
            index = (index + 1) % spans.length;

            // mostrar siguiente
            spans[index].classList.add('active');

        }, duration);

        return this._super(...arguments);
    },
});