import publicWidget from "@web/legacy/js/public/public_widget";
import { rpc } from "@web/core/network/rpc";

publicWidget.registry.OfferCartActions = publicWidget.Widget.extend({
    selector: ".o_wpo_cart",
    events: {
        "submit .o_wpo_submit_form": "_onSubmitFinal",
        "click .o_wpo_clear_cart": "_onClearCart",
        "click .o_wpo_remove_line": "_onRemoveLine",
    },

    async _onClearCart(ev) {
        ev.preventDefault();
        try {
            const response = await rpc("/shop/offer/clear", {});
            if (response.ok) {
                window.location.href = response.redirect;
            } else {
                window.alert(response.error || "No se pudo limpiar el carrito.");
            }
        } catch (error) {
            console.error(error);
            window.alert("Error al limpiar el carrito.");
        }
    },

    async _onRemoveLine(ev) {
        ev.preventDefault();
        const productId = ev.currentTarget.dataset.productId;
        try {
            const response = await rpc("/shop/offer/remove", { product_id: productId });
            if (response.ok) {
                window.location.href = response.redirect;
            } else {
                window.alert(response.error || "No se pudo eliminar el producto.");
            }
        } catch (error) {
            console.error(error);
            window.alert("Error al eliminar el producto.");
        }
    },

    async _onSubmitFinal(event) {
        event.preventDefault();
        event.stopPropagation();
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

    _showErrorBox(message) {
        const alertBox = this.el.querySelector(".o_wpo_error");
        if (alertBox) {
            alertBox.textContent = message || "No pudimos procesar la solicitud.";
            alertBox.classList.remove("d-none");
            alertBox.scrollIntoView({ behavior: "smooth", block: "nearest" });
        } else {
            window.alert(message);
        }
    },

    _hideErrorBox() {
        const alertBox = this.el.querySelector(".o_wpo_error");
        if (alertBox) {
            alertBox.textContent = "";
            alertBox.classList.add("d-none");
        }
    },

    _showSuccess(response) {
        this.el.querySelector(".o_wpo_success_message").textContent = response.message;
        this.el.querySelector(".o_wpo_reference").textContent = response.reference;
        window.location.href = response.portal_url;
}

});
