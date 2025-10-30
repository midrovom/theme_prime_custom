/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.TpUiComponent.include({
    async _renderContent() {
        // Render original
        await this._super(...arguments);

        // Solo si el estilo es el 12
        if (this.options.style === 's_tp_hierarchical_category_style_12') {
            const $slider = this.$('.js_style12_slider');
            if ($slider.length && $slider.find('.item').length) {
                $slider.owlCarousel({
                    items: 8,
                    margin: 10,
                    loop: true,
                    nav: true,
                    dots: false,
                    responsive: {
                        0: { items: 2 },
                        576: { items: 4 },
                        768: { items: 6 },
                        992: { items: 8 }
                    }
                });
            }
        }
    },
});
