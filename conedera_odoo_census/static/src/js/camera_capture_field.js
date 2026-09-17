/** @odoo-module **/

import { Component, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class CameraCaptureField extends Component {
    static template = "conedera_odoo_census.CameraCaptureField";
    static props = { ...standardFieldProps };

    setup() {
        this.notification = useService("notification");
        this.fileInput = useRef("fileInput");
        this.state = useState({ loading: false, preview: null });
    }

    get hasValue() {
        return Boolean(this.props.record.data[this.props.name]);
    }

    openCamera() {
        if (!this.props.readonly) {
            this.fileInput.el?.click();
        }
    }

    async onFileChange(ev) {
        const file = ev.target.files?.[0];
        if (!file) {
            return;
        }
        if (!file.type.startsWith("image/")) {
            this.notification.add(_t("Seleccione o tome una fotografía válida."), { type: "danger" });
            return;
        }
        this.state.loading = true;
        try {
            const dataUrl = await new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onload = () => resolve(reader.result);
                reader.onerror = reject;
                reader.readAsDataURL(file);
            });
            const encoded = String(dataUrl).split(",", 2)[1];
            this.state.preview = dataUrl;
            await this.props.record.update({ [this.props.name]: encoded });
            this.notification.add(_t("Foto capturada. Guarde la visita para conservarla."), { type: "success" });
        } catch (_error) {
            this.notification.add(_t("No fue posible procesar la fotografía."), { type: "danger" });
        } finally {
            this.state.loading = false;
            ev.target.value = "";
        }
    }
}

export const cameraCaptureField = {
    component: CameraCaptureField,
    supportedTypes: ["binary"],
};

registry.category("fields").add("camera_capture", cameraCaptureField);
