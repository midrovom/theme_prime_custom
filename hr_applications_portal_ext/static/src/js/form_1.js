odoo.define('hr_applications_portal_ext.steps_control', function (require) {
    "use strict";
    var publicWidget = require('web.public.widget');

    publicWidget.registry.RecruitmentStepsControl = publicWidget.Widget.extend({
        selector: '#hr_job_recruitment_form',
        start: function () {
            var self = this;
            // Forzar estado inicial: mostrar solo step-1, ocultar step-3
            var $step1 = this.$el.find('#form-step-1');
            var $step3 = this.$el.find('#form-step-3');

            if ($step1.length) {
                $step1.removeClass('d-none');
            }
            if ($step3.length) {
                $step3.addClass('d-none');
            }

            // Botón para pasar de 1 a 3 (si existe)
            this.$el.on('click', '#btn_next_to_step3', function (ev) {
                ev.preventDefault();
                $step1.addClass('d-none');
                $step3.removeClass('d-none');
                $step3[0].scrollIntoView({behavior: 'smooth'});
            });

            // Opcional: botón para volver de 3 a 1
            this.$el.on('click', '#btn_back_to_step1', function (ev) {
                ev.preventDefault();
                $step3.addClass('d-none');
                $step1.removeClass('d-none');
                $step1[0].scrollIntoView({behavior: 'smooth'});
            });
        },
    });
});
