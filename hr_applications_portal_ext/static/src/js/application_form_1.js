/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.MultistepFormCustom = publicWidget.registry.MultistepForm.extend({

    
    /**
     * Sobrescribimos la función _onNextClick
     */
    _onNextClick(ev) {
        ev.preventDefault();

        if (this._validateCurrentStep1()) {
            this.$('#form-step-1').addClass('d-none');
            this.$('#form-step-3').removeClass('d-none');

        }
    },

    /**
     * Sobrescribimos la función _onPrevClick para regresar de step 3 a step 1
     */
    _onPrevClick(ev) {
        ev.preventDefault();
        this.$('#form-step-3').addClass('d-none');
        this.$('#form-step-1').removeClass('d-none');
    },
});
