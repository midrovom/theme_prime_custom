# -*- coding: utf-8 -*-
"""Controlled, read-only API refresh for inventory viewers using API Administrator."""
import json
from odoo import fields, models, _
from odoo.exceptions import UserError
from ..services.api_import import (ENDPOINTS, fetch_from_api_administrator,
                                   convert_api_payloads, APIInventoryError)


class TranscashInventoryApiSyncWizard(models.TransientModel):
    _name = 'transcash.inventory.api.sync.wizard'
    _description = 'Sincronizar inventario desde API Administrator'

    company_id = fields.Many2one('res.company', required=True, readonly=True,
                                  default=lambda self: self.env.company)
    endpoint_products = fields.Char(default=ENDPOINTS['productos'], readonly=True)
    endpoint_sales = fields.Char(default=ENDPOINTS['ventas'], readonly=True)
    endpoint_purchases = fields.Char(default=ENDPOINTS['compras'], readonly=True)
    endpoint_stock = fields.Char(default=ENDPOINTS['stock'], readonly=True)
    reference_end = fields.Char(string='Mes de corte (YYYY-MM, opcional)', help='Dejar vacío para usar el último mes completo reconocido.')
    last_result = fields.Text(readonly=True, string='Resultado de importación')
    snapshot_id = fields.Many2one('transcash.inventory.snapshot', readonly=True)

    def action_sync(self):
        self.ensure_one()
        # Viewers may REQUEST a refresh, but cannot configure the APIs or write
        # arbitrary inventory data. The server fetches the four fixed GET sources.
        if not (self.env.user.has_group('transcash_inventory.group_transcash_user')
                or self.env.user.has_group('base.group_system')):
            raise UserError(_('No tiene permiso para sincronizar inventarios.'))
        if self.company_id != self.env.company:
            raise UserError(_('Seleccione la empresa autorizada antes de importar.'))
        from datetime import datetime
        # Viewers always use the freshest source period; only admins can override.
        reference_end = ((self.reference_end or '').strip()
                         if self.env.user.has_group('base.group_system') else '')
        if reference_end:
            try:
                if datetime.strptime(reference_end, '%Y-%m').strftime('%Y-%m') != reference_end:
                    raise ValueError()
            except ValueError:
                raise UserError(_('El mes de corte debe tener formato YYYY-MM.')) from None
        # Prevent simultaneous expensive requests for the same company. This
        # transaction advisory lock is released automatically by PostgreSQL.
        self.env.cr.execute('SELECT pg_try_advisory_xact_lock(%s, %s)',
                            (872246, self.env.company.id))
        if not self.env.cr.fetchone()[0]:
            raise UserError(_('Ya existe una sincronización API en curso para esta empresa.'))
        try:
            payloads = fetch_from_api_administrator(self.env)
            dataset, counts = convert_api_payloads(payloads, reference_end or None)
        except APIInventoryError as exc:
            raise UserError(str(exc)) from None
        # Create a new atomic version: old dashboard and fact tables remain untouched.
        # Elevated permission is scoped to the validated server-side import, NOT
        # granted to the viewer. API Administrator credentials stay server-side.
        inventory = self.env['transcash.inventory.snapshot'].sudo()
        previous = inventory.current_for_company()
        snapshot = inventory.create_from_dataset(dataset, filename='API Administrator', raw_size=0)
        unchanged = bool(previous and previous.id == snapshot.id)
        self.write({'last_result': json.dumps({
            'estado': 'Sin cambios; versión vigente conservada' if unchanged else 'Datos reemplazados en la versión vigente',
            'version_id': snapshot.id, 'productos': counts['productos'],
            'ventas': counts['ventas'], 'compras': counts['compras'],
            'stock': counts['stock'], 'duplicados_reemplazados': counts.get('reemplazos', {}),
            'corte': dataset['source']['end']}, ensure_ascii=False),
            'snapshot_id': snapshot.id})
        # Important Odoo 18 action contract: doAction() preprocesses act_window
        # with action.views.map(...). Returning only view_mode on an inline
        # action (especially under display_notification.params.next) crashes
        # the browser with "Cannot read properties of undefined (reading 'map')".
        # Reopen the wizard using a complete, server-resolved form action.
        return {
            'type': 'ir.actions.act_window',
            'name': _('Sincronización de inventario por API'),
            'res_model': 'transcash.inventory.api.sync.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(self.env.ref('transcash_inventory.view_transcash_inventory_api_sync_form').id, 'form')],
            'target': 'new',
            'context': {},
        }
