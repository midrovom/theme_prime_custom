from odoo import models

class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def _convert_to_tax_base_line_dict_negotiable(self):
        self.ensure_one()

        price_unit = self.negotiable_price
        if self.tax_id:
            tax = self.tax_id[0].amount / 100
            price_unit = self.negotiable_price / (1 + tax)

        return self.env['account.tax']._prepare_base_line_for_taxes_computation(
            self,
            partner_id=self.order_id.partner_id,
            currency_id=self.order_id.currency_id,
            product_id=self.product_id,
            tax_ids=self.tax_id,
            price_unit=price_unit,
            quantity=self.product_uom_qty,
            discount=self.discount,
            price_subtotal=None,  # aquí no es necesario calcularlo
        )
