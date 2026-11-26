import logging
import requests
import json
from odoo import models, fields, api

_logger = logging.getLogger(__name__)

class QuotesApiAssing(models.Model):
    _name = 'quotes.api.assing'
    _description = 'Quotes API Assing'

    name = fields.Char()
    date = fields.Datetime(string='Fecha', default=fields.Datetime.now)
    value = fields.Char()
    description = fields.Text(string='Descripción')
    company_id = fields.Many2one(
        'res.company', string='Compañía', default=lambda self: self.env.user.company_id)

    @api.model
    def cron_export_order_sale(self, company_id):
        """ Ejecuta la exportación de órdenes de venta,cotizaciones todas cuidado con el tipo de dato"""
        order_result = self.get_sale_orders(company_id)
        if order_result.get('data_result'):
            self.create({
                'name': 'Actualización de order_sale desde API',
                'value': order_result.get('count'),
                'description': order_result.get('order_send'),
                'company_id': company_id
            })
            _logger.info("Órdenes procesadas correctamente: %s", order_result.get('data_result'))
        else:
            _logger.warning("No hay órdenes para procesar: %s", order_result)

    @api.model
    def get_sale_orders(self, company_id):
        """ Obtiene órdenes de venta pendientes de envío a Radis """
        try:
            domain = [
                ("company_id", "=", company_id),
                ("export_send", "!=", "E"),
                ("state", "!=", "cancel"),
                ("amount_total", ">", 0)
            ]
            sale_orders = self.env['sale.order'].sudo().search(domain, limit=3)

            if not sale_orders:
                _logger.info("No hay órdenes pendientes para exportar.")
                return {'data_result': False, 'count': 0, 'order_send': []}

            order_data = [{
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
                    'order_location_wh': line.warehouse_id.code,
                    'price_unit': str(line.price_unit),
                    'negotiable_price': str(line.negotiable_price),
                    "total_tax": str(line.price_tax),
                } for line in order.order_line]
            } for order in sale_orders]


            data_result = self.send_order_sale_api(order_data, company_id)

            count = 0
            order_send = []

            for order in sale_orders:
                new_status = 'E' if data_result else 'N'
                order.write({'export_send': new_status})
                if new_status == 'E':
                    count += 1
                    order_send.append(order.name)

            return {'data_result': data_result, 'count': count, 'order_send': order_send}

        except Exception as e:
            _logger.error("Error obteniendo órdenes de venta: %s", e, exc_info=True)
            return {'data_result': False, 'count': 0, 'order_send': str(e)}

    @api.model
    def send_order_sale_api(self, orders, company_id):
        """ Envía las órdenes de venta a la API externa de Radis """
        try:
            api_data = self.env['maintenance.api'].sudo().search_read(
                [('name', '=', 'check_update_qoutes'), ('type', '=', 'post'), ('company_id', '=', company_id)],
                ['url', 'end_point', 'user_id', 'password'],
                limit=1
            )

            if not api_data:
                _logger.warning("No se encontró configuración de API para la compañía ID %s", company_id)
                return False

            api_url = f"{api_data[0]['url']}{api_data[0]['end_point'].strip()}"
            headers = {
                'Accept': 'application/json',
                'version': '1',
                'framework': 'PRUEBAS',
                'userid': api_data[0]['user_id'].strip(),
                'password': api_data[0]['password'].strip(),
                'deviceid': '000000000000000',
                'sessionid': '0',
                'Content-Type': 'application/json'
            }

            _logger.info("Enviando órdenes a %s", api_url)
            with requests.post(api_url, headers=headers, json=orders) as response:
                if response.status_code == 200:
                    result = response.json()
                    return result.get("success", False)
                else:
                    _logger.error("Error en la API Radis: %s", response.status_code)
                    return False
        except requests.RequestException as e:
            _logger.error("Error en la solicitud a Radis: %s", e, exc_info=True)
            return False
        except Exception as e:
            _logger.error("Error inesperado en la integración con Radis: %s", e, exc_info=True)
            return False


