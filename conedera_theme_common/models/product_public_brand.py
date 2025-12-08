from odoo import api, fields, models

class ProductPublicBrand(models.Model):
    _name = 'product.public.brand'
    _description = "Website Product Brand"
    _order = 'name, id'

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10, index=True)

    product_ids = fields.One2many(
        comodel_name='product.product',
        inverse_name='dr_brand_value_id',
        string="Products"
    )

    website_description = fields.Html(
        string="Brand Description",
        translate=True
    )

    website_footer = fields.Html(
        string="Brand Footer",
        translate=True
    )
