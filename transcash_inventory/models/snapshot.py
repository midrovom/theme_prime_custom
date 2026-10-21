# -*- coding: utf-8 -*-
import base64
import json
import zlib
import hashlib
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class TranscashInventorySnapshot(models.Model):
    _name = 'transcash.inventory.snapshot'
    _check_company_auto = True
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
    is_current = fields.Boolean(string='Versión vigente', default=False, index=True, copy=False, readonly=True)
    content_fingerprint = fields.Char(string='Huella de datos', index=True, copy=False, readonly=True)
    relational_ready = fields.Boolean(string='Datos SQL preparados', readonly=True, default=False, copy=False)
    relational_months = fields.Text(string='Períodos disponibles para consultas', readonly=True, copy=False)

    @api.model
    def _fingerprint(self, dataset):
        """Canonical content key: API order changes must not create duplicate versions.

        The source metadata and aggregate summaries are intentionally excluded: only
        the normalized, actual catalog and fact rows determine identity.
        """
        contents = {
            'products': sorted(dataset['products'], key=lambda p: str(p[0])),
            'sales': sorted(dataset['sales']),
            'purchases': sorted(dataset['purchases']),
            'stock': sorted(dataset['stockWarehouses']),
            'supplier_purchases': sorted(dataset.get('supplierPurchases') or []),
            'months': dataset['months'],
            'categories': dataset['categories'],
            'brands': dataset['brands'],
            'providers': dataset['providers'],
            'warehouses': dataset['warehouses'],
            'suppliers': dataset.get('purchaseSuppliers') or [],
        }
        canonical = json.dumps(contents, separators=(',', ':'), sort_keys=True, ensure_ascii=False, allow_nan=False)
        return hashlib.sha256(canonical.encode('utf-8')).hexdigest()

    @api.model
    def current_for_company(self, company=None):
        """Support legacy snapshots created before is_current existed."""
        company = company or self.env.company
        domain = [('company_id', '=', company.id)]
        return (self.search(domain + [('is_current', '=', True)], limit=1,
                            order='create_date desc, id desc') or
                self.search(domain, limit=1, order='create_date desc, id desc'))

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
        fingerprint = self._fingerprint(dataset)
        # Serialize updates for this company. One complete API snapshot replaces the
        # active version; archived versions remain read-only and are never summed.
        self.env.cr.execute('SELECT pg_advisory_xact_lock(%s, %s)', (872245, self.env.company.id))
        current = self.current_for_company()
        if current:
            old_fingerprint = current.content_fingerprint
            if not old_fingerprint:
                old_fingerprint = self._fingerprint(json.loads(current.get_dashboard_json()))
                current.sudo().write({'content_fingerprint': old_fingerprint})
            if old_fingerprint == fingerprint:
                if not current.is_current:
                    current.sudo().write({'is_current': True})
                return current
            # The new snapshot is the sole active data source for this company.
            self.search([('company_id', '=', self.env.company.id),
                         ('is_current', '=', True)]).sudo().write({'is_current': False})

        snapshot = self.create({
            'name': '%s — %s' % (filename, fields.Datetime.now().strftime('%Y-%m-%d %H:%M')),
            'company_id': self.env.company.id,
            'original_filename': filename,
            'file_size': raw_size,
            'imported_by': self.env.user.id,
            'dashboard_data': base64.b64encode(compressed).decode('ascii'),
            'is_current': True,
            'content_fingerprint': fingerprint,
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
