/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.EducationExperiencePrefill = publicWidget.Widget.extend({
    selector: '#hr_job_recruitment_form',

    start() {
        this._super(...arguments);
        this.educationCount = 1;
        this.experienceCount = 1;
        this._prefillEducations();
        this._prefillExperiences();
    },

    async _prefillEducations() {
        let educationsRaw = this.$el.attr('data-educations');
        if (!educationsRaw) return;

        let educations;
        try {
            educations = JSON.parse(educationsRaw);
        } catch (e) {
            console.error("Error parseando educations:", e);
            return;
        }

        if (!Array.isArray(educations) || educations.length === 0) return;

        const container = this.$('#education_container');
        container.empty();

        for (let i = 0; i < educations.length; i++) {
            const edu = educations[i];
            const block = await this._getEducationBlock(i === 0, edu);
            container.append(block);
            this.educationCount++;
        }
    },

    async _getEducationBlock(isFirstBlock = false, edu = {}) {
        await loadCountriesAndStates();

        const separator = isFirstBlock ? '' : `
            <div class="row d-flex justify-content-center my-4">
                <div class="col-12 col-md-10">
                    <div class="separator-education" style="border-top: 2px solid #e0e0e0; position: relative; margin: 20px 0;">
                        <span style="position: absolute; top: -12px; left: 50%; transform: translateX(-50%);
                            background: white; padding: 0 15px; color: #666; font-size: 14px;">
                            Educación # ${this.educationCount}
                        </span>
                    </div>
                </div>
            </div>
        `;

        const studiesLevels = await fetch("/api/study_levels").then(r => r.json());
        const optionsStudiesLevels = studiesLevels.map(
            studyLevel => `<option value="${studyLevel.id}" ${edu.level_id && edu.level_id[0] === studyLevel.id ? 'selected' : ''}>${studyLevel.name}</option>`
        ).join('');

        const block = `
            <div class="row d-flex justify-content-center">
                <div class="col-12 col-md-10">
                    <div class="row d-flex justify-content-between">

                        <!-- Nivel educativo -->
                        <div class="col-12 col-md-4 mb-4">
                            <label class="fs-6">Nivel Educativo:</label>
                            <select name="level_id_${this.educationCount}" class="form-select rounded-pill py-2">
                                <option value=""></option>
                                ${optionsStudiesLevels}
                            </select>
                        </div>

                        <!-- Institución -->
                        <div class="col-12 col-md-4 mb-4">
                            <label class="fs-6">Nombre de la institución:</label>
                            <input type="text" name="institucion_${this.educationCount}" class="form-control rounded-pill py-2"
                                value="${edu.institucion || ''}"/>
                        </div>

                        <!-- Desde -->
                        <div class="col-12 col-md-4 mb-4">
                            <label class="fs-6">Desde:</label>
                            <input type="date" name="inicioEstudio_${this.educationCount}" class="form-control rounded-pill py-2"
                                value="${edu.fecha_inicio || ''}"/>
                        </div>

                        <!-- Hasta -->
                        <div class="col-12 col-md-4 mb-4">
                            <label class="fs-6">Hasta:</label>
                            <select name="finEstudio_${this.educationCount}" class="form-select rounded-pill py-2">
                                <option value=""></option>
                                ${edu.year_fin ? `<option value="${edu.year_fin}" selected>${edu.year_fin}</option>` : ''}
                                <option value="presente">Presente</option>
                            </select>
                        </div>

                        <!-- País -->
                        <div class="col-12 col-md-4 mb-4">
                            <label class="fs-6">País:</label>
                            <select name="paisEducacion_${this.educationCount}" class="form-select rounded-pill py-2">
                                <option value=""></option>
                                ${cachedCountries.map(country => `
                                    <option value="country-${country.id}" ${edu.country_id && edu.country_id[0] === country.id ? 'selected' : ''}>
                                        ${country.name}
                                    </option>
                                `).join('')}
                            </select>
                        </div>

                        <!-- Ciudad -->
                        <div class="col-12 col-md-4 mb-4">
                            <label class="fs-6">Ciudad/Provincia:</label>
                            <select name="ciudad_${this.educationCount}" class="form-select rounded-pill py-2">
                                <option value=""></option>
                                ${cachedStatesByCountry[cachedCountries.find(c => c.name === 'Ecuador').id].map(state => `
                                    <option value="state-${state.id}" ${edu.state_id && edu.state_id[0] === state.id ? 'selected' : ''}>
                                        ${state.name}
                                    </option>
                                `).join('')}
                            </select>
                        </div>

                        <!-- Título -->
                        <div class="col-12 col-md-4 mb-4">
                            <label class="fs-6">Título Recibido:</label>
                            <input type="text" name="titulo_${this.educationCount}" class="form-control rounded-pill py-2"
                                value="${edu.titulo || ''}"/>
                        </div>

                    </div>
                </div>
            </div>
        ` + separator;

        return block;
    },

    async _prefillExperiences() {
        let experiencesRaw = this.$el.attr('data-experiences');
        if (!experiencesRaw) return;

        let experiences;
        try {
            experiences = JSON.parse(experiencesRaw);
        } catch (e) {
            console.error("Error parseando experiences:", e);
            return;
        }

        if (!Array.isArray(experiences) || experiences.length === 0) return;

        const container = this.$('#experience_container');
        container.empty();

        for (let i = 0; i < experiences.length; i++) {
            const exp = experiences[i];
            const block = await this._getExperienceBlock(i === 0, exp);
            container.append(block);
            this.experienceCount++;
        }
    },

    async _getExperienceBlock(isFirstBlock = false, exp = {}) {
        await loadCountriesAndStates();

        const block = `
            <div class="row d-flex justify-content-center experience-block">
                <div class="col-12 col-md-10">

                    <div class="separator-education" style="border-top: 2px solid #e0e0e0; position: relative; margin: 20px 0;">
                        <span style="position: absolute; top: -12px; left: 50%; transform: translateX(-50%);
                            background: white; padding: 0 15px; color: #666; font-size: 14px;">
                            Experiencia Laboral # ${this.experienceCount}
                        </span>
                    </div>

                    <div class="row d-flex justify-content-between">

                        <!-- Nombre de la compañía -->
                        <div class="col-12 col-md-3 mb-4">
                            <label class="fs-6">Nombre de la compañía:</label>
                            <input type="text" name="company_${this.experienceCount}" class="form-control rounded-pill py-2"
                                value="${exp.empresa || ''}"/>
                        </div>

                        <!-- Cargo desempeñado -->
                        <div class="col-12 col-md-3 mb-4">
                            <label class="fs-6">Cargo desempeñado:</label>
                            <input type="text" name="cargo_${this.experienceCount}" class="form-control rounded-pill py-2"
                                value="${exp.name || ''}"/>
                        </div>

                        <!-- Desde -->
                        <div class="col-12 col-md-3 mb-4">
                            <label class="fs-6">Desde:</label>
                            <input type="date" name="jobInicio_${this.experienceCount}" class="form-control rounded-pill py-2"
                                value="${exp.fecha_inicio || ''}"/>
                        </div>

                        <!-- Hasta -->
                        <div class="col-12 col-md-3 mb-4">
                            <label class="fs-6">Hasta:</label>
                            <select name="jobFin_${this.experienceCount}" class="form-select rounded-pill py-2">
                                <option value=""></option>
                                ${exp.year_fin ? `<option value="${exp.year_fin}" selected>${exp.year_fin}</option>` : ''}
                                <option value="presente">Presente</option>
                            </select>
                        </div>

                        <!-- Teléfonos -->
                        <div class="col-12 col-md-3 mb-4">
                            <label class="fs-6">Teléfonos:</label>
                            <input type="text" name="telefonos_${this.experienceCount}" class="form-control rounded-pill py-2"
                                value="${exp.telefonos || ''}"/>
                        </div>

                        <!-- Tiempo de servicio -->
                        <div class="col-12 col-md-3 mb-4">
                            <label class="fs-6">Tiempo que prestó su servicio:</label>
                            <input type="text" name="tiempo_${this.experienceCount}" class="form-control rounded-pill py-2"
                                value="${exp.tiempo_servicio || ''}"/>
                        </div>

                        <!-- Ingreso mensual -->
                        <div class="col-12 col-md-3 mb-4">
                            <label class="fs-6">Ingreso mensual:</label>
                            <input type="number" name="ingreso_${this.experienceCount}" class="form-control rounded-pill py-2"
                                value="${exp.ingreso_mensual || ''}"/>
                        </div>

                        <!-- Motivo de separación -->
                        <div class="col-12 col-md-3 mb-4">
                            <label class="fs-6">Motivo de separación:</label>
                            <input type="text" name="motivo_${this.experienceCount}" class="form-control rounded-pill py-2"
                                value="${exp.motivo_separacion || ''}"/>
                        </div>

                        <!-- Jefe directo -->
                        <div class="col-12 col-md-3 mb-4">
                            <label class="fs-6">Nombre de su jefe directo:</label>
                            <input type="text" name="jefe_${this.experienceCount}" class="form-control rounded-pill py-2"
                                value="${exp.jefe_directo || ''}"/>
                        </div>

                        <!-- Cargo jefe directo -->
                        <div class="col-12 col-md-3 mb-4">
                            <label class="fs-6">Cargo de su jefe directo:</label>
                            <input type="text" name="cargoJefe_${this.experienceCount}" class="form-control rounded-pill py-2"
                                value="${exp.cargo_jefe_directo || ''}"/>
                        </div>

                        <!-- País -->
                        <div class="col-12 col-md-3 mb-4">
                            <label class="fs-6">País:</label>
                            <select name="paisExperiencia_${this.experienceCount}" class="form-select rounded-pill py-2">
                                <option value=""></option>
                                ${cachedCountries.map(country => `
                                    <option value="country-${country.id}" ${exp.country_id && exp.country_id[0] === country.id ? 'selected' : ''}>
                                        ${country.name}
                                    </option>
                                `).join('')}
                            </select>
                        </div>

                        <!-- Ciudad -->
                        <div class="col-12 col-md-3 mb-4">
                            <label class="fs-6">Ciudad/Provincia:</label>
                            <select name="ciudadExperiencia_${this.experienceCount}" class="form-select rounded-pill py-2">
                                <option value=""></option>
                                ${cachedStatesByCountry[cachedCountries.find(c => c.name === 'Ecuador').id].map(state => `
                                    <option value="state-${state.id}" ${exp.state_id && exp.state_id[0] === state.id ? 'selected' : ''}>
                                        ${state.name}
                                    </option>
                                `).join('')}
                            </select>
                        </div>

                    </div>
                </div>
            </div>
        `;

        return block;
    },
});
