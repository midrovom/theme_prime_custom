odoo.define('theme_prime.category_carousel', function (require) {
    "use strict";

    var publicWidget = require('web.public.widget');

    publicWidget.registry.CategoryCarousel = publicWidget.Widget.extend({
        selector: '.owl-carousel.droggol_product_slider',
        start: function () {
            if (this.$el.data('owl.carousel')) {
                this.$el.trigger('destroy.owl.carousel');
                this.$el.find('.owl-stage-outer').children().unwrap();
            }
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
        }
    });
});
