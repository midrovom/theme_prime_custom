# -*- coding: utf-8 -*-
"""Sincronización con Radis. Se conserva el modelo y los campos del módulo 16."""
import logging

import requests

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_compare

_logger = logging.getLogger(__name__)


class StockAPIAssing(models.Model):
    _name = 'stock.api.assing'
    _description = 'Stock API Sync Log'
    _order = 'date desc, id desc'

    name = fields.Char(string='Nombre')
    date = fields.Datetime(string='Fecha', default=fields.Datetime.now)
    description = fields.Text(string='Descripción')
    company_id = fields.Many2one('res.company', string='Empresa Local', default=lambda self: self.env.company)


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    check_manage_sync = fields.Boolean(string='Sincronizado con API', default=False)


class StockAPISync(models.Model):
    _name = 'stock.api.sync'
    _description = 'Stock API Sync Logic'

    @api.model
    def sync_configured_companies(self):
        """Cron de 30 minutos; reemplaza IDs fijos 1/2 sin duplicar ejecuciones."""
        apis = self.env['api.administrator'].sudo().search([
            ('type', '=', 'get'), ('status', '=', 'A'), ('is_stock_update', '=', True),
        ])
        for company in apis.mapped('company_id'):
            self.with_company(company).sync_all_inventory(company.id)

    @api.model
    def sync_all_inventory(self, company_id):
        company = self.env['res.company'].browse(company_id).exists()
        if not company:
            raise UserError(_('No existe la empresa seleccionada para sincronización.'))
        api_records = self.env['api.administrator'].sudo().search([
            ('company_id', '=', company.id),
            ('type', '=', 'get'),
            ('status', '=', 'A'),
            ('is_stock_update', '=', True),
        ])
        if not api_records:
            self._log_sync(company.id, 'Sin APIs activas', 'No se encontraron APIs activas para la empresa.')
            return

        for api_data in api_records:
            try:
                with self.env.cr.savepoint():
                    url = (api_data.url or '').strip() + (api_data.end_point or '').strip()
                    if not url or not api_data.user_id or not api_data.password:
                        raise UserError(_('Configuración incompleta en la API %s') % api_data.name)
                    if not api_data.warehouse_id:
                        raise UserError(_('Debe asociar una bodega a la API %s') % api_data.name)
                    response = requests.get(url, headers={
                        'Accept': 'application/json', 'version': '1', 'framework': 'PRUEBAS',
                        'userid': api_data.user_id.strip(),
                        'password': api_data.password.strip(),
                        'deviceid': '000000000000000', 'sessionid': '0',
                    }, timeout=120)
                    response.raise_for_status()
                    payload = response.json()
                    data = payload.get('data', []) if isinstance(payload, dict) else []
                    if not isinstance(data, list):
                        raise UserError(_('La API %s no devolvió una lista en data.') % api_data.name)
                    if not data:
                        self._log_sync(company.id, 'Sync %s' % api_data.name,
                                       'No se encontraron datos para sincronizar; el stock existente se conservó.')
                        continue
                    inserted, updated = self.with_company(company)._process_inventory_data(data, api_data)
                    self._log_sync(company.id, 'Sync %s' % api_data.name,
                                   'Insertados: %s, Actualizados: %s' % (inserted, updated))
            except Exception as exc:
                _logger.exception('Error sincronizando Radis API %s empresa %s', api_data.name, company.name)
                self._log_sync(company.id, 'Error Sync %s' % api_data.name, str(exc))

    @api.model
    def _log_sync(self, company_id, name, description):
        self.env['stock.api.assing'].sudo().create({
            'name': name, 'description': description, 'company_id': company_id,
        })

    def _process_inventory_data(self, data, api_data):
        """Actualizar productos marcados, precios y cantidad absoluta por bodega.

        Los productos sincronizados ausentes del catálogo se ponen en cero,
        como hacía el código original. No modifica stock de productos ajenos a
        la integración y no escribe el campo `quantity` de stock.quant directamente.
        """
        Product = self.env['product.template'].sudo()
        Quant = self.env['stock.quant'].sudo().with_context(inventory_mode=True)
        company = api_data.company_id
        inserted = updated = 0
        # Odoo 16 permitía type='product'; en 18 es type='consu', is_storable=True.
        warehouses = api_data.warehouse_id
        changes = {}  # (warehouse_id, variant_id) -> counted quantity
        pricelist = api_data.price_list_id
        public_pricelist = not pricelist or pricelist.name == 'Public Pricelist'
        tax = company.account_sale_tax_id

        for item in data:
            if not isinstance(item, dict):
                continue
            code = str(item.get('codigo') or '').strip()
            if not code:
                continue
            name = str(item.get('Nombre') or code).strip()
            try:
                price = float(item.get('Precio') or 0)
                stock = float(item.get('Stock') or 0)
                weight = float(item.get('Peso') or 0)
            except (TypeError, ValueError) as exc:
                raise UserError(_('Valores numéricos incorrectos para SKU %s: %s') % (code, exc)) from exc

            # Buscar sin duplicar variantes de SKU; conservar el selector check_manage_sync.
            product = Product.search([('default_code', '=', code)], limit=1)
            if product and not product.check_manage_sync:
                _logger.info('Radis: SKU %s existe sin check_manage_sync; se omite.', code)
                continue
            if not product:
                vals = {
                    'name': name, 'default_code': code,
                    'list_price': price if public_pricelist else 0,
                    'type': 'consu', 'is_storable': True,
                    'check_manage_sync': True,
                }
                if tax:
                    vals['taxes_id'] = [(6, 0, tax.ids)]
                if weight > 0:
                    vals['peso'] = weight
                product = Product.with_company(company).create(vals)
                inserted += 1
            else:
                vals = {}
                # Odoo 18 distingue productos almacenables mediante is_storable.
                # Conserva la conversión realizada en la sincronización del usuario.
                if not product.is_storable:
                    vals['is_storable'] = True
                if weight > 0 and not product.peso:
                    vals['peso'] = weight
                if tax and not product.taxes_id:
                    vals['taxes_id'] = [(6, 0, tax.ids)]
                if public_pricelist and float_compare(product.list_price, price, precision_digits=4):
                    vals['list_price'] = price
                if vals:
                    product.with_company(company).write(vals)
                updated += 1

            if not public_pricelist:
                self._assign_price_to_pricelist(product, pricelist, price)
            variant = product.product_variant_id
            if not variant:
                continue
            for warehouse in warehouses:
                if warehouse.company_id != company:
                    _logger.warning('Radis: bodega %s no pertenece a %s; ignorada.', warehouse.name, company.name)
                    continue
                changes[warehouse.id, variant.id] = stock

        # Aplica inventario de Odoo para generar los movimientos correctos.
        # Agrupar por bodega evita que se borre el inventario de otras empresas.
        for warehouse in warehouses:
            if warehouse.company_id != company or not warehouse.lot_stock_id:
                continue
            location = warehouse.lot_stock_id
            sync_products = Product.search([('check_manage_sync', '=', True)]).mapped('product_variant_id')
            existing = Quant.search([
                ('location_id', '=', location.id), ('product_id', 'in', sync_products.ids),
                ('lot_id', '=', False), ('package_id', '=', False), ('owner_id', '=', False),
            ])
            quantities_by_variant = {}
            for quant in existing:
                quantities_by_variant[quant.product_id.id] = quantities_by_variant.get(quant.product_id.id, 0) + quant.quantity
            # Mantener lógica 'no enviado = cero', solo para artículos gestionados por API.
            for variant_id, old_qty in quantities_by_variant.items():
                changes.setdefault((warehouse.id, variant_id), 0.0)
            for (wh_id, variant_id), new_qty in changes.items():
                if wh_id != warehouse.id:
                    continue
                variant = self.env['product.product'].browse(variant_id)
                old_qty = quantities_by_variant.get(variant_id, 0.0)
                if not float_compare(old_qty, new_qty, precision_rounding=variant.uom_id.rounding):
                    continue
                quant = Quant.search([
                    ('product_id', '=', variant_id), ('location_id', '=', location.id),
                    ('lot_id', '=', False), ('package_id', '=', False), ('owner_id', '=', False),
                ], limit=1)
                if not quant:
                    quant = Quant.with_company(company).create({
                        'product_id': variant_id, 'location_id': location.id,
                    })
                quant.with_company(company).write({'inventory_quantity': new_qty, 'check_update': True})
                quant.with_company(company).action_apply_inventory()
                quant.with_company(company).write({'check_update': False})
        return inserted, updated

    @api.model
    def _assign_price_to_pricelist(self, product, price_list, price):
        item = self.env['product.pricelist.item'].sudo().search([
            ('pricelist_id', '=', price_list.id),
            ('product_tmpl_id', '=', product.id),
            ('applied_on', '=', '1_product'),
        ], limit=1)
        if item:
            if float_compare(item.fixed_price, price, precision_digits=4):
                item.write({'fixed_price': price})
        else:
            self.env['product.pricelist.item'].sudo().create({
                'pricelist_id': price_list.id, 'product_tmpl_id': product.id,
                'applied_on': '1_product', 'compute_price': 'fixed', 'fixed_price': price,
            })

    @api.model
    def update_published_for_storable_products(self):
        products = self.env['product.template'].search([('is_storable', '=', True)])
        if products:
            products.write({'check_manage_sync': True, 'company_id': False})
            if 'is_published' in products._fields:
                products.write({'is_published': True})
