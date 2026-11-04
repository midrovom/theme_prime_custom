# -*- coding: utf-8 -*-
import logging
from collections import Counter

from lxml import html
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)
CONV_TONELADA = 1000


class CustomSaleOrder(models.Model):
    _inherit = 'sale.order'

    export_send = fields.Selection([
        ('E', 'Enviado'), ('N', 'No enviado'), ('P', 'Pendiente'),
    ], string='Envío a Radis', default='P', readonly=True, copy=False)

    # Odoo 18 sale_stock define warehouse_id y su cálculo estándar por usuario.
    # No se vuelve a declarar: así conserva su implementación nativa.

    total_peso = fields.Float('Total peso (t)', compute='_compute_total_peso', store=True)
    state = fields.Selection(selection_add=[('async', 'Sincronizadas')], ondelete={'async': 'set default'})
    tax_totals_negotiable = fields.Binary(compute='_compute_tax_totals_negotiable', exportable=False)

    @api.depends('order_line.product_id.peso', 'order_line.product_uom_qty')
    def _compute_total_peso(self):
        for order in self:
            order.total_peso = sum(
                (line.product_id.peso or 0.0) * line.product_uom_qty
                for line in order.order_line if not line.display_type
            ) / CONV_TONELADA

    @api.onchange('warehouse_id')
    def _onchange_radis_warehouse(self):
        if self.env.user.has_group('stock_api_assing.group_multi_warehouse'):
            return
        for order in self:
            warehouses = order.order_line.filtered(lambda l: not l.display_type).mapped('warehouse_id')
            if warehouses and (len(warehouses) != 1 or order.warehouse_id != warehouses):
                return {'warning': {
                    'title': _('Cambio de bodega no permitido'),
                    'message': _('Ya hay líneas de otra bodega. Elimine las líneas antes de cambiar la bodega del pedido.'),
                }}

    @api.constrains('warehouse_id', 'order_line')
    def _constrains_warehouse_id(self):
        if self.env.user.has_group('stock_api_assing.group_multi_warehouse'):
            return
        for order in self:
            warehouses = order.order_line.filtered(lambda l: l.product_id and not l.display_type).mapped('warehouse_id')
            if warehouses and (len(warehouses) != 1 or warehouses != order.warehouse_id):
                raise ValidationError(_(
                    'La bodega del pedido debe coincidir con la de todas las líneas. '
                    'Elimine las líneas de la bodega anterior antes de modificarla.'
                ))

    @api.constrains('order_line')
    def _check_duplicate_products(self):
        for order in self:
            keys = Counter(
                (line.product_id.id, line.warehouse_id.id)
                for line in order.order_line if line.product_id and line.warehouse_id and not line.display_type
            )
            duplicates = [key for key, count in keys.items() if count > 1]
            if duplicates:
                names = []
                for product_id, warehouse_id in duplicates:
                    product = self.env['product.product'].browse(product_id)
                    warehouse = self.env['stock.warehouse'].browse(warehouse_id)
                    names.append('%s (Bodega: %s)' % (product.display_name, warehouse.display_name))
                raise ValidationError(_(
                    'No se pueden repetir productos de la misma bodega: %s'
                ) % ', '.join(names))

    @api.depends_context('lang')
    @api.depends('order_line.tax_id', 'order_line.negotiable_price',
                 'order_line.product_uom_qty', 'order_line.discount', 'currency_id', 'company_id', 'payment_term_id')
    def _compute_tax_totals_negotiable(self):
        AccountTax = self.env['account.tax']
        for order in self:
            base_lines = [
                line._convert_to_tax_base_line_dict_negotiable()
                for line in order.order_line if not line.display_type
            ]
            # Mantener las líneas de descuento por pronto pago del flujo original.
            base_lines += order._add_base_lines_for_early_payment_discount()
            AccountTax._add_tax_details_in_base_lines(base_lines, order.company_id)
            AccountTax._round_base_lines_tax_details(base_lines, order.company_id)
            order.tax_totals_negotiable = AccountTax._get_tax_totals_summary(
                base_lines=base_lines,
                currency=order.currency_id or order.company_id.currency_id,
                company=order.company_id,
            )

    def selection_multi(self):
        self.ensure_one()
        if not isinstance(self.id, int):
            raise UserError(_('Guarde la cotización antes de seleccionar varios productos.'))
        return {
            'name': _('Seleccionar productos'),
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order.select.products',
            'view_mode': 'form', 'target': 'new',
            'context': {
                'active_id': self.id, 'active_model': 'sale.order',
                'default_order_id': self.id,
                'default_warehouse_id': self.warehouse_id.id,
            },
        }

    def action_export_to_radis(self):
        self.ensure_one()
        order = self
        if order.state != 'draft':
            raise UserError(_('La orden %s no está en estado Borrador.') % order.name)
        lines = order.order_line.filtered(lambda l: l.product_id and not l.display_type)
        if not lines:
            raise UserError(_('La cotización no contiene productos para exportar.'))
        if not order.warehouse_id:
            raise UserError(_('Seleccione la bodega del pedido antes de exportarlo.'))
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
                'order_location_wh': (line.warehouse_id or order.warehouse_id).code,
                'price_unit': str(line.price_unit),
                'negotiable_price': '%.4f' % line._get_negotiable_price_excluded(),
                'total_tax': str(line.price_tax),
            } for line in lines],
        }]
        try:
            response = self.env['api.administrator'].call_api(
                api_name='check_update_qoutes', method='post',
                company_id=order.company_id.id, params=order_data,
            )
        except Exception as exc:
            _logger.exception('Error exportando orden %s a Radis', order.name)
            raise UserError(_('No se pudo consultar la API Radis: %s') % exc) from exc
        if not isinstance(response, dict) or not response.get('success') or not response.get('order'):
            reason = response.get('mensaje') or response.get('message') if isinstance(response, dict) else None
            raise UserError(_('Radis no confirmó el envío de %s: %s') % (order.name, reason or _('Respuesta no válida')))
        order.write({'export_send': 'E', 'state': 'async'})
        return {'effect': {
            'fadeout': 'slow', 'message': _('Orden %s enviada a Radis con éxito') % order.name,
            'type': 'rainbow_man',
        }}

    def extract_plain_text(self):
        self.ensure_one()
        if not self.note:
            return ''
        tree = html.fromstring(self.note)
        lines = [p.text_content().strip() for p in tree.xpath('//p') if p.text_content().strip()]
        return ' '.join(lines) if lines else tree.text_content().strip()
