from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class WebsiteProductOfferRule(models.Model):
    _name = "website.product.offer.rule"
    _description = "Regla de oferta por producto y sitio"
    _rec_name = "product_tmpl_id"
    _order = "website_id, product_tmpl_id"

    active = fields.Boolean(default=True)
    website_id = fields.Many2one(
        comodel_name="website",
        string="Sitio web",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        related="website_id.company_id",
        store=True,
        index=True,
    )
    product_tmpl_id = fields.Many2one(
        comodel_name="product.template",
        string="Producto",
        required=True,
        ondelete="cascade",
        index=True,
        domain="[('sale_ok', '=', True)]",
    )
    min_qty = fields.Float(
        string="Cantidad mínima",
        default=0.0,
        digits="Product Unit of Measure",
        help="Use cero para aplicar la cantidad predeterminada del sitio.",
    )
    max_qty = fields.Float(
        string="Cantidad máxima",
        default=0.0,
        digits="Product Unit of Measure",
        help="Use cero para no establecer un máximo adicional al stock.",
    )
    minimum_price_percent = fields.Float(
        string="Precio mínimo (% de lista)",
        default=0.0,
        help="Use cero para aplicar el porcentaje configurado en el sitio.",
    )
    note = fields.Char(string="Nota interna")

    _sql_constraints = [
        (
            "website_product_unique",
            "unique(website_id, product_tmpl_id)",
            "Ya existe una regla para este producto en el sitio seleccionado.",
        ),
    ]

    @api.constrains("min_qty", "max_qty", "minimum_price_percent")
    def _check_values(self):
        for rule in self:
            if rule.min_qty < 0 or rule.max_qty < 0:
                raise ValidationError(_("Las cantidades no pueden ser negativas."))
            if rule.max_qty and rule.min_qty and rule.max_qty < rule.min_qty:
                raise ValidationError(_("La cantidad máxima no puede ser menor que la mínima."))
            if not 0 <= rule.minimum_price_percent <= 100:
                raise ValidationError(_("El porcentaje de precio mínimo debe estar entre 0 y 100."))

    def _effective_min_qty(self):
        self.ensure_one()
        return self.min_qty or self.website_id.offer_default_min_qty

    def _effective_minimum_price_percent(self):
        self.ensure_one()
        return self.minimum_price_percent or self.website_id.offer_minimum_price_percent
