/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import { _t } from "@web/core/l10n/translation";

const YEARS = Array.from({ length: 2026 - 1900 }, (_, i) => i + 1900);

const optionsYears = YEARS.map(year => `<option value="${year}">${year}</option>`).join("");

let cachedCountries = null;
let cachedStatesByCountry = {};

async function loadCountriesAndStates() {
    if (!cachedCountries) {
        cachedCountries = await fetch("/api/countries").then(r => r.json());
        for (const country of cachedCountries) {
            cachedStatesByCountry[country.id] = await fetch(`/api/states/${country.id}`).then(r => r.json());
        }
    }
}

publicWidget.registry.MultistepForm = publicWidget.Widget.extend({
    selector: '#hr_job_recruitment_form',
    events: {
        'click #next-button': '_onNextClick',
        'click #next-button-step2': '_onNextStep2',
        'click #prev-button': '_onPrevClick',
        'submit': '_onSubmitForm',
        'click #add-experience': '_onAddExperience',
        'click #add-reference': '_onAddReference',

        'change #hr-perfil': '_validateImage',

        'input #experience_container input, #experience_container select, #experience_container textarea': '_checkFieldsFilled',
        'change #experience_container input, #experience_container select, #experience_container textarea': '_checkFieldsFilled',

        'click #add-education': '_onAddEducation',
        'click #add-family': '_addFamilyBlock',
        'input #education_container input, #education_container select': '_checkEducationFieldsFilled',
        'input input[name^="famTelefono_"]': '_validateDynamicPhone',
        'input input[name^="telefonos_"]': '_validateDynamicPhone',
        'input input[name^="ref_telefono_"]': '_validateDynamicPhone',


        'blur #hr-lastname-paterno, #hr-lastname-materno, #hr-name, #hr-age, #hr-address, #hr-parish, #hr-hijos, #hr-nationality, #experience_container input, #experience_container textarea, #education_container input': '_validateField',
        'blur #hr-email': '_validateEmail',
        'blur #hr-number-doc': '_validateDocumentNumber',
        'blur #hr-cellphone': '_validatePhone',
        'blur input[name^="famTelefono_"]': '_validateDynamicPhone',
        'blur input[name^="telefonos_"]': '_validateDynamicPhone',
        'blur input[name^="ref_telefono_"]': '_validateDynamicPhone',
        'blur input[name^="ref_nombre_"]': '_validateReferenceField',
        'blur input[name^="ref_domicilio_"]': '_validateReferenceField',
        'blur input[name^="ref_ocupacion_"]': '_validateReferenceField',
        'blur input[name^="ref_tiempo_"]': '_validateReferenceField',
        'blur input[name^="famNombre_"]': '_validateReferenceField',
        'blur input[name^="famFecha_"]': '_validateFamilyDate',
        'blur input[name^="famOcupacion_"]': '_validateReferenceField',
        'blur input[name^="famDepende_"]': '_validateReferenceField',
        'blur input[name^="famDisc_"]': '_validateReferenceField',
        'blur input[name^="famCedula_"]': '_validateFamilyCedula',

        'change #hr-type-doc, #hr-country, #hr-provincia, #curriculum-vitae, #experience_container select, #education_container select': '_validateField',
        'change #hr-country': '_onChangeCountry',
        'change input[name="discapacidad"]': '_toggleDisabilityFields',
        'change input[name="viveCon"]': '_validateField',
        'change input[name="tipoVivienda"]': '_validateField',
        'change input[name="estadoCivil"]': '_validateField',
        'change #education_container input, #education_container select': '_checkEducationFieldsFilled',
        'change input[name="knownPosee_1"]': '_toggleFamilyKnownFields',
        'change input[name="knownRelacion_1"]': '_toggleParentescoField',
        'change #hr-code-cellphone': '_validateCodePhone',
        'change #hr-day, #hr-month, #hr-year': '_validateBirthDate',
        'change input[name="viveCon"], input[name="tipoVivienda"], input[name="dependientes"], input[name="estadoCivil"]': '_validateField',
        'change input[name="jobOptions"], input[name="discOptions"], #policy': '_validateField',
        'change input[name="studyOptions"]': '_toggleStudyFields',
        'change input[name="jobOptions"]': '_toggleJobDisabilityFields',
        'change input[name="enfermedad_persistente"]': function() {
            this._validateHealthGroup('enfermedad_persistente','detalle_enfermedad_persistente');
        },
        'change input[name="medicacion_continua"]': function() {
            this._validateHealthGroup('medicacion_continua','detalle_medicacion_continua');
        },
        'change input[name="enfermedad_laboral"]': function() {
            this._validateHealthGroup('enfermedad_laboral','detalle_enfermedad_laboral');
        },
        'change input[name="cirugia_realizada"]': function() {
            this._validateHealthGroup('cirugia_realizada','detalle_cirugia_realizada');
        },
        'input input[name="detalle_enfermedad_persistente"]': function() {
            this._validateHealthGroup('enfermedad_persistente','detalle_enfermedad_persistente');
        },

        'input input[name="detalle_medicacion_continua"]': function() {
            this._validateHealthGroup('medicacion_continua','detalle_medicacion_continua');
        },
        'input input[name="detalle_enfermedad_laboral"]': function() {
            this._validateHealthGroup('enfermedad_laboral','detalle_enfermedad_laboral');
        },
        'input input[name="detalle_cirugia_realizada"]': function() {
            this._validateHealthGroup('cirugia_realizada','detalle_cirugia_realizada');
        },

        'change input[name^="famDisc_"]': function(ev) {
            const name = $(ev.currentTarget).attr('name'); 
            const index = name.split('_')[1];
            this._validateFamilyDisability(index);
        },
        'input input[name^="famDiscTipo_"]': function(ev) {
            const name = $(ev.currentTarget).attr('name'); 
            const index = name.split('_')[1];
            this._validateFamilyDisability(index);
        },

        'blur input[name^="inicioEstudio_"]': function(ev) {
            this._validateDateField(ev.currentTarget);
        },
        
        'blur input[name^="jobInicio_"]': function(ev) {
            this._validateDateField(ev.currentTarget);
        },

        'blur input[name="tipo_sangre"]': '_validateTipoSangre',


    },
    


    /**
     * @override
     */
    init() {
        this._super(...arguments);
        this.educationCount = 1;
        this.experienceCount = 1;
        this.familyCount = 0;
        this.referenceCount = 0;
    },

    /**
     * @override
     */
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

        this._validateHealthQuestions();
        this._onChangeCountry({ currentTarget: this.$('#hr-country') });

        return this._super();
    },

    //----------------------------------------------------------------------
    // Private
    //----------------------------------------------------------------------

    _initializeForm() {
        this.$('#add-experience').css({
            'opacity': '0.5',
            'pointer-events': 'none'
        });

        this.$('#add-education').css({
            'opacity': '0.5',
            'pointer-events': 'none'
        });

        this._checkFieldsFilled();
        this._checkEducationFieldsFilled();
    },


    async _getEducationBlock(isFirstBlock = false) {
        await loadCountriesAndStates();  // asegura que ya están cargados

        const separator = isFirstBlock ? '' : `
            <div class="row d-flex justify-content-center my-4">
                <div class="col-12 col-md-10">
                    <div class="separator-education" style="border-top: 2px solid #e0e0e0; position: relative; margin: 20px 0;">
                        <span style="position: absolute; top: -12px; left: 50%; transform: translateX(-50%);
                            background: white; padding: 0 15px; color: #666; font-size: 14px;">
                            Educación # ${this.educationCount - 1}
                        </span>
                    </div>
                </div>
            </div>
        `;

        const studiesLevels = await fetch("/api/study_levels").then(r => r.json());

        // Construir opciones de país + ciudad usando cache
        let optionsCountries = "";
        for (const country of cachedCountries) {
            optionsCountries += `<option value="country-${country.id}">${country.name}</option>`;
            cachedStatesByCountry[country.id].forEach(state => {
                optionsCountries += `<option value="state-${state.id}">${state.name}</option>`;
            });
        }

        const optionsStudiesLevels = studiesLevels.map(
            studyLevel => `<option value="${studyLevel.id}">${studyLevel.name}</option>`
        ).join('');

        return `
            <div class="row d-flex justify-content-center">
                <div class="col-12 col-md-10">
                    <div class="row d-flex justify-content-between">
                        <!-- Nivel educativo -->
                        <div class="col-12 col-md-4 mb-4">
                            <label for="institucion-educativa_${this.educationCount}" class="fs-6">
                                Nivel Educativo: <span class="text-danger">*</span>
                            </label>
                            <select id="institucion-educativa_${this.educationCount}" required name="level_id_${this.educationCount}" class="form-select rounded-pill py-2">
                                <option selected="selected"></option>
                                ${ optionsStudiesLevels }
                            </select>
                            <div class="invalid-feedback">Seleccione una opción.</div>
                        </div>

                        <!-- Institución -->
                        <div class="col-12 col-md-4 mb-4">
                            <label for="institucion_${this.educationCount}" class="fs-6">Nombre de la institución: <span class="text-danger">*</span></label>
                            <input type="text" required name="institucion_${this.educationCount}" class="form-control rounded-pill py-2" id="institucion_${this.educationCount}"/>
                            <div class="invalid-feedback">Campo obligatorio.</div>
                        </div>

                        <!-- Fechas -->
                        <div class="col-12 col-md-4 mb-4">
                            <label for="estudio-inicio_${this.educationCount}" class="fs-6">Desde: <span class="text-danger">*</span></label>
                            <input type="date" required name="inicioEstudio_${this.educationCount}" class="form-control rounded-pill py-2" id="estudio-inicio_${this.educationCount}"/>
                            <div class="invalid-feedback">Campo obligatorio.</div>
                        </div>

                        <div class="col-12 col-md-4 mb-4">
                            <label for="estudio-fin_${this.educationCount}" class="fs-6">Hasta: <span class="text-danger">*</span></label>
                            <select id="estudio-fin_${this.educationCount}" required name="finEstudio_${this.educationCount}" class="form-select rounded-pill py-2">
                                <option selected="selected"></option>
                                ${ optionsYears }
                                <option value="presente">Presente</option>
                            </select>
                            <div class="invalid-feedback">Seleccione una opción.</div>
                        </div>

                        <!-- País Educación -->
                        <div class="col-12 col-md-4 mb-4">
                            <label for="pais-educacion_${this.educationCount}" class="fs-6"> País: <span class="text-danger">*</span> </label>
                                <select id="pais-educacion_${this.educationCount}" name="paisEducacion_${this.educationCount}" class="form-select rounded-pill py-2" 
                                    aria-label="Seleccionar país" required> <option value=""></option> ${ cachedCountries.map(country => `
                                    <option value="country-${country.id}" ${country.name === 'Ecuador' ? 'selected' : ''}>
                                        ${country.name}
                                    </option>
                                `).join('') }
                            </select>
                            <div class="invalid-feedback">Seleccione una opción.</div>
                        </div>

                        <!-- Ciudad/Provincia Educación -->
                        <div class="col-12 col-md-4 mb-4">
                            <label for="ciudad_${this.educationCount}" class="fs-6">Ciudad/Provincia:</label>
                                <select id="ciudad_${this.educationCount}" name="ciudad_${this.educationCount}" class="form-select rounded-pill py-2" 
                                    aria-label="Seleccionar ciudad/provincia"> <option value=""></option> ${ cachedStatesByCountry[cachedCountries.find(c => c.name === 'Ecuador').id].map(state => `
                                    <option value="state-${state.id}">${state.name}</option>
                                `).join('') }
                            </select>
                        </div>

                        <div class="row d-flex justify-content-between">
                        <div class="col-12 col-md-4 mb-4">
                            <label for="titulo_${this.educationCount}" class="fs-6">Título Recibido: <span class="text-danger">*</span></label>
                            <input type="text" required name="titulo_${this.educationCount}" class="form-control rounded-pill py-2" id="titulo_${this.educationCount}"/>
                            <div class="invalid-feedback">Campo obligatorio.</div>
                        </div>
                    </div>
                </div>
            </div>
        ` + separator;

    },

    async _getExperienceBlock(isFirstBlock = false) {
        await loadCountriesAndStates(); 

        const separator = isFirstBlock ? '' : `
            <div class="row d-flex justify-content-center my-4">
                <div class="col-12 col-md-10">
                    <div class="separator-education" style="
                        border-top: 2px solid #e0e0e0;
                        position: relative;
                        margin: 20px 0;
                    ">
                        <span style="
                            position: absolute;
                            top: -12px;
                            left: 50%;
                            transform: translateX(-50%);
                            background: white;
                            padding: 0 15px;
                            color: #666;
                            font-size: 14px;
                        ">Experiencia Laboral # ${this.experienceCount - 1}</span>
                    </div>
                </div>
            </div>
        `;

        return `
            <div class="row d-flex justify-content-center">
                <div class="col-12 col-md-10">
                    <div class="row d-flex justify-content-between">

                        <!-- Tiempo que prestó su servicio -->
                        <div class="col-12 col-md-3 mb-4">
                            <label for="tiempo_${this.experienceCount}" class="fs-6">Tiempo que prestó su servicio: <span class="text-danger">*</span></label>
                            <input id="tiempo_${this.experienceCount}" type="text" name="tiempo_${this.experienceCount}" class="form-control rounded-pill py-2" required/>
                            <div class="invalid-feedback">Campo obligatorio.</div>
                        </div>

                        <!-- Nombre de la compañía -->
                        <div class="col-12 col-md-3 mb-4">
                            <label for="company_${this.experienceCount}" class="fs-6">Nombre de la compañía: <span class="text-danger">*</span></label>
                            <input id="company_${this.experienceCount}" type="text" name="company_${this.experienceCount}" class="form-control rounded-pill py-2" required/>
                            <div class="invalid-feedback">Campo obligatorio.</div>
                        </div>

                        <!-- País Experiencia -->
                        <div class="col-12 col-md-3 mb-4">
                            <label for="pais-experiencia_${this.experienceCount}" class="fs-6">País: <span class="text-danger">*</span></label>
                                <select id="pais-experiencia_${this.experienceCount}" name="paisExperiencia_${this.experienceCount}" class="form-select rounded-pill py-2" required>
                                    <option value=""></option> ${ cachedCountries.map(country => `
                                        <option value="country-${country.id}" ${country.name === 'Ecuador' ? 'selected' : ''}>
                                            ${country.name}
                                    </option>
                                `).join('') }
                            </select>
                            <div class="invalid-feedback">Seleccione una opción.</div>
                        </div>

                        <!-- Ciudad/Provincia Experiencia -->
                        <div class="col-12 col-md-3 mb-4">
                            <label for="ciudad-experiencia_${this.experienceCount}" class="fs-6">Ciudad/Provincia:</label>
                                <select id="ciudad-experiencia_${this.experienceCount}" name="ciudadExperiencia_${this.experienceCount}" 
                                    class="form-select rounded-pill py-2"> <option value=""></option> ${ cachedStatesByCountry[ cachedCountries.find(c => c.name === 'Ecuador').id].map(state => `
                                    <option value="state-${state.id}">${state.name}</option>
                                `).join('') }
                            </select>
                        </div>

                        <!-- Teléfono (movido antes de Cargo desempeñado) -->
                        <div class="col-12 col-md-3 mb-4">
                            <label for="telefonos_${this.experienceCount}" class="fs-6">Teléfono: <span class="text-danger">*</span></label>
                            <input id="telefonos_${this.experienceCount}" type="text" name="telefonos_${this.experienceCount}" class="form-control rounded-pill py-2" required/>
                            <div class="invalid-feedback">Campo obligatorio.</div>
                        </div>

                        <!-- Cargo desempeñado -->
                        <div class="col-12 col-md-3 mb-4">
                            <label for="cargo_${this.experienceCount}" class="fs-6">Cargo desempeñado: <span class="text-danger">*</span></label>
                            <input id="cargo_${this.experienceCount}" type="text" name="cargo_${this.experienceCount}" class="form-control rounded-pill py-2" required/>
                            <div class="invalid-feedback">Campo obligatorio.</div>
                        </div>

                        <!-- Ingreso mensual -->
                        <div class="col-12 col-md-3 mb-4">
                            <label for="ingreso_${this.experienceCount}" class="fs-6">Ingreso mensual: <span class="text-danger">*</span></label>
                            <input id="ingreso_${this.experienceCount}" type="number" name="ingreso_${this.experienceCount}" class="form-control rounded-pill py-2" required/>
                            <div class="invalid-feedback">Campo obligatorio.</div>
                        </div>

                        <!-- Motivo de separación -->
                        <div class="col-12 col-md-3 mb-4">
                            <label for="motivo_${this.experienceCount}" class="fs-6">Motivo de separación: <span class="text-danger">*</span></label>
                            <input id="motivo_${this.experienceCount}" type="text" name="motivo_${this.experienceCount}" class="form-control rounded-pill py-2" required/>
                            <div class="invalid-feedback">Campo obligatorio.</div>
                        </div>

                        <!-- Nombre de su jefe directo (movido antes de Cargo de su jefe directo) -->
                        <div class="col-12 col-md-3 mb-4">
                            <label for="jefe_${this.experienceCount}" class="fs-6">Nombre de su jefe directo: <span class="text-danger">*</span></label>
                            <input id="jefe_${this.experienceCount}" type="text" name="jefe_${this.experienceCount}" class="form-control rounded-pill py-2" required/>
                            <div class="invalid-feedback">Campo obligatorio.</div>
                        </div>

                        <!-- Cargo de su jefe directo -->
                        <div class="col-12 col-md-3 mb-4">
                            <label for="cargo-jefe_${this.experienceCount}" class="fs-6">Cargo de su jefe directo: <span class="text-danger">*</span></label>
                            <input id="cargo-jefe_${this.experienceCount}" type="text" name="cargoJefe_${this.experienceCount}" class="form-control rounded-pill py-2" required/>
                            <div class="invalid-feedback">Campo obligatorio.</div>
                        </div>

                        <!-- Fecha de inicio -->
                        <div class="col-12 col-md-3 mb-4">
                            <label for="job-inicio_${this.experienceCount}" class="fs-6">Desde: <span class="text-danger">*</span></label>
                            <input id="job-inicio_${this.experienceCount}" type="date" name="jobInicio_${this.experienceCount}" class="form-control rounded-pill py-2" required/>
                            <div class="invalid-feedback">Campo obligatorio.</div>
                        </div>

                        <!-- Año de finalización -->
                        <div class="col-12 col-md-3 mb-4">
                            <label for="job-fin_${this.experienceCount}" class="fs-6">Hasta: <span class="text-danger">*</span></label>
                            <select id="job-fin_${this.experienceCount}" name="jobFin_${this.experienceCount}" class="form-select rounded-pill py-2" required>
                                <option selected="selected"></option>
                                ${ optionsYears }
                                <option value="presente">Presente</option>
                            </select>
                            <div class="invalid-feedback">Seleccione una opción.</div>
                        </div>

                    </div>
                </div>
            </div>
        ` + separator;
    },

    async _getFamilyBlock() {
        return `
            <div class="row d-flex justify-content-center">
                <div class="col-12 col-md-10">

                    <div class="py-3 d-flex justify-content-start mb-3">
                        <span class="fw-normal fs-4 text-info">
                            ${this.familyCount === 1 ? 'Datos Familiares' : 'Familiar #' + this.familyCount}
                        </span>
                    </div>

                    <div class="row g-3">

                        <!-- Nombre completo -->
                        <div class="col-md-3">
                            <label class="fs-6">Nombres completos <span class="required-asterisk">*</span></label>
                                <input type="text" name="famNombre_${this.familyCount}" class="form-control rounded-pill" required/>
                            <span class="error-message">Campo obligatorio</span>
                        </div>

                        <!-- Cédula -->
                        <div class="col-md-3">
                            <label class="fs-6">Cédula <span class="required-asterisk">*</span></label>
                                <input type="text" name="famCedula_${this.familyCount}" class="form-control rounded-pill" required/>
                            <span class="error-message">Campo obligatorio</span>
                        </div>

                        <!-- Fecha nacimiento -->
                        <div class="col-md-3">
                            <label class="fs-6">Fecha nacimiento <span class="required-asterisk">*</span></label>
                                <input type="date" name="famFecha_${this.familyCount}" class="form-control rounded-pill" required/>
                            <span class="error-message">Campo obligatorio</span>
                        </div>

                        <!-- Teléfono -->
                        <div class="col-md-3">
                            <label class="fs-6">Teléfono <span class="required-asterisk">*</span></label>
                                <input type="tel" name="famTelefono_${this.familyCount}" class="form-control rounded-pill fam-telefono" required/>
                            <span class="error-message">Campo obligatorio</span>
                        </div>

                        <!-- Ocupación y empresa -->
                        <div class="col-md-3">
                            <label class="fs-6">Ocupación y Empresa <span class="required-asterisk">*</span></label>
                            <input type="text" name="famOcupacion_${this.familyCount}" 
                                class="form-control rounded-pill" required/>
                            <span class="error-message">Campo obligatorio</span>
                        </div>

                        <!-- Depende económicamente -->
                        <div class="col-md-3">
                            <label class="fs-6">Depende económicamente <span class="required-asterisk">*</span></label>
                            <div class="d-flex mt-2">
                                <div class="form-check me-3">
                                    <input class="form-check-input" type="radio" 
                                        name="famDepende_${this.familyCount}" value="si" required/>
                                    <label class="form-check-label">Sí</label>
                                </div>
                                <div class="form-check">
                                    <input class="form-check-input" type="radio" 
                                        name="famDepende_${this.familyCount}" value="no" required/>
                                    <label class="form-check-label">No</label>
                                </div>
                            </div>
                            <span class="error-message">Campo obligatorio</span>
                        </div>

                        <!-- Discapacidad -->
                        <div class="col-md-3">
                            <label class="fs-6">Discapacidad <span class="required-asterisk">*</span></label>
                            <div class="d-flex mt-2">
                                <div class="form-check me-3">
                                    <input class="form-check-input" type="radio" 
                                        name="famDisc_${this.familyCount}" value="si" required/>
                                    <label class="form-check-label">Sí</label>
                                </div>
                                <div class="form-check">
                                    <input class="form-check-input" type="radio" 
                                        name="famDisc_${this.familyCount}" value="no" required/>
                                    <label class="form-check-label">No</label>
                                </div>
                            </div>
                            <span class="error-message">Campo obligatorio</span>
                        </div>

                        <!-- Tipo discapacidad -->
                        <div class="col-md-3">
                            <label class="fs-6">Tipo de discapacidad</label>
                            <input type="text" name="famDiscTipo_${this.familyCount}" 
                                class="form-control rounded-pill"/>
                        </div>

                    </div>

                </div>
            </div>
        `;
    },

    async _getReferenceBlock() {
        return `
            <div class="row d-flex justify-content-center reference-block">
                <div class="col-12 col-md-10">
                    <div class="row d-flex justify-content-start">

                        <!-- Nombre -->
                        <div class="col-12 col-md-3 mb-4">
                            <label class="fs-6">Nombre <span class="required-asterisk">*</span></label>
                            <input type="text" name="ref_nombre_${this.referenceCount}" 
                                class="form-control rounded-pill py-2" required/>
                            <span class="error-message">Campo obligatorio</span>
                        </div>

                        <!-- Domicilio -->
                        <div class="col-12 col-md-3 mb-4">
                            <label class="fs-6">Domicilio <span class="required-asterisk">*</span></label>
                            <input type="text" name="ref_domicilio_${this.referenceCount}" 
                                class="form-control rounded-pill py-2" required/>
                            <span class="error-message">Campo obligatorio</span>
                        </div>

                        <!-- Teléfono -->
                        <div class="col-12 col-md-3 mb-4">
                            <label class="fs-6">Teléfono <span class="required-asterisk">*</span></label>
                            <input type="text" name="ref_telefono_${this.referenceCount}" 
                                class="form-control rounded-pill py-2 ref-telefono" required/>
                            <span class="error-message">Campo obligatorio</span>
                        </div>

                        <!-- Ocupación -->
                        <div class="col-12 col-md-3 mb-4">
                            <label class="fs-6">Ocupación <span class="required-asterisk">*</span></label>
                            <input type="text" name="ref_ocupacion_${this.referenceCount}" 
                                class="form-control rounded-pill py-2" required/>
                            <span class="error-message">Campo obligatorio</span>
                        </div>

                        <!-- Tiempo de conocerlo -->
                        <div class="col-12 col-md-3 mb-4">
                            <label class="fs-6">Tiempo de conocerlo <span class="required-asterisk">*</span></label>
                            <input type="text" name="ref_tiempo_${this.referenceCount}" 
                                class="form-control rounded-pill py-2" required/>
                            <span class="error-message">Campo obligatorio</span>
                        </div>

                    </div>
                </div>
            </div>
        `;
    },

    //----------------------------------------------------------------------
    // Validations
    //----------------------------------------------------------------------

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
            !isEstadoCivilValid
        ) {

            alert("Por favor complete todos los campos requeridos correctamente");

            this._scrollToFirstError();
            return false;
        }

        return true;
    },

    _validateCurrentStep2() {
        const enfermedad = this._validateHealthGroup('enfermedad_persistente','detalle_enfermedad_persistente');
        const medicacion = this._validateHealthGroup('medicacion_continua','detalle_medicacion_continua');
        const enfermedadLaboral = this._validateHealthGroup('enfermedad_laboral','detalle_enfermedad_laboral');
        const cirugia = this._validateHealthGroup('cirugia_realizada','detalle_cirugia_realizada');
        
        if (!enfermedad || !medicacion || !enfermedadLaboral || !cirugia) {

            alert("Complete correctamente la información médica");

            this._scrollToFirstError();
            return false;
        }
        return true;
    },

    _validateHealthQuestions() {
        this._validateHealthGroup('enfermedad_persistente','detalle_enfermedad_persistente');
        this._validateHealthGroup('medicacion_continua','detalle_medicacion_continua');
        this._validateHealthGroup('enfermedad_laboral','detalle_enfermedad_laboral');
        this._validateHealthGroup('cirugia_realizada','detalle_cirugia_realizada');
    },

    _validateHealthGroup(radioName, detailName) {
        const value = this.$(`input[name="${radioName}"]:checked`).val();
        const $detail = this.$(`input[name="${detailName}"]`);

        if (value === 'si') {
            $detail.prop('disabled', false).prop('required', true);
            if (!$detail.val().trim()) {
                $detail.addClass('is-invalid');
                return false;
            } else {
                $detail.removeClass('is-invalid');
            }
        } else if (value === 'no') {
            $detail.prop('disabled', true).prop('required', false).val('');
            $detail.removeClass('is-invalid');
        } else {

            return false;
        }
        return true;
    },

    _validateCurrentStep3() {

        const isStudyValid = this._validateField('input[name="studyOptions"]');
        const experienceValidation = this._validateExperienceBlocks();
        const educationValidation = this._validateEducationBlocks();
        const isFamilyOptionValid = this._validateField('input[name="familyOptions"]');

        let isNombreValid = true;
        let isRelationValid = true;
        let isParentescoValid = true;

        const familyOption = this.$('input[name="familyOptions"]:checked').val();

        if (familyOption === 't') {
            isNombreValid = this._validateField('#hr-nombre-completo');
            isRelationValid = this._validateField('input[name="relationType"]');

            const relation = this.$('input[name="relationType"]:checked').val();

            if (relation === 'familiar') {
                isParentescoValid = this._validateField('#hr-parentesco');
            }
        }

        if (
            !isStudyValid ||
            !experienceValidation.isValid ||
            !educationValidation.isValid ||
            !isFamilyOptionValid ||
            !isNombreValid ||
            !isRelationValid ||
            !isParentescoValid
        ) {
            alert("Complete todos los campos obligatorios");
            return false;
        }

        return true;
    },
    
    _validateExperienceBlocks() {
        const experienceBlocks = this.$('#experience_container input, #experience_container select, #experience_container textarea');
        let allValid = true;

        experienceBlocks.each((index, block) => {
            const $field = $(block);

            if (!$field.is(':visible') || $field.prop('disabled')) return;

            let fieldValid = true;

            if (block.type === 'date') {
                fieldValid = this._validateDateField(`#${block.id}`);
            } else {
                fieldValid = this._validateField(`#${block.id}`);
            }

            if (!fieldValid) {
                allValid = false;
            }
        });

        return {
            isValid: allValid,
        };
    },
    
    _validateEducationBlocks() {
        const educationBlocks = this.$('#education_container input, #education_container select');
        let allValid = true;

        educationBlocks.each((index, block) => {
            const $field = $(block);

            if (!$field.is(':visible') || $field.prop('disabled')) return;

            let fieldValid = true;

            if (block.type === 'date') {
                fieldValid = this._validateDateField(`#${block.id}`);
            } else {
                fieldValid = this._validateField(`#${block.id}`);
            }

            if (!fieldValid) {
                allValid = false;
            }
        });

        return {
            isValid: allValid,
        };
    },

    _validateFamilyDisability(familyIndex) {
        const $radio = this.$(`input[name="famDisc_${familyIndex}"]`);
        const selected = $radio.filter(':checked').val();
        const $detail = this.$(`input[name="famDiscTipo_${familyIndex}"]`);

        if (selected === 'si') {
            $detail.prop('disabled', false);
            $detail.prop('required', true);

            if (!$detail.val()) {
                $detail.addClass('is-invalid');
            } else {
                $detail.removeClass('is-invalid');
            }

        } else {
            $detail.prop('disabled', true);
            $detail.prop('required', false);
            $detail.val('');
            $detail.removeClass('is-invalid');
        }

        $radio.toggleClass('is-invalid', !selected);
    },

    _validateFamilyFields(index) {
        let isValid = true;

        const fields = [
            `input[name="famNombre_${index}"]`,
            `input[name="famCedula_${index}"]`,
            `input[name="famFecha_${index}"]`,
            `input[name="famTelefono_${index}"]`,
            `input[name="famOcupacion_${index}"]`
        ];

        fields.forEach(selector => {
            const $field = this.$(selector);
            const valid = !!$field.val();

            $field.toggleClass('is-invalid', !valid);

            if (!valid) isValid = false;
        });

        const depende = this.$(`input[name="famDepende_${index}"]:checked`).val();
        this.$(`input[name="famDepende_${index}"]`).toggleClass('is-invalid', !depende);
        if (!depende) isValid = false;

        const disc = this.$(`input[name="famDisc_${index}"]:checked`).val();
        this.$(`input[name="famDisc_${index}"]`).toggleClass('is-invalid', !disc);
        if (!disc) isValid = false;

        const $tipo = this.$(`input[name="famDiscTipo_${index}"]`);
        if (disc === 'si') {
            const validTipo = !!$tipo.val();
            $tipo.toggleClass('is-invalid', !validTipo);
            if (!validTipo) isValid = false;
        } else {
            $tipo.removeClass('is-invalid');
        }

        return isValid;
    },

    // Métodos de validación individuales

    _validateField(ev) {
        const selector = ev && ev.currentTarget ? `#${ev.currentTarget.id}` : arguments[0];
        const $field = this.$(selector);

        if (!$field.length) return true;

        if ($field.prop('disabled')) {
            $field.removeClass('is-invalid');
            return true;
        }

        if (!$field.is(':visible')) {
            $field.removeClass('is-invalid');
            return true;
        }

        if ($field.is('select')) {
            const isValid = $field.val() !== "" && $field.val() !== null;
            $field.toggleClass('is-invalid', !isValid);
            return isValid;
        }

        if ($field.is('[type="radio"]')) {
            const radioName = $field.attr('name');
            const isRadioValid = !!this.$(`input[name="${radioName}"]:checked`).val();
            this.$(`input[name="${radioName}"]`).toggleClass('is-invalid', !isRadioValid);
            return isRadioValid;
        }

        if ($field.is('[type="checkbox"]')) {
            const name = $field.attr('name');
            const $group = this.$(`input[name="${name}"]`);
            const isValid = $group.is(':checked');
            $group.toggleClass('is-invalid', !isValid);

            return isValid;
        }

        const isValid = !!$field.val();

        if (isValid && $field[0].files && $field[0].files.length > 0) {
            const $curriculumName = this.$('#file-selected-message');
            const curriculum = $field[0].files[0].name;
            $curriculumName.text(_t(curriculum + ' ✓')).show();
        }

        $field.toggleClass('is-invalid', !isValid);
        return isValid;
    },

    _validateImage: function(ev) {
        const input = ev ? ev.currentTarget : document.getElementById('hr-perfil');
        const errorDiv = document.getElementById('image-error');
        const preview = document.getElementById('preview-img');
        const textImg = document.getElementById('text-img');

        if (!input) return true;

        const file = input.files[0];

        if (!file) {
            errorDiv.textContent = "Debe subir una foto de perfil.";
            errorDiv.style.display = "block";
            input.classList.add("is-invalid");

            if (preview) preview.style.display = "none";
            if (textImg) textImg.style.display = "block";

            return false;
        }
        errorDiv.textContent = "";
        errorDiv.style.display = "none";
        input.classList.remove("is-invalid");

        if (preview) {
            preview.src = URL.createObjectURL(file);
            preview.style.display = "block";
        }

        if (textImg) {
            textImg.style.display = "none";
        }

        return true; 
    },

    _validateEmail() {
        const $email = this.$('#hr-email');
        const $error = this.$('#email-error');
        const email = $email.val().trim();

        if (!email) {
            $error.text(_t("El correo es obligatorio.")).show();
            $email.addClass('is-invalid');
            return false;
        }

        const isValid = this._isValidEmail(email);

        if (!isValid) {
            $error.text(_t("Correo no válido.")).show();
        } else {
            $error.hide();
        }

        $email.toggleClass('is-invalid', !isValid);
        return isValid;
    },

    _validatePhone() {
        const $error = this.$('#cell-error');
        const $phone = this.$('#hr-cellphone');
        const phone = $phone.val();

        if(phone === '') {
            $error.text(_t("Campo obligatorio.")).show();
        }

        const isValid = /^\d{10}$/.test(phone);

        if(!isValid && phone != '') {
            $error.text(_t("Celular no válido.")).show();
        }

        if(isValid) {
            $error.hide();
        }
        
        $phone.toggleClass('is-invalid', !isValid);
        return isValid;
    },

    _validateDynamicPhone(ev) {
        const $field = $(ev.currentTarget);
        const $error = $field.closest('div').find('.error-message'); 
        const phone = $field.val();

        if (phone.trim() === '') {
            $error.text(_t("Campo obligatorio.")).show();
            $field.addClass('is-invalid');
            return false;
        }

        const isValid = /^\d{10}$/.test(phone);

        if (!isValid) {
            $error.text(_t("Teléfono no válido.")).show();
            $field.addClass('is-invalid');
            return false;
        }

        $error.hide();
        $field.removeClass('is-invalid');
        return true;
    },

    _validateDocumentNumber() {
        const $error = this.$('#doc-error');
        const $docNumber = this.$('#hr-number-doc');
        const docNumber = $docNumber.val();

        if(docNumber === '') {
            $error.text(_t("Campo obligatorio.")).show();
        }

        const isValid = /^\d{10}$/.test(docNumber);

        if(!isValid && docNumber != '') {
            $error.text(_t("Documento no válido.")).show();
        }

        if(isValid) {
            $error.hide();
        }
        
        $docNumber.toggleClass('is-invalid', !isValid);
        return isValid;
    },

    _validateFamilyCedula(ev) {
        const $field = $(ev.currentTarget);
        const $error = $field.siblings('.error-message');
        const cedula = $field.val();

        if (cedula === '') {
            $error.text(_t("Campo obligatorio.")).show();
            $field.addClass('is-invalid');
            return false;
        }

        const isValid = /^\d{10}$/.test(cedula);

        if (!isValid) {
            $error.text(_t("Cédula no válida.")).show();
            $field.addClass('is-invalid');
            return false;
        }

        $error.hide();
        $field.removeClass('is-invalid');
        return true;
    },

    _validateCodePhone() {
        const codPhone = this.$('#hr-code-cellphone').val();

        const isValid = codPhone !== "código";

        this.$('#hr-code-cellphone').toggleClass('is-invalid', !isValid);
        return isValid
    },

    _validateBirthDate() {
        const day = this.$('#hr-day').val();
        const month = this.$('#hr-month').val();
        const year = this.$('#hr-year').val();
        
        const isValid = day !== "Dia" && month !== "Mes" && year !== "Año";
        
        this.$('#hr-day, #hr-month, #hr-year').toggleClass('is-invalid', !isValid);
        return isValid;
    },

    _validateDateField(field) {
        const $field = field instanceof jQuery ? field : $(field);
        const value = $field.val();
        const $errorMessage = $field.siblings('.invalid-feedback');

        if (!value) {
            $field.addClass('is-invalid');
            $errorMessage.text('Campo obligatorio.').show();
            return false;
        }

        const regex = /^\d{4}-\d{2}-\d{2}$/;
        if (!regex.test(value)) {
            $field.addClass('is-invalid');
            $errorMessage.text('Campo no válido.').show();
            return false;
        }

        const date = new Date(value);
        if (isNaN(date.getTime())) {
            $field.addClass('is-invalid');
            $errorMessage.text('Campo no válido.').show();
            return false;
        }

        const year = date.getFullYear();
        const currentYear = new Date().getFullYear();
        if (year < 1900 || year > currentYear) {
            $field.addClass('is-invalid');
            $errorMessage.text('Campo no válido.').show();
            return false;
        }

        $field.removeClass('is-invalid');
        $errorMessage.hide();
        return true;
    },

    _validateFamilyDate(ev) {
        const $field = $(ev.currentTarget);
        const value = $field.val();

        const $errorMessage = $field.siblings('.error-message'); 

        if (!value) {
            $field.addClass('is-invalid');
            if ($errorMessage.length) {
                $errorMessage.text('Campo obligatorio').show();
            }
            return false;
        }

        // Caso 2: formato inválido
        const regex = /^\d{4}-\d{2}-\d{2}$/;
        if (!regex.test(value)) {
            $field.addClass('is-invalid');
            if ($errorMessage.length) {
                $errorMessage.text('Campo no válido').show();
            }
            return false;
        }

        const date = new Date(value);
        if (isNaN(date.getTime())) {
            $field.addClass('is-invalid');
            if ($errorMessage.length) {
                $errorMessage.text('Campo no válido').show();
            }
            return false;
        }

        const today = new Date();
        if (date > today) {
            $field.addClass('is-invalid');
            if ($errorMessage.length) {
                $errorMessage.text('Campo no válido').show();
            }
            return false;
        }

        $field.removeClass('is-invalid');
        if ($errorMessage.length) {
            $errorMessage.hide();
        }
        return true;
    },

    _validateReferenceField(ev) {
        const $field = $(ev.currentTarget);
        const $error = $field.siblings('.error-message'); 
        const value = $field.val();

        if (value.trim() === '') {
            $error.text("Campo obligatorio").show();
            $field.addClass('is-invalid');
            return false;
        }

        $error.hide();
        $field.removeClass('is-invalid');
        return true;
    },

    _validateTipoSangre: function(ev) {
        const $field = $(ev.currentTarget);
        const value = $field.val();

        if (value === '') {
            $field.addClass('is-invalid');
            return false;
        }

        $field.removeClass('is-invalid');
        return true;
    },

    _toggleStudyFields() {
        const value = this.$('input[name="studyOptions"]:checked').val();
        const isStudying = value === 't';

        const fields = [
            'input[name="titulo_por_obtener"]',
            'input[name="institucion"]',
            'input[name="horario"]',
            'input[name="carrera"]',
            'input[name="estado"]'
        ];

        fields.forEach(selector => {
            const $field = this.$(selector);

            $field.prop('disabled', !isStudying);
            $field.prop('required', isStudying);

            if (!isStudying) {
                $field.val('');
            }

            $field.removeClass('is-invalid');
        });
    },

    _toggleJobDisabilityFields() {

        const value = this.$('input[name="jobOptions"]:checked').val();

        const $percentage = this.$('#hr-disc-percentage');
        const $type = this.$('#hr-disc-type');

        if (value === 'f') {

            $percentage.prop('disabled', true);
            $type.prop('disabled', true);

            $percentage.val('');
            $type.val('');

            $percentage.removeClass('is-invalid');
            $type.removeClass('is-invalid');

        } else {

            $percentage.prop('disabled', false);
            $type.prop('disabled', false);

        }
    }, 
    

    _toggleFamilyKnownFields() {
        const value = this.$('input[name="knownPosee_1"]:checked').val();
        const hasFamily = value === 't';

        const $nombre = this.$('input[name="knownNombre_1"]');
        const $relacion = this.$('input[name="knownRelacion_1"]');
        const $parentesco = this.$('input[name="knownParentesco_1"]');

        if (hasFamily) {
            $nombre.prop('disabled', false).prop('required', true);
            $relacion.prop('disabled', false).prop('required', true);
        } else {
            $nombre.prop('disabled', true).prop('required', false).val('');
            $relacion.prop('disabled', true).prop('required', false).prop('checked', false);
            $parentesco.prop('disabled', true).prop('required', false).val('');
            $parentesco.removeClass('is-invalid');
        }
    },

    _toggleParentescoField() {
        const relation = this.$('input[name="knownRelacion_1"]:checked').val();
        const $parentesco = this.$('input[name="knownParentesco_1"]');

        if (relation === 'familiar') {
            $parentesco.prop('disabled', false).prop('required', true);
        } else {
            $parentesco.prop('disabled', true).prop('required', false);
            $parentesco.val('');
            $parentesco.removeClass('is-invalid');
        }
    },

    _toggleDisabilityFields: function() {
        const value = this.$('input[name="discapacidad"]:checked').val();
        const tipo = this.$('input[name="tipo_discapacidad"]');
        const porcentaje = this.$('input[name="porcentaje_discapacidad"]');

        if (value === 'no') {
            tipo.prop('disabled', true).val('');
            porcentaje.prop('disabled', true).val('');
        } else {
            tipo.prop('disabled', false);
            porcentaje.prop('disabled', false);
        }
    },

    _onChangeCountry(ev) {
        const countryId = $(ev.currentTarget).val();
        const $province = this.$('#hr-provincia');


        $province.val('');
        $province.removeClass('is-invalid');
        $province.find('option').each(function () {
            const optionCountry = $(this).data('country');

            if (!optionCountry) {
                $(this).show(); 
            } else if (optionCountry == countryId) {
                $(this).show();
            } else {
                $(this).hide();
            }
        });
    },


    _isValidEmail(email) {
        return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
    },

    _scrollToFirstError() {
        const $firstError = this.$('.is-invalid').first();
        if ($firstError.length) {
            $('html, body').animate({
                scrollTop: $firstError.offset().top - 100
            }, 500);
        }
    },

    //----------------------------------------------------------------------
    // Handlers
    //----------------------------------------------------------------------

    _onNextStep2(ev) {
        ev.preventDefault();

        if (this._validateCurrentStep2()) {
            this.$('#form-step-2').addClass('d-none');
            this.$('#form-step-3').removeClass('d-none');
        }
    },

    _onNextClick(ev) {
        ev.preventDefault();

        if (this._validateCurrentStep1()) {
            this.$('#form-step-1').addClass('d-none');
            this.$('#form-step-2').removeClass('d-none');
        }
    },

    _onPrevClick(ev) {
        ev.preventDefault();

        this.$('#form-step-3').addClass('d-none');
        this.$('#form-step-2').removeClass('d-none');
    },


    // Método de envío actualizado
    _onSubmitForm(ev) {
        ev.preventDefault();

        if (!this._validateCurrentStep3()) return;

        this.$('#submit-form')
            .prop('disabled', true)
            .text('Enviando...');

        this.el.submit();
    },

    //----------------------------------------------------------------------
    // Methods education
    //----------------------------------------------------------------------

    async _addEducationBlock() {
        const newBlock = await this._getEducationBlock(true);
        this.$('#education_container').append(newBlock);

        this.$('#education_container').find('.remove-education').last().on('click', (ev) => {
            $(ev.target).closest('.education-block').remove();
            this.educationCount--;
            this.$('#total_educations').val(this.educationCount);
            this._checkEducationFieldsFilled();
        });
        
        this._checkEducationFieldsFilled();
    },

    async _addFamilyBlock() {
        this.familyCount++;

        const html = await this._getFamilyBlock();
        this.$('#family_container').append(html);
    },

    async _onAddEducation(ev) {
        ev.preventDefault();
        this.educationCount++;
        const newBlock = await this._getEducationBlock(false);
        this.$('#education_container').prepend(newBlock);
        this.$('#total_educations').val(this.educationCount);
        
        // Resetear validación
        this.$('#add-education').css({
            'opacity': '0.5',
            'pointer-events': 'none'
        });
    },

    _checkEducationFieldsFilled() {
        const $inputs = this.$('#education_container').find('input:not(:disabled), select:not(:disabled)');
        let allFilled = true;

        $inputs.each(function () {
            const $input = $(this);

            if (!$input.is(':visible')) return;

            if ($input.is('select') && $input.prop('selectedIndex') === 0) {
                allFilled = false;
                return false;
            }

            if (!$input.is('select') && $input.val().trim() === '') {
                allFilled = false;
                return false;
            }
        });

        this.$('#add-education').css({
            'opacity': allFilled ? '1' : '0.5',
            'pointer-events': allFilled ? 'auto' : 'none'
        });
    },

    //----------------------------------------------------------------------
    // Methods experience job
    //----------------------------------------------------------------------

    async _addExperienceBlock() {
        const newBlock = await this._getExperienceBlock(true);
        this.$('#experience_container').append(newBlock);
        
        // Manejar el botón de eliminar
        this.$('#experience_container').find('.remove-experience').last().on('click', (ev) => {
            $(ev.target).closest('.education-block').remove();
            this._checkFieldsFilled();
        });
        
        this._checkFieldsFilled();
    },

    async _onAddExperience(ev) {
        ev.preventDefault();
        this.experienceCount++;
        const newBlock = await this._getExperienceBlock(false);
        this.$('#experience_container').prepend(newBlock);
        this.$('#total_experiences').val(this.experienceCount);
        
        // Resetear validación
        this.$('#add-experience').css({
            'opacity': '0.5',
            'pointer-events': 'none'
        });
    },

    async _addReferenceBlock() {
        this.referenceCount++;

        // Si es el primer bloque, pasamos true como parámetro
        const newBlock = await this._getReferenceBlock(this.referenceCount === 1);
        this.$('#reference_container').append(newBlock);

        // Actualizar contador en el input hidden
        this.$('#total_references').val(this.referenceCount);

        // Validación de campos requeridos
        this.$('#reference_container')
            .find('.reference-block')
            .last()
            .find('input[required]')
            .on('blur', (ev) => this._validateReferenceField(ev));

        // Acción para eliminar el bloque
        this.$('#reference_container')
            .find('.remove-reference')
            .last()
            .on('click', (ev) => {
                $(ev.currentTarget).closest('.reference-block').remove();
                this.referenceCount--;
                this.$('#total_references').val(this.referenceCount);
            });
    },

    async _onAddReference(ev) {
        ev.preventDefault();
        await this._addReferenceBlock();
    },

    _checkFieldsFilled() {
        const $inputs = this.$('#experience_container').find('input:not(:disabled), select:not(:disabled), textarea:not(:disabled)');
        let allFilled = true;

        $inputs.each(function () {
            const $input = $(this);

            if (!$input.is(':visible')) return;

            if ($input.is('select') && $input.prop('selectedIndex') === 0) {
                allFilled = false;
                return false;
            }

            if (!$input.is('select') && $input.val().trim() === '') {
                allFilled = false;
                return false;
            }
        });

        this.$('#add-experience').css({
            'opacity': allFilled ? '1' : '0.5',
            'pointer-events': allFilled ? 'auto' : 'none'
        });
    }


});
