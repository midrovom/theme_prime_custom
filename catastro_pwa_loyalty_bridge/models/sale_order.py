from odoo import models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _catastro_loyalty_bridge_active(self):
        return True

    def _get_no_effect_on_threshold_lines(self):
        """Sale Loyalty 18 native hook: exclude separate finance fees from promotions.

        Prevents coupons from discounting the surcharge service, and prevents
        that charge from fulfilling promotion minimum spend thresholds.
        """
        return super()._get_no_effect_on_threshold_lines() | self.order_line.filtered('is_catastro_payment_surcharge')
