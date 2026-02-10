/** @odoo-module **/

import { registry } from "@web/core/registry";
import { ListRenderer } from "@web/views/list/list_renderer";
import { listView } from "@web/views/list/list_view";

export class ListRendererMobile extends ListRenderer {
    /**
     * @override
     */
    get hasSelectors() {
        // Solo mostrar selectores si están permitidos y no es un dispositivo pequeño
        return this.props.allowSelectors;
    }
}

// Crear una copia y reemplazar Renderer
const customListView = {
    ...listView,
    Renderer: ListRendererMobile,
};

// Registrar nuevamente
registry.category("views").add("list", customListView, { force: true });
