/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

const MultistepForm = publicWidget.registry.MultistepForm;

// El formulario original exige volver a seleccionar foto y curriculum en cada envío.
// En modo actualización, si ya existe la información, se permite conservarla sin volver a cargarla.
if (MultistepForm && !MultistepForm.prototype.__portalEditPatched) {
    const originalValidateImage = MultistepForm.prototype._validateImage;
    const originalValidateCurriculum = MultistepForm.prototype._validateCurriculum;

    MultistepForm.prototype._validateImage = function (ev) {
        const isEdit = this.$el?.attr("data-portal-edit") === "1";
        const hasExisting = this.$el?.attr("data-existing-image") === "1";
        const input = this.$("#hr-perfil")[0];

        if (isEdit && hasExisting && input && !input.files?.length && !ev) {
            const errorDiv = document.getElementById("image-error");
            if (errorDiv) errorDiv.textContent = "";
            input.classList.remove("is-invalid");
            return true;
        }
        return originalValidateImage.call(this, ev);
    };

    MultistepForm.prototype._validateCurriculum = function () {
        const isEdit = this.$el?.attr("data-portal-edit") === "1";
        const hasExisting = this.$el?.attr("data-existing-curriculum") === "1";
        const hasNewFiles = this.uploadedFiles && this.uploadedFiles.length > 0;

        if (isEdit && hasExisting && !hasNewFiles) {
            this.$("#curriculum-vitae").removeClass("is-invalid");
            return true;
        }
        return originalValidateCurriculum.call(this);
    };

    MultistepForm.prototype.__portalEditPatched = true;
}

publicWidget.registry.PortalApplicantEdit = publicWidget.Widget.extend({
    selector: "#hr_job_recruitment_form",

    async start() {
        await this._super(...arguments);

        const params = new URLSearchParams(window.location.search);
        const applicantId = params.get("edit_applicant");
        if (!applicantId || !/^\d+$/.test(applicantId)) {
            return this;
        }

        this.$el.attr("data-portal-edit", "1");
        this.$el.attr("data-edit-applicant-id", applicantId);
        this.$el.attr("action", `/my/application/${applicantId}/update`);

        if (!this.$el.prev("#portal-edit-notice").length) {
            this.$el.before(`
                <div id="portal-edit-notice" class="alert alert-warning rounded-4 mb-4">
                    Esta actualización fue habilitada por el equipo de reclutamiento.
                    Al enviar el formulario, el permiso se cerrará nuevamente.
                </div>
            `);
        }

        try {
            await this._loadApplicantData(applicantId);
        } catch (error) {
            console.error("No se pudo cargar la información de la postulación", error);
            if (!this.$el.prev("#portal-edit-load-error").length) {
                this.$el.before(`
                    <div id="portal-edit-load-error" class="alert alert-danger rounded-4 mb-4">
                        No se pudo cargar la información guardada de la postulación.
                        Recargue la página antes de actualizar.
                    </div>
                `);
            }
        }
        return this;
    },

    _sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    },

    async _waitFor(selector, minimum = 1, timeout = 10000) {
        const start = Date.now();
        while (Date.now() - start < timeout) {
            if (this.$(selector).length >= minimum) return;
            await this._sleep(100);
        }
        throw new Error(`Tiempo agotado esperando ${selector}`);
    },

    _setValue(selector, value, trigger = false) {
        const $el = this.$(selector);
        if (!$el.length) return;
        $el.val(value ?? "");
        if (trigger) $el.trigger("change");
    },

    _setRadio(name, value, trigger = true) {
        const $radio = this.$(`input[name="${name}"][value="${value}"]`);
        if (!$radio.length) return;
        $radio.prop("checked", true);
        if (trigger) $radio.trigger("change");
    },

    _setChecks(name, values) {
        const wanted = new Set(values || []);
        this.$(`input[name="${name}"]`).each(function () {
            this.checked = wanted.has(this.value);
        });
    },

    _splitFullName(value) {
        const parts = String(value || "").trim().split(/\s+/).filter(Boolean);
        return {
            paterno: parts[0] || "",
            materno: parts[1] || "",
            primero: parts[2] || "",
            segundo: parts.slice(3).join(" "),
        };
    },

    async _loadApplicantData(applicantId) {
        const response = await fetch(`/my/application/${applicantId}/data`, {
            headers: { "Accept": "application/json" },
        });
        if (!response.ok) {
            throw new Error("No fue posible consultar la postulación.");
        }
        const data = await response.json();

        this.$el.attr("data-existing-image", data.has_image ? "1" : "0");
        this.$el.attr("data-existing-curriculum", data.has_curriculum ? "1" : "0");

        await this._waitFor("#education_container [name^='level_id_']");
        this._fillStep1(data);

        // El formulario nativo genera los bloques familiares al pasar al paso 2.
        this.$("#next-button").trigger("click");
        await this._waitFor("#family_container .family-block", Math.max(3, 3 + Number(data.num_hijos || 0)));
        await this._fillStep2(data);

        this.$("#next-button-step2").trigger("click");
        await this._waitFor("#experience_container .experience-block", Math.min(3, Math.max(1, data.experience?.length || 1)));
        await this._fillStep3(data);
    },

    _fillStep1(data) {
        this._setValue("#hr-lastname-paterno", data.lastname_paterno);
        this._setValue("#hr-lastname-materno", data.lastname_materno);
        this._setValue("#hr-name", data.firstname);
        this._setValue("#hr-age", data.age);
        this._setValue("#hr-address", data.address);
        this._setValue("#hr-parish", data.parish);

        this._setValue("#hr-day", data.birthdate?.day);
        this._setValue("#hr-month", data.birthdate?.month);
        this._setValue("#hr-year", data.birthdate?.year);

        this._setValue("#hr-country", data.birth_country_id, true);
        this._setValue("#hr-provincia", data.provincia_id);
        this._setValue("#hr-code-cellphone", data.cellphone_code || "+593");
        this._setValue("#hr-cellphone", data.cellphone);
        this._setValue("#hr-phone", data.phone);
        this._setValue("#hr-email", data.email);
        this._setValue("#hr-hijos", data.num_hijos);
        this._setChecks("dependientes", data.dependientes);

        this._setRadio("viveCon", data.vive_con);
        this._setRadio("tipoVivienda", data.tipo_vivienda);
        this._setRadio("estadoCivil", data.estado_civil);
        this._setValue("#hr-type-doc", data.document_type);
        this._setValue("#hr-number-doc", data.document_number);
        this._setValue("#hr-nationality", data.nationality);

        this._setRadio("jobOptions", data.disability ? "t" : "f", true);
        this._setRadio("discOptions", data.family_disability ? "t" : "f", true);

        // Mostrar la foto existente en el preview del formulario nativo.
        if (data.id && data.has_image) {
            const preview = this.$("#preview-img")[0];
            const textImg = this.$("#text-img")[0];
            if (preview) {
                preview.src = `/web/image/hr.applicant/${data.id}/image_1920`;
                preview.style.display = "block";
            }
            if (textImg) textImg.style.display = "none";
        }

        const inputImage = this.$("#hr-perfil")[0];
        if (inputImage) inputImage.required = !data.has_image;

        const inputCurriculum = this.$("#curriculum-vitae")[0];
        if (inputCurriculum) inputCurriculum.required = !data.has_curriculum;
        if (data.has_curriculum) {
            this.$("#file-selected-message").html(
                '<div class="text-success custom-message fs-6">Ya existen archivos curriculares registrados. Puede conservarlos o seleccionar nuevos.</div>'
            );
        }
    },

    async _fillStep2(data) {
        const medical = data.medical || {};
        [
            "enfermedad_persistente",
            "medicacion_continua",
            "enfermedad_laboral",
            "cirugia_realizada",
            "discapacidad",
        ].forEach(name => this._setRadio(name, medical[name]));

        this._setValue('input[name="detalle_enfermedad_persistente"]', medical.detalle_enfermedad_persistente);
        this._setValue('input[name="detalle_medicacion_continua"]', medical.detalle_medicacion_continua);
        this._setValue('input[name="detalle_enfermedad_laboral"]', medical.detalle_enfermedad_laboral);
        this._setValue('input[name="detalle_cirugia_realizada"]', medical.detalle_cirugia_realizada);
        this._setValue('input[name="tipo_discapacidad"]', medical.tipo_discapacidad);
        this._setValue('input[name="porcentaje_discapacidad"]', medical.porcentaje_discapacidad);
        this._setValue('input[name="tipo_sangre"]', medical.tipo_sangre);

        await this._fillFamilies(data.family || []);
    },

    async _fillFamilies(families) {
        const siblings = families.filter(x => x.familiar_type === "3").length;
        const siblingCount = Math.max(1, siblings);
        this._setValue("#famNumHermanos", siblingCount, true);
        await this._sleep(250);

        const byType = {};
        for (const family of families) {
            byType[family.familiar_type] = byType[family.familiar_type] || [];
            byType[family.familiar_type].push(family);
        }

        const blocks = this.$("#family_container .family-block").toArray();
        const counters = {};

        for (const blockElement of blocks) {
            const $block = $(blockElement);
            const type = $block.find('input[name^="famTipo_"]').val() || "";
            counters[type] = counters[type] || 0;
            const family = byType[type]?.[counters[type]];
            counters[type] += 1;
            if (!family) continue;

            const index = $block.find('input[name^="famNombre_"]').attr("name")?.split("_")[1];
            if (!index) continue;

            const name = this._splitFullName(family.name);
            this._setValue(`input[name="famApellidoPaterno_${index}"]`, name.paterno);
            this._setValue(`input[name="famApellidoMaterno_${index}"]`, name.materno);
            this._setValue(`input[name="famPrimerNombre_${index}"]`, name.primero);
            this._setValue(`input[name="famSegundoNombre_${index}"]`, name.segundo);
            this._setValue(`input[name="famNombre_${index}"]`, family.name);
            this._setValue(`select[name="famTipoDoc_${index}"]`, family.document_type, true);
            this._setValue(`input[name="famCedula_${index}"]`, family.cedula);
            this._setValue(`input[name="famFecha_${index}"]`, family.birthdate);
            this._setValue(`input[name="famTelefono_${index}"]`, family.phone);
            this._setValue(`input[name="famOcupacion_${index}"]`, family.occupation);
            this._setRadio(`famDepende_${index}`, family.economically_dependent);
            this._setRadio(`famDisc_${index}`, family.disability, true);
            this._setValue(`input[name="famDiscTipo_${index}"]`, family.disability_type);
            this._setValue(`input[name="famDiscPorcentaje_${index}"]`, family.disability_percentage);

            const $fallecido = this.$(`input[name="famFallecido_${index}"]`);
            if ($fallecido.length) {
                $fallecido.prop("checked", !!family.fallecido).trigger("change");
            }
            const $noTiene = this.$(`input[name="famNoTiene_${index}"]`);
            if ($noTiene.length) {
                $noTiene.prop("checked", !!family.no_tiene).trigger("change");
            }
        }
    },

    async _fillStep3(data) {
        const studies = data.education || [];
        const studyCurrent = data.secondary_studies ? "t" : "f";
        this._setRadio("studyOptions", studyCurrent, true);

        // El formulario nativo puede manejar una segunda formación.
        if (studies.length > 1) {
            const addButton = this.$("#add-education");
            if (addButton.length && addButton.css("pointer-events") !== "none") {
                addButton.trigger("click");
                await this._sleep(500);
            }
        }

        const educationBlocks = this.$("#education_container [name^='level_id_']").length;
        for (let i = 0; i < Math.min(studies.length, educationBlocks); i++) {
            const education = studies[i];
            const index = i + 1;
            this._setValue(`select[name="level_id_${index}"]`, education.level_id);
            this._setValue(`input[name="institucion_${index}"]`, education.institucion);
            this._setValue(`input[name="inicioEstudio_${index}"]`, education.fecha_inicio, true);
            await this._sleep(50);
            this._setValue(`select[name="finEstudio_${index}"]`, education.year_fin);
            this._setValue(`select[name="paisEducacion_${index}"]`, `country-${education.country_id}`, true);
            await this._sleep(100);
            this._setValue(`select[name="ciudad_${index}"]`, `state-${education.state_id}`);
            this._setValue(`input[name="titulo_${index}"]`, education.titulo);
        }

        const education = studies[0] || {};
        this._setValue('input[name="titulo_por_obtener"]', education.titulo_por_obtener);
        this._setValue('input[name="institucion_2"]', education.institucion_2);
        this._setValue('input[name="horario"]', education.horario);
        this._setValue('input[name="carrera"]', education.carrera);
        this._setValue('input[name="estado"]', education.estado);

        // Experiencia.
        const experienceCount = Math.min(3, Math.max(1, data.experience?.length || 1));
        this._setValue("#total_experiences", experienceCount, true);
        await this._waitFor("#experience_container .experience-block", experienceCount, 10000);

        for (let i = 0; i < experienceCount; i++) {
            const exp = data.experience[i] || {};
            const index = i + 1;
            this._setValue(`input[name="company_${index}"]`, exp.empresa);
            this._setValue(`select[name="paisExperiencia_${index}"]`, `country-${exp.country_id}`, true);
            await this._sleep(80);
            this._setValue(`select[name="ciudadExperiencia_${index}"]`, `state-${exp.state_id}`);
            this._setValue(`input[name="telefonos_${index}"]`, exp.telefonos);
            this._setValue(`input[name="cargo_${index}"]`, exp.name);
            this._setValue(`input[name="ingreso_${index}"]`, exp.ingreso_mensual);
            this._setValue(`input[name="motivo_${index}"]`, exp.motivo_separacion);
            this._setValue(`input[name="jefe_${index}"]`, exp.jefe_directo);
            this._setValue(`input[name="cargoJefe_${index}"]`, exp.cargo_jefe_directo);
            this._setValue(`input[name="jobInicio_${index}"]`, exp.fecha_inicio, true);
            await this._sleep(50);
            this._setValue(`select[name="jobFin_${index}"]`, exp.year_fin);
        }

        // Referencias (el formulario crea inicialmente 3).
        const references = data.references || [];
        while (this.$("#reference_container .reference-block").length < references.length) {
            this.$("#add-reference").trigger("click");
            await this._sleep(100);
        }
        references.forEach((ref, index) => {
            const i = index;
            this._setValue(`input[name="ref_nombre_${i}"]`, ref.nombre);
            this._setValue(`input[name="ref_telefono_${i}"]`, ref.telefono);
            this._setValue(`input[name="ref_ocupacion_${i}"]`, ref.ocupacion);
            this._setValue(`input[name="ref_tiempo_${i}"]`, ref.tiempo_conocerlo);
            this._setValue(`input[name="ref_domicilio_${i}"]`, ref.domicilio);
        });

        const known = data.known || {};
        this._setRadio("knownPosee_1", known.posee ? "t" : "f", true);
        this._setValue('input[name="knownNombre_1"]', known.nombre);
        this._setRadio("knownRelacion_1", known.relacion, true);
        this._setValue('input[name="knownParentesco_1"]', known.parentesco);
    },
});
