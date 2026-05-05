/** JS para agregar dinámicamente slides a un carousel en Odoo **/
odoo.define('theme_prime_custom.carousel_extend', function (require) {
    "use strict";

    const publicWidget = require('web.public.widget');

    publicWidget.registry.CarouselExtend = publicWidget.Widget.extend({
        selector: '.tp-custom-carousel',   
        events: {
            'click .add-slide-btn': '_onAddSlide', 
        },

        /**
         * Agregar un nuevo slide dinámicamente
         */
        _onAddSlide: function (ev) {
            ev.preventDefault();
            const $carousel = this.$el;
            const $inner = $carousel.find('.carousel-inner');
            const $indicators = $carousel.find('.carousel-indicators');

            // contar cuántos slides hay
            const index = $inner.find('.carousel-item').length;

            // crear nuevo slide
            const $newSlide = $(`
                <div class="carousel-item p-0" data-name="Slide">
                    <div class="container-fluid px-0">
                        <div class="row content g-0 align-items-center">
                            <div class="jumbotron rounded px-4 col-lg-5 pt32 pb32">
                                <h3>Nuevo Slide ${index+1}</h3>
                                <h2 class="display-4 fw-bold">Título dinámico</h2>
                                <p class="lead">Este slide fue agregado con JS.</p>
                                <a href="/shop" class="btn btn-primary mt-2">Ver más</a>
                            </div>
                            <div class="col-lg-6">
                                <img class="img img-fluid" src="/web/image/theme_prime.s_cover_3_1" alt="Nuevo Slide"/>
                            </div>
                        </div>
                    </div>
                </div>
            `);

            // añadir al carousel
            $inner.append($newSlide);

            // añadir indicador
            const $newIndicator = $(`<button type="button" data-bs-target="#${$carousel.attr('id')}" data-bs-slide-to="${index}"></button>`);
            $indicators.append($newIndicator);
        },
    });
});
