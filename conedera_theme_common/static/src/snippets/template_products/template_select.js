/** @odoo-module **/

document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll(".o_desc_product_snippet .desc-header")
        .forEach(header => {
            header.addEventListener("click", () => {
                const container = header.closest(".o_desc_product_snippet");
                const body = container.querySelector(".desc-body");
                const icon = container.querySelector(".desc-icon");

                body.classList.toggle("d-none");
                icon.style.transform = body.classList.contains("d-none") ? "rotate(0deg)" : "rotate(180deg)";
            });
        });
});
