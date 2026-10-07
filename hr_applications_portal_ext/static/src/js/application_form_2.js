/** @odoo-module **/

(() => {
    const FORM_ID = "#hr_application_form2";

    const safeParse = (value, fallback) => {
        try {
            return JSON.parse(value || "") || fallback;
        } catch (error) {
            console.warn("No se pudo interpretar el payload familiar del Formulario 2.", error);
            return fallback;
        }
    };

    const htmlEscape = (value) => {
        const div = document.createElement("div");
        div.textContent = value == null ? "" : String(value);
        return div.innerHTML;
    };

    const getDocumentOptions = () => `
        <option value=""></option>
        <option value="cedula">Cédula</option>
        <option value="id_extrj">Cédula extranjera</option>
        <option value="pasaporte">Pasaporte</option>
        <option value="part_naci">Partida de Nacimiento</option>
    `;

    const getFamilyBlock = (label, index, typeCode) => {
        const showDeceased = ["Padre", "Madre"].includes(label);
        const showNoTiene = ["Padre", "Madre", "Conyugue"].includes(label);
        const requiredFields = label === "Hijo(a)" || label === "Hermano(a)" || showDeceased || showNoTiene;
        return `
            <div class="row d-flex justify-content-center family-block" data-type="${htmlEscape(label)}" data-family-index="${index}">
                <div class="col-12 col-md-10">
                    <input type="hidden" name="famTipo_${index}" value="${htmlEscape(typeCode)}"/>
                    <input type="hidden" name="famIndex_${index}" value="${index}"/>

                    <div class="py-3 d-flex justify-content-start mb-3">
                        <span class="fw-normal fs-4 text-info">${htmlEscape(label)}</span>
                    </div>

                    <div class="col-12 d-flex align-items-center mb-3 gap-3">
                        ${showDeceased ? `
                            <div class="col-md-3 d-flex align-items-center">
                                <label class="fs-6 me-2">Fallecido</label>
                                <input class="form-check-input" type="checkbox" name="famFallecido_${index}" value="1"/>
                            </div>
                        ` : ""}
                        ${showNoTiene ? `
                            <div class="form-check">
                                <input class="form-check-input fam-no-tiene" type="checkbox" name="famNoTiene_${index}" value="1"/>
                                <label class="form-check-label fs-6">No tiene</label>
                            </div>
                        ` : ""}
                    </div>

                    <div class="row g-3">
                        <div class="col-md-3">
                            <label class="fs-6">Apellido paterno <span class="required-asterisk">*</span></label>
                            <input type="text" name="famApellidoPaterno_${index}" class="form-control rounded-pill" required="${requiredFields ? "required" : "required"}"/>
                            <div class="invalid-feedback">Campo obligatorio</div>
                        </div>
                        <div class="col-md-3">
                            <label class="fs-6">Apellido materno <span class="required-asterisk">*</span></label>
                            <input type="text" name="famApellidoMaterno_${index}" class="form-control rounded-pill" required="required"/>
                            <div class="invalid-feedback">Campo obligatorio</div>
                        </div>
                        <div class="col-md-3">
                            <label class="fs-6">Primer nombre <span class="required-asterisk">*</span></label>
                            <input type="text" name="famPrimerNombre_${index}" class="form-control rounded-pill" required="required"/>
                            <div class="invalid-feedback">Campo obligatorio</div>
                        </div>
                        <div class="col-md-3">
                            <label class="fs-6">Segundo nombre</label>
                            <input type="text" name="famSegundoNombre_${index}" class="form-control rounded-pill"/>
                        </div>

                        <input type="hidden" name="famNombre_${index}" class="fam-nombre-completo"/>

                        <div class="col-12 col-md-3">
                            <label class="fs-6">Tipo de documento <span class="text-danger">*</span></label>
                            <select name="famTipoDoc_${index}" class="form-select rounded-pill py-2" required="required">
                                ${getDocumentOptions()}
                            </select>
                            <div class="invalid-feedback">Seleccione una opción.</div>
                        </div>
                        <div class="col-md-3">
                            <label class="fs-6">Numero de Documento <span class="required-asterisk">*</span></label>
                            <input type="text" name="famCedula_${index}" class="form-control rounded-pill" required="required"/>
                            <div class="invalid-feedback">Campo obligatorio</div>
                        </div>
                        <div class="col-md-3">
                            <label class="fs-6">Fecha nacimiento <span class="required-asterisk">*</span></label>
                            <input type="date" name="famFecha_${index}" class="form-control rounded-pill" required="required"/>
                            <div class="invalid-feedback">Campo obligatorio</div>
                        </div>
                        <div class="col-md-3">
                            <label class="fs-6">Teléfono <span class="required-asterisk">*</span></label>
                            <input type="tel" name="famTelefono_${index}" class="form-control rounded-pill fam-telefono" required="required"/>
                            <div class="invalid-feedback">Campo obligatorio</div>
                        </div>
                        <div class="col-md-3">
                            <label class="fs-6">Ocupación y Empresa <span class="required-asterisk">*</span></label>
                            <input type="text" name="famOcupacion_${index}" class="form-control rounded-pill" required="required"/>
                            <div class="invalid-feedback">Campo obligatorio</div>
                        </div>
                        <div class="col-md-3">
                            <label class="fs-6">Depende económicamente <span class="required-asterisk">*</span></label>
                            <div class="d-flex mt-2">
                                <div class="form-check me-3">
                                    <input class="form-check-input" type="radio" name="famDepende_${index}" value="si" required="required"/>
                                    <label class="form-check-label">Sí</label>
                                </div>
                                <div class="form-check">
                                    <input class="form-check-input" type="radio" name="famDepende_${index}" value="no" required="required"/>
                                    <label class="form-check-label">No</label>
                                </div>
                            </div>
                        </div>
                        <div class="col-md-3">
                            <label class="fs-6">Discapacidad <span class="required-asterisk">*</span></label>
                            <div class="d-flex mt-2">
                                <div class="form-check me-3">
                                    <input class="form-check-input fam-disc-radio" type="radio" name="famDisc_${index}" value="si" required="required"/>
                                    <label class="form-check-label">Sí</label>
                                </div>
                                <div class="form-check">
                                    <input class="form-check-input fam-disc-radio" type="radio" name="famDisc_${index}" value="no" required="required"/>
                                    <label class="form-check-label">No</label>
                                </div>
                            </div>
                            <div class="invalid-feedback d-none fam-disc-error">Campo obligatorio</div>
                        </div>
                        <div class="col-md-3">
                            <label class="fs-6">Tipo de discapacidad</label>
                            <input type="text" name="famDiscTipo_${index}" class="form-control rounded-pill fam-disc-tipo" disabled="disabled"/>
                        </div>
                        <div class="col-md-3">
                            <label class="fs-6">Porcentaje de discapacidad</label>
                            <input type="number" name="famDiscPorcentaje_${index}" class="form-control rounded-pill fam-disc-porcentaje" min="0" max="100" step="1" disabled="disabled"/>
                            <div class="invalid-feedback">Ingrese un valor entre 0 y 100</div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    };

    const setBlockValues = ($block, record) => {
        if (!record) return;

        const index = $block.dataset.familyIndex;
        const name = String(record.name || "").trim();
        const parts = name.split(/\s+/).filter(Boolean);
        const set = (suffix, value) => {
            const el = $block.querySelector(`[name="${suffix}_${index}"]`);
            if (el && value !== undefined && value !== null) el.value = value;
        };

        if (parts.length) {
            set("famApellidoPaterno", parts[0] || "");
            set("famApellidoMaterno", parts[1] || "");
            set("famPrimerNombre", parts.slice(2).join(" ") || parts[0] || "");
        }
        set("famNombre", name);
        set("famTipoDoc", record.document_type || "");
        set("famCedula", record.cedula || "");
        set("famFecha", record.birthdate || "");
        set("famTelefono", record.phone || "");
        set("famOcupacion", record.occupation || "");
        set("famDiscTipo", record.disability_type || "");
        set("famDiscPorcentaje", record.disability_percentage || "");

        const fallecido = $block.querySelector(`input[name="famFallecido_${index}"]`);
        const noTiene = $block.querySelector(`input[name="famNoTiene_${index}"]`);
        if (fallecido) fallecido.checked = Boolean(record.fallecido);
        if (noTiene) noTiene.checked = Boolean(record.no_tiene);

        const depende = $block.querySelectorAll(`input[name="famDepende_${index}"]`);
        depende.forEach(input => { input.checked = input.value === (record.economically_dependent || ""); });
        const disc = $block.querySelectorAll(`input[name="famDisc_${index}"]`);
        disc.forEach(input => { input.checked = input.value === (record.disability || ""); });
    };

    const activateDisability = ($block) => {
        const index = $block.dataset.familyIndex;
        const value = $block.querySelector(`input[name="famDisc_${index}"]:checked`)?.value;
        const type = $block.querySelector(`[name="famDiscTipo_${index}"]`);
        const percentage = $block.querySelector(`[name="famDiscPorcentaje_${index}"]`);
        if (value === "si") {
            type.disabled = false;
            percentage.disabled = false;
        } else {
            type.disabled = true;
            percentage.disabled = true;
            type.value = "";
            percentage.value = "";
        }
    };

    const bindFamilyBlock = ($block) => {
        const index = $block.dataset.familyIndex;
        const updateName = () => {
            const val = [
                $block.querySelector(`[name="famApellidoPaterno_${index}"]`)?.value || "",
                $block.querySelector(`[name="famApellidoMaterno_${index}"]`)?.value || "",
                $block.querySelector(`[name="famPrimerNombre_${index}"]`)?.value || "",
                $block.querySelector(`[name="famSegundoNombre_${index}"]`)?.value || "",
            ].map(v => v.trim()).filter(Boolean).join(" ");
            const hidden = $block.querySelector(`[name="famNombre_${index}"]`);
            if (hidden) hidden.value = val;
        };

        $block.querySelectorAll(`input[name="famApellidoPaterno_${index}"], input[name="famApellidoMaterno_${index}"], input[name="famPrimerNombre_${index}"], input[name="famSegundoNombre_${index}"]`)
            .forEach(input => input.addEventListener("input", updateName));

        $block.querySelectorAll(`input[name="famDisc_${index}"]`).forEach(input => {
            input.addEventListener("change", () => activateDisability($block));
        });

        const deceased = $block.querySelector(`input[name="famFallecido_${index}"]`);
        const noTiene = $block.querySelector(`input[name="famNoTiene_${index}"]`);
        const applySpecialState = () => {
            const locked = Boolean(deceased?.checked || noTiene?.checked);
            if (deceased?.checked && noTiene) noTiene.checked = false;
            if (noTiene?.checked && deceased) deceased.checked = false;
            $block.querySelectorAll("input:not([type='hidden']), select, textarea").forEach(field => {
                if (field === deceased || field === noTiene) return;
                field.disabled = locked;
                if (locked) {
                    field.required = false;
                    if (field.type === "radio" || field.type === "checkbox") field.checked = false;
                    else field.value = "";
                } else {
                    field.required = true;
                }
            });
            const hidden = $block.querySelector(`[name="famNombre_${index}"]`);
            if (hidden) hidden.value = deceased?.checked ? "FALLECIDO" : noTiene?.checked ? "NO TIENE" : hidden.value;
        };
        if (deceased) deceased.addEventListener("change", applySpecialState);
        if (noTiene) noTiene.addEventListener("change", applySpecialState);

        updateName();
        if (deceased?.checked || noTiene?.checked) {
            const specialName = deceased?.checked ? "FALLECIDO" : "NO TIENE";
            const hidden = $block.querySelector(`[name="famNombre_${index}"]`);
            if (hidden) hidden.value = specialName;
        }
        applySpecialState();
        activateDisability($block);
    };

    const ensureSiblingField = (container) => {
        let input = document.querySelector("#famNumHermanos");
        if (input) return input;
        const wrapper = document.createElement("div");
        wrapper.className = "row d-flex justify-content-center mb-4 o_hr_num_hermanos_generated";
        wrapper.innerHTML = `
            <div class="col-12 col-md-10">
                <label class="fs-6">Número de hermanos:</label>
                <input type="number" id="famNumHermanos" name="numHermanos" class="form-control rounded-pill py-2" min="0" value="0"/>
                <div class="invalid-feedback">Ingrese 0 o un número mayor.</div>
            </div>
        `;
        container.parentElement.insertBefore(wrapper, container);
        return wrapper.querySelector("#famNumHermanos");
    };

    const normalizeNativeReferencesForController = () => {
        const form = document.querySelector("#hr_job_recruitment_form");
        if (!form) return;

        const zeroBased = form.querySelector('input[name="ref_nombre_0"]');
        const third = form.querySelector('input[name="ref_nombre_3"]');
        if (zeroBased || !third) return;

        const suffixes = ["nombre", "telefono", "ocupacion", "tiempo", "domicilio"];
        const mappings = [[3, 2], [2, 1], [1, 0]];

        for (const [from, to] of mappings) {
            for (const suffix of suffixes) {
                form.querySelectorAll(`[name="ref_${suffix}_${from}"]`).forEach((input) => {
                    input.name = `ref_${suffix}_${to}`;
                });
            }
        }
    };

    const bindNativeReferenceFix = () => {
        const form = document.querySelector("#hr_job_recruitment_form");
        if (!form || form.dataset.hrReferenceNormalized === "1") return;

        const normalize = () => normalizeNativeReferencesForController();
        form.addEventListener("submit", normalize, true);
        form.dataset.hrReferenceNormalized = "1";
    };

    const initializeForm2 = () => {
        bindNativeReferenceFix();

        const form = document.querySelector(FORM_ID);
        if (!form) return;

        const payload = document.querySelector("#hr_application_form2_payload");
        const familyContainer = document.querySelector("#family_container");
        if (!familyContainer) return;

        familyContainer.querySelectorAll(".family-block").forEach(node => node.remove());

        const numHijos = Math.max(0, parseInt(payload?.dataset.numHijos || "0", 10) || 0);
        const familyRecords = safeParse(payload?.dataset.families || "[]", []);

        const recordsByType = {
            "1": [],
            "2": [],
            "3": [],
            "4": [],
            "5": [],
        };

        familyRecords.forEach((record) => {
            const type = String(record?.familiar_type || "");
            if (recordsByType[type]) recordsByType[type].push(record);
        });

        let familyCount = 0;

        const appendFamily = (label, typeCode, record) => {
            familyCount += 1;
            const wrapper = document.createElement("div");
            wrapper.innerHTML = getFamilyBlock(label, familyCount, typeCode).trim();
            const block = wrapper.firstElementChild;
            familyContainer.appendChild(block);
            setBlockValues(block, record);
            bindFamilyBlock(block);
        };

        // El nativo siempre presenta un bloque para Padre, Madre y Cónyuge.
        appendFamily("Padre", "1", recordsByType["1"][0] || null);
        appendFamily("Madre", "2", recordsByType["2"][0] || null);
        appendFamily("Conyugue", "4", recordsByType["4"][0] || null);

        // Los hijos se generan exactamente según hr.applicant.num_hijos.
        for (let i = 0; i < numHijos; i++) {
            appendFamily("Hijo(a)", "5", recordsByType["5"][i] || null);
        }

        // El número de hermanos es exclusivamente de frontend y no se guarda
        // en hr.applicant. El campo ya existe en el Formulario 2 nativo.
        const siblingInput = document.querySelector("#famNumHermanos");
        if (siblingInput) {
            const renderSiblings = () => {
                const quantity = Math.max(0, parseInt(siblingInput.value || "0", 10) || 0);
                familyContainer
                    .querySelectorAll('.family-block[data-type="Hermano(a)"]')
                    .forEach(node => node.remove());

                for (let i = 0; i < quantity; i++) {
                    appendFamily("Hermano(a)", "3", recordsByType["3"][i] || null);
                }
            };

            siblingInput.addEventListener("input", renderSiblings);
            siblingInput.addEventListener("change", renderSiblings);
            renderSiblings();
        }

        const step2 = document.querySelector("#form-step-2");
        if (step2) step2.classList.remove("d-none");
    };

    // Los assets de Odoo pueden cargarse después de DOMContentLoaded.
    // Ejecutamos inmediatamente si el DOM ya está listo y, de lo contrario,
    // esperamos una sola vez al evento.
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initializeForm2, { once: true });
    } else {
        initializeForm2();
    }
})();
