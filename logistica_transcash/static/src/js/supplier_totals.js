/* Totales de selección en la PWA del proveedor; servidor valida montos nuevamente. */
(function () {
    "use strict";
    function boot() {
        const forms = document.querySelectorAll(".tc-supplier-select-form");
        forms.forEach((form) => {
        const checkboxes = Array.from(form.querySelectorAll('input[name="embarques"]'));
        const total = form.querySelector(".tc-supplier-total");
        const count = form.querySelector(".tc-supplier-count");
        function update() {
            const selected = checkboxes.filter((c) => c.checked);
            const sum = selected.reduce((value, c) => value + Number(c.dataset.amount || 0), 0);
            if (total) total.textContent = sum.toLocaleString("es-EC", {minimumFractionDigits: 2, maximumFractionDigits: 2});
            if (count) count.textContent = selected.length + " viajes seleccionados";
        }
        checkboxes.forEach((c) => c.addEventListener("change", update));
        const selectAll = form.querySelector(".tc-select-all-trips");
        if (selectAll) selectAll.addEventListener("click", () => {
            const allSelected = checkboxes.length > 0 && checkboxes.every((c) => c.checked);
            checkboxes.forEach((c, i) => { c.checked = !allSelected && i < 100; });
            update();
        });
        form.addEventListener("submit", (event) => {
            if (!checkboxes.some((c) => c.checked)) {
                event.preventDefault();
                window.alert("Selecciona al menos un viaje para liquidar.");
            }
        });
        update();
        });
    }
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
    else boot();
})();
