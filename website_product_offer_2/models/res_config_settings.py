from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    website_offer_enabled = fields.Boolean(
        related="website_id.offer_enabled",
        readonly=False,
    )
    website_offer_product_scope = fields.Selection(
        related="website_id.offer_product_scope",
        readonly=False,
    )
    website_offer_require_login = fields.Boolean(
        related="website_id.offer_require_login",
        readonly=False,
    )
    website_offer_in_stock_only = fields.Boolean(
        related="website_id.offer_in_stock_only",
        readonly=False,
    )
    website_offer_limit_to_stock = fields.Boolean(
        related="website_id.offer_limit_to_stock",
        readonly=False,
    )
    website_offer_default_min_qty = fields.Float(
        related="website_id.offer_default_min_qty",
        readonly=False,
    )
    website_offer_minimum_price_percent = fields.Float(
        related="website_id.offer_minimum_price_percent",
        readonly=False,
    )
    website_offer_validity_days = fields.Integer(
        related="website_id.offer_validity_days",
        readonly=False,
    )
    website_offer_user_id = fields.Many2one(
        related="website_id.offer_user_id",
        readonly=False,
    )

