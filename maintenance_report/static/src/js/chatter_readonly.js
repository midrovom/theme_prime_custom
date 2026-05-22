/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { Chatter } from "@mail/chatter/web/chatter";
import { useService } from "@web/core/utils/hooks";

patch(Chatter.prototype, {

    setup() {
        super.setup();

        this.user = useService("user");

        this.initReadonlyChatter();
    },

    async initReadonlyChatter() {

        const hasGroup = await this.user.hasGroup(
            "maintenance_report.group_chatter_readonly"
        );

        if (!hasGroup) {
            return;
        }

        const applyReadonly = () => {

            // =========================
            // BOTON ADJUNTAR
            // =========================

            document.querySelectorAll(
                ".o-mail-Chatter-attachment button, .o-mail-Chatter-fileUploader"
            ).forEach(el => {
                el.remove();
            });

            // =========================
            // INPUT FILE
            // =========================

            document.querySelectorAll(
                "input.o-mail-Chatter-fileUploader"
            ).forEach(el => {
                el.disabled = true;
                el.remove();
            });

            // =========================
            // ELIMINAR ADJUNTO
            // =========================

            document.querySelectorAll(
                ".o-mail-AttachmentCard-unlink"
            ).forEach(el => {
                el.remove();
            });

            // =========================
            // DESCARGAR
            // =========================

            document.querySelectorAll(
                ".o-mail-AttachmentCard button[title='Descargar']"
            ).forEach(el => {
                el.remove();
            });

            // =========================
            // COMPOSER
            // =========================

            document.querySelectorAll(
                ".o-mail-Composer"
            ).forEach(el => {
                el.remove();
            });

            // =========================
            // ACTIVIDADES
            // =========================

            document.querySelectorAll(
                ".o-mail-Activity"
            ).forEach(el => {
                el.remove();
            });

            // =========================
            // ACCIONES MENSAJE
            // =========================

            document.querySelectorAll(
                ".o-mail-Message-actions"
            ).forEach(el => {
                el.remove();
            });

        };

        // primera ejecución
        applyReadonly();

        // observar cambios OWL
        const observer = new MutationObserver(() => {
            applyReadonly();
        });

        observer.observe(document.body, {
            childList: true,
            subtree: true,
        });
    },
});