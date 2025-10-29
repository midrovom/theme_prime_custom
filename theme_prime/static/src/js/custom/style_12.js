odoo.define('theme_prime.owl_carousel_init', function (require) {
    var publicWidget = require('web.public.widget');

    publicWidget.registry.OwlCarouselInit = publicWidget.Widget.extend({
        selector: '.owl-carousel.droggol_product_slider',
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
