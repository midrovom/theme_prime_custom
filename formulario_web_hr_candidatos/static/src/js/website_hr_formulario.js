/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.EducationExperiencePrefill = publicWidget.Widget.extend({
    selector: '#hr_job_recruitment_form',

    start() {
        this._super(...arguments);
        this._prefillEducations();
        this._prefillExperiences();
    },

    _prefillEducations() {
        let educationsRaw = this.$el.attr('data-educations');
        if (!educationsRaw) return;

        const educations = JSON.parse(educationsRaw);
        if (!Array.isArray(educations) || educations.length === 0) return;

        const container = this.$('#education_container');
        container.empty();

        educations.forEach((edu, index) => {
            const block = `
                <div class="row d-flex justify-content-center mb-3">
                    <div class="col-12 col-md-10">
                        <div class="border rounded p-3">
                            <h6 class="text-info">Educación #${index + 1}</h6>
                            <p><strong>Nivel:</strong> ${edu.level_id ? edu.level_id[1] : ''}</p>
                            <p><strong>Institución:</strong> ${edu.institucion || ''}</p>
                            <p><strong>Desde:</strong> ${edu.fecha_inicio || ''} <strong>Hasta:</strong> ${edu.year_fin || ''}</p>
                            <p><strong>Título:</strong> ${edu.titulo || ''}</p>
                            <p><strong>País:</strong> ${edu.country_id ? edu.country_id[1] : ''}</p>
                            <p><strong>Ciudad/Provincia:</strong> ${edu.state_id ? edu.state_id[1] : ''}</p>
                        </div>
                    </div>
                </div>`;
            container.append(block);
        });
    },

    _prefillExperiences() {
        let experiencesRaw = this.$el.attr('data-experiences');
        if (!experiencesRaw) return;

        const experiences = JSON.parse(experiencesRaw);
        if (!Array.isArray(experiences) || experiences.length === 0) return;

        const container = this.$('#experience_container');
        container.empty();

        experiences.forEach((exp, index) => {
            const block = `
                <div class="row d-flex justify-content-center mb-3">
                    <div class="col-12 col-md-10">
                        <div class="border rounded p-3">
                            <h6 class="text-info">Experiencia #${index + 1}</h6>
                            <p><strong>Empresa:</strong> ${exp.empresa || ''}</p>
                            <p><strong>Cargo:</strong> ${exp.name || ''}</p>
                            <p><strong>Desde:</strong> ${exp.fecha_inicio || ''} <strong>Hasta:</strong> ${exp.year_fin || ''}</p>
                            <p><strong>Tiempo de servicio:</strong> ${exp.tiempo_servicio || ''}</p>
                            <p><strong>Ingreso mensual:</strong> ${exp.ingreso_mensual || ''}</p>
                            <p><strong>Motivo de separación:</strong> ${exp.motivo_separacion || ''}</p>
                            <p><strong>Jefe directo:</strong> ${exp.jefe_directo || ''} (${exp.cargo_jefe_directo || ''})</p>
                        </div>
                    </div>
                </div>`;
            container.append(block);
        });
    },
});

