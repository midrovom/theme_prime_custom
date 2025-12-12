/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.SimpleAccordion = publicWidget.Widget.extend({
    selector: '.s_simple_accordion',

    start() {
        this._super(...arguments);

        this.el.querySelectorAll('.sa_header').forEach(header => {
            header.addEventListener('click', () => {
                const item = header.closest('.sa_item');
                const body = item.querySelector('.sa_body');

                const isOpen = item.classList.contains('open');

                // cerrar todos
                this.el.querySelectorAll('.sa_item').forEach(i => {
                    i.classList.remove('open');
                    i.querySelector('.sa_body').style.display = 'none';
                });

                if (!isOpen) {
                    item.classList.add('open');
                    body.style.display = 'block';
                }
            });
        });
    },
});
