/** @odoo-module **/

const URL_IMAGE_DATAFAST = "https://www.datafast.com.ec/images/verified.png";

const wpwlOptions = {
    onReady() {
        // Selector de tipo de crédito
        const tipocredito = `
            <div class="wpwl-label wpwl-label-brand" style="display:inline-block; margin: 3px 0;">Tipo de crédito:</div>
            <div class="wpwl-wrapper wpwl-wrapper-brand" style="display:inline-block; margin: 3px 0; padding-right: 30px;">
                <select class="wpwl-control wpwl-control-brand" name="customParameters[SHOPPER_TIPOCREDITO]">
                    <option value="00">Corriente</option>
                    <option value="01">Dif Corriente</option>
                    <option value="02">Dif con int</option>
                    <option value="03">Dif sin int</option>
                    <option value="07">Dif con int + Meses gracia</option>
                    <option value="09">Dif sin int + Meses gracia</option>
                    <option value="21">Dif plus cuotas</option>
                    <option value="22">Dif plus</option>
                </select>
            </div>`;

        // Selector de cuotas
        const numberOfInstallmentsHtml = `
            <div class="wpwl-label wpwl-label-brand" style="display:inline-block; margin: 3px 0;">Diferidos:</div>
            <div class="wpwl-wrapper wpwl-wrapper-brand" style="display:inline-block; margin: 3px 0;">
                <select class="wpwl-control wpwl-control-brand" name="recurring.numberOfInstallments">
                    <option value="0">0</option>
                    <option value="3">3</option>
                    <option value="6">6</option>
                    <option value="9">9</option>
                </select>
            </div>`;

        // Imagen DataFast
        const datafast = `<div style="margin: 25px 0; width:100%; display:inline-block;">
            <img src="${URL_IMAGE_DATAFAST}" style="display:block; margin:0 auto; width:100%;">
        </div>`;

        // Guardar datos de pago
        const createRegistrationHtml = `
            <div class="wpwl-label wpwl-label-brand customLabel" style="display:inline-block;">Desea guardar de manera segura sus datos?</div>
            <div class="wpwl-wrapper wpwl-wrapper-brand customInput" style="display:inline-block;">
                <input class="wpwl-control wpwl-control-brand" type="checkbox" name="createRegistration" />
            </div>`;

        // Función auxiliar para insertar antes del botón
        function insertBeforeButton(formSelector, html) {
            const form = document.querySelector(formSelector);
            if (form) {
                const button = form.querySelector('.wpwl-button');
                if (button) {
                    button.insertAdjacentHTML('beforebegin', html);
                }
            }
        }

        // Insertar en los formularios
        insertBeforeButton('form.wpwl-form-card', tipocredito);
        insertBeforeButton('form.wpwl-form-registrations', tipocredito);

        insertBeforeButton('form.wpwl-form-card', numberOfInstallmentsHtml);
        insertBeforeButton('form.wpwl-form-registrations', numberOfInstallmentsHtml);

        insertBeforeButton('form.wpwl-form-card', datafast);
        insertBeforeButton('form.wpwl-form-card', createRegistrationHtml);
    },

    style: "card",
    locale: "es",
    labels: { cvv: "CVV", cardHolder: "Nombre (Igual que en la tarjeta)" },
    registrations: {
        requireCvv: true,
        hideInitialPaymentForms: true,
    },

    onBeforeSubmitCard() {
        const cardHolderInput = document.querySelector(".wpwl-control-cardHolder");
        if (cardHolderInput && cardHolderInput.value === "") {
            cardHolderInput.classList.add("wpwl-has-error");
            cardHolderInput.insertAdjacentHTML("afterend", "<div class='wpwl-hint-cardHolderError'>Campo requerido</div>");
            const payButton = document.querySelector(".wpwl-button-pay");
            if (payButton) {
                payButton.classList.add("wpwl-button-error");
                payButton.setAttribute("disabled", "disabled");
            }
            return false;
        }
        return true;
    },
};

// Extender las opciones globales del widget
if (typeof window.wpwlOptions !== 'undefined') {
    Object.assign(window.wpwlOptions, wpwlOptions);
} else {
    window.wpwlOptions = wpwlOptions;
}
