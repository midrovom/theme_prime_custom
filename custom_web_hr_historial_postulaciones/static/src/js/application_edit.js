/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

const MultistepForm = publicWidget.registry.MultistepForm;

if (MultistepForm && !MultistepForm.prototype.__portalEditPatchedV2) {
    // ---------------------------------------------------------------
    // Helpers
    // ---------------------------------------------------------------
    const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));

    const waitFor = async function (selector, minimum = 1, timeout = 20000) {
        const start = Date.now();
        while (Date.now() - start < timeout) {
            if (this.$(selector).length >= minimum) {
                return;
            }
            await sleep(100);
        }
        throw new Error(`Tiempo agotado esperando ${selector}`);
    };

    const isEditMode = function () {
        return this.$el?.attr("data-portal-edit") === "1";
    };

    const setValue = function (selector, value, trigger = false) {
        const $field = this.$(selector);
        if (!$field.length) return;
        $field.val(value ?? "");
        if (trigger) {
            $field.trigger("change");
        }
    };

    const setRadio = function (name, value, trigger = true) {
        if (value === undefined || value === null || value === "") return;
        const $radio = this.$(`input[name="${name}"][value="${value}"]`);
        if (!$radio.length) return;
        $radio.prop("checked", true);
        if (trigger) {
            $radio.trigger("change");
        }
    };

    const setChecks = function (name, values) {
        const wanted = new Set(values || []);
        this.$(`input[name="${name}"]`).each(function () {
            this.checked = wanted.has(this.value);
        });
    };

    const splitFullName = function (value) {
        const parts = String(value || "").trim().split(/\s+/).filter(Boolean);
        return {
            paterno: parts[0] || "",
            materno: parts[1] || "",
            primero: parts[2] || "",
            segundo: parts.slice(3).join(" "),
        };
    };

    // ---------------------------------------------------------------
    // Archivo/imagen/currículum existentes
    // ---------------------------------------------------------------
    const originalValidateImage = MultistepForm.prototype._validateImage;
    const originalValidateCurriculum = MultistepForm.prototype._validateCurriculum;

    MultistepForm.prototype._validateImage = function (ev) {
        const existingImage = this.$el.attr("data-existing-image") === "1";
        const input = this.$("#hr-perfil")[0];

        if (isEditMode.call(this) && existingImage && input && !input.files?.length && !ev) {
            const errorDiv = document.getElementById("image-error");
            if (errorDiv) {
                errorDiv.textContent = "";
                errorDiv.style.display = "none";
            }
            input.classList.remove("is-invalid");
            return true;
        }

        return originalValidateImage.call(this, ev);
    };

    MultistepForm.prototype._validateCurriculum = function () {
        const existingCurriculum = this.$el.attr("data-existing-curriculum") === "1";
        const hasNewFiles = this.uploadedFiles && this.uploadedFiles.length > 0;

        if (isEditMode.call(this) && existingCurriculum && !hasNewFiles) {
            this.$("#curriculum-vitae").removeClass("is-invalid");
            return true;
        }

        return originalValidateCurriculum.call(this);
    };

    // ---------------------------------------------------------------
    // Familia: no exigir volver a subir un documento ya existente.
    // ---------------------------------------------------------------
    const originalValidateFamilyFields = MultistepForm.prototype._validateFamilyFields;
    MultistepForm.prototype._validateFamilyFields = function (i) {
        if (!isEditMode.call(this)) {
            return originalValidateFamilyFields.call(this, i);
        }

        const existingDocument = this.$el.attr(`data-family-existing-document-${i}`) === "1";
        const $file = this.$(`input[name="famArchivo_${i}"]`);

        if (!existingDocument || !$file.length || $file[0].files?.length) {
            return originalValidateFamilyFields.call(this, i);
        }

        // Validamos con la lógica original, pero temporalmente retiramos el
        // campo de archivo de la comprobación para ese familiar.
        const previousRequired = $file.prop("required");
        const previousName = $file.attr("data-original-validation-name");
        $file.attr("data-original-validation-name", `famArchivo_${i}`);
        $file.removeAttr("name").prop("required", false).removeClass("is-invalid");

        let valid;
        try {
            valid = originalValidateFamilyFields.call(this, i);
        } finally {
            $file.attr("name", previousName || `famArchivo_${i}`);
            $file.prop("required", previousRequired);
        }
        return valid;
    };

    // En el paso 2 Odoo también comprueba explícitamente el archivo cuando el
    // tipo es "Partida de nacimiento". Si ese archivo ya existe en el servidor,
    // se omite temporalmente esa comprobación y se restaura el valor original.
    const originalNextStep2 = MultistepForm.prototype._onNextStep2;
    MultistepForm.prototype._onNextStep2 = function (ev) {
        if (!isEditMode.call(this)) {
            return originalNextStep2.call(this, ev);
        }

        const restore = [];
        this.$("#family_container .family-block").each(function () {
            const $block = $(this);
            const $type = $block.find('select[name^="famTipoDoc_"]');
            const $file = $block.find('input[name^="famArchivo_"]');
            const index = $file.attr("name")?.split("_")[1];
            const existing = index && document.querySelector("#hr_job_recruitment_form")?.getAttribute(`data-family-existing-document-${index}`) === "1";

            if ($type.length && $file.length && existing && $type.val() === "part_naci" && !$file[0].files?.length) {
                restore.push({
                    $type,
                    value: $type.val(),
                });
                // El validador nativo solo usa el valor para decidir si exige
                // el PDF. Después de validar lo restauramos.
                $type.val("cedula");
            }
        });

        try {
            return originalNextStep2.call(this, ev);
        } finally {
            restore.forEach(item => item.$type.val(item.value));
        }
    };

    // ---------------------------------------------------------------
    // Precarga real sobre la instancia NATIVA del formulario.
    // Esto garantiza que la precarga ocurra después de que el widget nativo
    // haya creado sus bloques dinámicos.
    // ---------------------------------------------------------------
    const originalStart = MultistepForm.prototype.start;

    MultistepForm.prototype.start = async function (...args) {
        const params = new URLSearchParams(window.location.search);
        const applicantId = params.get("edit_applicant");
        const editRequested = applicantId && /^\d+$/.test(applicantId);

        if (editRequested) {
            this.$el.attr("data-portal-edit", "1");
            this.$el.attr("data-edit-applicant-id", applicantId);
            this.$el.attr("action", `/my/application/${applicantId}/update`);
        }

        const result = await originalStart.apply(this, args);

        if (!editRequested) {
            return result;
        }

        if (!this.$el.prev("#portal-edit-notice").length) {
            this.$el.before(`
                <div id="portal-edit-notice" class="alert alert-warning rounded-4 mb-4">
                    Esta actualización fue habilitada por el equipo de reclutamiento.
                    Al guardar, se conservará la información existente y solo se modificarán los datos que cambie.
                </div>
            `);
        }

        try {
            await loadApplicantData.call(this, applicantId);
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

        return result;
    };

    async function loadApplicantData(applicantId) {
        const response = await fetch(`/my/application/${applicantId}/data`, {
            headers: { "Accept": "application/json" },
            credentials: "same-origin",
        });

        if (!response.ok) {
            throw new Error(`No fue posible consultar la postulación (${response.status}).`);
        }

        const data = await response.json();

        this.$el.attr("data-existing-image", data.has_image ? "1" : "0");
        this.$el.attr("data-existing-curriculum", data.has_curriculum ? "1" : "0");

        await waitFor.call(this, "#education_container .education-block, #education_container [name^='level_id_']", 1);

        // Primero completamos el Paso 1.
        fillStep1.call(this, data);

        // También cargamos las variables de salud ANTES de intentar pasar
        // internamente al paso 2, porque el formulario nativo las valida.
        fillMedical.call(this, data.medical || {});

        // Generar los bloques nativos del paso 2 sin enviar el formulario.
        // _onNextClick solo cambia de paso y crea los familiares; no enviamos nada.
        this._onNextClick({ preventDefault() {} });

        const expectedFamilyBlocks = 3 + Math.max(0, Number(data.num_hijos || 0));
        await waitFor.call(this, "#family_container .family-block", expectedFamilyBlocks);

        await fillFamilies.call(this, data.family || []);

        // Rellenar la información de estudio/experiencia/referencias sin usar
        // la validación del botón Siguiente.
        this.$("#famNumHermanos").val((data.family || []).filter(x => x.familiar_type === "3").length || 1);
        this.$("#famNumHermanos").prop("readonly", true);

        // Mostrar el paso 3 para que el usuario pueda continuar con el flujo
        // nativo. No se valida aquí; ya estamos precargando datos existentes.
        this.$("#form-step-2").addClass("d-none");
        this.$("#form-step-3").removeClass("d-none");

        await fillStep3.call(this, data);

        // Dejar al postulante en el Paso 1.
        this.$("#form-step-1").removeClass("d-none");
        this.$("#form-step-2").addClass("d-none");
        this.$("#form-step-3").addClass("d-none");

        if (!this.$el.prev("#portal-edit-loaded").length) {
            this.$el.before(`
                <div id="portal-edit-loaded" class="alert alert-success rounded-4 mb-4">
                    La información registrada anteriormente fue cargada. Revise o corrija los datos necesarios y continúe con los siguientes pasos.
                </div>
            `);
        }
    }

    function fillStep1(data) {
        setValue.call(this, "#hr-lastname-paterno", data.lastname_paterno);
        setValue.call(this, "#hr-lastname-materno", data.lastname_materno);
        setValue.call(this, "#hr-name", data.firstname);
        setValue.call(this, "#hr-age", data.age);
        setValue.call(this, "#hr-address", data.address);
        setValue.call(this, "#hr-parish", data.parish);

        setValue.call(this, "#hr-day", data.birthdate?.day);
        setValue.call(this, "#hr-month", data.birthdate?.month);
        setValue.call(this, "#hr-year", data.birthdate?.year);

        setValue.call(this, "#hr-country", data.birth_country_id, true);
        setValue.call(this, "#hr-provincia", data.provincia_id);
        setValue.call(this, "#hr-code-cellphone", data.cellphone_code || "+593");
        setValue.call(this, "#hr-cellphone", data.cellphone);
        setValue.call(this, "#hr-phone", data.phone);
        setValue.call(this, "#hr-email", data.email);
        setValue.call(this, "#hr-hijos", data.num_hijos);
        setChecks.call(this, "dependientes", data.dependientes);

        setRadio.call(this, "viveCon", data.vive_con, false);
        setRadio.call(this, "tipoVivienda", data.tipo_vivienda, false);
        setRadio.call(this, "estadoCivil", data.estado_civil, false);
        setValue.call(this, "#hr-type-doc", data.document_type);
        setValue.call(this, "#hr-number-doc", data.document_number);
        setValue.call(this, "#hr-nationality", data.nationality);

        // Estas opciones pertenecen a lógica del formulario original.
        // No reemplazan a la información médica del paso 2.
        if (data.disability !== undefined) {
            setRadio.call(this, "jobOptions", data.disability ? "t" : "f", true);
        }
        if (data.family_disability !== undefined) {
            setRadio.call(this, "discOptions", data.family_disability ? "t" : "f", true);
        }

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
    }

    function fillMedical(medical) {
        const values = [
            "enfermedad_persistente",
            "medicacion_continua",
            "enfermedad_laboral",
            "cirugia_realizada",
            "discapacidad",
        ];

        values.forEach(name => {
            setRadio.call(this, name, medical[name] || "no", true);
        });

        setValue.call(this, 'input[name="detalle_enfermedad_persistente"]', medical.detalle_enfermedad_persistente);
        setValue.call(this, 'input[name="detalle_medicacion_continua"]', medical.detalle_medicacion_continua);
        setValue.call(this, 'input[name="detalle_enfermedad_laboral"]', medical.detalle_enfermedad_laboral);
        setValue.call(this, 'input[name="detalle_cirugia_realizada"]', medical.detalle_cirugia_realizada);
        setValue.call(this, 'input[name="tipo_discapacidad"]', medical.tipo_discapacidad);
        setValue.call(this, 'input[name="porcentaje_discapacidad"]', medical.porcentaje_discapacidad);
        setValue.call(this, 'input[name="tipo_sangre"]', medical.tipo_sangre);

        // El formulario original tiene un bug: al validar el paso 1 consulta
        // este radio del paso 2. Lo dejamos marcado antes de avanzar.
        const discapacidad = medical.discapacidad || "no";
        setRadio.call(this, "discapacidad", discapacidad, true);
    }

    async function fillFamilies(families) {
        const byType = {};
        (families || []).forEach(family => {
            byType[family.familiar_type] = byType[family.familiar_type] || [];
            byType[family.familiar_type].push(family);
        });

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

            const name = splitFullName(family.name);
            setValue.call(this, `input[name="famApellidoPaterno_${index}"]`, name.paterno);
            setValue.call(this, `input[name="famApellidoMaterno_${index}"]`, name.materno);
            setValue.call(this, `input[name="famPrimerNombre_${index}"]`, name.primero);
            setValue.call(this, `input[name="famSegundoNombre_${index}"]`, name.segundo);
            setValue.call(this, `input[name="famNombre_${index}"]`, family.name);
            setValue.call(this, `select[name="famTipoDoc_${index}"]`, family.document_type, true);
            setValue.call(this, `input[name="famCedula_${index}"]`, family.cedula);
            setValue.call(this, `input[name="famFecha_${index}"]`, family.birthdate);
            setValue.call(this, `input[name="famTelefono_${index}"]`, family.phone);
            setValue.call(this, `input[name="famOcupacion_${index}"]`, family.occupation);
            setRadio.call(this, `famDepende_${index}`, family.economically_dependent, false);
            setRadio.call(this, `famDisc_${index}`, family.disability, true);
            setValue.call(this, `input[name="famDiscTipo_${index}"]`, family.disability_type);
            setValue.call(this, `input[name="famDiscPorcentaje_${index}"]`, family.disability_percentage);

            const $fallecido = this.$(`input[name="famFallecido_${index}"]`);
            if ($fallecido.length) {
                $fallecido.prop("checked", !!family.fallecido).trigger("change");
            }

            const $noTiene = this.$(`input[name="famNoTiene_${index}"]`);
            if ($noTiene.length) {
                $noTiene.prop("checked", !!family.no_tiene).trigger("change");
            }

            // Guardar el ID para que el servidor pueda conservar el PDF del
            // familiar si el usuario no selecciona uno nuevo.
            if (family.id) {
                let hidden = this.$(`input[name="famOriginalId_${index}"]`);
                if (!hidden.length) {
                    hidden = $("<input>", {
                        type: "hidden",
                        name: `famOriginalId_${index}`,
                    }).appendTo($block);
                }
                hidden.val(family.id);
            }

            this.$el.attr(`data-family-existing-document-${index}`, family.has_document ? "1" : "0");

            if (family.fallecido || family.no_tiene) {
                continue;
            }

            // Mostrar una leyenda para los PDFs existentes.
            if (family.has_document && family.filename) {
                let $message = $block.find(".portal-family-existing-file");
                if (!$message.length) {
                    $message = $('<div class="portal-family-existing-file text-success small mt-1"></div>');
                    const $file = $block.find(`input[name="famArchivo_${index}"]`);
                    $file.after($message);
                }
                $message.text(`Documento registrado: ${family.filename}. Puede conservarlo o reemplazarlo.`);
            }
        }
    }

    async function fillStep3(data) {
        const studies = data.education || [];
        const studyCurrent = data.secondary_studies ? "t" : "f";
        setRadio.call(this, "studyOptions", studyCurrent, true);

        // El formulario nativo crea inicialmente una formación.
        await waitFor.call(this, "#education_container [name^='level_id_']", 1);

        while (this.$("#education_container [name^='level_id_']").length < studies.length) {
            const addButton = this.$("#add-education");
            if (!addButton.length) break;
            this.educationCount++;
            const block = await this._getEducationBlock(false);
            this.$("#education_container").prepend(block);
        }

        const educationBlocks = this.$("#education_container [name^='level_id_']").length;
        for (let i = 0; i < Math.min(studies.length, educationBlocks); i++) {
            const education = studies[i] || {};
            const index = i + 1;
            setValue.call(this, `select[name="level_id_${index}"]`, education.level_id);
            setValue.call(this, `input[name="institucion_${index}"]`, education.institucion);
            setValue.call(this, `input[name="inicioEstudio_${index}"]`, education.fecha_inicio, true);
            await sleep(50);
            setValue.call(this, `select[name="finEstudio_${index}"]`, education.year_fin);
            setValue.call(this, `select[name="paisEducacion_${index}"]`, education.country_id ? `country-${education.country_id}` : "", true);
            await sleep(80);
            setValue.call(this, `select[name="ciudad_${index}"]`, education.state_id ? `state-${education.state_id}` : "");
            setValue.call(this, `input[name="titulo_${index}"]`, education.titulo);
        }

        const firstEducation = studies[0] || {};
        setValue.call(this, 'input[name="titulo_por_obtener"]', firstEducation.titulo_por_obtener);
        setValue.call(this, 'input[name="institucion_2"]', firstEducation.institucion_2);
        setValue.call(this, 'input[name="horario"]', firstEducation.horario);
        setValue.call(this, 'input[name="carrera"]', firstEducation.carrera);
        setValue.call(this, 'input[name="estado"]', firstEducation.estado);

        // Experiencias.
        const experiences = data.experience || [];
        const experienceCount = Math.min(3, Math.max(1, experiences.length || 1));
        setValue.call(this, "#total_experiences", experienceCount, true);
        await waitFor.call(this, "#experience_container .experience-block", experienceCount);

        for (let i = 0; i < experienceCount; i++) {
            const exp = experiences[i] || {};
            const index = i + 1;
            setValue.call(this, `input[name="tiempo_${index}"]`, exp.tiempo_servicio);
            setValue.call(this, `input[name="company_${index}"]`, exp.empresa);
            setValue.call(this, `select[name="paisExperiencia_${index}"]`, exp.country_id ? `country-${exp.country_id}` : "", true);
            await sleep(60);
            setValue.call(this, `select[name="ciudadExperiencia_${index}"]`, exp.state_id ? `state-${exp.state_id}` : "");
            setValue.call(this, `input[name="telefonos_${index}"]`, exp.telefonos);
            setValue.call(this, `input[name="cargo_${index}"]`, exp.name);
            setValue.call(this, `input[name="ingreso_${index}"]`, exp.ingreso_mensual);
            setValue.call(this, `input[name="motivo_${index}"]`, exp.motivo_separacion);
            setValue.call(this, `input[name="jefe_${index}"]`, exp.jefe_directo);
            setValue.call(this, `input[name="cargoJefe_${index}"]`, exp.cargo_jefe_directo);
            setValue.call(this, `input[name="jobInicio_${index}"]`, exp.fecha_inicio, true);
            await sleep(50);
            setValue.call(this, `select[name="jobFin_${index}"]`, exp.year_fin);
        }

        // Referencias.
        const references = data.references || [];
        while (this.$("#reference_container .reference-block").length < references.length) {
            this._addReferenceBlock();
        }
        references.forEach((ref, index) => {
            setValue.call(this, `input[name="ref_nombre_${index}"]`, ref.nombre);
            setValue.call(this, `input[name="ref_telefono_${index}"]`, ref.telefono);
            setValue.call(this, `input[name="ref_ocupacion_${index}"]`, ref.ocupacion);
            setValue.call(this, `input[name="ref_tiempo_${index}"]`, ref.tiempo_conocerlo);
            setValue.call(this, `input[name="ref_domicilio_${index}"]`, ref.domicilio);
        });

        const known = data.known || {};
        setRadio.call(this, "knownPosee_1", known.posee ? "t" : "f", true);
        setValue.call(this, 'input[name="knownNombre_1"]', known.nombre);
        setRadio.call(this, "knownRelacion_1", known.relacion, true);
        setValue.call(this, 'input[name="knownParentesco_1"]', known.parentesco);
    }

    MultistepForm.prototype.__portalEditPatchedV2 = true;
}
