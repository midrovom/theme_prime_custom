/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import { _t } from "@web/core/l10n/translation";

const YEARS = Array.from({ length: 2026 - 1900 }, (_, i) => i + 1900);
const optionsYears = YEARS.map(year => `<option value="${year}">${year}</option>`).join("");

let cachedCountries = null;
let cachedStatesByCountry = {};

const DOCUMENT_TYPES = [
    ['cedula', 'Cédula'],
    ['id_extrj', 'Cédula extranjera'],
    ['pasaporte', 'Pasaporte'],
    ['part_naci', 'Partida de Nacimiento'],
];

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
        'click #prev-button-2': '_onPrevClickStep2',
        'submit': '_onSubmitForm',
        'click #add-experience': '_onAddExperience',
        'click .remove-experience': '_onRemoveExperience',
        'click #add-reference': '_onAddReference',
        'click .remove-family': '_onRemoveFamily',
        'click #add-education': '_onAddEducation',
        'click #add-family': '_addFamilyBlock',
        'click .family-btn': '_onSelectFamily',

        'change #hr-perfil': '_validateImage',

        'input #experience_container input, #experience_container select, #experience_container textarea': '_checkFieldsFilled',
        'change #experience_container input, #experience_container select, #experience_container textarea': '_checkFieldsFilled',

        'input #education_container input, #education_container select': '_checkEducationFieldsFilled',
        'input input[name^="famTelefono_"]': '_validateDynamicPhone',
        'input input[name^="telefonos_"]': '_validateDynamicPhone',
        'input input[name^="ref_telefono_"]': '_validateDynamicPhone',
        'input input[name="titulo_por_obtener"], input[name="institucion_2"], input[name="horario"], input[name="carrera"], input[name="estado"]': '_validateStudyBlock',
        'input input[name="detalle_enfermedad_persistente"]': function() {this._validateHealthGroup('enfermedad_persistente','detalle_enfermedad_persistente');},
        'input input[name="detalle_medicacion_continua"]': function() {this._validateHealthGroup('medicacion_continua','detalle_medicacion_continua');},
        'input input[name="detalle_enfermedad_laboral"]': function() {this._validateHealthGroup('enfermedad_laboral','detalle_enfermedad_laboral');},
        'input input[name="detalle_cirugia_realizada"]': function() {this._validateHealthGroup('cirugia_realizada','detalle_cirugia_realizada');},

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
        'blur input[name^="famCedula_"]': '_validateDocumentNumber',
        'blur input[name^="famOcupacion_"]': '_validateReferenceField',
        'blur input[name^="famDepende_"]': '_validateReferenceField',
        'blur input[name^="famDisc_"]': '_validateReferenceField',
        'blur input[name^="inicioEstudio_"]': function(ev) { this._validateDateField(ev.currentTarget);},
        'blur input[name^="jobInicio_"]': function(ev) {this._validateDateField(ev.currentTarget);},
        'blur input[name="tipo_sangre"]': '_validateTipoSangre',

        'change input[name="studyOptions"]': '_toggleStudyFields',
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
        'change input[name="viveCon"], input[name="tipoVivienda"], input[name="estadoCivil"]': '_validateField',
        'change input[name="jobOptions"], input[name="discOptions"], #policy': '_validateField',
        'change input[name="studyOptions"]': '_toggleStudyFields',
        'change input[name="jobOptions"]': '_toggleJobDisabilityFields',
        'change input[name="enfermedad_persistente"]': function() { this._validateHealthGroup('enfermedad_persistente','detalle_enfermedad_persistente');},
        'change input[name="medicacion_continua"]': function() {this._validateHealthGroup('medicacion_continua','detalle_medicacion_continua');},
        'change input[name="enfermedad_laboral"]': function() {this._validateHealthGroup('enfermedad_laboral','detalle_enfermedad_laboral');},
        'change input[name="cirugia_realizada"]': function() {this._validateHealthGroup('cirugia_realizada','detalle_cirugia_realizada');},
        'change #curriculum-vitae': '_onFileSelected',
        'change select[name^="famTipoDoc_"]': '_validateField',
        'change select[name^="famTipoDoc_"]': '_onChangeFamilyDocType',
        'change input[name^="famArchivo_"]': '_validateFamilyFile',
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
        this.uploadedFiles = [];
    },

    /**
     * @override
     */
    start() {
        
        this._initializeForm();
        this._addExperienceBlock();
        this._addEducationBlock();
        for (let i = 0; i < 3; i++) {
            this._addReferenceBlock();
        }
        this._toggleStudyFields(); 
        this._toggleDisabilityFields();
        this._toggleFamilyKnownFields();
        this._toggleParentescoField();
        this._toggleJobDisabilityFields();
        this._onChangeCountry({ currentTarget: this.$('#hr-country') });
        this.$('input[name="knownPosee_1"]').on('change', () => {
            this._toggleFamilyKnownFields();
        });

        this.$('input[name="knownNombre_1"]').on('input', (ev) => {
            const $f = $(ev.currentTarget);
            $f.toggleClass('is-invalid', !$f.val().trim());
        });

        this.$('input[name="knownRelacion_1"]').on('change', () => {
            this._toggleParentescoField();
            this.$('input[name="knownRelacion_1"]').removeClass('is-invalid');
        });

        this.$('input[name="knownParentesco_1"]').on('input', (ev) => {
            const $f = $(ev.currentTarget);
            $f.toggleClass('is-invalid', !$f.val().trim());
        });

        this.$('input[name="studyOptions"]').on('change', () => {
            this.$('input[name="studyOptions"]').removeClass('is-invalid');
        });

        // NUEVO: controlar hijos automáticamente
        this.$('#hr-hijos').on('input change', async (ev) => {
            const numHijos = parseInt(ev.currentTarget.value, 10);
            this.$('.family-block[data-type="Hijo"]').remove();
            if (!isNaN(numHijos) && numHijos > 0) {
                for (let i = 0; i < numHijos; i++) {
                    this.familyCount++;
                    const blockHtml = await this._getFamilyBlock("Hijo");
                    this.$('#family_container').append(blockHtml);
                    const index = this.familyCount;
                    this.$(`input[name="famDisc_${index}"]`).on('change', () => {
                        this._toggleFamilyDisability(index);
                    });
                }
            }
        });

        this.$('#total_experiences').on('input change', async (ev) => {
            let num = parseInt($(ev.currentTarget).val(), 10);
            this.$('#experience_container').empty();
            this.experienceCount = 0;

            if (!isNaN(num) && num > 0) {
                for (let i = 0; i < num; i++) {
                    this.experienceCount++;
                    const newBlock = await this._getExperienceBlock(false);
                    this.$('#experience_container').append(newBlock);
                }
            }

            this._checkFieldsFilled();
        });


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

    async _getFamilyBlock(parentesco) {
        const block = `
            <div class="row d-flex justify-content-center family-block" data-type="${parentesco}">
                <div class="col-12 col-md-10">
                    <div class="py-3 d-flex justify-content-start mb-3">
                        <span class="fw-normal fs-4 text-info">${parentesco}</span>
                    </div>

                    <div class="row g-3">

                        <input type="hidden" name="famTipo_${this.familyCount}" value="${parentesco}"/>
                        
                        <!-- Apellido paterno -->
                        <div class="col-md-3">
                            <label class="fs-6">Apellido paterno <span class="required-asterisk">*</span></label>
                            <input type="text" name="famApellidoPaterno_${this.familyCount}" class="form-control rounded-pill" required/>
                            <div class="invalid-feedback">Campo obligatorio</div>
                        </div>

                        <!-- Apellido materno -->
                        <div class="col-md-3">
                            <label class="fs-6">Apellido materno <span class="required-asterisk">*</span></label>
                            <input type="text" name="famApellidoMaterno_${this.familyCount}" class="form-control rounded-pill" required/>
                            <div class="invalid-feedback">Campo obligatorio</div>
                        </div>

                        <!-- Primer nombre -->
                        <div class="col-md-3">
                            <label class="fs-6">Primer nombre <span class="required-asterisk">*</span></label>
                            <input type="text" name="famPrimerNombre_${this.familyCount}" class="form-control rounded-pill" required/>
                            <div class="invalid-feedback">Campo obligatorio</div>
                        </div>

                        <!-- Segundo nombre -->
                        <div class="col-md-3">
                            <label class="fs-6">Segundo nombre</label>
                            <input type="text" name="famSegundoNombre_${this.familyCount}" class="form-control rounded-pill"/>
                        </div>

                        <input type="hidden" name="famNombre_${this.familyCount}" class="fam-nombre-completo"/>

                        <!-- Tipo de documento -->
                        <div class="col-12 col-md-3">
                            <label for="fam-type-doc_${this.familyCount}" class="fs-6"> Tipo de documento: <span class="text-danger">*</span></label>
                                <select id="fam-type-doc_${this.familyCount}" name="famTipoDoc_${this.familyCount}" class="form-select rounded-pill py-2" aria-label="Seleccionar tipo de documento" required="required">
                                    <option selected="selected"></option>
                                ${DOCUMENT_TYPES.map(doc => `<option value="${doc[0]}">${doc[1]}</option>`).join('')}
                            </select>
                            <div class="invalid-feedback">Seleccione una opción.</div>
                        </div>

                        <!-- Numero de Documento -->
                        <div class="col-md-3">
                            <label class="fs-6">Numero de Documento <span class="required-asterisk">*</span></label>
                            <input type="text" name="famCedula_${this.familyCount}" class="form-control rounded-pill"/>
                            <div class="invalid-feedback">Campo obligatorio</div>
                        </div>

                        <!-- Archivo PDF -->
                        <div class="col-md-3">
                            <label class="fs-6">Adjuntar Documento (PDF) <span class="required-asterisk">*</span></label>
                                <input type="file" name="famArchivo_${this.familyCount}" class="form-control rounded-pill fam-archivo-doc d-none" accept="application/pdf"/>
                            <div class="invalid-feedback">Debe adjuntar un archivo PDF</div>
                        </div>

                        <!-- Fecha -->
                        <div class="col-md-3">
                            <label class="fs-6">Fecha nacimiento <span class="required-asterisk">*</span></label>
                            <input type="date" name="famFecha_${this.familyCount}" class="form-control rounded-pill" required/>
                            <div class="invalid-feedback">Campo obligatorio</div>
                        </div>

                        <!-- Teléfono -->
                        <div class="col-md-3">
                            <label class="fs-6">Teléfono <span class="required-asterisk">*</span></label>
                            <input type="tel" name="famTelefono_${this.familyCount}" class="form-control rounded-pill fam-telefono" required/>
                            <div class="invalid-feedback">Campo obligatorio</div>
                        </div>

                        <!-- Ocupación -->
                        <div class="col-md-3">
                            <label class="fs-6">Ocupación y Empresa <span class="required-asterisk">*</span></label>
                            <input type="text" name="famOcupacion_${this.familyCount}" class="form-control rounded-pill" required/>
                            <div class="invalid-feedback">Campo obligatorio</div>
                        </div>

                        <!-- Depende -->
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
                        </div>

                        <!-- Discapacidad -->
                        <div class="col-md-3">
                            <label class="fs-6">Discapacidad <span class="required-asterisk">*</span></label>

                            <div class="d-flex mt-2">
                                <div class="form-check me-3">
                                    <input class="form-check-input fam-disc-radio" type="radio"
                                        name="famDisc_${this.familyCount}" value="si" required/>
                                    <label class="form-check-label">Sí</label>
                                </div>

                                <div class="form-check">
                                    <input class="form-check-input fam-disc-radio" type="radio"
                                        name="famDisc_${this.familyCount}" value="no" required/>
                                    <label class="form-check-label">No</label>
                                </div>
                            </div>

                            <div class="invalid-feedback d-none fam-disc-error">Campo obligatorio</div>
                        </div>

                        <!-- Tipo discapacidad -->
                        <div class="col-md-3">
                            <label class="fs-6">Tipo de discapacidad</label>
                                <input type="text"name="famDiscTipo_${this.familyCount}" class="form-control rounded-pill fam-disc-tipo" disabled />
                        </div>

                        <div class="col-md-3">
                            <label class="fs-6">Porcentaje de discapacidad</label>
                                <input type="number" name="famDiscPorcentaje_${this.familyCount}" class="form-control rounded-pill fam-disc-porcentaje" min="0" max="100" step="1" disabled/>
                            <div class="invalid-feedback">Ingrese un valor entre 0 y 100</div>
                        </div>

                    </div>

                    <div class="row d-flex justify-content-between">
                        <div class="col-12 mt-3 d-flex justify-content-end">
                            <button type="button" class="btn btn-outline-danger rounded-pill px-4 remove-family">
                                Eliminar
                            </button>
                        </div>
                    </div>

                </div>
            </div>
        `;

        setTimeout(() => {
            const i = this.familyCount;
            const updateFullName = () => {
                const paterno = this.$(`input[name="famApellidoPaterno_${i}"]`).val()?.trim() || "";
                const materno = this.$(`input[name="famApellidoMaterno_${i}"]`).val()?.trim() || "";
                const primer = this.$(`input[name="famPrimerNombre_${i}"]`).val()?.trim() || "";
                const segundo = this.$(`input[name="famSegundoNombre_${i}"]`).val()?.trim() || "";

                const fullName = `${paterno} ${materno} ${primer} ${segundo}`.trim();
                this.$(`input[name="famNombre_${i}"]`).val(fullName);
            };

            this.$(`input[name="famApellidoPaterno_${i}"], 
                    input[name="famApellidoMaterno_${i}"], 
                    input[name="famPrimerNombre_${i}"], 
                    input[name="famSegundoNombre_${i}"]`).on("input blur", function() {
                const $f = $(this);
                if (!$f.val().trim() && $f.prop("required")) {
                    $f.addClass("is-invalid");
                    if ($f.next(".invalid-feedback").length === 0) {
                        $f.after('<div class="invalid-feedback">Campo obligatorio</div>');
                    }
                } else {
                    $f.removeClass("is-invalid");
                }
                updateFullName();
            });

        }, 0);

        return block;

    },

    async _getEducationBlock(isFirstBlock = false) {
        await loadCountriesAndStates();

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

        const optionsStudiesLevels = studiesLevels.map(
            studyLevel => `<option value="${studyLevel.id}">${studyLevel.name}</option>`
        ).join('');

        const block = `
            <div class="row d-flex justify-content-center">
                <div class="col-12 col-md-10">
                    <div class="row d-flex justify-content-between">

                        <!-- Nivel educativo -->
                        <div class="col-12 col-md-4 mb-4">
                            <label class="fs-6">Nivel Educativo:</label>
                            <select id="institucion-educativa_${this.educationCount}" 
                                name="level_id_${this.educationCount}" 
                                class="form-select rounded-pill py-2">
                                <option value=""></option>
                                ${optionsStudiesLevels}
                            </select>
                            <div class="invalid-feedback">Campo obligatorio</div>
                        </div>

                        <!-- Institución -->
                        <div class="col-12 col-md-4 mb-4">
                            <label class="fs-6">Nombre de la institución:</label>
                            <input type="text" 
                                name="institucion_${this.educationCount}" 
                                class="form-control rounded-pill py-2"
                                id="institucion_${this.educationCount}"/>
                            <div class="invalid-feedback">Campo obligatorio</div>
                        </div>

                        <!-- Desde -->
                        <div class="col-12 col-md-4 mb-4">
                            <label class="fs-6">Desde:</label>
                            <input type="date" 
                                name="inicioEstudio_${this.educationCount}" 
                                class="form-control rounded-pill py-2"
                                id="estudio-inicio_${this.educationCount}"/>
                            <div class="invalid-feedback">Campo obligatorio</div>
                        </div>

                        <!-- Hasta -->
                        <div class="col-12 col-md-4 mb-4">
                            <label class="fs-6">Hasta:</label>
                            <select id="estudio-fin_${this.educationCount}" 
                                name="finEstudio_${this.educationCount}" 
                                class="form-select rounded-pill py-2">
                                <option value=""></option>
                            </select>
                            <div class="invalid-feedback">Campo obligatorio</div>
                        </div>

                        <!-- País -->
                        <div class="col-12 col-md-4 mb-4">
                            <label class="fs-6">País:</label>
                            <select id="pais-educacion_${this.educationCount}" 
                                name="paisEducacion_${this.educationCount}" 
                                class="form-select rounded-pill py-2">
                                <option value=""></option>
                                ${cachedCountries.map(country => `
                                    <option value="country-${country.id}" 
                                        ${country.name === 'Ecuador' ? 'selected' : ''}>
                                        ${country.name}
                                    </option>
                                `).join('')}
                            </select>
                            <div class="invalid-feedback">Campo obligatorio</div>
                        </div>

                        <!-- Ciudad -->
                        <div class="col-12 col-md-4 mb-4">
                            <label class="fs-6">Ciudad/Provincia:</label>
                            <select id="ciudad_${this.educationCount}" 
                                name="ciudad_${this.educationCount}" 
                                class="form-select rounded-pill py-2">
                                <option value=""></option>
                                ${cachedStatesByCountry[cachedCountries.find(c => c.name === 'Ecuador').id].map(state => `
                                    <option value="state-${state.id}">
                                        ${state.name}
                                    </option>
                                `).join('')}
                            </select>
                            <div class="invalid-feedback">Campo obligatorio</div>
                        </div>

                        <!-- Título -->
                        <div class="col-12 col-md-4 mb-4">
                            <label class="fs-6">Título Recibido:</label>
                            <input type="text" 
                                name="titulo_${this.educationCount}" 
                                class="form-control rounded-pill py-2"
                                id="titulo_${this.educationCount}"/>
                            <div class="invalid-feedback">Campo obligatorio</div>
                        </div>

                    </div>
                </div>
            </div>
        ` + separator;

        setTimeout(() => {
            const startId = `estudio-inicio_${this.educationCount}`;
            const endId = `estudio-fin_${this.educationCount}`;
            const startInput = document.getElementById(startId);
            const endSelect = document.getElementById(endId);

            if (startInput && endSelect) {
                startInput.addEventListener("change", () => {
                    const startDate = startInput.value;
                    if (startDate) {
                        const startYear = new Date(startDate).getFullYear();
                        const currentYear = new Date().getFullYear();

                        endSelect.innerHTML = "<option value=''></option>";

                        // Recorremos hasta el año anterior al actual
                        for (let year = startYear + 1; year < currentYear; year++) {
                            const opt = document.createElement("option");
                            opt.value = year;
                            opt.textContent = year;
                            endSelect.appendChild(opt);
                        }

                        // Agregamos solo "Presente" en lugar del año actual
                        const presentOpt = document.createElement("option");
                        presentOpt.value = "presente";
                        presentOpt.textContent = "Presente";
                        endSelect.appendChild(presentOpt);
                    }
                });
            }
        }, 0);

        return block;
    },

    async _getExperienceBlock(isFirstBlock = false) {
        await loadCountriesAndStates(); 

        const block = `
            <div class="row d-flex justify-content-center experience-block">
                <div class="col-12 col-md-10">

                    <!-- Separador con numeración -->
                    <div class="separator-education" style="border-top: 2px solid #e0e0e0; position: relative; margin: 20px 0;">
                        <span style="position: absolute; top: -12px; left: 50%; transform: translateX(-50%);
                            background: white; padding: 0 15px; color: #666; font-size: 14px;">
                            Experiencia Laboral # ${this.experienceCount}
                        </span>
                    </div>

                    <div class="row d-flex justify-content-between">

                        <!-- Tiempo que prestó su servicio -->
                        <div class="col-12 col-md-3 mb-4">
                            <label class="fs-6">Tiempo que prestó su servicio:</label>
                            <input id="tiempo_${this.experienceCount}" type="text" name="tiempo_${this.experienceCount}" class="form-control rounded-pill py-2" required/>
                            <div class="invalid-feedback">Campo obligatorio</div>
                        </div>

                        <!-- Nombre de la compañía -->
                        <div class="col-12 col-md-3 mb-4">
                            <label class="fs-6">Nombre de la compañía:</label>
                            <input id="company_${this.experienceCount}" type="text" name="company_${this.experienceCount}" class="form-control rounded-pill py-2" required/>
                            <div class="invalid-feedback">Campo obligatorio</div>
                        </div>

                        <!-- País Experiencia -->
                        <div class="col-12 col-md-3 mb-4">
                            <label class="fs-6">País:</label>
                            <select id="pais-experiencia_${this.experienceCount}" name="paisExperiencia_${this.experienceCount}" class="form-select rounded-pill py-2" required>
                                <option value=""></option> 
                                ${ cachedCountries.map(country => `
                                    <option value="country-${country.id}" ${country.name === 'Ecuador' ? 'selected' : ''}>
                                        ${country.name}
                                    </option>
                                `).join('') }
                            </select>
                            <div class="invalid-feedback">Campo obligatorio</div>
                        </div>

                        <!-- Ciudad/Provincia Experiencia -->
                        <div class="col-12 col-md-3 mb-4">
                            <label class="fs-6">Ciudad/Provincia:</label>
                            <select id="ciudad-experiencia_${this.experienceCount}" name="ciudadExperiencia_${this.experienceCount}" class="form-select rounded-pill py-2" required>
                                <option value=""></option> 
                                ${ cachedStatesByCountry[ cachedCountries.find(c => c.name === 'Ecuador').id].map(state => `
                                    <option value="state-${state.id}">${state.name}</option>
                                `).join('') }
                            </select>
                            <div class="invalid-feedback">Campo obligatorio</div>
                        </div>

                        <!-- Teléfono -->
                        <div class="col-12 col-md-3 mb-4">
                            <label class="fs-6">Teléfono:</label>
                            <input id="telefonos_${this.experienceCount}" type="text" name="telefonos_${this.experienceCount}" class="form-control rounded-pill py-2" required/>
                            <div class="invalid-feedback">Campo obligatorio</div>
                        </div>

                        <!-- Cargo desempeñado -->
                        <div class="col-12 col-md-3 mb-4">
                            <label class="fs-6">Cargo desempeñado:</label>
                            <input id="cargo_${this.experienceCount}" type="text" name="cargo_${this.experienceCount}" class="form-control rounded-pill py-2" required/>
                            <div class="invalid-feedback">Campo obligatorio</div>
                        </div>

                        <!-- Ingreso mensual -->
                        <div class="col-12 col-md-3 mb-4">
                            <label class="fs-6">Ingreso mensual:</label>
                            <input id="ingreso_${this.experienceCount}" type="number" name="ingreso_${this.experienceCount}" class="form-control rounded-pill py-2" required/>
                            <div class="invalid-feedback">Campo obligatorio</div>
                        </div>

                        <!-- Motivo de separación -->
                        <div class="col-12 col-md-3 mb-4">
                            <label class="fs-6">Motivo de separación:</label>
                            <input id="motivo_${this.experienceCount}" type="text" name="motivo_${this.experienceCount}" class="form-control rounded-pill py-2" required/>
                            <div class="invalid-feedback">Campo obligatorio</div>
                        </div>

                        <!-- Nombre de su jefe directo -->
                        <div class="col-12 col-md-3 mb-4">
                            <label class="fs-6">Nombre de su jefe directo:</label>
                            <input id="jefe_${this.experienceCount}" type="text" name="jefe_${this.experienceCount}" class="form-control rounded-pill py-2" required/>
                            <div class="invalid-feedback">Campo obligatorio</div>
                        </div>

                        <!-- Cargo de su jefe directo -->
                        <div class="col-12 col-md-3 mb-4">
                            <label class="fs-6">Cargo de su jefe directo:</label>
                            <input id="cargo-jefe_${this.experienceCount}" type="text" name="cargoJefe_${this.experienceCount}" class="form-control rounded-pill py-2" required/>
                            <div class="invalid-feedback">Campo obligatorio</div>
                        </div>

                        <!-- Fecha de inicio -->
                        <div class="col-12 col-md-3 mb-4">
                            <label class="fs-6">Desde:</label>
                            <input id="job-inicio_${this.experienceCount}" type="date" name="jobInicio_${this.experienceCount}" class="form-control rounded-pill py-2" required/>
                            <div class="invalid-feedback">Campo obligatorio</div>
                        </div>

                        <!-- Año de finalización -->
                        <div class="col-12 col-md-3 mb-4">
                            <label class="fs-6">Hasta:</label>
                            <select id="job-fin_${this.experienceCount}" name="jobFin_${this.experienceCount}" class="form-select rounded-pill py-2" required>
                                <option value=""></option>
                            </select>
                            <div class="invalid-feedback">Campo obligatorio</div>
                        </div>

                        <div class="row d-flex justify-content-between">
                            <div class="col-12 mt-3 d-flex justify-content-end">
                                <button type="button" class="btn btn-outline-danger rounded-pill px-4 remove-experience">
                                    Eliminar
                                </button>
                            </div>
                        </div>

                    </div>
                </div>
            </div>
        `;

        setTimeout(() => {
            const startId = `job-inicio_${this.experienceCount}`;
            const endId = `job-fin_${this.experienceCount}`;
            const startInput = document.getElementById(startId);
            const endSelect = document.getElementById(endId);

            if (startInput && endSelect) {
                startInput.addEventListener("change", () => {
                    const startDate = startInput.value;
                    if (startDate) {
                        const startYear = new Date(startDate).getFullYear();
                        const currentYear = new Date().getFullYear();
                        endSelect.innerHTML = "<option value=''></option>";

                        for (let year = startYear; year < currentYear; year++) {
                            const opt = document.createElement("option");
                            opt.value = year;
                            opt.textContent = year;
                            endSelect.appendChild(opt);
                        }

                        // agregar solo "Presente" en lugar del año actual
                        const presentOpt = document.createElement("option");
                        presentOpt.value = "presente";
                        presentOpt.textContent = "Presente";
                        endSelect.appendChild(presentOpt);
                    }
                });
            }
        }, 0);

        return block;
    },

    _getReferenceBlock() {
        return `
            <div class="row d-flex justify-content-center reference-block">
                <div class="col-12 col-md-10">
                    <div class="separator-education" style="border-top: 2px solid #e0e0e0; position: relative; margin: 20px 0;">
                        <span style="position: absolute; top: -12px; left: 50%; transform: translateX(-50%);
                            background: white; padding: 0 15px; color: #666; font-size: 14px;">
                            Referencia # ${this.referenceCount + 1}
                        </span>
                    </div>

                    <div class="row g-3">
                        <!-- Nombre -->
                        <div class="col-md-4">
                            <label class="fs-6">Nombre completo <span class="required-asterisk">*</span></label>
                            <input type="text" name="ref_nombre_${this.referenceCount}" class="form-control rounded-pill" required/>
                            <div class="invalid-feedback">Campo obligatorio</div>
                        </div>

                        <!-- Teléfono -->
                        <div class="col-md-4">
                            <label class="fs-6">Teléfono <span class="required-asterisk">*</span></label>
                            <input type="tel" name="ref_telefono_${this.referenceCount}" class="form-control rounded-pill" required/>
                            <div class="invalid-feedback">Campo obligatorio</div>
                        </div>

                        <!-- Ocupación -->
                        <div class="col-md-4">
                            <label class="fs-6">Ocupación <span class="required-asterisk">*</span></label>
                            <input type="text" name="ref_ocupacion_${this.referenceCount}" class="form-control rounded-pill" required/>
                            <div class="invalid-feedback">Campo obligatorio</div>
                        </div>

                        <!-- Tiempo de conocimiento -->
                        <div class="col-md-4">
                            <label class="fs-6">Tiempo de conocimiento <span class="required-asterisk">*</span></label>
                            <input type="text" name="ref_tiempo_${this.referenceCount}" class="form-control rounded-pill" required/>
                            <div class="invalid-feedback">Campo obligatorio</div>
                        </div>

                        <!-- Domicilio -->
                        <div class="col-md-4">
                            <label class="fs-6">Domicilio <span class="required-asterisk">*</span></label>
                            <input type="text" name="ref_domicilio_${this.referenceCount}" class="form-control rounded-pill" required/>
                            <div class="invalid-feedback">Campo obligatorio</div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    },

    // función para mostrar archivos seleccionados

    _onFileSelected: function(ev) {

        const input = ev.currentTarget;
        const newFiles = Array.from(input.files);
        const container = document.getElementById("file-selected-message");

        if (!this.uploadedFiles) {
            this.uploadedFiles = [];
        }

        const invalidFiles = newFiles.filter(file => {
            return file.type !== "application/pdf" &&
                !file.name.toLowerCase().endsWith(".pdf");
        });

        if (invalidFiles.length > 0) {
            container.innerHTML = `
                <div class="text-danger custom-message fs-6">
                    Solo se permiten archivos PDF.
                </div>
            `;

            input.value = "";
            return;
        }

        this.uploadedFiles = this.uploadedFiles.concat(newFiles);
        this.uploadedFiles = this.uploadedFiles.filter(
            (file, index, self) =>
                index === self.findIndex(f => f.name === file.name)
        );

        this._refreshFileInput(input);
        this._renderFileList(container, input);
    },

    _refreshFileInput: function(input) {
        const dataTransfer = new DataTransfer();
        this.uploadedFiles.forEach(file => {
            dataTransfer.items.add(file);
        });
        input.files = dataTransfer.files;
    },

    _renderFileList: function(container, input) {

        container.innerHTML = "";
        if (this.uploadedFiles.length === 0) {
            container.innerHTML = `
                <div class="text-danger custom-message fs-6">
                    No se seleccionó ningún archivo
                </div>
            `;

            return;
        }

        this.uploadedFiles.forEach((file, index) => {
            const fileItem = document.createElement("div");
            fileItem.className = "d-flex align-items-center justify-content-between border rounded-pill px-3 py-2 mb-2";
            fileItem.innerHTML = `
                <span class="text-success">
                    ${file.name}
                </span>
                <button type="button"
                        class="btn btn-sm btn-danger remove-file"
                        data-index="${index}">
                    ×
                </button>
            `;

            container.appendChild(fileItem);
        });

        // Eventos eliminar
        container.querySelectorAll(".remove-file").forEach(button => {
            button.addEventListener("click", (e) => {
                const index = parseInt(e.currentTarget.dataset.index);
                this.uploadedFiles.splice(index, 1);
                this._refreshFileInput(input);
                this._renderFileList(container, input);
            });
        });
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
        const isCurriculumValid = this._validateCurriculum();
        const isDiscapacidadValid = this._validateField('input[name="discapacidad"]');
        let isTipoDiscapacidadValid = true;
        let isPorcentajeDiscapacidadValid = true;

        if (this.$('input[name="discapacidad"]:checked').val() === 'si') {
            isTipoDiscapacidadValid = this._validateField('input[name="tipo_discapacidad"]');
            isPorcentajeDiscapacidadValid = this._validateField('input[name="porcentaje_discapacidad"]');
        }

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
            !isDiscapacidadValid ||
            !isTipoDiscapacidadValid ||
            !isPorcentajeDiscapacidadValid
        ) {
            this._scrollToFirstError();
            return false;
        }

        return true;
    },

    _validateCurrentStep2() {
        const enfermedad = this._validateRadio('enfermedad_persistente');
        const medicacion = this._validateRadio('medicacion_continua');
        const enfermedadLaboral = this._validateRadio('enfermedad_laboral');
        const cirugia = this._validateRadio('cirugia_realizada');
        const discapacidad = this._validateRadio('discapacidad');
        const enfermedadDetalle = this._validateHealthGroup('enfermedad_persistente','detalle_enfermedad_persistente');
        const medicacionDetalle = this._validateHealthGroup('medicacion_continua','detalle_medicacion_continua');
        const enfermedadLaboralDetalle = this._validateHealthGroup('enfermedad_laboral','detalle_enfermedad_laboral');
        const cirugiaDetalle = this._validateHealthGroup('cirugia_realizada','detalle_cirugia_realizada');

        const tipoSangre = this._validateTipoSangre({
            currentTarget: this.$('input[name="tipo_sangre"]')[0]
        });

        let discapacidadExtra = true;
        const discValue = this.$('input[name="discapacidad"]:checked').val();

        if (discValue === 'si') {
            const tipo = this.$('input[name="tipo_discapacidad"]');
            const porcentaje = this.$('input[name="porcentaje_discapacidad"]');

            const tipoValid = !!tipo.val();
            const porcentajeValid = !!porcentaje.val();

            tipo.toggleClass('is-invalid', !tipoValid);
            porcentaje.toggleClass('is-invalid', !porcentajeValid);
        }

        let familyValid = true;

        for (let i = 1; i <= this.familyCount; i++) {
            const valid = this._validateFamilyFields(i);
            if (!valid) {
                familyValid = false;
            }
        }

        if (
            !enfermedad ||
            !medicacion ||
            !enfermedadLaboral ||
            !cirugia ||
            !discapacidad ||
            !enfermedadDetalle ||
            !medicacionDetalle ||
            !enfermedadLaboralDetalle ||
            !cirugiaDetalle ||
            !tipoSangre 
        ) {
            this._scrollToFirstError();
            return false;
        }

        return true;
    },

    _validateRadio(name) {
        const radios = this.$(`input[name="${name}"]`);
        const checked = radios.filter(':checked');
        const isValid = checked.length > 0;

        if (isValid) {
            radios.removeClass('is-invalid');
        } else {
            radios.addClass('is-invalid');
        }

        return isValid;
    },
    _validateHealthQuestions() {
        this._validateHealthGroup('enfermedad_persistente','detalle_enfermedad_persistente');
        this._validateHealthGroup('medicacion_continua','detalle_medicacion_continua');
        this._validateHealthGroup('enfermedad_laboral','detalle_enfermedad_laboral');
        this._validateHealthGroup('cirugia_realizada','detalle_cirugia_realizada');
    },

    _validateHealthGroup(radioName, detailName) {
        const $radios = this.$(`input[name="${radioName}"]`);
        const value = $radios.filter(':checked').val();
        const $detail = this.$(`input[name="${detailName}"]`);

        if (value === 'si') {
            $detail.prop('disabled', false).prop('required', true);

            if (!$detail.val().trim()) {
                $detail.addClass('is-invalid');
            } else {
                $detail.removeClass('is-invalid');
            }

        } else if (value === 'no') {
            $detail.prop('disabled', true)
                .prop('required', false)
                .val('')
                .removeClass('is-invalid');
        }

        this._validateRadio(radioName);

        return true;
    },

    _validateCurrentStep3() {

        const isStudyValid = this._validateRadio('studyOptions');
        const isStudyBlockValid = this._validateStudyBlock();
        const educationValidation = this._validateEducationBlocks();
        const isFamilyOptionValid = this._validateField('input[name="familyOptions"]');
        const knownValid = this._validateKnownBlock();
        const referenceValid = this._validateReferenceBlocks();

        if (
            !isStudyValid ||
            !isStudyBlockValid ||
            !educationValidation.isValid ||
            !isFamilyOptionValid ||
            !knownValid ||
            !referenceValid

        ) {
            this._scrollToFirstError();
            return false;
        }

        return true;
    },
    
    _validateKnownBlock() {
        const hasKnown = this.$('input[name="knownPosee_1"]:checked').val();
        let isValid = true;

        const $nombre = this.$('input[name="knownNombre_1"]');
        const $relacion = this.$('input[name="knownRelacion_1"]');
        const $parentesco = this.$('input[name="knownParentesco_1"]');
        if (!hasKnown) {
            this.$('input[name="knownPosee_1"]').addClass('is-invalid');
            return false;
        } else {
            this.$('input[name="knownPosee_1"]').removeClass('is-invalid');
        }

        if (hasKnown === 'f') {
            $nombre.removeClass('is-invalid');
            $relacion.removeClass('is-invalid');
            $parentesco.removeClass('is-invalid');
            return true;
        }

        if (!$nombre.val().trim()) {
            $nombre.addClass('is-invalid');
            isValid = false;
        } else {
            $nombre.removeClass('is-invalid');
        }

        const relacionVal = this.$('input[name="knownRelacion_1"]:checked').val();
        if (!relacionVal) {
            this.$('input[name="knownRelacion_1"]').addClass('is-invalid');
            isValid = false;
        } else {
            this.$('input[name="knownRelacion_1"]').removeClass('is-invalid');
        }

        if (relacionVal === 'familiar') {
            if (!$parentesco.val().trim()) {
                $parentesco.addClass('is-invalid');
                isValid = false;
            } else {
                $parentesco.removeClass('is-invalid');
            }
        } else {
            $parentesco.removeClass('is-invalid');
        }

        return isValid;
    },
    
    _validateEducationBlocks() {
        const $fields = this.$('#education_container').find('input, select');
        let allValid = true;

        $fields.each((index, block) => {
            const $field = this.$(block);

            if (!$field.is(':visible') || $field.prop('disabled')) return;

            let valid = true;

            if ($field.is('select')) {
                valid = $field.val() && $field.val() !== "";
            } else if ($field.attr('type') === 'date') {
                valid = this._validateDateField($field);
            } else {
                valid = !!$field.val();
            }

            $field.toggleClass('is-invalid', !valid);

            if (!valid) allValid = false;
        });

        return { isValid: allValid };
    },

    _validateStudyBlock() {
        const studyValue = this.$('input[name="studyOptions"]:checked').val();
        let isValid = true;

        const fields = [
            'input[name="titulo_por_obtener"]',
            'input[name="institucion_2"]',
            'input[name="horario"]',
            'input[name="carrera"]',
            'input[name="estado"]',
        ];

        if (studyValue === 'f') {
            fields.forEach(sel => {
                const $f = this.$(sel);
                $f.removeClass('is-invalid');
            });
            return true;
        }

        fields.forEach(sel => {
            const $field = this.$(sel);

            const valid = !!$field.val();

            $field.toggleClass('is-invalid', !valid);

            if (!valid) {
                isValid = false;
            }
        });

        return isValid;
    },

    _validateFamilyFile(ev) {
        const $fileInput = $(ev.currentTarget);
        const file = ev.currentTarget.files[0];
        const ok = !!file && file.type === "application/pdf";
        $fileInput.toggleClass('is-invalid', !ok);
    },

    // _toggleFamilyDisability(i) {
    //     const discValue = this.$(`input[name="famDisc_${i}"]:checked`).val();
    //     const $tipo = this.$(`input[name="famDiscTipo_${i}"]`);
    //     const $porcentaje = this.$(`input[name="famDiscPorcentaje_${i}"]`);
    //     const $errorTipo = $tipo.siblings('.fam-disc-type-error');
    //     const $errorRadio = this.$(`input[name="famDisc_${i}"]`)
    //         .closest('.col-md-3')
    //         .find('.fam-disc-error');

    //     if (discValue === 'si') {
    //         $tipo.prop('disabled', false);
    //         $porcentaje.prop('disabled', false);

    //         if (!$tipo.val().trim()) {
    //             $tipo.addClass('is-invalid');
    //         } else {
    //             $tipo.removeClass('is-invalid');
    //         }

    //         const val = $porcentaje.val();
    //         const isValid = val && !isNaN(val) && val >= 0 && val <= 100;
    //         if (!isValid) {
    //             $porcentaje.addClass('is-invalid');
    //         } else {
    //             $porcentaje.removeClass('is-invalid');
    //         }

    //     } else if (discValue === 'no') {
    //         $tipo.prop('disabled', true)
    //             .val('')
    //             .removeClass('is-invalid');
    //         $porcentaje.prop('disabled', true)
    //             .val('')
    //             .removeClass('is-invalid');

    //         $errorTipo.addClass('d-none');
    //         $errorRadio.addClass('d-none');
    //     }

    //     if (!discValue) {
    //         $errorRadio.removeClass('d-none');
    //     } else {
    //         $errorRadio.addClass('d-none');
    //     }
    // },

    _toggleFamilyDisability(i) {
        const discValue = this.$(`input[name="famDisc_${i}"]:checked`).val();
        const $tipo = this.$(`input[name="famDiscTipo_${i}"]`);
        const $porcentaje = this.$(`input[name="famDiscPorcentaje_${i}"]`);
        const $errorTipo = $tipo.siblings('.fam-disc-type-error');
        const $errorRadio = this.$(`input[name="famDisc_${i}"]`)
            .closest('.col-md-3')
            .find('.fam-disc-error');

        if (discValue === 'si') {
            $tipo.prop('disabled', false).prop('required', true);
            $porcentaje.prop('disabled', false).prop('required', true);
            if (!$tipo.val().trim()) {
                $tipo.addClass('is-invalid');
            } else {
                $tipo.removeClass('is-invalid');
            }

            const val = $porcentaje.val();
            const isValid = val && !isNaN(val) && val >= 0 && val <= 100;
            if (!isValid) {
                $porcentaje.addClass('is-invalid');
            } else {
                $porcentaje.removeClass('is-invalid');
            }

        } else if (discValue === 'no') {
            $tipo.prop('disabled', true)
                .prop('required', false)
                .val('')
                .removeClass('is-invalid');
            $porcentaje.prop('disabled', true)
                .prop('required', false)
                .val('')
                .removeClass('is-invalid');

            $errorTipo.addClass('d-none');
            $errorRadio.addClass('d-none');
        }

        if (!discValue) {
            $errorRadio.removeClass('d-none');
        } else {
            $errorRadio.addClass('d-none');
        }
    },

    _validateFamilyFields(i) {
        let valid = true;

        const requiredFields = [
            `famApellidoPaterno_${i}`,
            `famApellidoMaterno_${i}`,
            `famPrimerNombre_${i}`,
            `famSegundoNombre_${i}`, 
            `famNombre_${i}`,
            `famCedula_${i}`,
            `famFecha_${i}`,
            `famTelefono_${i}`,
            `famOcupacion_${i}`,
            `famDepende_${i}`,
            `famDisc_${i}`,
            `famArchivo_${i}`   // campo archivo PDF
        ];

        requiredFields.forEach(name => {
            const $group = this.$(`input[name="${name}"]`);
            const isRadio = $group.length && $group.first().attr('type') === 'radio';
            const isFile = $group.length && $group.first().attr('type') === 'file';

            let ok;

            if (isRadio) {
                ok = $group.filter(':checked').length > 0;
                $group.removeClass('is-invalid');
                if (!ok) {
                    $group.addClass('is-invalid');
                    valid = false;
                }
            } else if (isFile) {
                const file = $group[0].files[0];
                ok = !!file && file.type === "application/pdf";
                $group.removeClass('is-invalid');
                if (!ok) {
                    $group.addClass('is-invalid');
                    valid = false;
                }
            } else {
                const $el = this.$(`[name="${name}"]`);
                ok = !!$el.val()?.toString().trim();
                $el.toggleClass('is-invalid', !ok);
                if (!ok) valid = false;
            }
        });

        const discValue = this.$(`input[name="famDisc_${i}"]:checked`).val();
        const $tipo = this.$(`input[name="famDiscTipo_${i}"]`);
        const $porcentaje = this.$(`input[name="famDiscPorcentaje_${i}"]`);

        if (discValue === 'si') {
            const okTipo = !!$tipo.val()?.trim();
            $tipo.toggleClass('is-invalid', !okTipo);
            if (!okTipo) valid = false;

            const valPorcentaje = $porcentaje.val();
            const okPorcentaje = valPorcentaje && !isNaN(valPorcentaje) && valPorcentaje >= 0 && valPorcentaje <= 100;
            $porcentaje.toggleClass('is-invalid', !okPorcentaje);
            if (!okPorcentaje) valid = false;

        } else {
            $tipo.removeClass('is-invalid');
            $porcentaje.removeClass('is-invalid');
        }

        return valid;
    },

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

    // Nuevo metodo para obligar a llenar la informacion dentro del campo
    _validateCurriculum() {
        const $input = this.$('#curriculum-vitae');
        const $container = this.$('#file-selected-message');

        const hasFiles = this.uploadedFiles && this.uploadedFiles.length > 0;

        if (!hasFiles) {
            $input.addClass('is-invalid');

            $container.html(`
                <div class="text-danger custom-message fs-6">
                    Campo obligatorio. Debe seleccionar al menos un archivo PDF.
                </div>
            `);

            return false;
        }

        $input.removeClass('is-invalid');

        // Verificar que todos los archivos sean PDF
        const invalidFiles = this.uploadedFiles.filter(file => {
            return file.type !== "application/pdf" &&
                !file.name.toLowerCase().endsWith(".pdf");
        });

        if (invalidFiles.length > 0) {
            $input.addClass('is-invalid');

            $container.html(`
                <div class="text-danger custom-message fs-6">
                    Solo se permiten archivos PDF.
                </div>
            `);

            return false;
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

    _validateDocumentNumber(ev) {
        const $input = ev ? $(ev.currentTarget) : this.$('#hr-number-doc');
        const value = $input.val().trim();
        const familyIndex = $input.attr("name").split("_")[1];
        let type;

        if ($input.attr("name").startsWith("famCedula_")) {
            type = this.$(`#fam-type-doc_${familyIndex}`).val();
        } else {
            type = this.$('#hr-type-doc').val();
        }

        let isValid = true;
        let errorMsg = '';

        function isValidEcuadorianId(cedula) {
            cedula = (cedula || '').replace(/\D/g, '');
            if (cedula.length !== 10) return false;
            const province = parseInt(cedula.substring(0, 2), 10);
            if (province < 1 || province > 24 || parseInt(cedula[2], 10) > 5) return false;
            const coefficients = [2,1,2,1,2,1,2,1,2];
            let total = 0;
            for (let i = 0; i < coefficients.length; i++) {
                let product = parseInt(cedula[i], 10) * coefficients[i];
                total += product >= 10 ? product - 9 : product;
            }
            const verifier = (10 - (total % 10)) % 10;
            return verifier === parseInt(cedula[9], 10);
        }

        function isValidForeignId(idNumber) {
            return /^\d{10}$/.test(idNumber);
        }

        if (type === 'cedula') {
            if (!isValidEcuadorianId(value)) {
                isValid = false;
                errorMsg = 'La cédula no es válida.';
            }
        } else if (type === 'id_extrj') {
            if (!isValidForeignId(value)) {
                isValid = false;
                errorMsg = 'La cédula extranjera no es válida.';
            }
        } else if (type === 'pasaporte') {
            isValid = true; 
        }

        if (!isValid) {
            $input.addClass('is-invalid');
            $input.next('.invalid-feedback').text(errorMsg);
        } else {
            $input.removeClass('is-invalid');
            $input.next('.invalid-feedback').text('');
        }

        return isValid;
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

    _validateReferenceBlocks() {
        let isValid = true;

        const $container = this.$('#reference_container');
        $container.find('.reference-block').each((index, block) => {

            const $block = this.$(block);
            const $name = $block.find('input[name^="ref_nombre_"]');
            const $address = $block.find('input[name^="ref_domicilio_"]');
            const $phone = $block.find('input[name^="ref_telefono_"]');
            const $occupation = $block.find('input[name^="ref_ocupacion_"]');
            const $time = $block.find('input[name^="ref_tiempo_"]');
            const fields = [$name, $address, $phone, $occupation, $time];

            fields.forEach($field => {
                const value = $field.val();

                if (!value || !value.trim()) {
                    $field.addClass('is-invalid');
                    isValid = false;
                } else {
                    $field.removeClass('is-invalid');
                }
            });

        });

        return isValid;
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

        const fields = [
            'input[name="titulo_por_obtener"]',
            'input[name="institucion_2"]',
            'input[name="horario"]',
            'input[name="carrera"]',
            'input[name="estado"]'
        ];

        fields.forEach(selector => {
            const $field = this.$(selector);
            const shouldDisable = value === 'f';

            $field.prop('disabled', shouldDisable);
            $field.prop('required', false); 

            if (shouldDisable) {
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

            $nombre.prop('disabled', true)
                .prop('required', false)
                .val('')
                .removeClass('is-invalid');

            $relacion.prop('disabled', true)
                .prop('required', false)
                .prop('checked', false)
                .removeClass('is-invalid');

            $parentesco.prop('disabled', true)
                .prop('required', false)
                .val('')
                .removeClass('is-invalid');
        }

        this.$('input[name="knownPosee_1"]').removeClass('is-invalid');
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

    _toggleDisabilityFields() {
        const $discapacidadSi = this.$('input[name="discapacidad"][value="si"]');
        const $tipo = this.$('input[name="tipo_discapacidad"]');
        const $porcentaje = this.$('input[name="porcentaje_discapacidad"]');

        if ($discapacidadSi.is(':checked')) {
            $tipo.prop('disabled', false);
            $porcentaje.prop('disabled', false);
            $tipo.attr('required', true);
            $porcentaje.attr('required', true);
            $tipo.on('blur', () => {
                $tipo.toggleClass('is-invalid', !$tipo.val().trim());
            });
            $porcentaje.on('blur', () => {
                $porcentaje.toggleClass('is-invalid', !$porcentaje.val().trim());
            });

        } else {
            $tipo.prop('disabled', true).removeClass('is-invalid').val('');
            $porcentaje.prop('disabled', true).removeClass('is-invalid').val('');
            $tipo.removeAttr('required');
            $porcentaje.removeAttr('required');
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

    _onChangeFamilyDocType(ev) {
        const $select = $(ev.currentTarget);
        const index = $select.attr("name").split("_")[1];
        const value = $select.val();

        const $cedula = this.$(`input[name="famCedula_${index}"]`);
        const $archivo = this.$(`input[name="famArchivo_${index}"]`);

        if (value === "part_naci") {
            $cedula.prop("disabled", true).prop("required", false).val("");
            $archivo.removeClass("d-none").prop("disabled", false).prop("required", true);
        } else {
            $cedula.prop("disabled", false).prop("required", true);
            $archivo.addClass("d-none").prop("disabled", true).prop("required", false).val("");
        }
    },

    // _onChangeFamilyDocType(ev) {
    //     const $select = $(ev.currentTarget);
    //     const index = $select.attr('name').split('_')[1];
    //     const $numDoc = this.$(`input[name="famCedula_${index}"]`);
    //     const $archivoDoc = this.$(`input[name="famArchivo_${index}"]`);

    //     if ($select.val() === 'part_naci') {
    //         $archivoDoc.removeClass('d-none').prop('disabled', false).attr('required', true);
    //         $numDoc.prop('disabled', true).removeAttr('required').val('').removeClass('is-invalid');
    //     } else {
    //         $numDoc.prop('disabled', false).attr('required', true);
    //         $archivoDoc.addClass('d-none').prop('disabled', true).removeAttr('required').val('').removeClass('is-invalid');
    //     }
    // },

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
            const numHijos = parseInt(this.$('#hr-hijos').val(), 10);
            this.$('.family-block[data-type="Hijo"]').remove();
            if (!isNaN(numHijos) && numHijos > 0) {
                for (let i = 0; i < numHijos; i++) {
                    this.familyCount++;
                    const index = this.familyCount;
                    this._getFamilyBlock("Hijo").then(blockHtml => {
                        this.$('#family_container').append(blockHtml);
                        this.$(`input[name="famDisc_${index}"]`).on('change', () => {
                            this._toggleFamilyDisability(index);
                        });

                        this._toggleFamilyDisability(index);
                    });
                }
            }
        }
    },

    _onPrevClick(ev) {
        ev.preventDefault();

        this.$('#form-step-3').addClass('d-none');
        this.$('#form-step-2').removeClass('d-none');
    },

    _onPrevClickStep2(ev) {
        ev.preventDefault();

        this.$('#form-step-2').addClass('d-none');
        this.$('#form-step-1').removeClass('d-none');
    },

    _onSubmitForm(ev) {
        ev.preventDefault();
        let valid = true;

        if (!this._validateCurrentStep3()) return;
        const totalExperiences = parseInt(this.$('#total_experiences').val(), 10);
        if (!isNaN(totalExperiences) && totalExperiences > 3) {
            $('#experienceMessageText').text("Debe ingresar mínimo 3 experiencias laborales.");
            $('#experienceMessage').removeClass('d-none');
            return;
        }

        this.$('#experience_container .experience-block').each((i, block) => {
            const $block = $(block);
            const noAplica = $block.find('.no-aplica-exp').is(':checked');

            if (!noAplica) {
                $block.find('input, select').each((j, el) => {
                    if (!$(el).val()) {
                        $(el).addClass('is-invalid');
                        valid = false;
                    } else {
                        $(el).removeClass('is-invalid');
                    }
                });
            } else {
                $block.find('input, select').removeClass('is-invalid').prop('disabled', true);
            }
        });

        if (!valid) {
            $('#experienceMessageText').text("Complete todos los campos de experiencia o marque 'No aplica'.");
            $('#experienceMessage').removeClass('d-none');
            return;
        }

        this.$('.family-block').each((index, block) => {
            const i = $(block).find('input[name^="famApellidoPaterno_"]').attr('name').split('_')[1];
            const paterno = this.$(`input[name="famApellidoPaterno_${i}"]`).val()?.trim() || "";
            const materno = this.$(`input[name="famApellidoMaterno_${i}"]`).val()?.trim() || "";
            const primer  = this.$(`input[name="famPrimerNombre_${i}"]`).val()?.trim() || "";
            const segundo = this.$(`input[name="famSegundoNombre_${i}"]`).val()?.trim() || "";

            const fullName = `${paterno} ${materno} ${primer} ${segundo}`.trim();
            this.$(`input[name="famNombre_${i}"]`).val(fullName);

            // NUEVO
            const docType = this.$(`select[name="famTipoDoc_${i}"]`).val();
            const $numDoc = this.$(`input[name="famCedula_${i}"]`);
            const $archivoDoc = this.$(`input[name="famArchivo_${i}"]`);
            const $porcentaje = this.$(`input[name="famDiscPorcentaje_${i}"]`);
            const discValue = this.$(`input[name="famDisc_${i}"]:checked`).val();

            if (docType === 'part_naci') {
                $archivoDoc.prop('disabled', false);   
                $numDoc.prop('disabled', true).val(''); 
            } else {
                $numDoc.prop('disabled', false);       
                $archivoDoc.prop('disabled', true).val(''); 
            }

            if (discValue === 'si') {
                $porcentaje.prop('disabled', false);
            } else {
                $porcentaje.prop('disabled', true).val('');
            }
        });

        this.$('#submit-form')
            .prop('disabled', true)
            .text('Enviando...');

        this.el.submit();
    },

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

    _onSelectFamily(ev) {
        const parentesco = $(ev.currentTarget).data('type');
        if (!parentesco) return;
        if (["Padre","Madre","Conyugue"].includes(parentesco)) {
            if (this.$(`#family_container .family-block[data-type="${parentesco}"]`).length) {
                alert(`${parentesco} ya fue agregado`);
                return;
            }
        }

        this._addFamilyBlock(parentesco); 
    },

    async _addFamilyBlock(parentesco) {
        const FAMILY_TYPES_MAP = {
            '1': 'Padre',
            '2': 'Madre',
            '3': 'Hermano(a)',
            '4': 'Conyugue',
            '5': 'Hijo(a)'
        };

        const UNIQUE_TYPES = ['Padre', 'Madre', 'Conyugue']; 
        const label = FAMILY_TYPES_MAP[parentesco] || parentesco;

        if (UNIQUE_TYPES.includes(label) &&
            this.$(`#family_container .family-block[data-type="${label}"]`).length > 0) {
            $('#familyMessageText').text(`Ya existe un bloque para ${label}`);
            $('#familyMessage').removeClass('d-none');
            return;
        }

        this.familyCount++;
        const html = await this._getFamilyBlock(label);
        this.$('#family_container').append(html);
        this.$(`#family_container .family-block:last`).append(`
            <input type="hidden" name="famTipo_${this.familyCount}" value="${parentesco}"/>
        `);

        const i = this.familyCount;
        this.$(`input[name="famDisc_${i}"]`).on('change', () => {
            this._toggleFamilyDisability(i);
        });
        this.$(`input[name="famDepende_${i}"]`).on('change', (ev) => {
            const name = $(ev.currentTarget).attr('name');
            this.$(`input[name="${name}"]`).removeClass('is-invalid');
        });
    },

    _onRemoveFamily(ev) {
        const $block = $(ev.currentTarget).closest('.family-block');
        $block.remove();
        this.familyCount--;
    },

    async _onAddEducation(ev) {
        ev.preventDefault();
        this.educationCount++;
        const newBlock = await this._getEducationBlock(false);
        this.$('#education_container').prepend(newBlock);
        this.$('#total_educations').val(this.educationCount);
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
        this.experienceCount++;
        const newBlock = await this._getExperienceBlock(true);
        this.$('#experience_container').append(newBlock);
        this.$('#experience_container').find('.remove-experience').last().on('click', (ev) => {
            $(ev.target).closest('.experience-block').remove();
            this.experienceCount--;
            this.$('#total_experiences').val(this.experienceCount); 
            this._checkFieldsFilled();
        });

        this.$('#total_experiences').val(this.experienceCount);

        const startId = `job-inicio_${this.experienceCount}`;
        const endId = `job-fin_${this.experienceCount}`;
        const startInput = document.getElementById(startId);
        const endSelect = document.getElementById(endId);

        if (startInput && endSelect) {
            startInput.addEventListener("change", () => {
                const startDate = startInput.value;
                if (startDate) {
                    const startYear = new Date(startDate).getFullYear();
                    const currentYear = new Date().getFullYear();

                    endSelect.innerHTML = "<option value=''></option>";

                    for (let year = startYear; year < currentYear; year++) {
                        const opt = document.createElement("option");
                        opt.value = year;
                        opt.textContent = year;
                        endSelect.appendChild(opt);
                    }

                    const presentOpt = document.createElement("option");
                    presentOpt.value = "presente";
                    presentOpt.textContent = "Presente";
                    endSelect.appendChild(presentOpt);
                }
            });
        }

        this._checkFieldsFilled();
    },

    async _onAddExperience(ev) {
        ev.preventDefault();
        this.experienceCount++;
        const newBlock = await this._getExperienceBlock(false);
        this.$('#experience_container').prepend(newBlock);
        this.$('#total_experiences').val(this.experienceCount);

        const startId = `job-inicio_${this.experienceCount}`;
        const endId = `job-fin_${this.experienceCount}`;
        const startInput = document.getElementById(startId);
        const endSelect = document.getElementById(endId);

        if (startInput && endSelect) {
            startInput.addEventListener("change", () => {
                const startDate = startInput.value;
                if (startDate) {
                    const startYear = new Date(startDate).getFullYear();
                    const currentYear = new Date().getFullYear();

                    endSelect.innerHTML = "<option value=''></option>";

                    for (let year = startYear; year < currentYear; year++) {
                        const opt = document.createElement("option");
                        opt.value = year;
                        opt.textContent = year;
                        endSelect.appendChild(opt);
                    }

                    const presentOpt = document.createElement("option");
                    presentOpt.value = "presente";
                    presentOpt.textContent = "Presente";
                    endSelect.appendChild(presentOpt);
                }
            });
        }

        this.$('#add-experience').css({
            'opacity': '0.5',
            'pointer-events': 'none'
        });
    },

    _onRemoveExperience(ev) {
        const $block = $(ev.currentTarget).closest('.experience-block'); 
        const index = this.$('#experience_container .experience-block').index($block);

        if (index === 0) {
            return;
        }

        $block.remove();
        this.experienceCount--;
        this.$('#experience_container .experience-block').each((i, el) => {
            $(el).find('.separator-education span').text(`Experiencia Laboral # ${i + 1}`);
        });
    },

    _addReferenceBlock() {
        const block = this._getReferenceBlock();
        this.$('#reference_container').append(block);
        this.referenceCount++;
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
