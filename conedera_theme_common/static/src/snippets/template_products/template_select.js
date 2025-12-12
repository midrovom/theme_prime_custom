/** @odoo-module **/
document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll(".o_select_text_snippet .select-trigger")
        .forEach(select => {
            select.addEventListener("change", () => {
                const container = select.closest(".o_select_text_snippet");
                const body = container.querySelector(".desc-body");

                if (select.value === "show") {
                    body.classList.remove("d-none");
                } else {
                    body.classList.add("d-none");
                }
            });
        });
});
