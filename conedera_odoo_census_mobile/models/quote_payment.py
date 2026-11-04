from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class CatastroQuotePaymentOption(models.Model):
    _name = 'catastro.quote.payment.option'
    _description = 'Condición de pago y recargo - Catastro PWA'
    _order = 'sequence,id'

    name = fields.Char(string='Condición de pago', required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    surcharge_percent = fields.Float(string='Recargo (%)', default=0, digits=(12, 4), required=True)
    payment_term_id = fields.Many2one('account.payment.term', string='Plazo de pago nativo')
    surcharge_product_id = fields.Many2one('product.product', string='Servicio de recargo')

    @api.constrains('surcharge_percent', 'surcharge_product_id', 'company_id', 'payment_term_id')
    def _check_option(self):
        for r in self:
            if r.surcharge_percent < 0 or r.surcharge_percent > 100:
                raise ValidationError('El recargo debe estar entre 0% y 100%.')
            if r.surcharge_percent and not r.surcharge_product_id:
                raise ValidationError('Configure un producto de tipo servicio para el recargo.')
            if r.surcharge_product_id:
                if r.surcharge_product_id.type != 'service' or not r.surcharge_product_id.sale_ok:
                    raise ValidationError('El producto de recargo debe ser un servicio vendible.')
                if r.surcharge_product_id.company_id and r.surcharge_product_id.company_id != r.company_id:
                    raise ValidationError('El servicio de recargo pertenece a otra empresa.')
            if r.payment_term_id and r.payment_term_id.company_id and r.payment_term_id.company_id != r.company_id:
                raise ValidationError('El plazo de pago debe pertenecer a esta empresa.')


class ResCompany(models.Model):
    _inherit = 'res.company'

    catastro_retail_partner_id = fields.Many2one('res.partner', string='Consumidor final para Catastro PWA',
        help='El perfil Tienda podrá crear cotizaciones únicamente a este cliente sin un catastro previo.')


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    catastro_payment_option_id = fields.Many2one('catastro.quote.payment.option',
        string='Condición de pago PWA', copy=False, ondelete='restrict')

    def catastro_recompute_surcharge(self):
        """Recargo explícito en una línea distinta de productos y descuentos.

        Base: subtotal antes de impuestos ya afectado por promociones de loyalty.
        No se usa el campo negotiable_price ni se muta price_unit de productos.
        """
        for order in self:
            option = order.catastro_payment_option_id
            if order.state != 'draft' or not option:
                continue
            if option.company_id != order.company_id:
                raise ValidationError('La condición de pago pertenece a otra empresa.')
            fees = order.order_line.filtered('is_catastro_payment_surcharge')
            base = sum(line.price_subtotal for line in order.order_line
                       if not line.display_type and not line.is_catastro_payment_surcharge)
            # Rewards can be negative, but no negative payment surcharge.
            amount = order.currency_id.round(max(0.0, base) * option.surcharge_percent / 100.0)
            if not option.surcharge_percent or not amount:
                fees.unlink()
                continue
            product = option.surcharge_product_id
            if not product or product.type != 'service' or not product.sale_ok:
                raise ValidationError('Configure un servicio válido de recargo para %s.' % option.name)
            taxes = order.fiscal_position_id.map_tax(product.taxes_id.filtered(
                lambda tax: tax.company_id == order.company_id))
            vals = {
                'order_id': order.id,
                'name': 'Recargo por forma de pago: %s (%s%%)' % (option.name, option.surcharge_percent),
                'product_id': product.id,
                'product_uom_qty': 1.0,
                'product_uom': product.uom_id.id,
                'price_unit': amount,
                'discount': 0,
                'tax_id': [(6, 0, taxes.ids)],
                'is_catastro_payment_surcharge': True,
            }
            if fees:
                fees[0].write(vals)
                (fees - fees[0]).unlink()
            else:
                self.env['sale.order.line'].create(vals)

    def action_confirm(self):
        # El importe queda actualizado frente a modificaciones en el formulario
        # estándar, sin sustituir los controles de aprobación de Ventas.
        self.filtered(lambda order: order.state == 'draft' and order.catastro_payment_option_id).catastro_recompute_surcharge()
        return super().action_confirm()


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    is_catastro_payment_surcharge = fields.Boolean(string='Recargo por condición de pago',
        copy=False, readonly=True, default=False)
