# -*- coding: utf-8 -*-
"""Registra anotaciones PWA de auditoría sin exigir correo del operador.

Las extensiones de modelos Odoo DEBEN heredar directamente de models.Model.
La versión 2.33 añadió una clase Python ordinaria como primera base de las
extensiones, lo que impedía construir el registro (__bases__ layout differs).
La lógica compartida se implementa como función independiente; todas las
clases ORM usan exclusivamente models.Model como clase base.

Solo las anotaciones implícitas de la PWA, sin destinatarios explícitos,
se convierten en entradas de bitácora. Los demás mensajes siguen utilizando
message_post() estándar, sin cambiar notificaciones comerciales ni contables.
"""
from odoo import models


def _pwa_message_post(record, args, kwargs, parent_message_post):
    """Respetar todas las opciones/validaciones de message_post salvo notas PWA."""
    basic = frozenset(('body', 'message_type', 'subtype_xmlid'))
    if (record.env.context.get('tc_pwa_audit_note')
            and not record.env.user.share
            and not args
            and 'body' in kwargs
            and set(kwargs).issubset(basic)
            and kwargs.get('message_type') in (None, 'notification', 'comment')
            and kwargs.get('subtype_xmlid') in (None, 'mail.mt_note')):
        record.check_access('write')
        return record._message_log(body=kwargs['body'])
    return parent_message_post(*args, **kwargs)


class PwaRutaAuditNote(models.Model):
    _inherit = 'transcash.hoja.ruta'

    def message_post(self, *args, **kwargs):
        return _pwa_message_post(self, args, kwargs, super().message_post)


class PwaEmbarqueAuditNote(models.Model):
    _inherit = 'transcash.embarque'

    def message_post(self, *args, **kwargs):
        return _pwa_message_post(self, args, kwargs, super().message_post)


class PwaGuiaAuditNote(models.Model):
    _inherit = 'transcash.guia'

    def message_post(self, *args, **kwargs):
        return _pwa_message_post(self, args, kwargs, super().message_post)
