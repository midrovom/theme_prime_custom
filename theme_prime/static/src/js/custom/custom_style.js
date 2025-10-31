odoo.define('theme_prime.carousel_init', function (require) {
    'use strict';

    var publicWidget = require('web.public.widget');

    publicWidget.registry.CarouselInit = publicWidget.Widget.extend({
        selector: '.owl-carousel.droggol_product_slider',
        start: function () {
            this.$el.owlCarousel({
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
            return this._super.apply(this, arguments);
        },
    });
});
