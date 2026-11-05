# -*- coding: utf-8 -*-
"""Extend the native sale_loyalty domains; never duplicate its reward engine."""
from odoo import models
from odoo.osv import expression

from ..warehouse_rules import warehouse_scope_domain


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _get_program_domain(self):
        """Filter automatic programs, existing coupons and PWA reward choices.

        Odoo sale_loyalty uses this domain in _update_programs_and_rewards(),
        _try_apply_program(), and coupon checks. PWA delegates to the same
        method in catastro_pwa_product_promotion_choices().
        """
        self.ensure_one()
        return expression.AND([
            super()._get_program_domain(),
            warehouse_scope_domain(self.warehouse_id.id),
        ])

    def _get_trigger_domain(self):
        """Also block promotional codes for a warehouse outside the program."""
        self.ensure_one()
        return expression.AND([
            super()._get_trigger_domain(),
            warehouse_scope_domain(self.warehouse_id.id, 'program_id.'),
        ])

    def write(self, vals):
        """Revalidate stored drafts when the selected warehouse changes.

        The PWA re-evaluates on create/update, but changes made directly in
        Odoo must also remove invalid PWA discounts and native reward lines.
        Internal Loyalty writes are guarded to avoid a recursion loop.
        """
        should_refresh = (
            'warehouse_id' in vals
            and not self.env.context.get('catastro_skip_warehouse_promotion_refresh')
        )
        previous = {order.id: order.warehouse_id.id for order in self} if should_refresh else {}
        result = super().write(vals)
        if not should_refresh:
            return result
        for order in self:
            if not order.id or order.state != 'draft' or previous.get(order.id) == order.warehouse_id.id:
                continue
            safe_order = order.with_context(catastro_skip_warehouse_promotion_refresh=True)
            # Read previously selected rewards BEFORE clearing the discount.
            # If the reward is valid in the new warehouse, it is preserved;
            # otherwise the existing bridge removes it.
            previous_rewards = {
                line.product_id.id: line.catastro_pwa_promo_reward_id.id
                for line in safe_order.order_line
                if line.product_id and line.catastro_pwa_promo_reward_id
            }
            safe_order.catastro_restore_base_prices()
            for line in safe_order.order_line.filtered('catastro_pwa_promo_reward_id'):
                line.write({
                    'discount': line.catastro_pwa_promo_base_discount,
                    'catastro_pwa_promo_reward_id': False,
                    'catastro_pwa_promo_base_discount': 0.0,
                })
            safe_order._update_programs_and_rewards()
            # Native Loyalty may leave valid reward lines (e.g. a coupon).
            # The existing PWA line-discount bridge deliberately refuses to
            # combine those with its own per-product promotions. Respect that
            # limitation without blocking edits of ordinary Odoo quotations.
            native_discount = safe_order.order_line.filtered(
                lambda line: line.reward_id and line.reward_id.reward_type == 'discount'
            )
            if native_discount:
                safe_order.catastro_recompute_surcharge()
            else:
                safe_order.catastro_pwa_apply_product_promotions(previous_rewards)
        return result
