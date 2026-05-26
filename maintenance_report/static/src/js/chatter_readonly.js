/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { Chatter } from "@mail/chatter/chatter";
import { useService } from "@web/core/utils/hooks";

patch(Chatter.prototype, "hr_chatter_restriction", {
    setup() {
        this._super();
        this.user = useService("user");
    },

    get showAttachButton() {
        // Si el usuario pertenece al grupo de solo lectura, ocultar botón
        const groups = this.user.context.user_groups || "";
        const readonlyGroup = "hr_chatter_restriction.group_attachment_hr_readonly";
        if (groups.includes(readonlyGroup) && this.props.record.model === "hr.employee") {
            return false;
        }
        return this._super ? this._super() : true;
    },
});

