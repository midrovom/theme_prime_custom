/** @odoo-module **/

/*
 * Corrección exclusiva para la vista pública de postulación.
 *
 * custom_web_hr_datos_candidatos genera dinámicamente los bloques de Formación
 * y Referencias desde MultistepForm.start(). Cuando el widget se inicializa
 * más de una vez sobre el mismo formulario, esos bloques se duplican.
 *
 * No modificamos el módulo base: aquí normalizamos el DOM de la vista heredada.
 * - Formación: siempre inicia con un solo bloque.
 * - Referencias: se mantienen exactamente 3 bloques fijos.
 * - Formación conserva el botón nativo "+ añadir educación" para agregar más
 *   bloques cuando el bloque actual esté completo.
 */

const FORM_SELECTOR = "#hr_job_recruitment_form";
const EDUCATION_SELECTOR = "#education_container .education-block";
const REFERENCE_SELECTOR = "#reference_container .reference-block";
const MAX_REFERENCES = 3;

function removeExtraEducation(form) {
    const container = form.querySelector("#education_container");
    if (!container) return;

    const blocks = container.querySelectorAll(".education-block");
    if (blocks.length <= 1) return;

    // Conservamos el primer bloque generado por el módulo nativo.
    Array.from(blocks).slice(1).forEach(block => block.remove());

    const total = form.querySelector("#total_educations");
    if (total) total.value = "1";
}

function removeExtraReferences(form) {
    const container = form.querySelector("#reference_container");
    if (!container) return;

    const blocks = container.querySelectorAll(".reference-block");
    if (blocks.length <= MAX_REFERENCES) return;

    // La sección de referencias es fija: únicamente deben existir 3.
    Array.from(blocks).slice(MAX_REFERENCES).forEach(block => block.remove());

    const total = form.querySelector("#total_references");
    if (total) total.value = String(MAX_REFERENCES);
}

function reindexReferences(form) {
    const container = form.querySelector("#reference_container");
    if (!container) return;

    const blocks = container.querySelectorAll(".reference-block");
    blocks.forEach((block, index) => {
        const number = index + 1;
        block.querySelectorAll("input[name]").forEach(input => {
            const name = input.getAttribute("name");
            if (!name) return;
            input.setAttribute("name", name.replace(/_(\\d+)$/, `_${number}`));
        });
    });

    const total = form.querySelector("#total_references");
    if (total) total.value = String(blocks.length);
}

function normalizeNativeRecruitmentForm(form) {
    removeExtraEducation(form);
    removeExtraReferences(form);
    reindexReferences(form);

    // La referencia es una sección fija de 3 registros.
    const addReference = form.querySelector("#add-reference");
    if (addReference) {
        addReference.style.display = "none";
        addReference.setAttribute("aria-hidden", "true");
    }
}

function installNormalization() {
    const form = document.querySelector(FORM_SELECTOR);
    if (!form || form.dataset.hrApplicationsNormalizationInstalled === "1") return;

    form.dataset.hrApplicationsNormalizationInstalled = "1";

    let scheduled = false;
    const normalize = () => {
        if (scheduled) return;
        scheduled = true;
        window.setTimeout(() => {
            scheduled = false;
            normalizeNativeRecruitmentForm(form);
        }, 0);
    };

    const observer = new MutationObserver(normalize);
    observer.observe(form, { childList: true, subtree: true });

    // El widget nativo genera los bloques después de iniciar y puede hacerlo
    // mediante llamadas asíncronas (fetch de catálogos).
    normalize();
    window.setTimeout(normalize, 250);
    window.setTimeout(normalize, 750);
    window.setTimeout(normalize, 1500);
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", installNormalization, { once: true });
} else {
    installNormalization();
}
