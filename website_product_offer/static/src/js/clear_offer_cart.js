/** Manejar limpiar todo el carrito */
async function _onClearCart(ev) {
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
}

/** Manejar eliminar una línea específica */
async function _onRemoveLine(ev) {
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
}

/** Registrar eventos al cargar la página */
document.addEventListener("DOMContentLoaded", () => {
    // Botón limpiar carrito
    const clearBtn = document.querySelector(".o_wpo_clear_cart");
    if (clearBtn) {
        clearBtn.addEventListener("click", _onClearCart);
    }

    // Botones eliminar línea
    document.querySelectorAll(".o_wpo_remove_line").forEach(btn => {
        btn.addEventListener("click", _onRemoveLine);
    });
});
