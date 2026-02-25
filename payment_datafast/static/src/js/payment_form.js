/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { CheckoutForm } from "@payment/js/checkout/checkout_form";
import { ManageForm } from "@payment/js/manage/manage_form";

patch(CheckoutForm.prototype, {
    _processRedirectPayment(code, providerId, processingValues) {
        if (code !== "datafast") {
            return super._processRedirectPayment(...arguments);
        }
        window.location.href = processingValues.redirect_form_html;
    },
});

patch(ManageForm.prototype, {
    _processRedirectPayment(code, providerId, processingValues) {
        if (code !== "datafast") {
            return super._processRedirectPayment(...arguments);
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
