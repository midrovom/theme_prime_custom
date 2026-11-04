/** @odoo-module **/

// Extensión visual ligera para los dos widgets nativos many2many_binary.
// La subida y el guardado siguen siendo responsabilidad del widget de Odoo.
const targetSelector = ".o_credit_signed_dropzone";

function targetFromEvent(event) {
    return event.target instanceof Element ? event.target.closest(targetSelector) : null;
}

document.addEventListener("dragover", (event) => {
    const target = targetFromEvent(event);
    if (!target || !event.dataTransfer || !Array.from(event.dataTransfer.types).includes("Files")) {
        return;
    }
    if (!target.querySelector('input[type="file"]')) {
        return;
    }
    event.preventDefault();
    event.dataTransfer.dropEffect = "copy";
    target.classList.add("o_credit_signed_dragover");
});

document.addEventListener("dragleave", (event) => {
    const target = targetFromEvent(event);
    if (target && !target.contains(event.relatedTarget)) {
        target.classList.remove("o_credit_signed_dragover");
    }
});

document.addEventListener("drop", (event) => {
    const target = targetFromEvent(event);
    if (!target) {
        return;
    }
    target.classList.remove("o_credit_signed_dragover");
    const input = target.querySelector('input[type="file"]');
    if (!input || !event.dataTransfer?.files?.length) {
        return;
    }
    event.preventDefault();
    event.stopPropagation();
    const dropped = Array.from(event.dataTransfer.files);
    const valid = dropped.filter((file) => file.name.toLowerCase().endsWith(".pdf"));
    if (valid.length !== dropped.length) {
        window.alert("Solo se admiten archivos PDF firmados.");
    }
    if (!valid.length) {
        return;
    }
    const transfer = new DataTransfer();
    valid.forEach((file) => transfer.items.add(file));
    input.files = transfer.files;
    input.dispatchEvent(new Event("change", { bubbles: true }));
});
