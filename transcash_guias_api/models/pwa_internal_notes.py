# -*- coding: utf-8 -*-
"""Notas automáticas de la PWA sin dependencia de correo en el usuario.

Odoo 18 message_post() falla con un UserError si el usuario operador no
posee email_from. Las bitácoras de carga y homologación son auditoría interna:
no deben invocar el mecanismo de notificación a seguidores. Odoo ofrece
_message_log() para ese propósito (con raise_on_email=False).

SOLO cuando el controlador interno habilita tc_pwa_audit_note=True y la
llamada contiene exclusivamente una nota ordinaria, se utiliza este modo.
Otros mensajes, destinatarios explícitos y comunicaciones financieras siguen
con el message_post estándar de Odoo.
"""
from odoo import models


class _PwaAuditNoteMixin:
    def message_post(self, *args, **kwargs):
        basic = frozenset(('body', 'message_type', 'subtype_xmlid'))
        if (self.env.context.get('tc_pwa_audit_note')
                and not self.env.user.share
                and not args
                and 'body' in kwargs
                and set(kwargs).issubset(basic)
                and kwargs.get('message_type') in (None, 'notification', 'comment')
                and kwargs.get('subtype_xmlid') in (None, 'mail.mt_note')):
            # No se usan sudo ni excepciones tragadas: conservar permisos y
            # errores de la operación; solo cambiar el medio de auditoría.
            self.check_access('write')
            return self._message_log(body=kwargs['body'])
        return super().message_post(*args, **kwargs)


class PwaRutaAuditNote(_PwaAuditNoteMixin, models.Model):
    _inherit = 'transcash.hoja.ruta'


class PwaEmbarqueAuditNote(_PwaAuditNoteMixin, models.Model):
    _inherit = 'transcash.embarque'


class PwaGuiaAuditNote(_PwaAuditNoteMixin, models.Model):
    _inherit = 'transcash.guia'
