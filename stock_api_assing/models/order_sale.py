import logging
import requests
import json
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from lxml import html
from collections import Counter

_logger = logging.getLogger(__name__)


CONV_TONELADA = 1000

class CustomSaleOrder(models.Model):
    _inherit = 'sale.order'

    export_send = fields.Selection(
        [('E', 'Enviado'), ('N', 'No enviado'), ('P', 'Pendiente')],
        string="Envío a Radis",
        default="P",
        readonly=True
    )

    warehouse_id = fields.Many2one(
        'stock.warehouse', string='Warehouse', required=True,
        compute="_compute_warehouse_id_by_user", store=True, readonly=False, precompute=True,
        states={'sale': [('readonly', True)], 'done': [('readonly', True)], 'cancel': [('readonly', False)]},
        check_company=True)

    note = fields.Html(string="Comentario", compute='_compute_note', default=False)

    total_peso = fields.Float('Total peso (t)', compute='_compute_total_peso', store=True)

    @api.depends('order_line')
    def _compute_total_peso(self):
        for record in self:
            suma_total_peso = 0.0
            for line in record.order_line:
                if line.product_id.peso and line.product_uom_qty:
                    total_peso = line.product_id.peso * line.product_uom_qty
                    suma_total_peso += total_peso

            
            record.total_peso = suma_total_peso / CONV_TONELADA
                    



    # @api.constrains('order_line')
    # def _check_duplicate_products(self):
    #     for order in self:
    #         product_names = [line.product_id.display_name for line in order.order_line if line.product_id]
    #         duplicates = [product for product, count in Counter(product_names).items() if count > 1]
    #         if duplicates:
    #             duplicated_str = ', '.join(duplicates)
    #             raise ValidationError(_(
    #                 "No se pueden repetir productos en las líneas de la orden de venta de la misma Bodega. "
    #                 "Productos duplicados: %s") % duplicated_str)

    @api.onchange('warehouse_id')
    def _onchange_warehouse_id(self):
        for record  in self:
            if record.order_line and not self.env.user.has_group("stock_api_assing.group_multi_warehouse"):
                warehouses = set(record.order_line.mapped('warehouse_id'))
                # Quitamos None (líneas sin bodega)
                warehouses.discard(None)

                if len(warehouses) == 1:
                    warehouse = warehouses.pop()
                else:
                    warehouse = None

                if warehouse.id != record.warehouse_id.id:
                    record.warehouse_id = warehouse

                    raise ValidationError(_(
                        "No se permite guardar el registro porque ya existen líneas en la orden "
                        f"correspondientes a la bodega actual { warehouse.name }. Si desea cambiar de bodega, elimine "
                        "primero las líneas de la orden y vuelva a intentarlo."
                    ))

            
    @api.constrains('warehouse_id')
    def _constrains_warehouse_id(self):
        for record  in self:
            if record.order_line and not self.env.user.has_group("stock_api_assing.group_multi_warehouse"):
                warehouses = set(record.order_line.mapped('warehouse_id'))
                # Quitamos None (líneas sin bodega)
                warehouses.discard(None)

                if len(warehouses) == 1:
                    warehouse = warehouses.pop()
                else:
                    warehouse = None

                if warehouse.id != record.warehouse_id.id:
                    record.warehouse_id = warehouse

                    raise ValidationError(_(
                        "No se permite guardar el registro porque ya existen líneas en la orden "
                        f"correspondientes a la bodega actual { warehouse.name }. Si desea cambiar de bodega, elimine "
                        "primero las líneas de la orden y vuelva a intentarlo."
                    ))

    @api.constrains('order_line')
    def _check_duplicate_products(self):
        for order in self:
            # Construir claves (producto, bodega) para cada línea
            product_warehouse_pairs = []
            for line in order.order_line:
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


    # @api.constrains('order_line')
    # def _check_duplicate_products(self):
    #     for order in self:
    #         for line in order.order_line:
    #             count = 0
    #             for l in order.order_line:
    #                 if line.product_id.id == l.product_id.id:
    #                     count += 1

    #             if count > 1:
    #                 raise ValidationError(_("No se pueden repetir productos en las líneas de la orden de venta."))

    @api.depends('user_id')
    def _compute_warehouse_id_by_user(self):
        for order in self:
            if order.state in ['draft', 'sent'] or not order.ids:
                order.warehouse_id = order.user_id.property_warehouse_id

    @api.depends()  # Sin dependencias para que no se recalcule automáticamente
    def _compute_note(self):
        for record in self:
            record.note = False  # Siempre vacío

    # Extender la selección del campo 'state'
    state = fields.Selection(
        selection_add=[
            ('async', "Sincronizadas"),  # Nuevo estado
        ],
        ondelete={'async': 'set default'}  # Comportamiento si se elimina el estado
    )

    tax_totals_negotiable = fields.Binary(compute='_compute_tax_totals_negotiable', exportable=False)


    @api.depends_context('lang')
    @api.depends('order_line.tax_id', 'order_line.negotiable_price', 'amount_total', 'amount_untaxed', 'currency_id')
    def _compute_tax_totals_negotiable(self):
        for order in self:
            order = order.with_company(order.company_id)
            order_lines = order.order_line.filtered(lambda x: not x.display_type)
            order.tax_totals_negotiable = order.env['account.tax']._prepare_tax_totals(
                [x._convert_to_tax_base_line_dict_negotiable() for x in order_lines],
                order.currency_id or order.company_id.currency_id,
            )

    def selection_multi(self):
        warehouse_id = self.env.context.get('warehouse_id')

        return {
            'name': 'Seleccionar Productos',
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order.select.products',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_product_ids': False, "default_warehouse_id": warehouse_id},
        }

    def action_export_to_radis(self):
        """ Ejecuta la exportación de esta orden de venta a Radis (solo si está en estado 'draft') """
        for order in self:
            try:
                # Validar que solo se envíen cotizaciones en estado 'draft'
                if order.state != 'draft':
                    return {
                        'warning': {
                            'title': "Acción no permitida",
                            'message': f"La orden {order.name} no está en estado Borrador. Solo se pueden enviar cotizaciones en curso.",
                        }
                    }

                company_id = order.company_id.id

                # Construcción de los datos de la orden
                order_data = [{
                    'order_name': order.name,
                    'order_partner': order.partner_id.name,
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
                    'bodega': order.warehouse_id.code,
                    'order_lines': [{
                        'product': line.product_id.name,
                        'sku': line.product_id.default_code or '',
                        'quantity': line.product_uom_qty,
                        'order_location_wh': line.warehouse_id.code,
                        'price_unit': str(line.price_unit),
                        'negotiable_price': "{:.4f}".format(line.negotiable_price / (1 + (line.tax_id[0].amount / 100))),
                        "total_tax": str(line.price_tax),
                    } for line in order.order_line]
                }]

                # _logger.info(f"MOSTRANDO ORDER SALE >> { order_data }")

                # Llamar a la API desde api.administrator
                result = self.env['api.administrator'].call_api(
                    api_name='check_update_qoutes',
                    method='post',
                    company_id=company_id,
                    params=order_data
                )

                #result = False
                _logger.info("__DEBUG result :  %s", result)
                
                if result and result.get("success") and result.get("order"):
                    order.write({'export_send': 'E','state': 'async'})  # Marcar como enviada
                    return {
                        'effect': {
                            'fadeout': 'slow',
                            'message': f'Orden {order.name} enviada a Radis con éxito',
                            'type': 'rainbow_man',
                        }
                    }
                else:
                    mensaje_error = result.get("mensaje", "Error desconocido en la API")
                    return {
                        'warning': {
                            'title': "Error",
                            'message': f"No se pudo enviar la orden {order.name} a Radis. Motivo: {mensaje_error}",
                        }
                    }
            except Exception as e:
                _logger.error("Error al exportar la orden %s a Radis: %s", order.name, e, exc_info=True)
                return {
                    'warning': {
                        'title': "Error",
                        'message': f"Hubo un problema al enviar la orden {order.name} a Radis.",
                    }
                }


    def extract_plain_text(self):
        if not self.note:
            return ""

        tree = html.fromstring(self.note)
        
        # Extrae solo los <p> con texto no vacío
        lines = [
            p.text_content().strip() 
            for p in tree.xpath('//p') 
            if p.text_content().strip()  # Filtra vacíos
        ]
        
        # Une con espacios (no saltos de línea)
        plain_text = ' '.join(lines)
        
        return plain_text.strip()
    

