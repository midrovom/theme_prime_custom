/** @odoo-module **/
import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";

class MediaPreview extends Component {
    static template = "logistica_transcash.MediaPreview";
    static props = ["*"];
}
registry.category("fields").add("transcash_media_preview", {
    component: MediaPreview,
    supportedTypes: ["char"],
});
