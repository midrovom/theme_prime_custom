# -*- coding: utf-8 -*-
"""Solo lectura y navegación para trazabilidad logística (Odoo 18).

No cambia estados ni asignaciones de guías, rutas o embarques.
"""
import re

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.osv import expression


def _document(value):
    value = re.sub(r'[^0-9]', '', str(value or ''))
    return value if len(value) in (10, 13) else ''


def _open_form(record, title):
    record.ensure_one()
    record.check_access('read')
    return {
        'type': 'ir.actions.act_window',
        'name': title,
        'res_model': record._name,
        'res_id': record.id,
        'view_mode': 'form',
        'views': [(False, 'form')],
        'target': 'current',
    }


class TranscashGuiaTraceability(models.Model):
    _inherit = 'transcash.guia'

    tc_traza_embarque_id = fields.Many2one(
        'transcash.embarque', string='Embarque relacionado',
        compute='_compute_tc_traza', readonly=True)
    tc_traza_embarque_estado = fields.Char(
        string='Estado del embarque', compute='_compute_tc_traza', readonly=True)
    tc_traza_ruta_estado = fields.Selection(
        related='hoja_ruta_id.estado_operativo', string='Estado de la hoja de ruta',
        readonly=True)
    tc_traza_situacion = fields.Selection([
        ('disponible', 'Disponible para ruta'),
        ('ruta', 'Asignada a hoja de ruta'),
        ('embarque', 'En embarque'),
        ('cancelada', 'Cancelada'),
        ('sin_vinculo', 'Revisar: sin vínculo de ruta'),
    ], string='Situación de planificación', compute='_compute_tc_traza', readonly=True)

    @api.depends('hoja_ruta_id', 'hoja_ruta_id.embarque_id', 'embarque_id', 'state')
    def _compute_tc_traza(self):
        for guia in self:
            embarque = guia.embarque_id or guia.hoja_ruta_id.embarque_id
            guia.tc_traza_embarque_id = embarque
            guia.tc_traza_embarque_estado = (
                dict(embarque._fields['state'].selection).get(embarque.state, embarque.state)
                if embarque else False)
            guia.tc_traza_situacion = (
                'cancelada' if guia.state == 'cancelada'
                else 'embarque' if embarque
                else 'ruta' if guia.hoja_ruta_id
                else 'disponible' if guia.state == 'registrada'
                else 'sin_vinculo'
            )

    def action_tc_ver_hoja_ruta(self):
        self.ensure_one()
        if not self.hoja_ruta_id:
            raise UserError(_('Esta guía todavía no tiene una hoja de ruta confirmada.'))
        return _open_form(self.hoja_ruta_id, _('Hoja de ruta de %s') % self.name)

    def action_tc_ver_embarque(self):
        self.ensure_one()
        if not self.tc_traza_embarque_id:
            raise UserError(_('Esta guía todavía no pertenece a un embarque.'))
        return _open_form(self.tc_traza_embarque_id, _('Embarque de %s') % self.name)


class TranscashHojaRutaTraceability(models.Model):
    _inherit = 'transcash.hoja.ruta'

    def action_tc_ver_embarque(self):
        self.ensure_one()
        if not self.embarque_id:
            raise UserError(_('Esta hoja de ruta todavía no pertenece a un embarque.'))
        return _open_form(self.embarque_id, _('Embarque de la ruta %s') % self.name)

    def action_tc_guias_del_chofer(self):
        """Consulta acotada a usuario/contacto/cédula, sin elegir por nombre.

        Es intencionadamente SOLO una acción de lectura, nunca un selector de guías.
        El dominio se limita además a la compañía de la ruta.
        """
        self.ensure_one()
        if not self.chofer_usuario_id:
            raise UserError(_('Seleccione primero un chofer en esta hoja de ruta.'))
        user = self.chofer_usuario_id
        partner = user.partner_id
        docs = {_document(user.login), _document(partner.vat)} - {''}
        conditions = [[('chofer_usuario_id', '=', user.id)]]
        if partner:
            conditions.append([('chofer_contacto_id', '=', partner.id)])
        if docs:
            conditions.append([('ruc_chofer', 'in', sorted(docs))])
        driver_domain = expression.OR(conditions)
        domain = expression.AND([
            [('company_id', '=', self.company_id.id)], driver_domain,
        ])
        return {
            'type': 'ir.actions.act_window',
            'name': _('Guías del chofer: %s') % user.name,
            'res_model': 'transcash.guia',
            'view_mode': 'kanban,list,form',
            'views': [(self.env.ref('transcash_guias_api.view_tc_operational_guide_kanban').id, 'kanban'),
                      (False, 'list'), (False, 'form')],
            'domain': domain,
            'context': {'create': False, 'edit': False, 'delete': False},
            'target': 'current',
        }
