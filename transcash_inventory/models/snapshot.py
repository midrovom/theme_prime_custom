# -*- coding: utf-8 -*-
import base64
import json
import zlib
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class TranscashInventorySnapshot(models.Model):
    _name = 'transcash.inventory.snapshot'
    _description = 'Versión de inventario inteligente Transcash'
    _order = 'create_date desc, id desc'

    name = fields.Char(required=True, index=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company, index=True)
    original_filename = fields.Char(readonly=True)
    file_size = fields.Integer(readonly=True)
    imported_by = fields.Many2one('res.users', readonly=True, default=lambda self: self.env.user)
    dashboard_data = fields.Binary(attachment=True, copy=False, readonly=True, groups='transcash_inventory.group_transcash_manager,base.group_system')
    product_count = fields.Integer(readonly=True)
    stock_value = fields.Float(readonly=True)
    revenue_12 = fields.Float(readonly=True)
    profit_12 = fields.Float(readonly=True)
    period_start = fields.Char(readonly=True)
    period_end = fields.Char(readonly=True)
    note = fields.Text(readonly=True)
    relational_ready = fields.Boolean(string='Datos SQL preparados', readonly=True, default=False, copy=False)
    relational_months = fields.Text(string='Períodos disponibles para consultas', readonly=True, copy=False)

    @api.model
    def create_from_dataset(self, dataset, filename='API', raw_size=0):
        if not (self.env.user.has_group('transcash_inventory.group_transcash_manager') or self.env.user.has_group('base.group_system')):
            raise ValidationError(_('No tiene permiso para cargar inventarios.'))
        if not isinstance(dataset, dict) or not all(k in dataset for k in ('products', 'sales', 'purchases', 'stockWarehouses', 'months', 'summary', 'source')):
            raise ValidationError(_('La información procesada no cumple el formato del dashboard.'))
        raw = json.dumps(dataset, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')
        compressed = zlib.compress(raw, level=6)
        summary = dataset['summary']
        source = dataset['source']
        snapshot = self.create({
            'name': '%s — %s' % (filename, fields.Datetime.now().strftime('%Y-%m-%d %H:%M')),
            'company_id': self.env.company.id,
            'original_filename': filename,
            'file_size': raw_size,
            'imported_by': self.env.user.id,
            'dashboard_data': base64.b64encode(compressed).decode('ascii'),
            'product_count': len(dataset['products']),
            'stock_value': summary.get('stock_catalogo', 0),
            'revenue_12': summary.get('ventas12', 0),
            'profit_12': summary.get('util12', 0),
            'period_start': source.get('start'),
            'period_end': source.get('end'),
            'note': 'Importación terminada. Indicadores recalculados desde Productos, Stock, Ventas y Compras.',
        })
        # El origen de datos para IA pasa a ser PostgreSQL/Odoo desde el instante
        # de la importación; el paquete binario se conserva para el dashboard.
        from .facts import materialize_snapshot
        materialize_snapshot(snapshot, dataset)
        return snapshot

    def ensure_relational_data(self):
        self.ensure_one()
        self.check_access('read')
        if not self.relational_ready:
            from .facts import materialize_snapshot
            materialize_snapshot(self)
        return self

    def get_dashboard_json(self):
        self.ensure_one()
        # Solo usar desde un usuario que tenga permiso de lectura sobre el registro.
        self.check_access('read')
        if not self.dashboard_data:
            return b'{}'
        return zlib.decompress(base64.b64decode(self.sudo().dashboard_data))

    def action_view_dashboard(self):
        self.ensure_one()
        self.check_access('read')
        return {
            'type': 'ir.actions.act_url',
            'name': 'Dashboard histórico Transcash',
            'url': '/transcash_inventory/dashboard?snapshot_id=%s' % self.id,
            'target': 'new',
        }
