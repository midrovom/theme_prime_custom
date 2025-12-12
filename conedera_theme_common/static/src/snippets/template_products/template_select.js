/** @odoo-module **/

import publicWidget from 'web.public.widget'; // path común
// Si tu versión no reconoce el import, puedes probar: import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.DescriptionAccordion = publicWidget.Widget.extend({
    selector: '.o_desc_product_snippet',
    events: {
        'click .desc-header': '_onToggle',
    },

    start: function () {
        this.$el.removeClass('open');
        this._setCollapsed(true);
        return this._super.apply(this, arguments);
    },

    _onToggle: function (ev) {
        ev.preventDefault();
        const $container = this.$el;
        const isOpen = $container.hasClass('open');

        // alternar clase open
        $container.toggleClass('open', !isOpen);

        // Forzar recalculo si necesitas (no estrictamente obligatorio)
        this._setCollapsed(isOpen);
    },
});
