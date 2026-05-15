/** @odoo-module **/

import publicWidget from '@web/legacy/js/public/public_widget';

publicWidget.registry.search = publicWidget.Widget.extend({
    selector: '.tp-search-input',
    start: function () {
        const input = this.$el[0];
        const spans = document.querySelectorAll('.tp-fake-placeholder');
        if (!spans.length) return;

        let index = 0;
        const duracion = parseFloat(spans[0].style.getPropertyValue('--anim-duration')) * 1000 || 2000;

        const cambiarFrase = () => {
            // Cambiar placeholder real
            input.setAttribute('placeholder', spans[index].textContent.trim());

            // Resetear todos los spans
            spans.forEach(span => {
                span.classList.remove('active');
                span.style.animation = 'none';
                span.offsetHeight; // fuerza reflow
                span.style.animation = '';
            });

            // Activar el span actual con su efecto
            spans[index].classList.add('active');

            index = (index + 1) % spans.length;
        };

        cambiarFrase();
        setInterval(cambiarFrase, duracion);
    },
});

