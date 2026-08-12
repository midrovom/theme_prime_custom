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

        'click #next-button': '_onNextClick',
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

    _onNextClick(ev) {
        ev.preventDefault();

        // Ejecutar validaciones del Step 1
        const isStepValid = this._validateCurrentStep1();

        if (isStepValid) {
            // Si todo está correcto, puedes avanzar al siguiente paso
            console.log("Step 1 validado correctamente, avanzar al siguiente paso.");
            // Aquí puedes disparar tu lógica para mostrar Step 2
        } else {
            console.log("Errores en Step 1, revisar campos.");
        }
    },

    _refreshFileInput(input) {
        input.value = "";
    },

    _validateCurrentStep1() {
        
        const isCurriculumValid = this._validateCurriculum();
        const isFotografiaValid = this._validateFotografia();
        const isCedulaValid = this._validateCedulaVotacion();
        const isHistoriaLaboralValid = this._validateHistoriaLaboral();
        const isEstudiosSenecytValid = this._validateEstudiosSenecyt();
        const isRecomendacionesValid = this._validateRecomendaciones();
        const isCertificadosTrabajoValid = this._validateCertificadosTrabajo();
        const isPlanillaServiciosValid = this._validatePlanillaServicios();
        const isCroquisDomicilioValid = this._validateCroquisDomicilio();
        const isCuentaBancoValid = this._validateCuentaBancoInternacional();
        const isCertificadoSaludValid = this._validateCertificadoSalud();

        if (
            !isCurriculumValid ||
            !isFotografiaValid ||
            !isCedulaValid ||
            !isHistoriaLaboralValid ||
            !isEstudiosSenecytValid ||
            !isRecomendacionesValid ||
            !isCertificadosTrabajoValid ||
            !isPlanillaServiciosValid ||
            !isCroquisDomicilioValid ||
            !isCuentaBancoValid ||
            !isCertificadoSaludValid
        ) {
            this._scrollToFirstError();
            return false;
        }

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
