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

                        <div class="col-12 col-md-4 mb-4">
                            <label class="fs-6">Nivel Educativo:</label>
                            <input type="text" class="form-control rounded-pill py-2" readonly
                                value="${edu.level_id ? edu.level_id[1] : ''}"/>
                        </div>

                        <div class="col-12 col-md-4 mb-4">
                            <label class="fs-6">Institución:</label>
                            <input type="text" class="form-control rounded-pill py-2" readonly
                                value="${edu.institucion || ''}"/>
                        </div>

                        <div class="col-12 col-md-4 mb-4">
                            <label class="fs-6">Desde:</label>
                            <input type="text" class="form-control rounded-pill py-2" readonly
                                value="${edu.fecha_inicio || ''}"/>
                        </div>

                        <div class="col-12 col-md-4 mb-4">
                            <label class="fs-6">Hasta:</label>
                            <input type="text" class="form-control rounded-pill py-2" readonly
                                value="${edu.year_fin || ''}"/>
                        </div>

                        <div class="col-12 col-md-4 mb-4">
                            <label class="fs-6">Título:</label>
                            <input type="text" class="form-control rounded-pill py-2" readonly
                                value="${edu.titulo || ''}"/>
                        </div>

                        <div class="col-12 col-md-4 mb-4">
                            <label class="fs-6">País:</label>
                            <input type="text" class="form-control rounded-pill py-2" readonly
                                value="${edu.country_id ? edu.country_id[1] : ''}"/>
                        </div>

                        <div class="col-12 col-md-4 mb-4">
                            <label class="fs-6">Ciudad/Provincia:</label>
                            <input type="text" class="form-control rounded-pill py-2" readonly
                                value="${edu.state_id ? edu.state_id[1] : ''}"/>
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

                        <div class="col-12 col-md-3 mb-4">
                            <label class="fs-6">Compañía:</label>
                            <input type="text" class="form-control rounded-pill py-2" readonly
                                value="${exp.empresa || ''}"/>
                        </div>

                        <div class="col-12 col-md-3 mb-4">
                            <label class="fs-6">Cargo:</label>
                            <input type="text" class="form-control rounded-pill py-2" readonly
                                value="${exp.name || ''}"/>
                        </div>

                        <div class="col-12 col-md-3 mb-4">
                            <label class="fs-6">Desde:</label>
                            <input type="text" class="form-control rounded-pill py-2" readonly
                                value="${exp.fecha_inicio || ''}"/>
                        </div>

                        <div class="col-12 col-md-3 mb-4">
                            <label class="fs-6">Hasta:</label>
                            <input type="text" class="form-control rounded-pill py-2" readonly
                                value="${exp.year_fin || ''}"/>
                        </div>

                        <div class="col-12 col-md-3 mb-4">
                            <label class="fs-6">Teléfonos:</label>
                            <input type="text" class="form-control rounded-pill py-2" readonly
                                value="${exp.telefonos || ''}"/>
                        </div>

                        <div class="col-12 col-md-3 mb-4">
                            <label class="fs-6">Tiempo de servicio:</label>
                            <input type="text" class="form-control rounded-pill py-2" readonly
                                value="${exp.tiempo_servicio || ''}"/>
                        </div>

                        <div class="col-12 col-md-3 mb-4">
                            <label class="fs-6">Ingreso mensual:</label>
                            <input type="text" class="form-control rounded-pill py-2" readonly
                                value="${exp.ingreso_mensual || ''}"/>
                        </div>

                        <div class="col-12 col-md-3 mb-4">
                            <label class="fs-6">Motivo de separación:</label>
                            <input type="text" class="form-control rounded-pill py-2" readonly
                                value="${exp.motivo_separacion || ''}"/>
                        </div>

                        <div class="col-12 col-md-3 mb-4">
                            <label class="fs-6">Jefe directo:</label>
                            <input type="text" class="form-control rounded-pill py-2" readonly
                                value="${exp.jefe_directo || ''}"/>
                        </div>

                        <div class="col-12 col-md-3 mb-4">
                            <label class="fs-6">Cargo jefe directo:</label>
                            <input type="text" class="form-control rounded-pill py-2" readonly
                                value="${exp.cargo_jefe_directo || ''}"/>
                        </div>

                        <div class="col-12 col-md-3 mb-4">
                            <label class="fs-6">País:</label>
                            <input type="text" class="form-control rounded-pill py-2" readonly
                                value="${exp.country_id ? exp.country_id[1] : ''}"/>
                        </div>

                        <div class="col-12 col-md-3 mb-4">
                            <label class="fs-6">Ciudad/Provincia:</label>
                            <input type="text" class="form-control rounded-pill py-2" readonly
                                value="${exp.state_id ? exp.state_id[1] : ''}"/>
                        </div>

                    </div>
                </div>
            </div>
        `;

        return block;
    },


});
