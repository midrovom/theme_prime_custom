odoo.define("payment_datafast.payment_form", function (require) {
    'use strict';

    const checkoutForm = require('payment.checkout_form');
    const manageForm = require('payment.manage_form');

    const datafastMixin = {
        _processRedirectPayment: function (code, providerId, processingValues) {
            if (code !== "datafast") {
                return this._super(...arguments);
            }

            if (processingValues.redirect_form_html) {
                const div = document.createElement('div');
                div.innerHTML = processingValues.redirect_form_html;
                const form = div.querySelector('form');

                if (form) {
                    document.body.appendChild(form);
                    form.submit();
                } else {
                    console.error("DataFast: redirect form not found");
                }
            }
        },
    };

    checkoutForm.include(datafastMixin);
    manageForm.include(datafastMixin);
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
