/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import { patch } from "@web/core/utils/patch";

/*
 * Extensión del formulario nativo sin tocar custom_web_hr_datos_candidatos.
 *
 * Cambios de este archivo:
 * 1) El flujo pasa directamente de Formulario 1 a Formulario 3.
 * 2) La navegación "Anterior" de Formulario 3 vuelve a Formulario 1.
 * 3) Se evita que _addEducationBlock() sea ejecutado más de una vez para
 *    crear el bloque inicial. Esto corrige la duplicación provocada al
 *    heredar/reescribir la navegación.
 * 4) Se limpia, solo durante la inicialización, cualquier bloque de
 *    educación duplicado. No se vuelve a limpiar después, para no borrar
 *    educaciones legítimamente agregadas por "+ añadir educación".
 * 5) Referencias: se mantienen exactamente 3 y se oculta el botón nativo
 *    de agregar referencia.
 */

const FORM_SELECTOR = "#hr_job_recruitment_form";
const MAX_REFERENCES = 3;

function getEducationContainer(form) {
    return form?.querySelector("#education_container");
}

function getEducationBlocks(form) {
    const container = getEducationContainer(form);
    if (!container) return [];

    /*
     * El JS nativo no añade una clase .education-block al HTML que genera.
     * Por eso identificamos cada bloque por los campos que pertenecen a una
     * educación y solo tomamos hijos directos del contenedor.
     */
    return Array.from(container.children).filter((node) => {
        if (node.nodeType !== Node.ELEMENT_NODE) return false;
        return Boolean(
            node.querySelector(
                'input[name^="institucion_"], ' +
                'select[name^="level_id_"], ' +
                'input[name^="inicioEstudio_"], ' +
                'select[name^="finEstudio_"]'
            )
        );
    });
}

function normalizeInitialEducation(form, widget = null) {
    const container = getEducationContainer(form);
    if (!container) return;

    const blocks = getEducationBlocks(form);
    if (blocks.length <= 1) {
        if (widget) widget.educationCount = Math.max(Number(widget.educationCount || 1), 1);
        const total = form.querySelector("#total_educations");
        if (total && blocks.length === 1) total.value = "1";
        return;
    }

    /*
     * Solo estamos normalizando la fase inicial. Conservamos el primer bloque
     * y eliminamos los restantes que llegaron de llamadas repetidas al método
     * nativo de creación inicial.
     */
    blocks.slice(1).forEach((block) => block.remove());

    // El separador de un bloque secundario puede quedar como hijo huérfano.
    Array.from(container.querySelectorAll(":scope > .separator-education")).forEach((separator) => {
        separator.remove();
    });

    const total = form.querySelector("#total_educations");
    if (total) total.value = "1";

    if (widget) {
        widget.educationCount = 1;
        if (typeof widget._checkEducationFieldsFilled === "function") {
            widget._checkEducationFieldsFilled();
        }
    }
}

function removeExtraReferences(form) {
    const container = form.querySelector("#reference_container");
    if (!container) return;

    const blocks = Array.from(container.querySelectorAll(".reference-block"));
    if (blocks.length <= MAX_REFERENCES) {
        const total = form.querySelector("#total_references");
        if (total && blocks.length === MAX_REFERENCES) total.value = String(MAX_REFERENCES);
        return;
    }

    blocks.slice(MAX_REFERENCES).forEach((block) => block.remove());

    const total = form.querySelector("#total_references");
    if (total) total.value = String(MAX_REFERENCES);
}

function reindexReferences(form) {
    const container = form.querySelector("#reference_container");
    if (!container) return;

    const blocks = container.querySelectorAll(".reference-block");
    blocks.forEach((block, index) => {
        const number = index + 1;
        block.querySelectorAll("input[name]").forEach((input) => {
            const name = input.getAttribute("name");
            if (!name) return;
            input.setAttribute("name", name.replace(/_(\d+)$/, `_${number}`));
        });
    });

    const total = form.querySelector("#total_references");
    if (total) total.value = String(blocks.length);
}


function syncReferenceFields(form) {
    const container = form.querySelector("#reference_container");
    if (!container) return;
    const blocks = Array.from(container.querySelectorAll(".reference-block")).slice(0, 3);
    const suffixes = ["nombre", "telefono", "ocupacion", "tiempo", "domicilio"];
    blocks.forEach((block, index) => {
        suffixes.forEach((suffix) => {
            const input = block.querySelector(`[name^="ref_${suffix}_"]`);
            if (input) {
                input.name = `ref_${suffix}_${index}`;
                input.disabled = false;
            }
        });
    });
    const total = form.querySelector("#total_references");
    if (total) total.value = String(blocks.length);
}

function normalizeReferences(form) {
    removeExtraReferences(form);
    reindexReferences(form);

    const addReference = form.querySelector("#add-reference");
    if (addReference) {
        addReference.style.display = "none";
        addReference.setAttribute("aria-hidden", "true");
        addReference.setAttribute("tabindex", "-1");
    }
}

function normalizeInitialState(form, widget = null) {
    if (form.dataset.hrApplicationsUserAddedEducation !== "1") {
        normalizeInitialEducation(form, widget);
    }
    normalizeReferences(form);
}

/*
 * Patch del widget legacy usado por custom_web_hr_datos_candidatos.
 * Odoo 18 recomienda patch() para modificar clases existentes sin editar el
 * módulo original.
 */
if (publicWidget.registry.MultistepForm) {
    patch(publicWidget.registry.MultistepForm.prototype, {
        async _addEducationBlock(...args) {
            /*
             * El bloque inicial solo puede solicitarse una vez. El botón
             * "+ añadir educación" utiliza _onAddEducation(), por lo que esta
             * protección no impide añadir bloques adicionales legítimos.
             */
            if (this.__hrApplicationsInitialEducationRequested) {
                return;
            }

            this.__hrApplicationsInitialEducationRequested = true;
            return super._addEducationBlock(...args);
        },

        _onAddEducation(ev) {
            /*
             * Desde este momento cualquier bloque adicional es legítimo y no
             * debe ser eliminado por las pasadas de normalización inicial.
             */
            this.el.dataset.hrApplicationsUserAddedEducation = "1";
            return super._onAddEducation(...arguments);
        },

        _onNextClick(ev) {
            ev.preventDefault();

            if (!this._validateCurrentStep1()) {
                return;
            }

            /*
             * Primera transición: Formulario 1 -> Formulario 3.
             * Antes de mostrar Formulario 3 limpiamos solamente duplicados
             * iniciales. Después de esta transición no ejecutamos más la
             * limpieza de educación, de modo que el usuario puede agregar
             * nuevas educaciones con el botón nativo.
             */
            if (!this.__hrApplicationsInitialEducationNormalized) {
                this.__hrApplicationsInitialEducationNormalized = true;
                normalizeInitialEducation(this.el, this);
            }

            this.$("#form-step-1").addClass("d-none");
            this.$("#form-step-2").addClass("d-none");
            this.$("#form-step-3").removeClass("d-none");
        },

        _onPrevClick(ev) {
            ev.preventDefault();

            this.$("#form-step-3").addClass("d-none");
            this.$("#form-step-2").addClass("d-none");
            this.$("#form-step-1").removeClass("d-none");
        },

        _onSubmitForm(ev) {
            // Antes de delegar al JS nativo dejamos las tres referencias con
            // nombres consecutivos y habilitadas para que /jobs/submit pueda
            // construir applicant.reference.
            syncReferenceFields(this.el);
            return super._onSubmitForm(...arguments);
        },
    });
}

function installNativeRecruitmentFixes() {
    const form = document.querySelector(FORM_SELECTOR);
    if (!form || form.dataset.hrApplicationsNativeFixesInstalled === "1") return;

    form.dataset.hrApplicationsNativeFixesInstalled = "1";

    /*
     * El JS nativo carga países/estados y crea bloques de forma asíncrona.
     * Hacemos varias pasadas iniciales, pero NO usamos un MutationObserver
     * permanente para Educación: eso podría borrar bloques que el usuario
     * agregue después mediante "+ añadir educación".
     */
    const run = () => normalizeInitialState(form);

    run();
    window.setTimeout(run, 250);
    window.setTimeout(run, 750);
    window.setTimeout(run, 1500);
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", installNativeRecruitmentFixes, { once: true });
} else {
    installNativeRecruitmentFixes();
}
