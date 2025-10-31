odoo.define('theme_prime.category_style_6', function (require) {
    'use strict';

    var publicWidget = require('web.public.widget');

    publicWidget.registry.CategoryStyle6Carousel = publicWidget.Widget.extend({
        selector: '.owl-carousel.droggol_product_slider',
        start: function () {
            this.$el.owlCarousel({
                items: 4,
                loop: true,
                margin: 10,
                nav: true,
                dots: false,
                autoplay: true,
                responsive: {
                    0: { items: 1 },
                    768: { items: 2 },
                    992: { items: 3 },
                    1200: { items: 4 }
                }
            });
        },
    });
});
