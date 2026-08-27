/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import { rpc } from "@web/core/network/rpc";

publicWidget.registry.OfferCartActions = publicWidget.Widget.extend({
    selector: ".o_wpo_cart",
    events: {
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
                alert(response.error || "No se pudo limpiar el carrito.");
            }
        } catch (error) {
            console.error(error);
            alert("Error al limpiar el carrito.");
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
                alert(response.error || "No se pudo eliminar el producto.");
            }
        } catch (error) {
            console.error(error);
            alert("Error al eliminar el producto.");
        }
    },
});
