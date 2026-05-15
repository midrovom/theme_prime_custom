/** @odoo-module **/

import publicWidget from '@web/legacy/js/public/public_widget';

publicWidget.registry.search = publicWidget.Widget.extend({
    selector: '.tp-search-input',
    start: function () {
        const input = this.$el[0];
        const frases = [];
        const spans = document.querySelectorAll('.tp-fake-placeholder');

        spans.forEach(span => frases.push(span.textContent.trim()));

        if (!frases.length) return;

        let index = 0;
        const duracion = parseInt(spans[0].style.getPropertyValue('--anim-duration')) * 1000 || 2000;

        const cambiarFrase = () => {
            input.setAttribute('placeholder', frases[index]);
            spans.forEach(span => span.classList.remove('active'));
            spans[index].classList.add('active');
            index = (index + 1) % frases.length;
        };

        cambiarFrase();
        setInterval(cambiarFrase, duracion);
    },
});
