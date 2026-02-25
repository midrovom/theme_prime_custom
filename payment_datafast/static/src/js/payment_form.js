odoo.define("payment_datafast.payment_form", function (require) {
    'use strict';

    const { patch } = require('web.utils');
    const CheckoutForm = require('payment.checkout_form');
    const ManageForm = require('payment.manage_form');

    const datafastMixin = {
        _processRedirectPayment(code, providerId, processingValues) {
            if (code !== "datafast") {
                return this._super(...arguments);
            }
            window.location.href = processingValues.redirect_form_html;
        },
    };

    patch(CheckoutForm.prototype, 'payment_datafast', datafastMixin);
    patch(ManageForm.prototype, 'payment_datafast', datafastMixin);
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
