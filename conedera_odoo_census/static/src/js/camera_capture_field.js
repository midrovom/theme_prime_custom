/** @odoo-module **/

import { Component, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { imageUrl } from "@web/core/utils/urls";
import { isBinarySize } from "@web/core/utils/binary";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

const fileTypeMagicWordMap = {
    "/": "jpeg",
    R: "gif",
    i: "png",
    P: "svg+xml",
    U: "webp",
};

export class CameraCaptureField extends Component {
    static template = "conedera_odoo_census.CameraCaptureField";
    static props = { ...standardFieldProps };

    setup() {
        this.notification = useService("notification");
        this.fileInput = useRef("fileInput");
        this.state = useState({ loading: false, preview: null, fullscreen: false });
    }

    get value() {
        return this.props.record.data[this.props.name];
    }

    get hasValue() {
        return Boolean(this.value);
    }

    get imageSrc() {
        if (this.state.preview) {
            return this.state.preview;
        }
        const value = this.value;
        if (!value) {
            return null;
        }
        if (isBinarySize(value) && this.props.record.resId) {
            return imageUrl(
                this.props.record.resModel,
                this.props.record.resId,
                this.props.name,
                { unique: this.props.record.data.write_date || "" }
            );
        }
        const raw = String(value);
        const magic = fileTypeMagicWordMap[raw[0]] || "jpeg";
        return `data:image/${magic};base64,${raw}`;
    }

    get captureLabel() {
        return this.hasValue ? _t("Tomar otra foto") : _t("Tomar foto");
    }

    openCamera() {
        if (!this.props.readonly) {
            this.fileInput.el?.click();
        }
    }

    openPreview() {
        if (this.imageSrc) {
            this.state.fullscreen = true;
        }
    }

    closePreview() {
        this.state.fullscreen = false;
    }

    async clearPhoto() {
        if (this.props.readonly) {
            return;
        }
        this.state.preview = null;
        this.state.fullscreen = false;
        await this.props.record.update({ [this.props.name]: false });
        this.notification.add(_t("Foto eliminada. Guarde la visita para confirmar el cambio."), {
            type: "info",
        });
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
            this.notification.add(_t("Foto lista. Pulse Guardar visita o Finalizar visita."), {
                type: "success",
            });
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
    fieldDependencies: [{ name: "write_date", type: "datetime" }],
};

registry.category("fields").add("camera_capture", cameraCaptureField);
