odoo.define('theme_prime_custom.carousel_extend', function (require) {
    'use strict';

    const options = require('web_editor.snippets.options');

    options.registry.carousel.include({

        /**
         * Override cuando se agrega slide
         */
        async addSlide() {

            await this._super(...arguments);

            console.log('Slide agregado en Theme Prime');

        },

    });

});