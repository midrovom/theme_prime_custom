odoo.define('theme_prime.owl_carousel_style_12', function (require) {
    var publicWidget = require('web.public.widget');

    publicWidget.registry.OwlCarouselStyle12 = publicWidget.Widget.extend({
        selector: '.s_tp_hierarchical_category_style_12 .owl-carousel.droggol_product_slider',
        start: function () {
            if (this.$el && this.$el.owlCarousel) {
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
        }
    });
});
