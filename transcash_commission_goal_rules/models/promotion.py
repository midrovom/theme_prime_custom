import base64
import binascii

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .promotion_utils import extract_promotion_products, normalize_product_name


class CommissionPeriodPromotionProduct(models.Model):
    _name = "commission.period.promotion.product"
    _description = "Producto en promoción del período"
    _order = "product_name, id"

    period_id = fields.Many2one(
        "commission.period",
        string="Período",
        required=True,
        ondelete="cascade",
        index=True,
    )
    product_name = fields.Char(
        string="Nombre del producto",
        required=True,
        index=True,
        help="Nombre proveniente del archivo de promociones. El código no se usa para comparar.",
    )
    normalized_name = fields.Char(
        string="Nombre normalizado",
        compute="_compute_normalized_name",
        store=True,
        index=True,
    )
    source_code = fields.Char(
        string="Código del archivo (referencia)",
        help="Se conserva para auditoría, pero nunca se usa para determinar coincidencias.",
    )
    source_row = fields.Integer(string="Fila archivo", readonly=True)

    _sql_constraints = [
        (
            "period_promotion_name_unique",
            "unique(period_id, normalized_name)",
            "El mismo producto en promoción no puede repetirse dentro del período.",
        ),
    ]

    @api.depends("product_name")
    def _compute_normalized_name(self):
        for rec in self:
            rec.normalized_name = normalize_product_name(rec.product_name)

    @api.constrains("product_name")
    def _check_product_name(self):
        for rec in self:
            if not normalize_product_name(rec.product_name):
                raise ValidationError(_("Debe indicar un nombre de producto válido."))


class CommissionPeriodPromotion(models.Model):
    _inherit = "commission.period"

    promotion_file = fields.Binary(
        string="Archivo de productos en promoción",
        attachment=True,
        copy=False,
        help="Formatos admitidos: XLSX y CSV. XLS antiguo requiere xlrd en el servidor.",
    )
    promotion_filename = fields.Char(string="Nombre archivo promociones", copy=False)
    promotion_imported_at = fields.Datetime(
        string="Productos importados el",
        readonly=True,
        copy=False,
    )
    promotion_product_ids = fields.One2many(
        "commission.period.promotion.product",
        "period_id",
        string="Productos en promoción",
        copy=False,
    )
    promotion_product_count = fields.Integer(
        string="Productos promoción",
        compute="_compute_promotion_product_count",
    )

    @api.depends("promotion_product_ids")
    def _compute_promotion_product_count(self):
        for rec in self:
            rec.promotion_product_count = len(rec.promotion_product_ids)

    def action_import_promotion_products(self):
        self.ensure_one()
        if self.state in ("approved", "paid"):
            raise UserError(_(
                "No puede reemplazar los productos en promoción de un período aprobado o pagado."
            ))
        if not self.promotion_file:
            raise UserError(_("Seleccione primero el archivo de productos en promoción."))
        try:
            result = extract_promotion_products(
                base64.b64decode(self.promotion_file),
                self.promotion_filename or "",
            )
        except (ValueError, OSError, UnicodeError, binascii.Error) as exc:
            raise UserError(_("No se pudo leer el archivo de promociones: %s") % exc) from exc

        commands = [Command.clear()]
        commands.extend(
            Command.create({
                "product_name": product["product_name"],
                "source_code": product["source_code"],
                "source_row": product["source_row"],
            })
            for product in result["products"]
        )
        self.write({
            "promotion_product_ids": commands,
            "promotion_imported_at": fields.Datetime.now(),
        })
        if self.state == "calculated":
            warning = _(" Debe recalcular la liquidación porque el período ya estaba calculado.")
        else:
            warning = ""
        message = _(
            "Productos cargados: %(count)s. Columna usada: %(column)s. "
            "Duplicados ignorados: %(duplicates)s. Filas vacías ignoradas: %(empty)s.%(warning)s"
        ) % {
            "count": len(result["products"]),
            "column": result["selected_column"],
            "duplicates": result["duplicates"],
            "empty": result["empty"],
            "warning": warning,
        }
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Productos en promoción"),
                "message": message,
                "type": "warning" if warning else "success",
                "sticky": bool(warning),
            },
        }

    def action_clear_promotion_products(self):
        for rec in self:
            if rec.state in ("approved", "paid"):
                raise UserError(_(
                    "No puede limpiar los productos en promoción de un período aprobado o pagado."
                ))
            rec.write({
                "promotion_product_ids": [Command.clear()],
                "promotion_file": False,
                "promotion_filename": False,
                "promotion_imported_at": False,
            })
        return True


class CommissionSalePromotionName(models.Model):
    _inherit = "commission.sale"

    promotion_match_name = fields.Char(
        string="Nombre normalizado para promoción",
        compute="_compute_promotion_match_name",
        store=True,
        index=True,
        help="Clave técnica de comparación por nombre; no utiliza el código del producto.",
    )

    @api.depends("product_name")
    def _compute_promotion_match_name(self):
        for rec in self:
            rec.promotion_match_name = normalize_product_name(rec.product_name)
