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
        const educations = this.$el.data('educations'); // viene del controlador
        if (!educations || educations.length === 0) return;

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
                            <p><strong>Desde:</strong> ${edu.inicio || ''} <strong>Hasta:</strong> ${edu.fin || ''}</p>
                            <p><strong>Título:</strong> ${edu.titulo || ''}</p>
                        </div>
                    </div>
                </div>`;
            container.append(block);
        });
    },

    _prefillExperiences() {
        const experiences = this.$el.data('experiences'); // viene del controlador
        if (!experiences || experiences.length === 0) return;

        const container = this.$('#experience_container');
        container.empty();

        experiences.forEach((exp, index) => {
            const block = `
                <div class="row d-flex justify-content-center mb-3">
                    <div class="col-12 col-md-10">
                        <div class="border rounded p-3">
                            <h6 class="text-info">Experiencia #${index + 1}</h6>
                            <p><strong>Empresa:</strong> ${exp.empresa || ''}</p>
                            <p><strong>Cargo:</strong> ${exp.cargo || ''}</p>
                            <p><strong>Desde:</strong> ${exp.fecha_inicio || ''} <strong>Hasta:</strong> ${exp.fecha_fin || ''}</p>
                            <p><strong>Funciones:</strong> ${exp.funciones || ''}</p>
                        </div>
                    </div>
                </div>`;
            container.append(block);
        });
    },
});
