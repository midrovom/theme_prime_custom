/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { AttachmentCard } from "@mail/core/web/attachment_card";

patch(AttachmentCard.prototype, "RestrictAttachmentActions", {
    setup() {
        this._super(...arguments);
        // Verifica si el usuario pertenece al grupo
        this.userHasGroup = this.env.services.user.hasGroup("tu_modulo.nombre_del_grupo");
    },

    get canUnlink() {
        // Solo permite eliminar si el usuario pertenece al grupo
        return this.userHasGroup;
    },

    get canUpload() {
        // Solo permite subir si el usuario pertenece al grupo
        return this.userHasGroup;
    },
});

