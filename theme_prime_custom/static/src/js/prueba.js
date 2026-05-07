odoo.define('theme_prime_custom.carousel_options', function (require) {
    'use strict';

    const options = require('web_editor.snippets.options');

    options.registry.tp_custom_carousel = options.Class.extend({

        /**
         * Agregar Slide
         */
        async addSlide(previewMode, widgetValue, params) {

            const $carousel = this.$target;
            const $inner = $carousel.find('.carousel-inner');
            const $indicators = $carousel.find('.carousel-indicators');

            const index = $inner.find('.carousel-item').length;

            const slide = `
                <div class="carousel-item p-0"
                     data-name="Slide">

                    <div class="container-fluid px-0">

                        <div class="row g-0 align-items-center"
                             style="min-height:300px;">

                            <div class="col-12 col-lg-6 p-4">

                                <div class="jumbotron rounded border p-4">

                                    <h3>
                                        Nuevo Slide ${index + 1}
                                    </h3>

                                    <h2 class="display-4 fw-bold">
                                        Título dinámico
                                    </h2>

                                    <p class="lead">
                                        Este slide fue agregado dinámicamente.
                                    </p>

                                    <a href="/shop"
                                       class="btn btn-primary mt-2">
                                        Ver más
                                    </a>

                                </div>

                            </div>

                            <div class="col-12 col-lg-6 text-center">

                                <img class="img-fluid"
                                     style="max-height:300px; object-fit:contain;"
                                     src="/web/image/theme_prime.s_cover_3_1"/>

                            </div>

                        </div>

                    </div>

                </div>
            `;

            $inner.append(slide);

            $indicators.append(`
                <button type="button"
                        data-bs-target="#${$carousel.attr('id')}"
                        data-bs-slide-to="${index}">
                </button>
            `);
        },
    });
});