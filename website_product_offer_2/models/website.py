from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class Website(models.Model):
    _inherit = "website"

    offer_enabled = fields.Boolean(
        string="Permitir ofertas comerciales",
        help="Muestra la opción de ofertar únicamente en este sitio web.",
    )
    offer_product_scope = fields.Selection(
        selection=[
            ("selected", "Solo productos configurados"),
            ("all", "Todos los productos publicados"),
        ],
        string="Productos que aceptan ofertas",
        required=True,
        default="selected",
    )
    offer_require_login = fields.Boolean(
        string="Exigir inicio de sesión",
        help="Si está activo, únicamente los clientes identificados podrán ofertar.",
    )
    offer_in_stock_only = fields.Boolean(
        string="Mostrar solo con existencias",
        default=True,
        help="Oculta el botón cuando ninguna variante tiene stock en el almacén del sitio.",
    )
    offer_limit_to_stock = fields.Boolean(
        string="Limitar cantidad al stock disponible",
        default=True,
        help="Impide solicitar más unidades que las disponibles en el almacén del sitio.",
    )
    offer_default_min_qty = fields.Float(
        string="Cantidad mínima predeterminada",
        default=1.0,
        digits="Product Unit of Measure",
    )
    offer_minimum_price_percent = fields.Float(
        string="Precio mínimo (% del precio de lista)",
        default=0.0,
        help=(
            "Use cero para revisar cualquier precio manualmente. Por ejemplo, 80 impide "
            "ofertas inferiores al 80 % del precio de lista."
        ),
    )
    offer_validity_days = fields.Integer(
        string="Vigencia de la oferta (días)",
        default=7,
    )
    offer_user_id = fields.Many2one(
        comodel_name="res.users",
        string="Vendedor responsable",
        domain="[('share', '=', False)]",
        help="Responsable asignado automáticamente a las ofertas de este sitio.",
    )

    @api.constrains(
        "offer_default_min_qty",
        "offer_minimum_price_percent",
        "offer_validity_days",
    )
    def _check_offer_configuration(self):
        for website in self:
            if website.offer_default_min_qty <= 0:
                raise ValidationError(_("La cantidad mínima debe ser mayor que cero."))
            if not 0 <= website.offer_minimum_price_percent <= 100:
                raise ValidationError(_("El porcentaje de precio mínimo debe estar entre 0 y 100."))
            if website.offer_validity_days < 1:
                raise ValidationError(_("La vigencia debe ser de al menos un día."))
