# -*- coding: utf-8 -*-
"""Admin-only manual API snapshot synchronization using existing API Administrator."""
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
        if not self.env.user.has_group('base.group_system'):
            raise UserError(_('La sincronización API está reservada al administrador.'))
        if self.company_id != self.env.company:
            raise UserError(_('Seleccione la empresa autorizada antes de importar.'))
        from datetime import datetime
        reference_end = (self.reference_end or '').strip()
        if reference_end:
            try:
                if datetime.strptime(reference_end, '%Y-%m').strftime('%Y-%m') != reference_end:
                    raise ValueError()
            except ValueError:
                raise UserError(_('El mes de corte debe tener formato YYYY-MM.')) from None
        try:
            payloads = fetch_from_api_administrator(self.env)
            dataset, counts = convert_api_payloads(payloads, reference_end or None)
        except APIInventoryError as exc:
            raise UserError(str(exc)) from None
        # Create a new atomic version: old dashboard and fact tables remain untouched.
        snapshot = self.env['transcash.inventory.snapshot'].create_from_dataset(
            dataset, filename='API Administrator', raw_size=0)
        self.write({'last_result': json.dumps({
            'version_id': snapshot.id, 'productos': counts['productos'],
            'ventas': counts['ventas'], 'compras': counts['compras'],
            'stock': counts['stock'], 'corte': dataset['source']['end']}, ensure_ascii=False),
            'snapshot_id': snapshot.id})
        # Important Odoo 18 action contract: doAction() preprocesses act_window
        # with action.views.map(...). Returning only view_mode on an inline
        # action (especially under display_notification.params.next) crashes
        # the browser with "Cannot read properties of undefined (reading 'map')".
        # Reopen the admin wizard using a complete, server-resolved form action.
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
