from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from collections import Counter
import logging
_logger = logging.getLogger(__name__)


class SaleOrderSelectProducts(models.TransientModel):
    _name = 'sale.order.select.products'
    _description = 'Seleccionar Productos para Orden de Venta'

    product_ids = fields.Many2many(
        'product.product', 
        string='Productos a agregar', 
    )

    warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Bodega',
        # default=lambda self: self.env.user.property_warehouse_id,
    )

    @api.onchange('warehouse_id')
    def _onchange_warehouse_id(self):
        domain = []

        if self.warehouse_id:
            location_id = self.warehouse_id.lot_stock_id
            quants = self.env['stock.quant'].read_group(
                [('location_id', '=', location_id.id), ('quantity', '>', 0)],
                ['product_id'],
                ['product_id']
            )
            product_ids = [q['product_id'][0] for q in quants if q['product_id']]
            domain = [('id', 'in', product_ids)]

        if self.product_ids:
            
            self.product_ids = False

            return {
                'warning': {
                    'title': _('Cambio de bodega no permitido'),
                    'message': _(
                        'Ya ha seleccionado productos de una bodega. '
                        'Para seleccionar otra bodega, primero agregue los productos '
                        'a las líneas de la orden y vuelva a intentar.'
                    )
                },
                'domain': {'product_ids': domain}
            }


        # if self.product_ids:

        #     return {
        #         'warning': {
        #             'title': _('Cambio de bodega no permitido'),
        #             'message': _(
        #                 'Ya ha seleccionado productos de la bodega actual. '
        #                 'Para seleccionar otra bodega, primero agregue estos productos a las líneas de la orden '
        #                 'y luego limpie la selección de productos.'
        #             )
        #         }
        #     }

        # if self.warehouse_id:
        #     location_id = self.warehouse_id.lot_stock_id
        #     quants = self.env['stock.quant'].read_group(
        #         [('location_id', '=', location_id.id), ('quantity', '>', 0)],
        #         ['product_id'],
        #         ['product_id']
        #     )
        #     product_ids = [q['product_id'][0] for q in quants if q['product_id']]
        #     domain = [('id', 'in', product_ids)]

        return {'domain': {'product_ids': domain}}
    

    @api.onchange('product_ids')
    def _onchange_validate_location(self):
        for record in self:
            if record.product_ids:
                if not record.warehouse_id:
                    record.product_ids = False
                    return {
                        'warning': {
                            'title': _('Ubicación requerida'),
                            'message': _(
                                'Por favor, seleccione la ubicación de origen antes de agregar productos, '
                                'para visualizar correctamente el stock disponible en la bodega.'
                            )
                        }
                    }
                



    # def add_products_to_order(self):
    #     active_id = self.env.context.get('active_id')
    #     sale_order = self.env['sale.order'].browse(active_id)

    #     for product in self.product_ids:
    #         # if sale_order and sale_order.order_line:
    #         #     self.validar_productos_repetidos(sale_order)
    #         if sale_order.order_line:
    #             for line in sale_order.order_line:
    #                 count = 0
    #                 if line.product_id.id == product.id:
    #                     count += 1

    #                 if count > 0:
    #                     raise ValidationError(_(
    #                         "No se pueden repetir productos en las líneas de la orden de venta. "
    #                         "Productos duplicados: %s") % product.display_name)
                    
    #         sale_order.order_line.create({
    #             'order_id': sale_order.id,
    #             'product_id': product.id,
    #             'name': product.name,
    #             'product_uom_qty': 1,  # Puedes personalizar cantidad
    #             'price_unit': product.lst_price,  # Precio de venta
    #             "warehouse_id": self.warehouse_id.id
    #         })
    #     return {'type': 'ir.actions.act_window_close'}





    def add_products_to_order(self):
        active_id = self.env.context.get('active_id')
        sale_order = self.env['sale.order'].browse(active_id)

        for product in self.product_ids:
            # Flag para saber si el producto YA EXISTE en la misma bodega
            already_exists = False

            if sale_order.order_line:
                for line in sale_order.order_line:
                    # Revisamos coincidencia de producto y bodega
                    if (
                        line.product_id.id == product.id and
                        line.warehouse_id.id == self.warehouse_id.id
                    ):
                        already_exists = True
                        break  # No necesitamos seguir buscando

            if already_exists:
                raise ValidationError(_(
                    "No se pueden repetir productos en las líneas de la orden de venta "
                    "de la misma Bodega. Producto duplicado: %s (Bodega: %s)"
                ) % (product.display_name, self.warehouse_id.display_name))

            # Si no está duplicado en la misma bodega, creamos la línea
            sale_order.order_line.create({
                'order_id': sale_order.id,
                'product_id': product.id,
                'name': product.name,
                'product_uom_qty': 1,  # Puedes personalizar cantidad
                'price_unit': product.lst_price,
                'warehouse_id': self.warehouse_id.id
            })

        return {'type': 'ir.actions.act_window_close'}


    

    # def validar_productos_repetidos(self, sale_order):
    #     # Extrae todos los nombres de productos de las líneas
    #     product_names = [line.product_id.display_name for line in sale_order.order_line if line.product_id]
    #     # Detecta duplicados
    #     duplicates = [name for name, count in Counter(product_names).items() if count > 0]
    #     # Lanza error si hay duplicados
    #     if duplicates:
    #         duplicated_str = ', '.join(duplicates)
    #         raise ValidationError(_(
    #             "No se pueden repetir productos en las líneas de la orden de venta. "
    #             "Productos duplicados: %s") % duplicated_str)



    def validar_productos_repetidos(self, sale_order):
        # Construir lista de pares (producto, bodega)
        product_warehouse_pairs = []
        for line in sale_order.order_line:
            if line.product_id and line.warehouse_id:
                product_warehouse_pairs.append(
                    (line.product_id.id, line.warehouse_id.id)
                )
        
        # Contar las repeticiones
        pair_counter = Counter(product_warehouse_pairs)

        # Buscar duplicados
        duplicates = [
            pair for pair, count in pair_counter.items() if count > 1
        ]

        if duplicates:
            duplicated_strs = []
            for product_id, warehouse_id in duplicates:
                product = self.env['product.product'].browse(product_id)
                warehouse = self.env['stock.warehouse'].browse(warehouse_id)
                duplicated_strs.append(
                    "%s (Bodega: %s)" % (
                        product.display_name,
                        warehouse.display_name
                    )
                )
            raise ValidationError(_(
                "No se pueden repetir productos en las líneas de la orden de venta "
                "de la misma Bodega. Productos duplicados: %s"
            ) % ', '.join(duplicated_strs))