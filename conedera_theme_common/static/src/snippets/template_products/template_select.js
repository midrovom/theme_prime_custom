/** @odoo-module **/

document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll(".o_desc_product_snippet .desc-header")
        .forEach(function (header) {
            
            header.addEventListener("click", function () {
                const container = header.closest(".o_desc_product_snippet");
                const body = container.querySelector(".desc-body");
                const icon = container.querySelector(".desc-icon");

                body.classList.toggle("d-none");

                if (body.classList.contains("d-none")) {
                    icon.style.transform = "rotate(0deg)";
                } else {
                    icon.style.transform = "rotate(180deg)";
                }
            });
        });
});
