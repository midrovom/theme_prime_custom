/** @odoo-module **/

import publicWidget from '@web/legacy/js/public/public_widget';

publicWidget.registry.PaymentForm = publicWidget.registry.PaymentForm.extend({
    _processRedirectFlow(providerCode, paymentOptionId, paymentMethodCode, processingValues) {
        if (providerCode !== "datafast") {
            return this._super(...arguments);
        }
        window.location.href = processingValues.redirect_form_html;
    },
});
