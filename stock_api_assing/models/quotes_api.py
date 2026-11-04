# -*- coding: utf-8 -*-
"""Exportación de cotizaciones pendiente vía cron, compatible con Odoo 18."""
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class QuotesApiAssing(models.Model):
    _name = 'quotes.api.assing'
    _description = 'Quotes API Assing'
    _order = 'date desc, id desc'

    name = fields.Char()
    date = fields.Datetime(string='Fecha', default=fields.Datetime.now)
    value = fields.Char()
    description = fields.Text(string='Descripción')
    company_id = fields.Many2one('res.company', string='Compañía', default=lambda self: self.env.company)

    @api.model
    def cron_export_order_sale(self, company_id):
        result = self.get_sale_orders(company_id)
        self.create({
            'name': 'Actualización de sale.order desde API',
            'value': str(result['count']),
            'description': str(result['order_send']),
            'company_id': company_id,
        })
        return result

    @api.model
    def get_sale_orders(self, company_id):
        orders = self.env['sale.order'].sudo().search([
            ('company_id', '=', company_id),
            ('export_send', '!=', 'E'),
            ('state', '!=', 'cancel'),
            ('amount_total', '>', 0),
        ], limit=3)
        if not orders:
            return {'data_result': False, 'count': 0, 'order_send': []}

        payload = []
        for order in orders:
            payload.append({
                'order_name': order.name,
                'order_partner': order.partner_id.name,
                'bodega': order.warehouse_id.code,
                'order_company_code': order.company_id.company_registry,
                'order_company_name': order.company_id.name,
                'order_partner_vat': order.partner_id.vat,
                'order_partner_adress': order.partner_id.contact_address,
                'order_partner_phone': order.partner_id.phone,
                'order_partner_email': order.partner_id.email,
                'order_partner_mobile': order.partner_id.mobile,
                'order_vendor_code': order.user_id.vendor_codes,
                'order_impuesto': order.amount_tax,
                'order_total': order.amount_total,
                'order_state': order.state,
                'export_send': order.export_send,
                'comentario': order.extract_plain_text(),
                'order_lines': [{
                    'product': line.product_id.name,
                    'sku': line.product_id.default_code or '',
                    'quantity': line.product_uom_qty,
                    'order_location_wh': (line.warehouse_id or order.warehouse_id).code,
                    'price_unit': str(line.price_unit),
                    'negotiable_price': str(line.negotiable_price),
                    'total_tax': str(line.price_tax),
                } for line in order.order_line if line.product_id and not line.display_type],
            })
        success = self.send_order_sale_api(payload, company_id)
        sent = []
        for order in orders:
            order.with_context(bypass_radis_lock=True).write({'export_send': 'E' if success else 'N'})
            if success:
                sent.append(order.name)
        return {'data_result': success, 'count': len(sent), 'order_send': sent}

    @api.model
    def send_order_sale_api(self, orders, company_id):
        # El modelo del ZIP antiguo era `maintenance.api` (no presente en dependencias).
        # En el 18 se reutiliza la API declarada en api_administrator.
        try:
            result = self.env['api.administrator'].call_api(
                api_name='check_update_qoutes', method='post',
                company_id=company_id, params=orders,
            )
            if isinstance(result, dict):
                return bool(result.get('success'))
            return False
        except Exception:
            _logger.exception('Error enviando cotizaciones a Radis empresa %s', company_id)
            return False
