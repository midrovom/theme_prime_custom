/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class GpsCapture extends Component {
    static template = "route_sales_crm.GpsCapture";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({ status: "requesting", message: "Solicitando ubicación del dispositivo…" });
        onWillStart(() => this.capture());
    }

    async capture() {
        if (!navigator.geolocation) {
            this.state.status = "error";
            this.state.message = "Este dispositivo o navegador no permite obtener la ubicación.";
            return;
        }
        navigator.geolocation.getCurrentPosition(
            async (position) => {
                try {
                    const { latitude, longitude, accuracy } = position.coords;
                    await this.orm.call("route.sale.visit", "save_gps_position", [[this.props.action.params.visit_id], this.props.action.params.mode, latitude, longitude, accuracy]);
                    this.state.status = "success";
                    this.state.message = this.props.action.params.mode === "checkin" ? "Entrada registrada correctamente." : "Salida registrada correctamente.";
                    this.notification.add(this.state.message, { type: "success" });
                    await this.action.doAction({ type: "ir.actions.act_window", res_model: "route.sale.visit", res_id: this.props.action.params.visit_id, views: [[false, "form"]], target: "current" });
                } catch (error) {
                    this.state.status = "error";
                    this.state.message = error.data?.message || error.message || "No se pudo guardar la ubicación.";
                }
            },
            (error) => {
                const messages = { 1: "Debe permitir el acceso a la ubicación.", 2: "La ubicación no está disponible.", 3: "Se agotó el tiempo para obtener la ubicación." };
                this.state.status = "error";
                this.state.message = messages[error.code] || "No se pudo obtener la ubicación.";
            },
            { enableHighAccuracy: true, timeout: 20000, maximumAge: 0 }
        );
    }

    retry() {
        this.state.status = "requesting";
        this.state.message = "Solicitando ubicación del dispositivo…";
        this.capture();
    }
}

registry.category("actions").add("route_sales_crm.gps_capture", GpsCapture);
