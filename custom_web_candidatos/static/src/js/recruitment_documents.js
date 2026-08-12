odoo.define('custom_web_candidatos.recruitment_documents', function (require) {
    "use strict";

    const publicWidget = require('web.public.widget');

    publicWidget.registry.MultistepForm = publicWidget.Widget.extend({
        selector: '#hr_job_recruitment_form',

        events: {
            'click #next-button': '_onNextClick',
            'click #next-button-step2': '_onNextStep2',
            'click #prev-button': '_onPrevClick',
            'click #prev-button-2': '_onPrevClickStep2',
            'submit': '_onSubmitForm',
            'click #add-experience': '_onAddExperience',
            'click #add-reference': '_onAddReference',

            'change #hr-perfil': '_validateImage',
            'change #curriculum-vitae': '_onFileSelected',

            // NUEVOS CAMPOS DE ARCHIVO
            'change #fotografia': '_onFileSelected',
            'change #cedula-votacion': '_onFileSelected',
            'change #historia-laboral-iess': '_onFileSelected',
            'change #acta-matrimonio': '_onFileSelected',
            'change #hijos-menores': '_onFileSelected',
        },

        init() {
            this._super(...arguments);
            this.educationCount = 1;
            this.experienceCount = 1;
            this.familyCount = 0;
            this.referenceCount = 0;
            this.uploadedFiles = [];
        },

        start() {
            this._initializeForm();
            this._addEducationBlock();
            this._addExperienceBlock();
            this._addFamilyBlock();
            this._addReferenceBlock();

            this._toggleStudyFields(); 
            this._toggleDisabilityFields();
            this._toggleFamilyKnownFields();
            this._toggleParentescoField();
            this._toggleJobDisabilityFields();
            this._onChangeCountry({ currentTarget: this.$('#hr-country') });

            return this._super();
        },

        //----------------------------------------------------------------------
        // Private
        //----------------------------------------------------------------------

        _onFileSelected(ev) {
            const input = ev.currentTarget;
            const file = input.files[0];
            if (file) {
                console.log(`Archivo seleccionado en ${input.name}: ${file.name}`);
                // Si es fotografía, mostrar preview
                if (input.id === 'fotografia' && file.type.startsWith('image/')) {
                    const reader = new FileReader();
                    reader.onload = (e) => {
                        const previewId = '#preview-fotografia';
                        let $preview = this.$(previewId);
                        if (!$preview.length) {
                            $preview = $('<img>', { id: 'preview-fotografia', class: 'img-thumbnail mt-2', width: 150 });
                            $(input).after($preview);
                        }
                        $preview.attr('src', e.target.result);
                    };
                    reader.readAsDataURL(file);
                }
            }
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

        _validateCurrentStep1() {
            const isImageValid = this._validateImage();
            const isLastnamePaternoValid = this._validateField('#hr-lastname-paterno');
            const isLastnameMaternoValid = this._validateField('#hr-lastname-materno');
            const isNameValid = this._validateField('#hr-name');
            const isAgeValid = this._validateField('#hr-age');
            const isAddressValid = this._validateField('#hr-address');
            const isParishValid = this._validateField('#hr-parish');
            const isBirthDateValid = this._validateBirthDate();
            const isBirthCountryValid = this._validateField('#hr-country');
            const isProvinceValid = this._validateField('#hr-provincia');
            const isCodeCellphoneValid = this._validateCodePhone();
            const isCellphoneValid = this._validatePhone();
            const isViveConValid = this._validateField('input[name="viveCon"]');
            const isTipoViviendaValid = this._validateField('input[name="tipoVivienda"]');
            const isHijosValid = this._validateField('#hr-hijos');
            const isEmailValid = this._validateEmail();
            const isDocTypeValid = this._validateField('#hr-type-doc');
            const isDocNumberValid = this._validateDocumentNumber();
            const isNationalityValid = this._validateField('#hr-nationality');
            const isEstadoCivilValid = this._validateField('input[name="estadoCivil"]');
            const isCurriculumValid = this._validateCurriculum();

            // NUEVAS VALIDACIONES DE ARCHIVOS
            const isFotografiaValid = this._validateFile('#fotografia', ['image/jpeg','image/png']);
            const isCedulaValid = this._validateFile('#cedula-votacion', ['application/pdf']);
            const isHistoriaLaboralValid = this._validateFile('#historia-laboral-iess', ['application/pdf']);
            const isActaMatrimonioValid = this._validateFile('#acta-matrimonio', ['application/pdf']);
            const isHijosMenoresValid = this._validateFile('#hijos-menores', ['application/pdf']);

            if (
                !isImageValid ||
                !isLastnamePaternoValid ||
                !isLastnameMaternoValid ||
                !isNameValid ||
                !isAgeValid ||
                !isAddressValid ||
                !isParishValid ||
                !isBirthDateValid ||
                !isBirthCountryValid ||
                !isProvinceValid ||
                !isCodeCellphoneValid ||
                !isCellphoneValid ||
                !isViveConValid ||
                !isTipoViviendaValid ||
                !isHijosValid ||
                !isEmailValid ||
                !isDocTypeValid ||
                !isDocNumberValid ||
                !isNationalityValid ||
                !isCurriculumValid ||
                !isEstadoCivilValid ||
                !isFotografiaValid ||
                !isCedulaValid ||
                !isHistoriaLaboralValid ||
                !isActaMatrimonioValid ||
                !isHijosMenoresValid
            ) {
                this._scrollToFirstError();
                return false;
            }

            return true;
        },
    });
});
