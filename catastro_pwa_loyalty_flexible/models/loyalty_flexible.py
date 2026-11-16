"""Incremental, opt-in loyalty discount negotiation for Catastro PWA.

Uses the original Loyalty bridge to determine eligibility, then replaces only
its promotional percentage by an operator-proposed percentage <= reward.discount.
Does not grant price_unit editing or alter negotiable_price.
"""
import math

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    catastro_pwa_promo_granted_percent = fields.Float(
        string='Promoción ofrecida (%)', digits=(8, 3), copy=False,
        help='Porcentaje de promoción elegido dentro del límite de Loyalty. '
             'No es el descuento combinado cuando existe otro descuento previo.')
    catastro_pwa_promo_grant_set = fields.Boolean(
        string='Promoción negociada explícitamente', default=False, copy=False)
    catastro_pwa_promo_grant_reward_id = fields.Many2one(
        'loyalty.reward', string='Regla de descuento negociado', copy=False,
        ondelete='set null')

    @api.constrains('catastro_pwa_promo_granted_percent',
                    'catastro_pwa_promo_grant_set',
                    'catastro_pwa_promo_grant_reward_id')
    def _check_pwa_promotion_grant(self):
        for line in self:
            if not line.catastro_pwa_promo_grant_set:
                continue
            percent = line.catastro_pwa_promo_granted_percent
            reward = line.catastro_pwa_promo_grant_reward_id
            if not math.isfinite(percent) or percent < 0 or percent > 100:
                raise ValidationError('El porcentaje de promoción ofrecido no es válido.')
            if reward and (reward.discount_mode != 'percent' or
                           reward.discount_applicability != 'specific' or
                           percent > float(reward.discount or 0) + 0.000001):
                raise ValidationError('El descuento negociado supera el máximo de Loyalty.')


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def catastro_pwa_apply_product_promotions(self, *args, **kwargs):
        """Apply native bridge FIRST, so its eligibility/warehouse logic prevails.

        Request context: {product_id: {reward_id, percent}} from the trusted PWA
        controller. On re-evaluation with no context, keep the previously chosen
        percentage only when the SAME reward is still eligible.
        """
        proposed = self.env.context.get('catastro_pwa_requested_promo_percent') or {}
        if not isinstance(proposed, dict) or len(proposed) > 60:
            raise ValidationError('Solicitud de descuentos negociados inválida.')
        # Snapshot before bridge may restore/reapply native promotions.
        original = {}
        for order in self:
            for line in order.order_line:
                if line.product_id and line.catastro_pwa_promo_grant_set:
                    original[(order.id, line.product_id.id)] = (
                        line.catastro_pwa_promo_grant_reward_id.id,
                        line.catastro_pwa_promo_granted_percent)

        result = super().catastro_pwa_apply_product_promotions(*args, **kwargs)
        consumed = set()
        for order in self:
            if order.state != 'draft':
                if proposed:
                    raise ValidationError('Solo se puede negociar Loyalty en borradores.')
                continue
            for line in order.order_line:
                if line.display_type or not line.product_id:
                    continue
                pid = line.product_id.id
                reward = line.catastro_pwa_promo_reward_id
                if not reward:
                    if line.catastro_pwa_promo_grant_set or line.catastro_pwa_promo_grant_reward_id:
                        line.write({
                            'catastro_pwa_promo_grant_set': False,
                            'catastro_pwa_promo_granted_percent': 0.0,
                            'catastro_pwa_promo_grant_reward_id': False,
                        })
                    continue

                if reward.discount_mode != 'percent' or reward.discount_applicability != 'specific':
                    raise ValidationError('La promoción seleccionada no admite negociación por producto.')
                max_percent = float(reward.discount or 0.0)
                if not math.isfinite(max_percent) or not 0 <= max_percent <= 100:
                    raise ValidationError('El máximo de la promoción de Loyalty no es válido.')
                request = proposed.get(pid, proposed.get(str(pid)))
                prior_reward_id, prior_pct = original.get((order.id, pid), (None, None))
                if request is not None:
                    try:
                        request_reward = int(request['reward_id'])
                        offered = float(request['percent'])
                    except (ValueError, TypeError, KeyError):
                        raise ValidationError('Descuento ofrecido inválido.')
                    if request_reward != reward.id:
                        raise ValidationError('La promoción dejó de ser elegible para el producto o la bodega.')
                    consumed.add(pid)
                elif prior_reward_id == reward.id and prior_pct is not None:
                    offered = float(prior_pct)
                else:
                    # Existing flow remains the maximum reward if seller did not negotiate.
                    offered = max_percent
                if not math.isfinite(offered) or offered < 0 or offered > max_percent + 0.000001:
                    raise ValidationError(
                        '%s: el descuento permitido es como máximo %.3f%%.'
                        % (line.product_id.display_name, max_percent))
                # Bridge stores the discount that existed BEFORE the loyalty reward.
                # Combine it multiplicatively; never add percentages arithmetically.
                base = float(line.catastro_pwa_promo_base_discount or 0.0)
                if not math.isfinite(base) or base < 0 or base > 100:
                    raise ValidationError('Descuento base incorrecto en la línea de venta.')
                combined = 100.0 - (100.0 - base) * (100.0 - offered) / 100.0
                line.write({
                    'discount': combined,
                    'catastro_pwa_promo_granted_percent': offered,
                    'catastro_pwa_promo_grant_set': True,
                    'catastro_pwa_promo_grant_reward_id': reward.id,
                })
        unknown = {int(pid) for pid in proposed} - consumed
        if unknown:
            raise ValidationError('La promoción elegida ya no está vigente o aplicable. Actualice el catálogo.')
        return result
