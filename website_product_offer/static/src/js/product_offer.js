/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import { rpc } from "@web/core/network/rpc";


publicWidget.registry.WebsiteProductOffer = publicWidget.Widget.extend({
    selector: ".o_wpo_offer_modal",
    events: {
        "submit .o_wpo_offer_form": "_onSubmit",
        "input .o_wpo_quantity": "_onAmountChanged",
        "change .o_wpo_quantity": "_onQuantityCommitted",
        "input .o_wpo_offered_price": "_onAmountChanged",
    },

    start() {
        console.log("WebsiteProductOffer inicializado en:", this.el);
        this.config = null;
        this._boundModalShow = this._onModalShow.bind(this);
        this._boundModalHidden = this._onModalHidden.bind(this);
        this.el.addEventListener("show.bs.modal", this._boundModalShow);
        this.el.addEventListener("hidden.bs.modal", this._boundModalHidden);
        return this._super(...arguments);
    },

    destroy() {
        this.el.removeEventListener("show.bs.modal", this._boundModalShow);
        this.el.removeEventListener("hidden.bs.modal", this._boundModalHidden);
        return this._super(...arguments);
    },

    _currentProductId() {
        const productInput = document.querySelector(
            ".js_main_product input[name='product_id']"
        );
        return Number(productInput?.value || this.el.querySelector(".o_wpo_product_id")?.value || 0);
    },

    async _onModalShow() {
        this._resetFeedback();
        const productId = this._currentProductId();
        this.el.querySelector(".o_wpo_product_id").value = productId;
        this._setLoading(true);
        try {
            const response = await rpc("/shop/offer/config", { product_id: productId });
            // if (!response.ok) {
            //     this._showError(response.error);
            //     if (response.login_required) {
            //         window.setTimeout(() => {
            //             window.location.href = `/web/login?redirect=${encodeURIComponent(window.location.pathname)}`;
            //         }, 900);
            //     }
            //     return;
            // }
            if (response.error) {
                this._showError(response.error);
                if (response.login_required) {
                    window.setTimeout(() => {
                        window.location.href = `/web/login?redirect=${encodeURIComponent(window.location.pathname)}`;
                    }, 900);
                }
                return;
            }
            this.config = response;
            this._applyConfig(response);
        } catch (error) {
            this._showError("No pudimos validar el producto. Inténtalo nuevamente.");
        } finally {
            this._setLoading(false);
        }
    },

    _applyConfig(config) {
        const quantity = this.el.querySelector(".o_wpo_quantity");
        const offeredPrice = this.el.querySelector(".o_wpo_offered_price");
        this.el.querySelector(".o_wpo_product_name").textContent = config.product_name;
        this.el.querySelector(".o_wpo_list_price").textContent = this._formatMoney(
            config.list_price
        );
        this.el.querySelector(".o_wpo_currency_symbol").textContent =
            config.currency_symbol || "$";

        quantity.min = config.min_qty;
        quantity.step = config.uom_rounding || 1;
        quantity.value = config.min_qty;
        if (config.max_qty) {
            quantity.max = config.max_qty;
        } else {
            quantity.removeAttribute("max");
        }

        offeredPrice.min = config.minimum_offer || 0.01;
        offeredPrice.value = "";
        const stockText = config.max_qty
            ? `Disponible para ofertar: hasta ${this._formatQuantity(config.max_qty)} ${config.uom_name}`
            : `Cantidad mínima: ${this._formatQuantity(config.min_qty)} ${config.uom_name}`;
        this.el.querySelector(".o_wpo_stock_text").textContent = stockText;
        this._onAmountChanged();
    },

    _formatMoney(value) {
        const currency = this.config?.currency || "USD";
        try {
            return new Intl.NumberFormat(document.documentElement.lang || "es-EC", {
                style: "currency",
                currency,
                minimumFractionDigits: 2,
            }).format(Number(value || 0));
        } catch (error) {
            return `${this.config?.currency_symbol || "$"}${Number(value || 0).toFixed(2)}`;
        }
    },

    _formatQuantity(value) {
        return new Intl.NumberFormat(document.documentElement.lang || "es-EC", {
            maximumFractionDigits: 2,
        }).format(Number(value || 0));
    },

    _onAmountChanged() {
        const quantity = Number(this.el.querySelector(".o_wpo_quantity")?.value || 0);
        const price = Number(this.el.querySelector(".o_wpo_offered_price")?.value || 0);
        this.el.querySelector(".o_wpo_offer_total").textContent =
            quantity > 0 && price > 0 ? this._formatMoney(quantity * price) : "—";
    },

    async _onQuantityCommitted() {
        const quantity = Number(this.el.querySelector(".o_wpo_quantity")?.value || 0);
        if (!quantity || !this.config) {
            return;
        }
        try {
            const response = await rpc("/shop/offer/config", {
                product_id: this._currentProductId(),
                quantity,
            });
            if (!response.ok) {
                this._showError(response.error);
                return;
            }
            this.config = response;
            this.el.querySelector(".o_wpo_list_price").textContent = this._formatMoney(
                response.list_price
            );
            this.el.querySelector(".o_wpo_offered_price").min = response.minimum_offer || 0.01;
            this._hideError();
            this._onAmountChanged();
        } catch (error) {
            this._showError("No pudimos actualizar el precio para esa cantidad.");
        }
    },

    async _onSubmit(event) {
        console.log("WebsiteProductOffer _onSubmit interceptado");
        event.preventDefault();
        const form = event.currentTarget;
        this._hideError();
        if (!form.checkValidity()) {
            form.classList.add("was-validated");
            return;
        }

        const email = form.querySelector("[name='contact_email']").value.trim();
        const phone = form.querySelector("[name='contact_phone']").value.trim();
        if (!email && !phone) {
            this._showError("Indica un correo o un teléfono para poder responderte.");
            return;
        }

        form.querySelector(".o_wpo_product_id").value = this._currentProductId();
        const payload = Object.fromEntries(new FormData(form).entries());
        this._setLoading(true);
        try {
            const response = await rpc("/shop/offer/submit", payload);
            if (!response.ok) {
                this._showError(response.error || "No pudimos registrar la oferta.");
                return;
            }
            this._showSuccess(response);
        } catch (error) {
            this._showError("Ocurrió un inconveniente al enviar la oferta. Inténtalo nuevamente.");
        } finally {
            this._setLoading(false);
        }
    },

    _setLoading(loading) {
        const button = this.el.querySelector(".o_wpo_submit");
        if (!button) {
            return;
        }
        button.disabled = loading;
        button.querySelector(".o_wpo_submit_label").classList.toggle("d-none", loading);
        button.querySelector(".o_wpo_submit_loading").classList.toggle("d-none", !loading);
    },

    _showError(message) {
        const alert = this.el.querySelector(".o_wpo_error");
        alert.textContent = message || "No pudimos procesar la solicitud.";
        alert.classList.remove("d-none");
        alert.scrollIntoView({ behavior: "smooth", block: "nearest" });
    },

    _hideError() {
        const alert = this.el.querySelector(".o_wpo_error");
        alert.textContent = "";
        alert.classList.add("d-none");
    },

    _showSuccess(response) {
        this.el.querySelector(".o_wpo_form_body").classList.add("d-none");
        this.el.querySelector(".o_wpo_form_footer").classList.add("d-none");
        this.el.querySelector(".o_wpo_success_message").textContent = response.message;
        this.el.querySelector(".o_wpo_reference").textContent = response.reference;
        this.el.querySelector(".o_wpo_portal_link").href = response.portal_url;
        this.el.querySelector(".o_wpo_success").classList.remove("d-none");
    },

    // _resetFeedback() {
    //     const form = this.el.querySelector(".o_wpo_offer_form");
    //     form.classList.remove("was-validated");
    //     this._hideError();
    //     this.el.querySelector(".o_wpo_form_body").classList.remove("d-none");
    //     this.el.querySelector(".o_wpo_form_footer").classList.remove("d-none");
    //     this.el.querySelector(".o_wpo_success").classList.add("d-none");
    // },

    _resetFeedback() {
        const form = this.el.querySelector(".o_wpo_offer_form");
        if (form) {
            form.classList.remove("was-validated");
        }
        this._hideError();

        const body = this.el.querySelector(".o_wpo_form_body");
        const footer = this.el.querySelector(".o_wpo_form_footer");
        const success = this.el.querySelector(".o_wpo_success");

        if (body) body.classList.remove("d-none");
        if (footer) footer.classList.remove("d-none");
        if (success) success.classList.add("d-none");
    },

    _onModalHidden() {
        this.config = null;
        this._resetFeedback();
    },
});
