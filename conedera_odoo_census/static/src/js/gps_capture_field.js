/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class GpsCaptureField extends Component {
    static template = "conedera_odoo_census.GpsCaptureField";
    static props = { ...standardFieldProps };

    setup() {
        this.notification = useService("notification");
        this.state = useState({ loading: false });
    }

    get hasValue() {
        return Boolean(this.props.record.data[this.props.name]);
    }

    async captureLocation() {
        if (this.props.readonly) {
            return;
        }

        // Los navegadores modernos bloquean Geolocation API en HTTP salvo localhost.
        if (!window.isSecureContext) {
            this.notification.add(
                _t("La captura GPS requiere HTTPS. Abra Odoo mediante una URL segura (https://)."),
                { type: "danger", sticky: true }
            );
            return;
        }

        if (!navigator.geolocation) {
            this.notification.add(_t("Este dispositivo o navegador no soporta geolocalización."), {
                type: "danger",
            });
            return;
        }

        this.state.loading = true;
        try {
            const position = await new Promise((resolve, reject) => {
                navigator.geolocation.getCurrentPosition(resolve, reject, {
                    enableHighAccuracy: true,
                    timeout: 20000,
                    maximumAge: 0,
                });
            });
            const payload = JSON.stringify({
                latitude: position.coords.latitude,
                longitude: position.coords.longitude,
                accuracy: position.coords.accuracy || 0,
                capturedAt: new Date(position.timestamp).toISOString(),
            });

            await this.props.record.update({ [this.props.name]: payload });
            this.notification.add(
                _t("Ubicación capturada. Guarde el registro para conservarla."),
                { type: "success" }
            );
        } catch (error) {
            let message = _t("No fue posible obtener la ubicación.");
            if (error && error.code === 1) {
                message = _t("Permiso de ubicación denegado. Habilítelo para Odoo en el navegador.");
            } else if (error && error.code === 2) {
                message = _t("La ubicación no está disponible en este momento.");
            } else if (error && error.code === 3) {
                message = _t("La captura de ubicación excedió el tiempo de espera.");
            }
            this.notification.add(message, { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }
}

export const gpsCaptureField = {
    component: GpsCaptureField,
    supportedTypes: ["char"],
};

registry.category("fields").add("gps_capture", gpsCaptureField);
