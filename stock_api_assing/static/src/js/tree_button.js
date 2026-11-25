odoo.define("stock_api_assing.tree_button", function (require) {
    "use strict";
    var ListController = require("web.ListController");
    var ListView = require("web.ListView");
    var viewRegistry = require("web.view_registry");
    var session = require('web.session');
    var rpc = require('web.rpc');
    var TreeButton = ListController.extend({
        buttons_template: "button_near_create.buttons",
        events: _.extend({}, ListController.prototype.events, {
            "click .oe_inventory_import_button": "_ImportButtonQuantity",
        }),

        _ImportButtonQuantity: function () {
            var self = this;
            //this.do_action('stock_api_assing.');
            let company_id = session.company_id;
            console.log('company_id1' )
            console.log(company_id )
            rpc.query({
                model: 'stock.api.assing',
                method: 'update_stock_quantity',
                args: [[],company_id],
            }).then(function (result) {
                console.log(result)
                location.reload();
            });
        },

    });
    var SaleOrderListView = ListView.extend({
        config: _.extend({}, ListView.prototype.config, {
            Controller: TreeButton,
        }),
    });
    viewRegistry.add("button_in_tree", SaleOrderListView);
});
