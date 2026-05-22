/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { Chatter } from "@mail/chatter/web/chatter";
import { useService } from "@web/core/utils/hooks";

patch(Chatter.prototype, {

    setup() {
        super.setup();

        this.user = useService("user");

        this.checkReadonlyGroup();
    },

    async checkReadonlyGroup() {

        const hasGroup = await this.user.hasGroup(
            "maintenance_report.group_chatter_readonly"
        );

        if (!hasGroup) {
            return;
        }

        setTimeout(() => {

            // upload
            document.querySelectorAll(
                ".o-mail-Chatter-fileUploader"
            ).forEach(el => {
                el.closest("span")?.remove();
                el.remove();
            });

            // eliminar adjunto
            document.querySelectorAll(
                ".o-mail-AttachmentCard-unlink"
            ).forEach(el => el.remove());

            // descargar
            document.querySelectorAll(
                ".o-mail-AttachmentCard button[title='Descargar']"
            ).forEach(el => el.remove());

            // composer
            document.querySelectorAll(
                ".o-mail-Composer"
            ).forEach(el => el.remove());

            // actividades
            document.querySelectorAll(
                ".o-mail-Activity"
            ).forEach(el => el.remove());

            // acciones mensajes
            document.querySelectorAll(
                ".o-mail-Message-actions"
            ).forEach(el => {
                el.style.display = "none";
            });

        }, 500);
    },
});