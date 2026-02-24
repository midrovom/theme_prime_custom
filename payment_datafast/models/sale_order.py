from odoo import models, fields, api

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    shopper_val_base0 = fields.Float(
        string='Base 0%',
        compute='_compute_tax_details',
        store=True,
        digits=(9, 2)
    )
    shopper_val_baseimp = fields.Float(
        string='Base Imponible',
        compute='_compute_tax_details',
        store=True,
        digits=(9, 2)
    )
    shopper_val_iva = fields.Float(
        string='Valor IVA',
        compute='_compute_tax_details',
        store=True,
        digits=(9, 2)
    )

    @api.depends('order_line.price_total', 'order_line.tax_id')
    def _compute_tax_details(self):
        '''
        Metodo para calcular base 0, base imponible y valor iva
        '''
        for order in self:
            base0 = baseimp = iva = 0.00
            for line in order.order_line:
                line_taxes = line.tax_id.compute_all(
                    line.price_unit,
                    quantity=line.product_uom_qty,
                    product=line.product_id,
                    partner=order.partner_id
                )

                if not line_taxes['taxes']:
                    base0 += line.price_subtotal
                else:
                    baseimp += line.price_subtotal
                    iva += sum(t['amount'] for t in line_taxes['taxes'])

            order.shopper_val_base0 = round(base0, 2)
            order.shopper_val_baseimp = round(baseimp, 2)
            order.shopper_val_iva = round(iva, 2)
