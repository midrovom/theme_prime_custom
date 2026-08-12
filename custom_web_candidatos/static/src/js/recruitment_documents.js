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

    _onFileSelected(ev) {
        const input = ev.currentTarget;
        const file = input.files[0];
        const messageId = `#file-selected-${input.id}`;
        if (file) {
            this.$(messageId).html(`
                Archivo seleccionado: ${file.name}
                <button type="button" class="btn btn-sm btn-danger remove-file" data-input="${input.id}">
                    Quitar
                </button>
            `);
            this._bindRemoveFile(input, messageId);
        } else {
            this.$(messageId).text('');
        }
    },

    _bindRemoveFile(input, messageId) {
        this.$(`${messageId} .remove-file`).on('click', (e) => {
            this._refreshFileInput(input);
            this.$(messageId).text('');
        });
    },

    _refreshFileInput(input) {
        input.value = "";
    },

    _validateFile(id, validTypes) {
        const $f = this.$(id);
        const file = $f[0].files[0];
        if (!file || (validTypes && !validTypes.includes(file.type))) {
            $f.addClass('is-invalid');
            return false;
        }
        $f.removeClass('is-invalid');
        return true;
    },

    _validateDocuments() {
        const isFotografiaValid = this._validateFile('#fotografia', ['image/jpeg','image/png']);
        const isCedulaValid = this._validateFile('#cedula-votacion', ['application/pdf']);
        const isHistoriaLaboralValid = this._validateFile('#historia-laboral-iess', ['application/pdf']);
        const isEstudiosSenecytValid = this._validateFile('#estudios-senecyt', ['application/pdf']);
        const isRecomendacionesValid = this._validateFile('#recomendaciones', ['application/pdf']);
        const isCertificadosTrabajoValid = this._validateFile('#certificados-trabajo', ['application/pdf']);
        const isPlanillaServiciosValid = this._validateFile('#planilla-servicios', ['application/pdf']);
        const isCroquisDomicilioValid = this._validateFile('#croquis-domicilio', ['application/pdf']);
        const isCuentaBancoValid = this._validateFile('#cuenta-banco-internacional', ['application/pdf']);
        const isCertificadoSaludValid = this._validateFile('#certificado-salud', ['application/pdf']);

        if (
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

    _scrollToFirstError() {
        const $firstError = this.$('.is-invalid').first();
        if ($firstError.length) {
            $('html, body').animate({
                scrollTop: $firstError.offset().top - 100
            }, 500);
        }
    },
});
