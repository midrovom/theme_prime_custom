/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { SearchBar } from "@web/search/search_bar/search_bar";

patch(SearchBar.prototype, {
    setup() {
        super.setup(...arguments);

        this._specificDateObserver = null;

        setTimeout(() => {
            this._initSpecificDateFilter();
        }, 500);
    },

    _initSpecificDateFilter() {
        const root = this.el;

        if (!root) {
            return;
        }

        // Evitar inicializar varias veces
        if (this._specificDateObserver) {
            this._specificDateObserver.disconnect();
        }

        this._specificDateObserver = new MutationObserver(() => {
            this._attachSpecificDateHandler();
        });

        this._specificDateObserver.observe(root, {
            childList: true,
            subtree: true,
        });

        this._attachSpecificDateHandler();
    },

    _attachSpecificDateHandler() {
        const elements = this.el.querySelectorAll(
            '[data-name="generated_specific_date"]'
        );

        elements.forEach((element) => {
            if (element.dataset.specificDateHandler === "true") {
                return;
            }

            element.dataset.specificDateHandler = "true";

            element.addEventListener("click", (event) => {
                event.preventDefault();
                event.stopPropagation();

                this._openSpecificDateCalendar();
            });
        });
    },

    _openSpecificDateCalendar() {
        const input = document.createElement("input");

        input.type = "date";

        input.style.position = "fixed";
        input.style.left = "50%";
        input.style.top = "50%";
        input.style.width = "1px";
        input.style.height = "1px";
        input.style.opacity = "0";
        input.style.zIndex = "99999";

        document.body.appendChild(input);

        input.addEventListener("change", (event) => {
            const selectedDate = event.target.value;

            if (selectedDate) {
                this._applySpecificDate(selectedDate);
            }

            input.remove();
        });

        input.addEventListener("blur", () => {
            setTimeout(() => {
                if (document.body.contains(input)) {
                    input.remove();
                }
            }, 300);
        });

        if (input.showPicker) {
            input.showPicker();
        } else {
            input.click();
        }
    },

    _applySpecificDate(selectedDate) {
        const date = new Date(`${selectedDate}T00:00:00`);

        const nextDate = new Date(date);
        nextDate.setDate(nextDate.getDate() + 1);

        const formatDate = (value) => {
            const year = value.getFullYear();
            const month = String(value.getMonth() + 1).padStart(2, "0");
            const day = String(value.getDate()).padStart(2, "0");

            return `${year}-${month}-${day}`;
        };

        const start = `${formatDate(date)} 00:00:00`;
        const end = `${formatDate(nextDate)} 00:00:00`;

        const domain = [
            ["generated_at", ">=", start],
            ["generated_at", "<", end],
        ];

        console.log(
            "Fecha específica seleccionada:",
            selectedDate
        );

        console.log(
            "Dominio aplicado:",
            domain
        );

        this.env.searchModel.setDomain(domain);
    },
});