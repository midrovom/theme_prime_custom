from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class CommissionSellerTarget(models.Model):
    _inherit = "commission.seller.target"

    @api.model_create_multi
    def create(self, vals_list):
        # La meta del vendedor es global al período y no depende de localidad.
        clean_vals = []
        for vals in vals_list:
            vals = dict(vals)
            vals["location_id"] = False
            clean_vals.append(vals)
        return super().create(clean_vals)

    def write(self, vals):
        vals = dict(vals)
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


class CommissionManagerGoalRule(models.Model):
    _name = "commission.manager.goal.rule"
    _description = "Gestión de comisión de administrador"
    _order = "period_id desc, manager_id, location_id"

    name = fields.Char(
        string="Descripción",
        compute="_compute_name",
    )
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
    location_id = fields.Many2one(
        "commission.location",
        string="Local cuya meta debe cumplirse",
        required=True,
        ondelete="restrict",
        help=(
            "La meta de este local debe cumplirse para habilitar las comisiones "
            "de gestión del administrador. Las ventas de cada vendedor se toman "
            "de todo el período, sin filtrarlas por este local."
        ),
    )
    line_ids = fields.One2many(
        "commission.manager.seller.rule",
        "management_id",
        string="Vendedores a cargo",
        copy=True,
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        (
            "manager_period_location_unique",
            "unique(period_id, manager_id, location_id)",
            "Ya existe una configuración para ese administrador, período y local.",
        )
    ]

    @api.depends("period_id", "manager_id", "location_id")
    def _compute_name(self):
        for rec in self:
            parts = [
                rec.manager_id.display_name if rec.manager_id else _("Administrador"),
                rec.period_id.display_name if rec.period_id else _("Período"),
                rec.location_id.display_name if rec.location_id else _("Local"),
            ]
            rec.name = " - ".join(parts)

    def write(self, vals):
        res = super().write(vals)
        if {"period_id", "manager_id", "location_id"} & set(vals):
            for rec in self:
                rec.line_ids.write({
                    "period_id": rec.period_id.id,
                    "manager_id": rec.manager_id.id,
                    "location_id": rec.location_id.id,
                })
        if {"active", "period_id", "manager_id", "location_id"} & set(vals):
            self.mapped("line_ids")._check_unique_active_seller_assignment()
        return res

    @api.constrains("manager_id", "line_ids")
    def _check_manager_not_in_lines(self):
        for rec in self:
            if rec.manager_id and rec.manager_id in rec.line_ids.mapped("seller_id"):
                raise ValidationError(_(
                    "El administrador no puede estar incluido como vendedor a su propio cargo."
                ))


class CommissionManagerSellerRule(models.Model):
    _name = "commission.manager.seller.rule"
    _description = "Detalle de vendedor para gestión del administrador"
    _order = "seller_id"

    # Nueva cabecera. Se mantiene opcional para poder actualizar bases que ya
    # tenían líneas creadas por una versión anterior de esta extensión.
    management_id = fields.Many2one(
        "commission.manager.goal.rule",
        string="Gestión administrador",
        ondelete="cascade",
        index=True,
    )

    # Campos técnicos conservados por compatibilidad. Cuando existe cabecera se
    # sincronizan automáticamente con ella y no se editan desde la nueva UI.
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
    location_id = fields.Many2one(
        "commission.location",
        string="Local para validar meta",
        required=True,
        ondelete="restrict",
    )
    seller_id = fields.Many2one(
        "commission.seller",
        string="Vendedor a cargo",
        required=True,
        ondelete="cascade",
        index=True,
        domain="[('id', '!=', manager_id)]",
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
            "Define cuánto debe vender este vendedor para que su administrador "
            "pueda cobrar comisión de gestión por él."
        ),
    )
    minimum_amount = fields.Float(
        string="Mínimo de venta",
        default=0.0,
        digits=(16, 4),
        help="Monto mínimo cuando el tipo de mínimo es Monto fijo.",
    )
    minimum_target_percent = fields.Float(
        string="Mínimo sobre meta (%)",
        default=80.0,
        digits=(16, 4),
        help=(
            "Porcentaje de la meta propia del vendedor que se usa como mínimo "
            "administrativo. Ej.: 80 = debe vender al menos 80% de su meta."
        ),
    )
    seller_target_amount = fields.Float(
        string="Meta del vendedor",
        compute="_compute_target_reference",
        digits=(16, 4),
    )
    seller_target_configured = fields.Boolean(
        string="Tiene meta",
        compute="_compute_target_reference",
    )
    effective_minimum = fields.Float(
        string="Mínimo efectivo",
        compute="_compute_target_reference",
        digits=(16, 4),
        help="Valor real que se validará contra las ventas del vendedor.",
    )
    commission_percent = fields.Float(
        string="Comisión administrador (%)",
        required=True,
        digits=(16, 4),
        help=(
            "Porcentaje específico que gana el administrador sobre las ventas "
            "de este vendedor cuando se cumplen su mínimo y la meta del local."
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
            "management_seller_unique",
            "unique(management_id, seller_id)",
            "El vendedor ya está incluido en esta gestión del administrador.",
        )
    ]

    @api.model_create_multi
    def create(self, vals_list):
        clean_vals = []
        Management = self.env["commission.manager.goal.rule"]
        for vals in vals_list:
            vals = dict(vals)
            management = Management.browse(vals.get("management_id"))
            if management:
                vals.update({
                    "period_id": management.period_id.id,
                    "manager_id": management.manager_id.id,
                    "location_id": management.location_id.id,
                })
            clean_vals.append(vals)
        return super().create(clean_vals)

    def write(self, vals):
        vals = dict(vals)
        res = super().write(vals)
        # Re-sincroniza campos técnicos si la cabecera cambió o si se editó
        # accidentalmente un valor heredado.
        for rec in self.filtered("management_id"):
            expected = {
                "period_id": rec.management_id.period_id.id,
                "manager_id": rec.management_id.manager_id.id,
                "location_id": rec.management_id.location_id.id,
            }
            current = {
                "period_id": rec.period_id.id,
                "manager_id": rec.manager_id.id,
                "location_id": rec.location_id.id,
            }
            if current != expected:
                super(CommissionManagerSellerRule, rec).write(expected)
        return res

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

    @api.onchange("management_id")
    def _onchange_management_id(self):
        for rec in self:
            if rec.management_id:
                rec.period_id = rec.management_id.period_id
                rec.manager_id = rec.management_id.manager_id
                rec.location_id = rec.management_id.location_id

    @api.constrains("management_id", "period_id", "seller_id", "active")
    def _check_unique_active_seller_assignment(self):
        """Evita pagar dos veces gestión por el mismo vendedor en un período."""
        for rec in self.filtered(lambda line: line.active and line.seller_id):
            if rec.management_id and not rec.management_id.active:
                continue
            period = rec.management_id.period_id or rec.period_id
            if not period:
                continue
            duplicate = self.search_count([
                ("id", "!=", rec.id),
                ("seller_id", "=", rec.seller_id.id),
                ("period_id", "=", period.id),
                ("active", "=", True),
                "|",
                ("management_id", "=", False),
                ("management_id.active", "=", True),
            ])
            if duplicate:
                raise ValidationError(_(
                    "El vendedor %(seller)s ya está asignado a una gestión activa "
                    "en el período %(period)s. No puede liquidarse gestión dos veces."
                ) % {
                    "seller": rec.seller_id.display_name,
                    "period": period.display_name,
                })

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
                raise ValidationError(_("El mínimo de venta no puede ser negativo."))
            if rec.minimum_target_percent < 0:
                raise ValidationError(_("El porcentaje mínimo sobre la meta no puede ser negativo."))
            if rec.commission_percent < 0:
                raise ValidationError(_("El porcentaje de comisión no puede ser negativo."))
