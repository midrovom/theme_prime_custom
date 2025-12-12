/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.DescriptionAccordion = publicWidget.Widget.extend({
    selector: '.o_desc_product_snippet',

    events: {
        'click .desc-header': '_toggleAccordion',
    },

    _toggleAccordion: function (ev) {
        const container = ev.currentTarget.closest(".o_desc_product_snippet");
        const body = container.querySelector(".desc-body");
        const icon = container.querySelector(".desc-icon");

        body.classList.toggle("d-none");

        if (body.classList.contains("d-none")) {
            icon.style.transform = "rotate(0deg)";
        } else {
            icon.style.transform = "rotate(180deg)";
        }
    },
});
