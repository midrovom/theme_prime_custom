"""Contacto operativo del conductor antes de crear/invitar su usuario Portal.

La guia puede indicar el conductor desde res.partner, mientras que el flujo
PWA existente sigue requiriendo un res.users Portal explicitamente autorizado.
"""
from odoo import api, fields, models


class ResPartnerTranscashDriver(models.Model):
    _inherit = 'res.partner'

    # No almacenar este indicador en res_partner: la actualización de módulos
    # puede leer res.partner antes de crear columnas de nuevos addons.
    # El valor procede de tc.guide.driver_partner_id, que ya conserva el vínculo.
    tc_chofer_logistica = fields.Boolean(
        string='Chofer registrado por logística',
        compute='_compute_tc_chofer_logistica',
        search='_search_tc_chofer_logistica',
        help='Contacto relacionado con guías importadas; NO habilita Portal.')

    def _tc_driver_partner_ids(self):
        guides = self.env['tc.guide'].sudo().search([
            ('driver_partner_id', '!=', False),
            ('company_id', 'in', self.env.companies.ids),
        ])
        return set(guides.mapped('driver_partner_id').ids)

    def _compute_tc_chofer_logistica(self):
        driver_ids = self._tc_driver_partner_ids() if self else set()
        for partner in self:
            partner.tc_chofer_logistica = partner.id in driver_ids

    @api.model
    def _search_tc_chofer_logistica(self, operator, value):
        if operator not in ('=', '!=') or not isinstance(value, bool):
            raise ValueError('Filtro de choferes: solo se permiten = o != con True/False.')
        driver_ids = list(self._tc_driver_partner_ids())
        is_in = (operator == '=' and value) or (operator == '!=' and not value)
        return [('id', 'in' if is_in else 'not in', driver_ids)]

    tc_chofer_portal_activo = fields.Boolean(
        string='Portal chofer habilitado', compute='_compute_tc_chofer_portal_activo')

    def _compute_tc_chofer_portal_activo(self):
        users = self.env['res.users'].sudo().search([
            ('partner_id', 'in', self.ids), ('active', '=', True), ('share', '=', True),
        ]) if self.ids else self.env['res.users'].browse()
        registrations = self.env['transcash.chofer'].sudo().search([
            ('usuario_id', 'in', users.ids), ('activo', '=', True),
            ('company_id', '=', self.env.company.id),
        ]) if users else self.env['transcash.chofer'].browse()
        valid_users = {
            r.usuario_id.id for r in registrations
            if (r.usuario_id.has_group('base.group_portal')
                and r.usuario_id.has_group('logistica_transcash.group_transcash_chofer'))
        }
        ready = {user.partner_id.id for user in users if user.id in valid_users}
        for partner in self:
            partner.tc_chofer_portal_activo = partner.id in ready


class TranscashGuiaDriverContact(models.Model):
    _inherit = 'transcash.guia'

    chofer_contacto_id = fields.Many2one(
        'res.partner', string='Chofer (contacto ERP)', index=True, copy=False,
        help='Conductor identificado por cedula/RUC. No requiere usuario Portal. '
             'La asignación al portal ocurre de forma separada y manual.')
    tc_estado_portal_chofer = fields.Selection([
        ('pendiente', 'Portal pendiente'), ('habilitado', 'Portal habilitado'),
        ('sin_contacto', 'Sin contacto')
    ], string='Portal del chofer', compute='_compute_tc_estado_portal_chofer')

    @api.depends('chofer_contacto_id', 'chofer_usuario_id')
    def _compute_tc_estado_portal_chofer(self):
        for guia in self:
            guia.tc_estado_portal_chofer = (
                'habilitado' if guia.chofer_usuario_id else
                'pendiente' if guia.chofer_contacto_id else 'sin_contacto'
            )
