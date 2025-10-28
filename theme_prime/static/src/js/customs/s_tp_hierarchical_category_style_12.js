odoo.define('theme_prime_image.category_carousel', function (require) {
    'use strict';

    var publicWidget = require('web.public.widget');

    publicWidget.registry.CategoryCarousel = publicWidget.Widget.extend({
        selector: '.owl-carousel.droggol_product_slider',
        start: function () {
            this.$el.owlCarousel({
                items: 8,
                margin: 10,
                loop: true,
                nav: true,
                dots: false,
                navText: [
                    '<span class="carousel-nav-icon"><i class="fa fa-chevron-left"></i></span>',
                    '<span class="carousel-nav-icon"><i class="fa fa-chevron-right"></i></span>'
                ],
                responsive: {
                    0: { items: 4 },
                    576: { items: 4 },
                    768: { items: 6 },
                    992: { items: 8 }
                }
            });
        },
    });
});
