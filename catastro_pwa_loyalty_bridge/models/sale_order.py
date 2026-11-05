# -*- coding: utf-8 -*-
"""Product-line promotions for Catastro PWA.

Only automatic, current-order, non-nominative percentage rewards that target
specific products are eligible. Native gift cards, eWallets, free products,
capped rewards and coupons remain exclusively in sale_loyalty: they MUST NOT be
reinterpreted as a product-line percentage or their accounting will change.
"""
from odoo import fields, models
from odoo.exceptions import ValidationError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _catastro_loyalty_bridge_active(self):
        return True

    def _get_no_effect_on_threshold_lines(self):
        return super()._get_no_effect_on_threshold_lines() | self.order_line.filtered('is_catastro_payment_surcharge')

    def catastro_pwa_product_promotion_choices(self):
        """Use sale_loyalty's own domain and rule engine for eligible promotions.

        This method does not create reward products, consume points, change
        pricing or write an order. It can also be called on a transient order.
        """
        self.ensure_one()
        if self.state and self.state != 'draft':
            return {}
        regular = self.order_line.filtered(
            lambda line: line.product_id and not line.display_type and
            not line.reward_id and line.product_uom_qty > 0
        )
        if not regular:
            return {}
        programs = self.env['loyalty.program'].search(self._get_program_domain() + [
            ('trigger', '=', 'auto'),
            ('applies_on', '=', 'current'),
        ]).filtered(lambda prog: prog.program_type == 'promotion' and not prog.is_nominative and
                   (not prog.limit_usage or prog.total_order_count < prog.max_usage))
        if not programs:
            return {}
        # Native engine checks customer, company, pricelist, dates, minimum
        # quantities and amounts, and product/category/tag conditions.
        statuses = self._program_check_compute_points(programs)
        result = {line.product_id.id: [] for line in regular}
        for program in programs:
            status = statuses.get(program, {})
            if 'error' in status or not status.get('points'):
                continue
            available_points = status['points'][0]
            for reward in program.reward_ids.filtered(lambda r:
                    r.active and r.reward_type == 'discount' and
                    r.discount_mode == 'percent' and r.discount_applicability == 'specific' and
                    0 < r.discount <= 100 and not r.discount_max_amount and
                    not r.program_id.is_payment_program and
                    r.required_points <= available_points):
                # Avoid stacking a native reward line with the same promotion.
                if reward in self.order_line.reward_id:
                    continue
                matching = regular.filtered(lambda line:
                    bool(line.product_id.filtered_domain(reward._get_discount_product_domain())))
                for line in matching:
                    offers = result[line.product_id.id]
                    if not any(offer['id'] == reward.id for offer in offers):
                        offers.append({'id': reward.id,
                                       'name': reward.description or program.name,
                                       'discount': reward.discount})
        for offers in result.values():
            offers.sort(key=lambda offer: (-offer['discount'], offer['id']))
        return result

    def catastro_pwa_apply_product_promotions(self, selections=None):
        """Recheck native conditions and materialize applicable offers in line.discount.

        Called after PWA creates/edits a quotation and again at confirmation.
        It first removes its OWN prior discounts so the threshold rules see
        full base prices. Unsupported Loyalty rewards are left untouched.
        """
        self.ensure_one()
        if self.state != 'draft':
            return {}
        selections = selections or {}
        # Prevent converting one discount while a second, native discount still
        # appears as a special product line. This is not an SRI-ready document.
        native_discount_lines = self.order_line.filtered(
            lambda l: l.reward_id and l.reward_id.reward_type == 'discount')
        if native_discount_lines:
            raise ValidationError(
                'Esta proforma ya tiene recompensas Loyalty como líneas especiales. '
                'No se pueden combinar con descuentos por artículo sin revisar su tratamiento fiscal.')
        self.catastro_restore_base_prices()
        regular = self.order_line.filtered(lambda l: l.product_id and not l.display_type and not l.reward_id)
        old = {}
        for line in regular:
            if line.catastro_pwa_promo_reward_id:
                old[line.product_id.id] = line.catastro_pwa_promo_reward_id.id
                line.write({
                    'discount': line.catastro_pwa_promo_base_discount,
                    'catastro_pwa_promo_reward_id': False,
                    'catastro_pwa_promo_base_discount': 0.0,
                })
        offers = self.catastro_pwa_product_promotion_choices()
        for line in regular:
            pid = line.product_id.id
            options = offers.get(pid, [])
            explicit = selections.get(pid, old.get(pid, None))
            if explicit is None:
                chosen = options[0] if options else None
            else:
                try:
                    requested = int(explicit)
                except (ValueError, TypeError):
                    raise ValidationError('La promoción seleccionada no es válida.')
                if requested == 0:
                    chosen = None
                else:
                    chosen = next((o for o in options if o['id'] == requested), None)
                    if chosen is None:
                        # If eligibility vanished after removing or editing a
                        # product, revoke the discount rather than silently
                        # keeping a stale price in the sale order.
                        chosen = None
            if not chosen:
                continue
            base = line.discount or 0.0
            combined = 100 - ((100 - base) * (100 - chosen['discount']) / 100.0)
            line.write({
                'catastro_pwa_promo_reward_id': chosen['id'],
                'catastro_pwa_promo_base_discount': base,
                'discount': min(100, max(0, combined)),
            })
        self.catastro_recompute_surcharge()
        return self.catastro_pwa_product_promotion_choices()

    def action_confirm(self):
        # When a salesperson confirms from the native Odoo interface, remove
        # any PWA promotion that no longer meets the program's conditions.
        for order in self.filtered(lambda o: o.state == 'draft' and o.order_line.filtered('catastro_pwa_promo_reward_id')):
            order.catastro_pwa_apply_product_promotions()
        return super().action_confirm()


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    catastro_pwa_promo_reward_id = fields.Many2one(
        'loyalty.reward', string='Promoción por producto (PWA)',
        copy=False, readonly=True, ondelete='set null')
    catastro_pwa_promo_base_discount = fields.Float(
        string='Descuento anterior a promoción PWA (%)',
        copy=False, readonly=True, digits=(12, 4))
