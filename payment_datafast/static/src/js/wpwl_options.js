/** @odoo-module **/

const URL_IMAGE_DATAFAST = "https://www.datafast.com.ec/images/verified.png";

const wpwlOptions = {
    onReady() {

        const tipocredito = `
            <div class="wpwl-label wpwl-label-brand" style="display:inline-block; margin: 3px 0;">
                Tipo de crédito:
            </div>
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

        const cuotas = `
            <div class="wpwl-label wpwl-label-brand" style="display:inline-block; margin: 3px 0;">
                Diferidos:
            </div>
            <div class="wpwl-wrapper wpwl-wrapper-brand" style="display:inline-block; margin: 3px 0;">
                <select class="wpwl-control wpwl-control-brand" name="recurring.numberOfInstallments">
                    <option value="0">0</option>
                    <option value="3">3</option>
                    <option value="6">6</option>
                    <option value="9">9</option>
                </select>
            </div>`;

        const datafastImg = `
            <div style="margin: 25px 0; width:100%; display:inline-block;">
                <img src="${URL_IMAGE_DATAFAST}" style="display:block; margin:0 auto; width:100%;">
            </div>`;

        const guardarTarjeta = `
            <div class="wpwl-label wpwl-label-brand customLabel" style="display:inline-block;">
                Desea guardar de manera segura sus datos?
            </div>
            <div class="wpwl-wrapper wpwl-wrapper-brand customInput" style="display:inline-block;">
                <input class="wpwl-control wpwl-control-brand" type="checkbox" name="createRegistration" />
            </div>`;

        const $forms = $('form.wpwl-form-card, form.wpwl-form-registrations');

        $forms.find('.wpwl-button').before(tipocredito);
        $forms.find('.wpwl-button').before(cuotas);
        $('form.wpwl-form-card').find('.wpwl-button').before(datafastImg);
        $('form.wpwl-form-card').find('.wpwl-button').before(guardarTarjeta);
    },

    style: "card",
    locale: "es",

    labels: {
        cvv: "CVV",
        cardHolder: "Nombre (Igual que en la tarjeta)"
    },

    registrations: {
        requireCvv: true,
        hideInitialPaymentForms: true,
    },

    onBeforeSubmitCard() {
        const $holder = $(".wpwl-control-cardHolder");

        if (!$holder.val()) {
            $holder.addClass("wpwl-has-error");
            if (!$(".wpwl-hint-cardHolderError").length) {
                $holder.after("<div class='wpwl-hint-cardHolderError'>Campo requerido</div>");
            }
            $(".wpwl-button-pay").addClass("wpwl-button-error").attr("disabled", true);
            return false;
        }
        return true;
    }
};

// Extender configuración global de DataFast
if (window.wpwlOptions) {
    Object.assign(window.wpwlOptions, wpwlOptions);
} else {
    window.wpwlOptions = wpwlOptions;
}
