/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { Chatter } from "@mail/chatter/web_portal/chatter";
import { useService } from "@web/core/utils/hooks";

patch(Chatter.prototype, {

    setup() {
        super.setup();

        this.user = useService("user");

        this.isChatterReadonly = false;

        this.checkReadonlyGroup();
    },

    async checkReadonlyGroup() {

        this.isChatterReadonly = await this.user.hasGroup(
            "maintenance_report.group_chatter_readonly"
        );

        if (this.isChatterReadonly) {

            setTimeout(() => {

                // ocultar adjuntar archivos
                document.querySelectorAll(
                    ".o-mail-Chatter-fileUploader"
                ).forEach(el => {
                    el.closest("span")?.remove();
                    el.remove();
                });

                // ocultar eliminar
                document.querySelectorAll(
                    ".o-mail-AttachmentCard-unlink"
                ).forEach(el => el.remove());

                // ocultar descargar
                document.querySelectorAll(
                    ".o-mail-AttachmentCard button[title='Descargar']"
                ).forEach(el => el.remove());

                // ocultar composer
                document.querySelectorAll(
                    ".o-mail-Composer"
                ).forEach(el => el.remove());

                // ocultar actividades
                document.querySelectorAll(
                    ".o-mail-Activity"
                ).forEach(el => el.remove());

                // desactivar botones chatter
                document.querySelectorAll(
                    ".o-mail-Message-actions"
                ).forEach(el => {
                    el.style.display = "none";
                });

            }, 500);
        }
    },
});