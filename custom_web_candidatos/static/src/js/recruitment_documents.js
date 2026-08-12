/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import { _t } from "@web/core/l10n/translation";

publicWidget.registry.MultistepForm = publicWidget.Widget.extend({
    selector: '#hr_job_recruitment_form',

    events: {
        'change #fotografia': '_onFileSelected',
        'change #cedula-votacion': '_onFileSelected',
        'change #historia-laboral-iess': '_onFileSelected',
        'change #estudios-senecyt': '_onFileSelected',
        'change #recomendaciones': '_onFileSelected',
        'change #certificados-trabajo': '_onFileSelected',
        'change #planilla-servicios': '_onFileSelected',
        'change #croquis-domicilio': '_onFileSelected',
        'change #cuenta-banco-internacional': '_onFileSelected',
        'change #certificado-salud': '_onFileSelected',
        'change #acta-matrimonio': '_onFileSelected',
        'change #hijos-menores': '_onFileSelected',
        'change #cursos-realizados': '_onFileSelected',
        'change #formulario-107': '_onFileSelected',
    },

    //----------------------------------------------------------------------
    // Private
    //----------------------------------------------------------------------

    // función para mostrar archivos seleccionados
    _onFileSelected(ev) {
        const input = ev.currentTarget;
        const newFiles = Array.from(input.files);
        const container = document.getElementById(`file-selected-${input.id}`);

        if (!this.uploadedFiles) {
            this.uploadedFiles = [];
        }

        // Validar que sean PDF (excepto fotografía que es imagen)
        const invalidFiles = newFiles.filter(file => {
            if (input.id === "fotografia") {
                return !file.type.startsWith("image/");
            }
            return file.type !== "application/pdf" && !file.name.toLowerCase().endsWith(".pdf");
        });

        if (invalidFiles.length > 0) {
            container.innerHTML = `
                <div class="text-danger custom-message fs-6">
                    Solo se permiten archivos ${input.id === "fotografia" ? "de imagen" : "PDF"}.
                </div>
            `;
            input.value = "";
            return;
        }

        // Agregar nuevos archivos evitando duplicados por nombre
        this.uploadedFiles = this.uploadedFiles.concat(newFiles);
        this.uploadedFiles = this.uploadedFiles.filter(
            (file, index, self) => index === self.findIndex(f => f.name === file.name)
        );

        // Refrescar input y renderizar lista
        this._refreshFileInput(input);
        this._renderFileList(container, input);
    },

    _validateCurriculum() {
        return this._validatePDF('#curriculum-vitae','#file-selected-curriculum-vitae','Debe adjuntar hoja de vida.');
    },

    _validateFotografia() {
        return this._validateImageFile('#fotografia','#file-selected-fotografia','Debe adjuntar una fotografía.');
    },

    _validateCedulaVotacion() {
        return this._validatePDF('#cedula-votacion','#file-selected-cedula-votacion','Debe adjuntar cédula y certificado de votación.');
    },

    _validateHistoriaLaboral() {
        return this._validatePDF('#historia-laboral-iess','#file-selected-historia-laboral-iess','Debe adjuntar historia laboral.');
    },

    _validateEstudiosSenecyt() {
        return this._validatePDF('#estudios-senecyt','#file-selected-estudios-senecyt','Debe adjuntar certificado o título.');
    },

    _validateRecomendaciones() {
        return this._validatePDF('#recomendaciones','#file-selected-recomendaciones','Debe adjuntar recomendaciones.');
    },

    _validateCertificadosTrabajo() {
        return this._validatePDF('#certificados-trabajo','#file-selected-certificados-trabajo','Debe adjuntar certificados de trabajo.');
    },

    _validatePlanillaServicios() {
        return this._validatePDF('#planilla-servicios','#file-selected-planilla-servicios','Debe adjuntar planilla de servicios básicos.');
    },

    _validateCroquisDomicilio() {
        return this._validatePDF('#croquis-domicilio','#file-selected-croquis-domicilio','Debe adjuntar croquis del domicilio.');
    },

    _validateCuentaBancoInternacional() {
        return this._validatePDF('#cuenta-banco-internacional','#file-selected-cuenta-banco-internacional','Debe adjuntar cuenta bancaria.');
    },

    _validateCertificadoSalud() {
        return this._validatePDF('#certificado-salud','#file-selected-certificado-salud','Debe adjuntar certificado de salud.');
    },

    _refreshFileInput(input) {
        input.value = "";
    },


    _validatePDF(inputId, containerId, message) {
        const $input = this.$(inputId);
        const $container = this.$(containerId);
        const file = $input[0].files[0];

        if (!file) {
            $input.addClass('is-invalid');
            $container.html(`<div class="text-danger fs-6">${message}</div>`);
            return false;
        }

        if (file.type !== "application/pdf" && !file.name.toLowerCase().endsWith(".pdf")) {
            $input.addClass('is-invalid');
            $container.html(`<div class="text-danger fs-6">Solo se permiten archivos PDF.</div>`);
            return false;
        }

        $input.removeClass('is-invalid');
        return true;
    },

    _validateImageFile(inputId, containerId, message) {
        const $input = this.$(inputId);
        const $container = this.$(containerId);
        const file = $input[0].files[0];

        if (!file) {
            $input.addClass('is-invalid');
            $container.html(`<div class="text-danger fs-6">${message}</div>`);
            return false;
        }

        if (!file.type.startsWith("image/")) {
            $input.addClass('is-invalid');
            $container.html(`<div class="text-danger fs-6">Solo se permiten imágenes.</div>`);
            return false;
        }

        $input.removeClass('is-invalid');
        return true;
    },


    _renderFileList(container, input) {
        container.innerHTML = "";
        this.uploadedFiles.forEach((file, index) => {
            container.innerHTML += `
                <div>
                    ${file.name}
                    <button type="button" class="btn btn-sm btn-danger remove-file" data-index="${index}">
                        X
                    </button>
                </div>
            `;
        });

        // Enganchar botones de quitar
        container.querySelectorAll(".remove-file").forEach(button => {
            button.addEventListener("click", (e) => {
                const index = parseInt(e.currentTarget.dataset.index);
                this.uploadedFiles.splice(index, 1);
                this._refreshFileInput(input);
                this._renderFileList(container, input);
            });
        });
    },
});
