/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { CheckoutForm } from "@payment/js/checkout_form";
import { ManageForm } from "@payment/js/manage_form";

const datafastMixin = {
    _processRedirectPayment(code, providerId, processingValues) {
        if (code !== "datafast") {
            return super._processRedirectPayment(...arguments);
        }

        window.location.href = processingValues.redirect_form_html;
    },
};

patch(CheckoutForm.prototype, "payment_datafast_checkout_patch", datafastMixin);
patch(ManageForm.prototype, "payment_datafast_manage_patch", datafastMixin);


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
