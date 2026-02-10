# -*- coding: utf-8 -*-

import datetime
import logging
import requests 
import json
from odoo import models, fields, api
from odoo.tools import config
from datetime import datetime, date , timedelta
_logger = logging.getLogger(__name__)
config['limit_time_real'] = 1000000


class QuotesApiAssing(models.Model):
    _name = 'quotes.api.assing'
    _description = 'quotes_api_assing'

    name = fields.Char()
    date = fields.Datetime(string='Fecha',default=fields.Datetime.now,)
    value = fields.Char()
    description = fields.Text(string='Description')
    company_id = fields.Many2one('res.company', string='Company Local', 
                                default=lambda self: self.env.user.company_id)    


    @api.model
    def cron_export_order_sale(self, company_id):
        order_result = self.get_sale_orders(company_id)
        if(order_result.get('data_result')) :
            in_data = {
                'name' : 'Actualización de order_sale desde api', 
                'value' : order_result.get('count'), 
                'description' :order_result.get('order_send'),  
                'company_id' : company_id
            }
            self.create(in_data)
            _logger.info("Estado (200) ORDENES PROCESADAS %s",order_result.get('data_result') )
        else :
            _logger.info("Error (404) No existen ordenes a procesar %s", order_result )

    @api.model
    def crete_orders_api(self, partner_id, orders_products):
        """ created order sale """
        create_qty = self.env['sale.order'].sudo().create({
            "partner_id" : partner_id,
            "order_line" : orders_products
        })
        return create_qty.id

    @api.model
    def crete_customer_api(self, partners):
        """ Crea un diccionario con los datos del partner a crear """
        partner_data = {
            "name":  partners[0]['name'],
            "city":  partners[0]['city'],
            "phone": partners[0]['phone'],
            "email": partners[0]['email'],
            "vat":   partners[0]['identification']
        }
        partner_id = self.env['res.partner'].sudo().create(partner_data)
        if(partner_id) :
            return partner_id.id
        else :
            return  False

    @api.model
    def get_sale_orders(self, company_id):
        """ obtiene todas las ordenes de venta  
            E fue nviada exitosamente
            N al enviar fallo el api 
            P que esta pendiente de envio
        """
        order_data = []

        try:
            count = 0
            order_result = []
            order_send = []
            data_result = []
            #domain = [('state', '=', 'sale')["state","!=","draft"]]  # You can customize the domain as needed
            domain = [  ("company_id","=", company_id), ("export_send","!=", "E"),("state", "!=", "cancel"),("amount_total",">",0)]

            sale_orders = self.env['sale.order'].sudo().search(domain, limit=3)
            if ( sale_orders ):
                _logger.info("ORDERS  %s", sale_orders)
                for order in sale_orders:
                    order_lines = []
                    for line in order.order_line:
                        order_lines.append({
                            'product': line.product_id.name,
                            'sku': line.product_id.default_code if line.product_id.default_code else '',
                            'quantity': line.product_uom_qty,
                            'order_location_wh': line.warehouse_id.code,
                            'price_unit': str(line.price_unit),
                            "total_tax": str(line.price_tax),
                        })
                    order_data.append({
                        'order_name': order.name,
                        'order_partner':order.partner_id.name,
                        "order_company_code": order.company_id.company_registry,
                        'bodega': order.warehouse_id.code,
                        'order_company_name':order.company_id.name,
                        'order_partner_vat':order.partner_id.vat,
                        'order_partner_adress':order.partner_id.contact_address,
                        'order_partner_phone':order.partner_id.phone,
                        'order_partner_email': order.partner_id.email,
                        'order_partner_mobile': order.partner_id.mobile,
                        'order_vendor_code': order.user_id.vendor_codes,
                        'comentario': order.extract_plain_text(),
                        'order_impuesto': order.amount_tax,
                        'order_total': order.amount_total,
                        'order_state': order.state,
                        'export_send': order.export_send,
                        'order_lines': order_lines,
                    })
                    #recibe los datos y la compania
                    data_result = self.send_order_sale_api(order_data, company_id) 
                    if  data_result == True :
                        count += 1
                        order_send.append(order.name)
                        """ actualiza el campo a Enviado """
                        order.write({
                            'export_send': 'E'
                        })
                        _logger.info("MENSAGE API data_result  %s", data_result )
                    else :
                        """ actualiza el campo a NO enviado """
                        order.write({
                            'export_send': 'N'
                        })
                        _logger.info("MENSAGE API data_result  %s", data_result )

            order_result = {'data_result': data_result, 'count': count, 'order_send': order_send}
            return order_result

        except Exception as e:
            _logger.info("sale_order Error  %s", e)
            order_result = {'data_result': False, 'count': 0, 'order_send': e}
            return order_result 


    @api.model
    def send_order_sale_api(self, orders, company_id):
        """ Crea la api en el systema externo Radis """
        try:
            result = []
            response_data = []
            api_url = ''
            api_data = self.env['maintenance.api'].sudo().search(
                        [ ('name', '=', 'check_update_qoutes'),('type','=','post'),('company_id','=',company_id)], limit=1)
            api_url = api_data.url + api_data.end_point.strip()
            payload = json.dumps(orders)
            #files={} 
            headers = {
                'Accept': 'application/json',
                'version': '1',
                'framework': 'PRUEBAS',
                'userid': api_data.user_id.strip(),
                'password': api_data.password.strip(),
                'deviceid': '000000000000000',
                'sessionid': '0',
                'Content-Type': 'application/json'
            }
            #_logger.info("MENSAGE API payload  %s", payload )
            response = requests.request("POST", api_url, headers=headers, data=payload)

            if response.status_code == 200:
                result = response.json()
                if result :
                    response_data = result["success"] 
                    # Maneja la respuesta según tus necesidades
                    _logger.info("MENSAGE API f_send_sale_order  %s", response_data  )
                
            else:
                _logger.info("Error al insertar en radis  %s", response.status_code )

            return response_data
        except Exception as e:
            return str(e)

class CustomSaleOrder(models.Model):
    """**********************************************************
    Se agrega un camp para control de las ordenes modificadas  
    table: sales order
    view:  sale.view_order_form
    Description:
            E fue nviada exitosamente
            N al enviar fallo el api (puedes revisar en log)
            P que esta pendiente de envio
    *********************************************************"""

    _inherit = 'sale.order'

    export_send = fields.Selection( 
                                    [('E', 'Enviado'), ('N', 'No enviado'), ('P', 'Pendiente')],
                                    string="Send Radis",  
                                    default="P", 
                                    readonly=True )
    
    def action_export_to_radis(self):
        """ Ejecuta la exportación de esta orden de venta a Radis """
        for order in self:
            try:
                company_id = order.company_id.id
                self.env['quotes.api.assing'].cron_export_order_sale(company_id)
                return {
                    'effect': {
                        'fadeout': 'slow',
                        'message': 'Orden enviada a Radis',
                        'type': 'rainbow_man',
                    }
                }
            except Exception as e:
                _logger.error("Error al exportar la orden %s a Radis: %s", order.name, e, exc_info=True)
                return {
                    'warning': {
                        'title': "Error",
                        'message': "Hubo un problema al enviar la orden a Radis.",
                    }
                }
