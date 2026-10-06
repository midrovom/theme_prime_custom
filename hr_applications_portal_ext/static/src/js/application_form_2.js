/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

function setValue(root, name, value) {
    const input = root.querySelector(`[name="${name}"]`);
    if (input && value !== undefined && value !== null) input.value = value;
}
function setRadio(root, name, value) {
    if (!value) return;
    const input = root.querySelector(`[name="${name}"][value="${value}"]`);
    if (input) input.checked = true;
}
function addFamilyBlock(container, index, family = {}) {
    const block = document.createElement("div");
    block.className = "row d-flex justify-content-center family-block";
    block.innerHTML = `
      <div class="col-12 col-md-10">
        <div class="py-3 d-flex justify-content-start mb-3">
          <span class="fw-normal fs-4 text-info">${index === 1 ? "Datos Familiares" : "Familiar #" + index}</span>
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
}

publicWidget.registry.HrApplicationsForm2 = publicWidget.Widget.extend({
    selector: "#hr_application_form2",
    start() {
        const result = this._super(...arguments);
        this.form = this.el;
        this.payload = document.getElementById("hr_application_form2_payload");
        this._loadPayload();
        this.form.querySelector("#prev-button-2")?.remove();
        this.form.querySelector("#next-button-step2")?.remove();

        const addButton = this.form.querySelector("#add-family");
        if (addButton) addButton.addEventListener("click", (ev) => {
            ev.preventDefault();
            const container = this.form.querySelector("#family_container");
            addFamilyBlock(container, container.querySelectorAll(".family-block").length + 1);
        });
        this.form.addEventListener("submit", () => {
            const button = document.getElementById("hr_application_form2_save");
            if (button) { button.disabled = true; button.textContent = "Guardando..."; }
        });
        return result;
    },
    _json(name, fallback) {
        try { return JSON.parse(this.payload.dataset[name] || JSON.stringify(fallback)); }
        catch { return fallback; }
    },
    _loadPayload() {
        const medical = this._json("medical", {});
        for (const [name, value] of Object.entries(medical)) {
            if (["enfermedad_persistente","medicacion_continua","enfermedad_laboral","cirugia_realizada","discapacidad"].includes(name))
                setRadio(this.form, name, value);
            else if (!["id","applicant_id","create_uid","create_date","write_uid","write_date","display_name"].includes(name))
                setValue(this.form, name, value);
        }
        const container = this.form.querySelector("#family_container");
        if (container) {
            container.innerHTML = "";
            this._json("families", []).forEach((family, i) => addFamilyBlock(container, i + 1, family));
        }
    },
});
