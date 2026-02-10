# -*- coding: utf-8 -*-
from odoo import models, fields, api
import requests
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)

class StockAPIAssing(models.Model):
    _name = 'stock.api.assing'
    _description = 'Stock API Sync Log'

    name = fields.Char(string='Nombre')
    date = fields.Datetime(string='Fecha', default=fields.Datetime.now)
    value = fields.Float(compute="_compute_value", store=True, string='Insertados')
    value2 = fields.Float(compute="_compute_value2", store=True, string='Actualizados')
    description = fields.Text(string='Descripción')
    company_id = fields.Many2one('res.company', string='Empresa Local', 
                                 default=lambda self: self.env.user.company_id)

    @api.depends('description')
    def _compute_value(self):
        for record in self:
            record.value = record.description.count('Insertado') if record.description else 0

    @api.depends('description')
    def _compute_value2(self):
        for record in self:
            record.value2 = record.description.count('Actualizado') if record.description else 0

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    check_manage_sync = fields.Boolean(string='Sincronizado con API', default=False)


class StockAPISync(models.Model):
    _name = 'stock.api.sync'
    _description = 'Stock API Sync Logic'

    @api.model
    def sync_inventory(self):
        try:
            # Obtener configuración de API
            api_data_xad = self.env['api.administrator'].sudo().search(
                [('name', '=', 'stock_api_assing_xad'), ('type', '=', 'get'), ('company_id', '=', 1)], limit=1
            )

            if not api_data_xad:
                raise ValueError("Configuración de API 'stock_api_assing_bpc' no encontrada.")

            # Validar los campos obligatorios
            api_url = (api_data_xad.url or '').strip() + (api_data_xad.end_point or '').strip()
            user_id = (api_data_xad.user_id or '').strip()
            password = (api_data_xad.password or '').strip()

            if not api_url or not user_id or not password:
                raise ValueError("Configuración de API incompleta: falta URL, User ID o Password.")

            # _logger.info("Iniciando sincronización con la API: %s", api_url)

            # Configurar cabeceras
            headers = {
                'Accept': 'application/json',
                'version': '1',
                'framework': 'PRUEBAS',
                'userid': user_id,
                'password': password,
                'deviceid': '000000000000000',
                'sessionid': '0',
            }

            # Consumir API
            response = requests.get(api_url, headers=headers, timeout=60)
            response.raise_for_status()
            data = response.json().get('data', [])

            if not data:
                _logger.warning("La API devolvió una respuesta vacía.")
                return

            # Procesar datos
            self._process_inventory_data(data)

        except requests.exceptions.RequestException as e:
            _logger.error(f"Error al conectar con la API: {str(e)}")
        except Exception as e:
            _logger.error(f"Error inesperado: {str(e)}")

    def _process_inventory_data(self, data):
        """Procesa datos de inventario devueltos por la API."""
        insertados = 0
        actualizados = 0
        # Limitar registros para pruebas (puedes eliminar esta línea para producción)
        #data = data[:2]
    
        for item in data:
            try:
                codigo = item.get('codigo', '').strip()
                name = item.get('Nombre', '').strip()
                price = float(item.get('Precio', 0))
                stock = float(item.get('Stock', 0))
    
                product = self.env['product.template'].search([('default_code', '=', codigo)], limit=1)
                if product:
                    # Actualizar producto existente
                    product.write({
                        'list_price': price,
                        'qty_available': stock,
                        'check_manage_sync': True,
                    })
                    actualizados += 1
                else:
                    # Crear nuevo producto
                    self.env['product.template'].create({
                        'name': name,
                        'default_code': codigo,
                        'list_price': price,
                        'type': 'consu',
                        'qty_available': stock,
                        'check_manage_sync': True,
                    })
                    insertados += 1
            except Exception as e:
                _logger.error(f"Error procesando producto {item.get('codigo', 'Desconocido')}: {str(e)}")
    
        # Crear un registro en el log con un resumen
        self.env['stock.api.assing'].create({
            'name': f"Sincronización {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            'description': f"Productos insertados: {insertados}, productos actualizados: {actualizados}.",
            'company_id': self.env.user.company_id.id,
        })
    
        # _logger.info(f"Sincronización completada: {insertados} productos insertados, {actualizados} productos actualizados.")



    def _process_inventory_data(self, data, api_data):
        insertados = 0
        actualizados = 0
        data = data[:2]

        for item in data:
            codigo = item.get('codigo', '').strip()
            name = item.get('Nombre', '').strip()
            price = float(item.get('Precio', 0))

            product = self.env['product.template'].search([('default_code', '=', codigo)], limit=1)

            # _logger.info(f"__DEBUG: pricelist name {api_data.price_list_id.name}")
            # _logger.info(f"__DEBUG: Precio {price}")
            if product:
                # Determinar si se debe actualizar el list_price o la lista de precios
                if not api_data.price_list_id or api_data.price_list_id.name == 'Public Pricelist':
                    if product.list_price != price:
                        # _logger.info(f"__DEBUG: Precio si va por update {price}")
                        product.write({'list_price': price})
                        actualizados += 1
                else:
                    self._assign_price_to_pricelist(product, api_data.price_list_id, price)
                    actualizados += 1
            else:
                # Crear nuevo producto sin stock
                new_product = self.env['product.template'].create({
                    'name': name,
                    'default_code': codigo,
                    'list_price': price if not api_data.price_list_id or api_data.price_list_id.name == 'Public Pricelist' else 0,
                    'type': 'consu',
                    'check_manage_sync': True,
                })

                # Si tiene una lista de precios configurada, asignar el precio a esa lista
                if api_data.price_list_id and api_data.price_list_id.name != 'Public Pricelist':
                    self._assign_price_to_pricelist(new_product, api_data.price_list_id, price)

                insertados += 1

        _logger.info(f"Productos procesados: Insertados {insertados}, Actualizados {actualizados}")
        return insertados, actualizados