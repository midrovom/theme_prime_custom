# -*- coding: utf-8 -*-
"""Restricted commercial links + date-only readouts on operational guides.

All added fields on transcash.guia are computed/non-stored. The ONLY physical
column introduced is operational_line_id on our own private connector model.
"""
from collections import defaultdict
from datetime import timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class TCRestrictedOperationalLine(models.Model):
    _inherit = 'tc.guide.line.private'

    operational_line_id = fields.Many2one(
        'transcash.guia.linea', string='Línea operativa vinculada',
        ondelete='set null', index=True, copy=False,
        help='Vínculo con línea de guía operativa; solo visible para administración de integración.')
    operational_guide_id = fields.Many2one(
        'transcash.guia', related='operational_line_id.guia_id',
        string='Guía operativa', readonly=True)

    _sql_constraints = [
        ('tc_private_unique_operational_line', 'unique(operational_line_id)',
         'Una línea operativa debe pertenecer a una sola ficha comercial privada.'),
    ]

    @api.constrains('operational_line_id', 'line_id')
    def _check_operational_link(self):
        for rec in self:
            if not rec.operational_line_id:
                continue
            guide = rec.line_id.guide_id
            op = rec.operational_line_id
            if (op.guia_id.company_id != guide.company_id or
                    op.guia_id.external_id_erp != guide.external_id or
                    op.external_line_id != rec.line_id.external_line_id):
                raise ValidationError(_('La ficha comercial no corresponde a esa guía y línea operativa.'))


class TCOperationalGuideCommercial(models.Model):
    _inherit = 'transcash.guia'

    tc_erp_date_start = fields.Date('Inicio previsto ERP', compute='_compute_tc_erp_dates')
    tc_erp_date_end = fields.Date('Fin previsto ERP', compute='_compute_tc_erp_dates')
    tc_erp_date_planned = fields.Date('Fecha prevista ERP', compute='_compute_tc_erp_dates')
    tc_private_commercial_line_ids = fields.Many2many(
        'tc.guide.line.private', compute='_compute_tc_private_lines',
        string='Marcas y proveedores por línea',
        groups='transcash_guias_api.group_tc_sync_admin,base.group_system')

    @api.depends('external_id_erp', 'company_id', 'fecha_inicio_traslado',
                 'fecha_fin_traslado', 'fecha_prevista')
    def _compute_tc_erp_dates(self):
        # Compute just date values, from staging first (source of truth), without
        # changing stored operational datetimes or revealing private data.
        by_company = defaultdict(list)
        for guide in self:
            if guide.company_id and guide.external_id_erp:
                by_company[guide.company_id.id].append(guide.external_id_erp)
        staged = {}
        Stage = self.env['tc.guide'].sudo()
        for company_id, external_ids in by_company.items():
            for row in Stage.search([('company_id', '=', company_id),
                                     ('external_id', 'in', list(set(external_ids)))]):
                staged[(company_id, row.external_id)] = row
        for guide in self:
            row = staged.get((guide.company_id.id, guide.external_id_erp))
            try:
                tz = ZoneInfo(guide.company_id.partner_id.tz or 'America/Guayaquil')
            except (ValueError, ZoneInfoNotFoundError):
                tz = ZoneInfo('America/Guayaquil')
            def date_display(erp_date, stored_date):
                if erp_date:
                    return erp_date
                if stored_date:
                    dt = fields.Datetime.to_datetime(stored_date)
                    return dt.replace(tzinfo=timezone.utc).astimezone(tz).date()
                return False
            guide.tc_erp_date_start = date_display(row.erp_start_date if row else False,
                                                    guide.fecha_inicio_traslado)
            guide.tc_erp_date_end = date_display(row.erp_end_date if row else False,
                                                  guide.fecha_fin_traslado)
            guide.tc_erp_date_planned = date_display(row.erp_planned_date if row else False,
                                                      guide.fecha_prevista)

    @api.depends('linea_ids', 'linea_ids.external_line_id')
    def _compute_tc_private_lines(self):
        Private = self.env['tc.guide.line.private'].sudo()
        all_lines = self.mapped('linea_ids').ids
        rows = Private.search([('operational_line_id', 'in', all_lines)]) if all_lines else Private.browse()
        by_guide = defaultdict(list)
        for row in rows:
            by_guide[row.operational_line_id.guia_id.id].append(row.id)
        for guide in self:
            guide.tc_private_commercial_line_ids = [(6, 0, by_guide.get(guide.id, []))]

    def action_tc_view_commercial(self):
        self.ensure_one()
        if not (self.env.user.has_group('transcash_guias_api.group_tc_sync_admin')
                or self.env.user.has_group('base.group_system')):
            raise AccessError(_('Acceso reservado a los administradores de integración.'))
        action = self.env.ref('transcash_guias_api.action_tc_private_lines').read()[0]
        action['domain'] = [('operational_line_id.guia_id', '=', self.id)]
        return action


class TCGuideRepair(models.Model):
    _inherit = 'tc.guide.sync'

    @api.model
    def repair_operational_dates_commercial(self, company_id):
        if not (self.env.user.has_group('transcash_guias_api.group_tc_sync_admin')
                or self.env.user.has_group('base.group_system')):
            raise AccessError(_('La reparación de relaciones es exclusiva para administración.'))
        if company_id not in self.env.companies.ids:
            raise AccessError(_('Empresa no autorizada.'))
        # Recuperar los maestros privados desde códigos ERP ya almacenados,
        # antes de enlazar las fichas con las líneas operativas.
        catalog = self.reconcile_private_data(company_id)
        staged = self.env['tc.guide'].sudo().search([('company_id', '=', company_id)], order='id')
        totals = {'guides': 0, 'dates': 0, 'linked': 0, 'missing_line': 0, 'errors': 0}
        notes = []
        for guide in staged:
            try:
                with self.env.cr.savepoint():
                    result = guide._repair_dates_and_links()
                    for key in ('guides','dates','linked','missing_line'):
                        totals[key] += result[key]
            except Exception as exc:
                totals['errors'] += 1
                if len(notes) < 15:
                    notes.append('%s: %s' % (guide.external_id, str(exc)[:180]))
        if catalog['errors']:
            totals['errors'] += len(catalog['errors'])
            if len(notes) < 15:
                notes.extend(catalog['errors'][:15-len(notes)])
        summary = ('Marcas nuevas vinculadas: %s | proveedores nuevos vinculados: %s | ' % (
            catalog['brands_linked'], catalog['suppliers_linked']))
        summary += ('Guías verificadas: %(guides)s | fechas reparadas: %(dates)s | '
                   'líneas comerciales vinculadas: %(linked)s | líneas sin coincidencia: %(missing_line)s | '
                   'errores: %(errors)s') % totals
        if notes:
            summary += '\n' + '\n'.join(notes)
        return {'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'title': _('Conciliación ERP → Logística'),
                           'message': summary,
                           'type': 'warning' if totals['errors'] or totals['missing_line'] else 'success',
                           'sticky': bool(totals['errors'] or totals['missing_line'])}}
