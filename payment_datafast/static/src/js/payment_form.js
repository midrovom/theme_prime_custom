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


// odoo.define("payment_datafast.payment_form", require => {
//     'use strict';

//     const checkoutForm = require('payment.checkout_form');
//     const manageForm = require('payment.manage_form');

//     const datafastMixin = {
//         _processRedirectPayment: function (code, providerId, processingValues) {
//             if (code !== "datafast") {
//                 return this._super(...arguments);
//             }
//             window.location.href = processingValues.redirect_form_html;
//         },

//     }

//     checkoutForm.include(datafastMixin);
//     manageForm.include(datafastMixin);
// });
