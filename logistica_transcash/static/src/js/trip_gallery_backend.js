/** @odoo-module **/
import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";

export class TripGalleryField extends Component {
    static template = "logistica_transcash.TripGalleryField";
    static props = ["*"];
}
registry.category("fields").add("transcash_trip_gallery", {
    component: TripGalleryField,
    supportedTypes: ["char"],
});

registry.category("fields").add("transcash_guide_gallery", {component: TripGalleryField, supportedTypes: ["char"]});
