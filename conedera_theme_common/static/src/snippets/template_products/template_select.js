odoo.define('conedera_theme_common.description_toggle', function (require) {
    "use strict";

    document.addEventListener("DOMContentLoaded", function() {
        const select = document.getElementById("toggleDescription");
        const box = document.getElementById("descriptionBox");

        if (select && box) {
            select.addEventListener("change", function() {
                if (this.value === "show") {
                    box.style.display = "block";
                } else {
                    box.style.display = "none";
                }
            });
        }
    });
});
