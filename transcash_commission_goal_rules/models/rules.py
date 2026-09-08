from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class CommissionSellerTarget(models.Model):
    _inherit = "commission.seller.target"

    @api.model_create_multi
    def create(self, vals_list):
        # Las metas del vendedor son globales al período. La localidad no forma
        # parte de la meta ni del cálculo de comisión propia.
        clean_vals = []
        for vals in vals_list:
            vals = dict(vals)
            vals["location_id"] = False
            clean_vals.append(vals)
        return super().create(clean_vals)

    def write(self, vals):
        vals = dict(vals)
        # Si el registro se modifica con esta extensión instalada, se normaliza
        # a una meta global del vendedor.
        vals["location_id"] = False
        return super().write(vals)

    @api.constrains("period_id", "seller_id", "active")
    def _check_one_active_target_per_seller(self):
        for rec in self.filtered("active"):
            duplicate = self.search_count([
                ("id", "!=", rec.id),
                ("period_id", "=", rec.period_id.id),
                ("seller_id", "=", rec.seller_id.id),
                ("active", "=", True),
            ])
            if duplicate:
                raise ValidationError(_(
                    "Solo puede existir una meta activa por vendedor y período."
                ))


class CommissionManagerSellerRule(models.Model):
    _name = "commission.manager.seller.rule"
    _description = "Regla de gestión de administrador por vendedor"
    _order = "period_id desc, manager_id, seller_id"

    period_id = fields.Many2one(
        "commission.period",
        string="Período",
        required=True,
        ondelete="cascade",
        index=True,
    )
    manager_id = fields.Many2one(
        "commission.seller",
        string="Administrador",
        required=True,
        ondelete="cascade",
        index=True,
        domain="[('role', 'in', ['manager', 'hybrid'])]",
    )
    seller_id = fields.Many2one(
        "commission.seller",
        string="Vendedor a cargo",
        required=True,
        ondelete="cascade",
        index=True,
        domain="[('id', '!=', manager_id)]",
    )
    location_id = fields.Many2one(
        "commission.location",
        string="Local para validar meta",
        required=True,
        ondelete="restrict",
        help=(
            "La meta de este local debe cumplirse para que el administrador "
            "pueda cobrar la comisión de gestión por este vendedor. Las ventas "
            "del vendedor NO se filtran por este local."
        ),
    )

    minimum_type = fields.Selection(
        [
            ("fixed", "Monto fijo"),
            ("target_percent", "% de la meta del vendedor"),
        ],
        string="Tipo de mínimo",
        default="fixed",
        required=True,
        help=(
            "Define el umbral de ventas que debe alcanzar este vendedor para "
            "habilitar la comisión de gestión de su administrador."
        ),
    )
    minimum_amount = fields.Float(
        string="Mínimo fijo de ventas",
        default=0.0,
        digits=(16, 4),
        help="Se utiliza cuando el tipo de mínimo es Monto fijo.",
    )
    minimum_target_percent = fields.Float(
        string="Mínimo sobre meta (%)",
        default=80.0,
        digits=(16, 4),
        help=(
            "Se utiliza cuando el tipo de mínimo es % de la meta del vendedor. "
            "Ej.: 80 significa que el mínimo administrativo es 80% de su meta."
        ),
    )
    seller_target_amount = fields.Float(
        string="Meta propia vendedor",
        compute="_compute_target_reference",
        digits=(16, 4),
        help=(
            "Referencia de la meta propia del vendedor. Su comisión personal "
            "se calcula por separado."
        ),
    )
    seller_target_configured = fields.Boolean(
        string="Tiene meta",
        compute="_compute_target_reference",
    )
    effective_minimum = fields.Float(
        string="Mínimo administrativo efectivo",
        compute="_compute_target_reference",
        digits=(16, 4),
        help="Umbral efectivo que se validará al calcular la gestión.",
    )

    commission_percent = fields.Float(
        string="Comisión gestión (%)",
        required=True,
        digits=(16, 4),
        help=(
            "Porcentaje específico que gana el administrador sobre las ventas "
            "del vendedor cuando se cumplen el mínimo administrativo y la meta del local."
        ),
    )
    basis = fields.Selection(
        [("net", "Total neto"), ("price", "Total precio"), ("margin", "Utilidad")],
        string="Base",
        default="net",
        required=True,
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        (
            "manager_seller_period_unique",
            "unique(period_id, manager_id, seller_id)",
            "Ya existe una regla para ese administrador y vendedor en el período.",
        )
    ]

    @api.depends(
        "period_id",
        "seller_id",
        "minimum_type",
        "minimum_amount",
        "minimum_target_percent",
    )
    def _compute_target_reference(self):
        Target = self.env["commission.seller.target"]
        for rec in self:
            target = Target.browse()
            if rec.period_id and rec.seller_id:
                target = Target.search([
                    ("period_id", "=", rec.period_id.id),
                    ("seller_id", "=", rec.seller_id.id),
                    ("active", "=", True),
                ], limit=1)

            rec.seller_target_configured = bool(target)
            rec.seller_target_amount = target.target_amount if target else 0.0
            if rec.minimum_type == "target_percent":
                rec.effective_minimum = (
                    rec.seller_target_amount * rec.minimum_target_percent / 100.0
                    if target
                    else 0.0
                )
            else:
                rec.effective_minimum = rec.minimum_amount

    @api.onchange("seller_id")
    def _onchange_seller_id(self):
        for rec in self:
            if rec.seller_id.manager_id and not rec.manager_id:
                rec.manager_id = rec.seller_id.manager_id

    @api.constrains("manager_id", "seller_id")
    def _check_people(self):
        for rec in self:
            if rec.manager_id and rec.seller_id and rec.manager_id == rec.seller_id:
                raise ValidationError(_(
                    "El administrador y el vendedor a cargo deben ser diferentes."
                ))

    @api.constrains("minimum_amount", "minimum_target_percent", "commission_percent")
    def _check_values(self):
        for rec in self:
            if rec.minimum_amount < 0:
                raise ValidationError(_("El mínimo fijo no puede ser negativo."))
            if rec.minimum_target_percent < 0:
                raise ValidationError(_("El porcentaje mínimo sobre la meta no puede ser negativo."))
            if rec.commission_percent < 0:
                raise ValidationError(_("El porcentaje de comisión no puede ser negativo."))
