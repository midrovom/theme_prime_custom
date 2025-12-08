from odoo import models, fields

class ProductTemplate(models.Model):
    _inherit = "product.template"

    dr_brand_value_id = fields.Many2one(
        related="product_variant_ids.dr_brand_value_id",
        store=True,
        readonly=True,
    )
