# -*- coding: utf-8 -*-
import logging
import requests
from datetime import datetime
from odoo import models, api, fields

_logger = logging.getLogger(__name__)
class StockAPIAssing(models.Model):
    _name = 'stock.api.assing'
    _description = 'Stock API Sync Log'

    name = fields.Char(string='Nombre')
    date = fields.Datetime(string='Fecha', default=fields.Datetime.now)
    description = fields.Text(string='Descripción')
    company_id = fields.Many2one('res.company', string='Empresa Local', 
                                 default=lambda self: self.env.user.company_id)

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    check_manage_sync = fields.Boolean(string='Sincronizado con API', default=False)

class StockAPISync(models.Model):
    _name = 'stock.api.sync'
    _description = 'Stock API Sync Logic'

    @api.model
    def sync_all_inventory(self, company_id): 
        try:
            # Obtener todas las APIs activas para la empresa que son para actualización de stock
            api_records = self.env['api.administrator'].sudo().search([
                ('company_id', '=', company_id),
                ('type', '=', 'get'),
                ('status', '=', 'A'),
                ('is_stock_update', '=', True)
            ])

            if not api_records:
                _logger.warning(f"No se encontraron APIs activas para la empresa ID {company_id}")
                self.env['stock.api.assing'].create({
                    'name': f"Sync Empresa {company_id}",
                    'description': "No se encontraron APIs activas para la empresa.",
                    'company_id': company_id
                })
                return

            for api_data in api_records:
                try:
                    # Validar configuración de API
                    api_url = (api_data.url or '').strip() + (api_data.end_point or '').strip()
                    user_id = (api_data.user_id or '').strip()
                    password = (api_data.password or '').strip()

                    if not api_url or not user_id or not password:
                        _logger.warning(f"Configuración incompleta para API '{api_data.name}', omitiendo.")
                        self.env['stock.api.assing'].create({
                            'name': f"Error Sync {api_data.name}",
                            'description': "Configuración incompleta de la API.",
                            'company_id': company_id
                        })
                        continue

                    headers = {
                        'Accept': 'application/json',
                        'version': '1',
                        'framework': 'PRUEBAS',
                        'userid': user_id,
                        'password': password,
                        'deviceid': '000000000000000',
                        'sessionid': '0',
                    }

                    _logger.info(f"Iniciando sincronización con API: {api_data.name}")

                    # Consumir API (solo los dos primeros registros)
                    response = requests.get(api_url, headers=headers, timeout=120)
                    response.raise_for_status()

                    #data = response.json().get('data', [])[2:4]  # Limitar a los primeros 2 registros
                    data = response.json().get('data', [])

                    if not data:
                        self.env['stock.api.assing'].create({
                            'name': f"Sync {api_data.name}",
                            'description': "No se encontraron datos para sincronizar.",
                            'company_id': company_id
                        })
                        continue
                    #_logger.info(f"__DEBUG: DATA INFO {data}")

                    #self.update_published_for_storable_products() #actualiza 

                    insertados, actualizados = self._process_inventory_data(data,api_data)

                    #_logger.info(f"API {api_data.name}: {insertados} insertados, {actualizados} actualizados")

                    # Guardar resultados en la tabla de log
                    self.env['stock.api.assing'].create({
                        'name': f"Sync {api_data.name}",
                        'description': f"Insertados: {insertados}, Actualizados: {actualizados}",
                        'company_id': company_id
                    })

                except requests.exceptions.RequestException as e:
                    error_msg = f"Error de conexión con la API {api_data.name}: {str(e)}"
                    _logger.error(error_msg)

                    self.env['stock.api.assing'].create({
                        'name': f"Error Sync {api_data.name}",
                        'description': error_msg,
                        'company_id': company_id
                    })

                except Exception as e:
                    error_msg = f"Error inesperado en la API {api_data.name}: {str(e)}"
                    _logger.error(error_msg)

                    self.env['stock.api.assing'].create({
                        'name': f"Error Sync {api_data.name}",
                        'description': error_msg,
                        'company_id': company_id
                    })

        except Exception as e:
            error_msg = f"Error crítico en la sincronización de inventario: {str(e)}"
            _logger.error(error_msg)

            self.env['stock.api.assing'].create({
                'name': "Error General",
                'description': error_msg, 
                'company_id': company_id
            })


    def _process_inventory_data(self, data, api_data):
        insertados = 0
        actualizados = 0
        #data = data[:2]  # Limitar a los dos primeros registros 

        for item in data:
            codigo = item.get('codigo', '').strip()
            name = item.get('Nombre', '').strip()
            price = float(item.get('Precio', 0))
            stock = float(item.get('Stock', 0))  # Agregar stock
            peso = item.get("Peso")


            product = self.env['product.template'].search([('default_code', '=', codigo),('check_manage_sync','=', True,), ('active', '=', True)], limit=1)

            # Si el producto existe pero tiene check_manage_sync=False, lo ignoramos
            if product and not product.check_manage_sync:
                _logger.info(f"__DEBUG: Producto {codigo} ignorado por check_manage_sync=False")
                continue
            # Verificar si la API tiene una lista de precios asignada
            has_custom_pricelist = api_data.price_list_id and api_data.price_list_id.name != 'Public Pricelist'

            _logger.info(f"__DEBUG: API {api_data.name} - Producto {codigo} - Precio {price} - Stock {stock} - Lista de precios: {api_data.price_list_id.name if api_data.price_list_id else 'Ninguna'}")


            _logger.info(f"__DEBUG: has_custom_pricelist {has_custom_pricelist} ")
            

            if product:
                if not product.is_storable:
                    product.write({ "is_storable": True })

                if peso and float(peso) > 0:
                    if not product.peso:
                        product.write({'peso': float(peso)})

                # actualizar impuesto por defecto si no tiene
                if not product.taxes_id:
                    product.write({'taxes_id': [(6, 0, [self.env.company.account_sale_tax_id.id])] })

                # Si el producto existe, actualizamos dependiendo de si la API tiene lista de precios
                if has_custom_pricelist:
                    # Actualizar solo la lista de precios asignada
                    self._assign_price_to_pricelist(product, api_data.price_list_id, price)
                else:
                    # Actualizar el list_price directamente
                    if product.list_price != price:
                        product.write({'list_price': price})
                
                # Actualizar stock si la API tiene una bodega asociada
                if api_data.warehouse_id:
                    self._update_stock(product, stock, api_data.warehouse_id)
                    # product.write({'check_update': True})

                actualizados += 1
                # product.write({'check_update': True})
            else:
                # Crear el producto
                new_product_data = {
                    'name': name,
                    'default_code': codigo,
                    'list_price': price if not has_custom_pricelist else 0,  # Asignar 0 si se usará lista de precios
                    'type': 'consu',
                    "is_storable": True,
                    'check_manage_sync': True,
                    'taxes_id': [(6, 0, [self.env.company.account_sale_tax_id.id])],

                }

                if peso and float(peso) > 0:
                    new_product_data['peso'] = float(peso)

                new_product = self.env['product.template'].create(new_product_data)

                # Si hay lista de precios asignada, actualizarla
                if has_custom_pricelist:
                    self._assign_price_to_pricelist(new_product, api_data.price_list_id, price)
                
                # Actualizar stock si la API tiene una bodega asociada
                if api_data.warehouse_id:
                    self._update_stock(new_product, stock, api_data.warehouse_id)

                insertados += 1

        # products = self.env['product.template'].search([('check_update', '=', False)])
        stock_quants = self.env['stock.quant'].search([('check_update', '=', False), ('location_id', '=', api_data.warehouse_id.lot_stock_id.id)])
        if stock_quants:
            stock_quants.write({'quantity': 0})
            # self.update_cero_quantity(products, api_data.warehouse_id)

        stock_quants = self.env['stock.quant'].search([('check_update', '=', True), ('location_id', '=', api_data.warehouse_id.lot_stock_id.id)])
        # products = self.env['product.template'].search([('check_update', '=', True)])
        if stock_quants:
            stock_quants.write({'check_update': False})


        _logger.info(f"Resumen de sincronización API {api_data.name}: Insertados {insertados}, Actualizados {actualizados}")
        return insertados, actualizados


    def _assign_price_to_pricelist(self, product, price_list, price):

        _logger.info(f"__DEBUG: product para LISTA {product} ")
        price_rule = self.env['product.pricelist.item'].search([
            ('pricelist_id', '=', price_list.id),
            ('product_tmpl_id', '=', product.id)
        ], limit=1)

        if price_rule:
            price_rule.write({'fixed_price': price})
        else:
            self.env['product.pricelist.item'].create({
                'pricelist_id': price_list.id,
                'product_tmpl_id': product.id,
                'fixed_price': price,
                'applied_on': '1_product',
            })

    def _update_stock(self, product, stock, warehouse):
        # Obtener la ubicación de stock de la bodega
        stock_location = warehouse.lot_stock_id
        if not stock_location:
            _logger.warning(f"La bodega {warehouse.name} no tiene una ubicación de stock configurada.")
            return

        # Verificar que el producto tenga una variante
        product_variant = product.product_variant_id
        if not product_variant:
            _logger.warning(f"El producto {product.default_code} no tiene una variante asociada.")
            return

        # Buscar el registro de stock.quant
        quant = self.env['stock.quant'].search([
            ('product_id', '=', product_variant.id),
            ('location_id', '=', stock_location.id),
        ], limit=1)

        if quant:
            # Actualizar el stock existente
            quant.sudo().write({'quantity': stock, 'check_update': True})
        else:
            # Crear un nuevo registro de stock
            self.env['stock.quant'].sudo().create({
                'product_id': product_variant.id,
                'location_id': stock_location.id,
                'quantity': stock,
                'check_update': True,
            })
        _logger.info(f"Stock actualizado para el producto {product.default_code} en la bodega {warehouse.name}: {stock}")


    @api.model
    def update_published_for_storable_products(self):
        # Buscar todos los productos de tipo "Almacenable"
        storable_products = self.env['product.template'].search([('type', '=', 'consu')])
        
        # Actualizar los campos necesarios
        if storable_products:
            storable_products.write({
                'is_published': True,
                'check_manage_sync': True,
                'company_id': False
            })

    # def update_cero_quantity(self, products, warehouse):
    #     for product in products:
    #         quants = self.env['stock.quant'].search([
    #             ('product_id', '=', product.product_variant_id.id),
    #         ])

    #         if quants:
    #             count = 0
    #             for q in quants:
    #                 if q.quantity == 0 and (q.location_id.location_id.name == "BPC" or q.location_id.location_id.name == "BVD"):
    #                     _logger.info(f'MOSTRANDO NAME UBICACION >>> { q.location_id.location_id.name }')
    #                     count += 1

    #             if count == 2:
    #                 quants.write({'quantity': 0})
