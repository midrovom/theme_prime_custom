from odoo import models, api

class CustomSaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.depends_context('lang')
    @api.depends('order_line.tax_id', 'order_line.negotiable_price', 'amount_total', 'amount_untaxed', 'currency_id')
    def _compute_tax_totals_negotiable(self):
        AccountTax = self.env['account.tax']
        for order in self:

            order_lines = order.order_line.filtered(lambda x: not x.display_type)
            base_lines = [line._convert_to_tax_base_line_dict_negotiable() for line in order_lines]
            base_lines += order._add_base_lines_for_early_payment_discount()
            AccountTax._add_tax_details_in_base_lines(base_lines, order.company_id)
            AccountTax._round_base_lines_tax_details(base_lines, order.company_id)

            order.tax_totals_negotiable = AccountTax._get_tax_totals_summary( base_lines=base_lines, currency=order.currency_id or order.company_id.currency_id, company=order.company_id,)
