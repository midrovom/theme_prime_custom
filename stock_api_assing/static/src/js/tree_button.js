// odoo.define("stock_api_assing.tree_button", function (require) {
//     "use strict";
//     var ListController = require("web.ListController");
//     var ListView = require("web.ListView");
//     var viewRegistry = require("web.view_registry");
//     var session = require('web.session');
//     var rpc = require('web.rpc');
//     var TreeButton = ListController.extend({
//         buttons_template: "button_near_create.buttons",
//         events: _.extend({}, ListController.prototype.events, {
//             "click .oe_inventory_import_button": "_ImportButtonQuantity",
//         }),

//         _ImportButtonQuantity: function () {
//             var self = this;
//             //this.do_action('stock_api_assing.');
//             let company_id = session.company_id;
//             console.log('company_id1' )
//             console.log(company_id )
//             rpc.query({
//                 model: 'stock.api.assing',
//                 method: 'update_stock_quantity',
//                 args: [[],company_id],
//             }).then(function (result) {
//                 console.log(result)
//                 location.reload();
//             });
//         },

//     });
//     var SaleOrderListView = ListView.extend({
//         config: _.extend({}, ListView.prototype.config, {
//             Controller: TreeButton,
//         }),
//     });
//     viewRegistry.add("button_in_tree", SaleOrderListView);
// });


/** @odoo-module **/

import { ListController } from "@web/views/list/list_controller";
import { listView } from "@web/views/list/list_view";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component } from "@odoo/owl";

export class TreeButtonController extends ListController {
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.user = useService("user");
    }

    /**
     * Evento del botón personalizado
     */
    async onClickImport() {
        const company_id = this.user.companyId;
        console.log("company_id", company_id);

        const result = await this.orm.call(
            "stock.api.assing",
            "update_stock_quantity",
            [[], company_id],
        );

        console.log(result);
        window.location.reload();
    }
}

// Reemplazar renderer, controller o agregar template
export const treeButtonView = {
    ...listView,
    Controller: class extends TreeButtonController {
        get buttons() {
            return [
                {
                    name: "import_quantity_btn",
                    label: "Actualizar Inventario",
                    class: "btn-primary",
                    onClick: () => this.onClickImport(),
                },
            ];
        }
    },
};

// Registrar la nueva vista
registry.category("views").add("button_in_tree", treeButtonView);
