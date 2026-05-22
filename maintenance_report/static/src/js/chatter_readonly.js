/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { Chatter } from "@mail/chatter/web/chatter";
import { onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

patch(Chatter.prototype, {

    setup() {
        super.setup();

        this.userService = useService("user");

        this.isReadonlyChatter = false;

        onWillStart(async () => {

            this.isReadonlyChatter =
                await this.userService.hasGroup(
                    "maintenance_report.group_chatter_readonly"
                );

        });
    },

});