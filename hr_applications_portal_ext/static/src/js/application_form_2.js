/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

const IGNORED_MEDICAL_KEYS = new Set([
    "id", "applicant_id", "create_uid", "create_date",
    "write_uid", "write_date", "display_name",
]);

function setValue(root, name, value) {
    const input = root.querySelector(`[name="${name}"]`);
    if (input && value !== undefined && value !== null) input.value = value;
}

function setRadio(root, name, value) {
    if (!value) return;
    const input = root.querySelector(`[name="${name}"][value="${value}"]`);
    if (input) input.checked = true;
}

function addChildBlock(container, index, family = {}, childNumber = index) {
    const block = document.createElement("div");
    block.className = "row d-flex justify-content-center family-block child-family-block";
    block.dataset.type = "Hijo";
    block.innerHTML = `
        <div class="col-12 col-md-10">
            <div class="py-3 d-flex justify-content-start mb-3">
                <span class="fw-normal fs-4 text-info">Hijo #${childNumber}</span>
            </div>
            <div class="row g-3">
                <div class="col-md-3">
                    <label class="fs-6">Apellido paterno</label>
                    <input type="text" name="famApellidoPaterno_${index}" class="form-control rounded-pill"/>
                </div>
                <div class="col-md-3">
                    <label class="fs-6">Apellido materno</label>
                    <input type="text" name="famApellidoMaterno_${index}" class="form-control rounded-pill"/>
                </div>
                <div class="col-md-3">
                    <label class="fs-6">Primer nombre</label>
                    <input type="text" name="famPrimerNombre_${index}" class="form-control rounded-pill"/>
                </div>
                <div class="col-md-3">
                    <label class="fs-6">Segundo nombre</label>
                    <input type="text" name="famSegundoNombre_${index}" class="form-control rounded-pill"/>
                </div>
                <input type="hidden" name="famNombre_${index}" class="fam-nombre-completo"/>

                <div class="col-md-3">
                    <label class="fs-6">Tipo de documento</label>
                    <select name="famTipoDoc_${index}" class="form-select rounded-pill py-2">
                        <option value=""></option>
                        <option value="cedula">Cédula</option>
                        <option value="ruc">RUC</option>
                        <option value="pasaporte">Pasaporte</option>
                    </select>
                </div>
                <div class="col-md-3">
                    <label class="fs-6">Número de documento</label>
                    <input type="text" name="famCedula_${index}" class="form-control rounded-pill"/>
                </div>
                <div class="col-md-3">
                    <label class="fs-6">Fecha nacimiento</label>
                    <input type="date" name="famFecha_${index}" class="form-control rounded-pill"/>
                </div>
                <div class="col-md-3">
                    <label class="fs-6">Teléfono</label>
                    <input type="tel" name="famTelefono_${index}" class="form-control rounded-pill"/>
                </div>
                <div class="col-md-3">
                    <label class="fs-6">Ocupación y Empresa</label>
                    <input type="text" name="famOcupacion_${index}" class="form-control rounded-pill"/>
                </div>
                <div class="col-md-3">
                    <label class="fs-6">Depende económicamente</label>
                    <div class="d-flex mt-2">
                        <label class="form-check me-3">
                            <input class="form-check-input" type="radio" name="famDepende_${index}" value="si"/> Sí
                        </label>
                        <label class="form-check">
                            <input class="form-check-input" type="radio" name="famDepende_${index}" value="no"/> No
                        </label>
                    </div>
                </div>
                <div class="col-md-3">
                    <label class="fs-6">Discapacidad</label>
                    <div class="d-flex mt-2">
                        <label class="form-check me-3">
                            <input class="form-check-input" type="radio" name="famDisc_${index}" value="si"/> Sí
                        </label>
                        <label class="form-check">
                            <input class="form-check-input" type="radio" name="famDisc_${index}" value="no"/> No
                        </label>
                    </div>
                </div>
                <div class="col-md-3">
                    <label class="fs-6">Tipo de discapacidad</label>
                    <input type="text" name="famDiscTipo_${index}" class="form-control rounded-pill"/>
                </div>
            </div>
        </div>`;

    container.appendChild(block);

    const updateName = () => {
        const parts = [
            block.querySelector(`[name="famApellidoPaterno_${index}"]`)?.value?.trim(),
            block.querySelector(`[name="famApellidoMaterno_${index}"]`)?.value?.trim(),
            block.querySelector(`[name="famPrimerNombre_${index}"]`)?.value?.trim(),
            block.querySelector(`[name="famSegundoNombre_${index}"]`)?.value?.trim(),
        ].filter(Boolean);
        setValue(block, `famNombre_${index}`, parts.join(" "));
    };

    block.querySelectorAll(
        `[name="famApellidoPaterno_${index}"],` +
        `[name="famApellidoMaterno_${index}"],` +
        `[name="famPrimerNombre_${index}"],` +
        `[name="famSegundoNombre_${index}"]`
    ).forEach((input) => input.addEventListener("input", updateName));

    updateName();

    setValue(block, `famNombre_${index}`, family.name);
    setValue(block, `famCedula_${index}`, family.cedula);
    setValue(block, `famFecha_${index}`, family.birthdate);
    setValue(block, `famTelefono_${index}`, family.phone);
    setValue(block, `famOcupacion_${index}`, family.occupation);
    setRadio(block, `famDepende_${index}`, family.economically_dependent);
    setRadio(block, `famDisc_${index}`, family.disability);
    setValue(block, `famDiscTipo_${index}`, family.disability_type);

    return block;
}

function addLegacyFamilyBlock(container, index, family = {}) {
    const block = document.createElement("div");
    block.className = "row d-flex justify-content-center family-block";
    block.innerHTML = `
      <div class="col-12 col-md-10">
        <div class="py-3 d-flex justify-content-start mb-3">
          <span class="fw-normal fs-4 text-info">Familiar #${index}</span>
        </div>
        <div class="row g-3">
          <div class="col-md-3"><label class="fs-6">Nombres completos</label><input type="text" name="famNombre_${index}" class="form-control rounded-pill"/></div>
          <div class="col-md-3"><label class="fs-6">Cédula</label><input type="text" name="famCedula_${index}" class="form-control rounded-pill"/></div>
          <div class="col-md-3"><label class="fs-6">Fecha nacimiento</label><input type="date" name="famFecha_${index}" class="form-control rounded-pill"/></div>
          <div class="col-md-3"><label class="fs-6">Teléfono</label><input type="tel" name="famTelefono_${index}" class="form-control rounded-pill"/></div>
          <div class="col-md-3"><label class="fs-6">Ocupación y Empresa</label><input type="text" name="famOcupacion_${index}" class="form-control rounded-pill"/></div>
          <div class="col-md-3"><label class="fs-6">Depende económicamente</label><div class="d-flex mt-2">
            <label class="form-check me-3"><input class="form-check-input" type="radio" name="famDepende_${index}" value="si"/> Sí</label>
            <label class="form-check"><input class="form-check-input" type="radio" name="famDepende_${index}" value="no"/> No</label>
          </div></div>
          <div class="col-md-3"><label class="fs-6">Discapacidad</label><div class="d-flex mt-2">
            <label class="form-check me-3"><input class="form-check-input" type="radio" name="famDisc_${index}" value="si"/> Sí</label>
            <label class="form-check"><input class="form-check-input" type="radio" name="famDisc_${index}" value="no"/> No</label>
          </div></div>
          <div class="col-md-3"><label class="fs-6">Tipo de discapacidad</label><input type="text" name="famDiscTipo_${index}" class="form-control rounded-pill"/></div>
        </div>
      </div>`;
    container.appendChild(block);
    setValue(block, `famNombre_${index}`, family.name);
    setValue(block, `famCedula_${index}`, family.cedula);
    setValue(block, `famFecha_${index}`, family.birthdate);
    setValue(block, `famTelefono_${index}`, family.phone);
    setValue(block, `famOcupacion_${index}`, family.occupation);
    setRadio(block, `famDepende_${index}`, family.economically_dependent);
    setRadio(block, `famDisc_${index}`, family.disability);
    setValue(block, `famDiscTipo_${index}`, family.disability_type);
    return block;
}

publicWidget.registry.HrApplicationsForm2 = publicWidget.Widget.extend({
    selector: "#hr_application_form2",

    start() {
        const result = this._super(...arguments);
        this.form = this.el;
        this.payload = document.getElementById("hr_application_form2_payload");

        // El XML nativo trae #form-step-2 con d-none. En el historial
        // queremos mostrar exclusivamente este formulario.
        const step2 = this.form.querySelector("#form-step-2");
        if (step2) step2.classList.remove("d-none");

        this._loadPayload();

        this.form.querySelector("#prev-button-2")?.remove();
        this.form.querySelector("#next-button-step2")?.remove();

        const addButton = this.form.querySelector("#add-family");
        if (addButton) addButton.addEventListener("click", (ev) => {
            ev.preventDefault();
            const container = this.form.querySelector("#family_container");
            addLegacyFamilyBlock(container, container.querySelectorAll(".family-block").length + 1);
        });

        this.form.addEventListener("submit", () => {
            const button = document.getElementById("hr_application_form2_save");
            if (button) {
                button.disabled = true;
                button.textContent = "Guardando...";
            }
        });
        return result;
    },

    _json(name, fallback) {
        try {
            return JSON.parse(this.payload.dataset[name] || JSON.stringify(fallback));
        } catch {
            return fallback;
        }
    },

    _loadPayload() {
        const medical = this._json("medical", {});
        for (const [name, value] of Object.entries(medical)) {
            if (["enfermedad_persistente", "medicacion_continua", "enfermedad_laboral", "cirugia_realizada", "discapacidad"].includes(name)) {
                setRadio(this.form, name, value);
            } else if (!IGNORED_MEDICAL_KEYS.has(name)) {
                setValue(this.form, name, value);
            }
        }

        const container = this.form.querySelector("#family_container");
        if (!container) return;

        container.innerHTML = "";

        const families = this._json("families", []);
        const numHijos = Math.max(parseInt(this.payload.dataset.numHijos || "0", 10) || 0, 0);

        // Conservamos familiares ya guardados. Si el postulante tiene hijos
        // registrados en hr.applicant y todavía no existen líneas familiares
        // suficientes, generamos los bloques faltantes para completar esa
        // cantidad. Esto evita duplicarlos cuando ya fueron guardados.
        families.forEach((family, i) => addLegacyFamilyBlock(container, i + 1, family));

        const existingCount = families.length;
        const missingChildren = Math.max(numHijos - existingCount, 0);
        for (let i = 0; i < missingChildren; i++) {
            const index = existingCount + i + 1;
            addChildBlock(container, index, {}, i + 1);
        }
    },
});
