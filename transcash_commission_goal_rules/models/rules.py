from odoo import Command, api, fields, models, _
from odoo.exceptions import ValidationError


class CommissionSellerTarget(models.Model):
    _inherit = "commission.seller.target"

    calculation_mode = fields.Selection(
        [
            ("tier", "Por rangos"),
            ("proportional", "Proporcional desde mínimo"),
        ],
        string="Cálculo de comisión",
        default="tier",
        required=True,
        help=(
            "Por rangos conserva la lógica tradicional. Proporcional desde mínimo "
            "paga una fracción del porcentaje acordado según el cumplimiento de la meta."
        ),
    )
    minimum_achievement = fields.Float(
        string="Cumplimiento mínimo (%)",
        default=80.0,
        digits=(16, 4),
        help=(
            "En modo proporcional, por debajo de este cumplimiento no se paga comisión. "
            "Ej.: 80 significa que debe alcanzar al menos 80% de la meta."
        ),
    )
    full_commission_percent = fields.Float(
        string="Comisión al 100% (%)",
        default=0.0,
        digits=(16, 4),
        help=(
            "Porcentaje acordado cuando el vendedor alcanza o supera el 100% de su meta. "
            "Entre el mínimo y el 100%, se paga proporcionalmente al cumplimiento."
        ),
    )

    @api.constrains("calculation_mode", "minimum_achievement", "full_commission_percent")
    def _check_proportional_configuration(self):
        for rec in self:
            if rec.minimum_achievement < 0 or rec.minimum_achievement > 100:
                raise ValidationError(_(
                    "El cumplimiento mínimo debe estar entre 0% y 100%."
                ))
            if rec.full_commission_percent < 0:
                raise ValidationError(_(
                    "El porcentaje de comisión al 100% no puede ser negativo."
                ))

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

    @api.constrains("period_id", "seller_id")
    def _check_unique_target(self):
        """Una sola parametrización de meta por vendedor y período."""
        for rec in self:
            if not rec.period_id or not rec.seller_id:
                continue
            duplicate = self.search_count([
                ("id", "!=", rec.id),
                ("period_id", "=", rec.period_id.id),
                ("seller_id", "=", rec.seller_id.id),
            ])
            if duplicate:
                raise ValidationError(_(
                    "Ya existe una meta para el vendedor %(seller)s en el período %(period)s."
                ) % {
                    "seller": rec.seller_id.display_name,
                    "period": rec.period_id.display_name,
                })

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

    def action_open_copy_wizard(self):
        self.ensure_one()
        return self.env["commission.goal.copy.wizard"].open_for(self)

    def copy_to_period(self, destination_period):
        self.ensure_one()
        existing = self.search([
            ("period_id", "=", destination_period.id),
            ("seller_id", "=", self.seller_id.id),
        ], limit=1)
        if existing:
            raise ValidationError(_(
                "El período destino ya tiene una meta para %(seller)s."
            ) % {"seller": self.seller_id.display_name})

        new_target = self.create({
            "period_id": destination_period.id,
            "seller_id": self.seller_id.id,
            "target_amount": self.target_amount,
            "basis": self.basis,
            "calculation_mode": self.calculation_mode,
            "minimum_achievement": self.minimum_achievement,
            "full_commission_percent": self.full_commission_percent,
            "active": self.active,
        })
        for tier in self.tier_ids:
            tier.copy({"target_id": new_target.id})
        return new_target


class CommissionSellerTargetTier(models.Model):
    _inherit = "commission.seller.target.tier"

    @api.constrains("target_id", "min_achievement", "max_achievement")
    def _check_unique_range(self):
        for rec in self:
            if not rec.target_id:
                continue
            duplicate = self.search_count([
                ("id", "!=", rec.id),
                ("target_id", "=", rec.target_id.id),
                ("min_achievement", "=", rec.min_achievement),
                ("max_achievement", "=", rec.max_achievement),
            ])
            if duplicate:
                raise ValidationError(_(
                    "Ya existe un rango con el mismo cumplimiento mínimo y máximo en esta meta."
                ))


class CommissionLocationTarget(models.Model):
    _inherit = "commission.location.target"

    @api.constrains("period_id", "location_id")
    def _check_unique_location_target_goal_rules(self):
        for rec in self:
            if not rec.period_id or not rec.location_id:
                continue
            duplicate = self.search_count([
                ("id", "!=", rec.id),
                ("period_id", "=", rec.period_id.id),
                ("location_id", "=", rec.location_id.id),
            ])
            if duplicate:
                raise ValidationError(_(
                    "Ya existe una meta para el local %(location)s en el período %(period)s."
                ) % {
                    "location": rec.location_id.display_name,
                    "period": rec.period_id.display_name,
                })

    def action_open_copy_wizard(self):
        self.ensure_one()
        return self.env["commission.goal.copy.wizard"].open_for(self)

    def copy_to_period(self, destination_period):
        self.ensure_one()
        existing = self.search([
            ("period_id", "=", destination_period.id),
            ("location_id", "=", self.location_id.id),
        ], limit=1)
        if existing:
            raise ValidationError(_(
                "El período destino ya tiene una meta para el local %(location)s."
            ) % {"location": self.location_id.display_name})
        return self.create({
            "period_id": destination_period.id,
            "location_id": self.location_id.id,
            "target_amount": self.target_amount,
            "basis": self.basis,
            "required_achievement": self.required_achievement,
        })


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

    def _related_sellers(self):
        self.ensure_one()
        if not self.manager_id:
            return self.env["commission.seller"]
        return self.env["commission.seller"].search([
            ("manager_id", "=", self.manager_id.id),
            ("active", "=", True),
            ("id", "!=", self.manager_id.id),
        ], order="code, name")

    def _seller_line_commands(self):
        """Prepara líneas de vendedores relacionados aún no asignados."""
        self.ensure_one()
        sellers = self._related_sellers()
        if not sellers:
            return []

        # No precarga un vendedor que ya esté asignado a otra gestión activa
        # del mismo período. Así evitamos que el usuario llegue a un error al
        # guardar por una duplicidad que podíamos anticipar en la pantalla.
        if self.period_id:
            domain = [
                ("period_id", "=", self.period_id.id),
                ("seller_id", "in", sellers.ids),
                ("active", "=", True),
                "|",
                ("management_id", "=", False),
                ("management_id.active", "=", True),
            ]
            if self._origin.id:
                domain.append(("management_id", "!=", self._origin.id))
            assigned = self.env["commission.manager.seller.rule"].search(domain).mapped("seller_id")
            sellers -= assigned

        return [
            Command.create({
                "seller_id": seller.id,
                "minimum_type": "fixed",
                "minimum_amount": 0.0,
                "minimum_target_percent": 80.0,
                "commission_percent": 0.0,
                "basis": "net",
                "active": True,
            })
            for seller in sellers
        ]

    @api.onchange("manager_id")
    def _onchange_manager_id_load_sellers(self):
        for rec in self:
            # Cambiar administrador reemplaza el detalle por los vendedores
            # actualmente relacionados al nuevo administrador.
            rec.line_ids = [Command.clear()] + rec._seller_line_commands()

    @api.onchange("period_id")
    def _onchange_period_id_reload_available_sellers(self):
        for rec in self:
            if rec.manager_id and not rec._origin.id:
                rec.line_ids = [Command.clear()] + rec._seller_line_commands()

    @api.model_create_multi
    def create(self, vals_list):
        clean_vals = []
        Seller = self.env["commission.seller"]
        RuleLine = self.env["commission.manager.seller.rule"]
        for vals in vals_list:
            vals = dict(vals)
            # Para creaciones por código/API sin detalle explícito, aplica el
            # mismo comportamiento que la pantalla: carga el equipo relacionado.
            if vals.get("manager_id") and "line_ids" not in vals:
                manager = Seller.browse(vals["manager_id"])
                sellers = Seller.search([
                    ("manager_id", "=", manager.id),
                    ("active", "=", True),
                    ("id", "!=", manager.id),
                ], order="code, name")
                if vals.get("period_id") and sellers:
                    assigned_ids = RuleLine.search([
                        ("period_id", "=", vals["period_id"]),
                        ("seller_id", "in", sellers.ids),
                        ("active", "=", True),
                        "|",
                        ("management_id", "=", False),
                        ("management_id.active", "=", True),
                    ]).mapped("seller_id").ids
                    sellers = sellers.filtered(lambda s: s.id not in assigned_ids)
                vals["line_ids"] = [
                    Command.create({
                        "seller_id": seller.id,
                        "minimum_type": "fixed",
                        "minimum_amount": 0.0,
                        "minimum_target_percent": 80.0,
                        "commission_percent": 0.0,
                        "basis": "net",
                        "active": True,
                    })
                    for seller in sellers
                ]
            clean_vals.append(vals)
        return super().create(clean_vals)

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

    @api.constrains("period_id", "manager_id", "location_id")
    def _check_unique_management_parameter(self):
        for rec in self:
            if not rec.period_id or not rec.manager_id or not rec.location_id:
                continue
            duplicate = self.search_count([
                ("id", "!=", rec.id),
                ("period_id", "=", rec.period_id.id),
                ("manager_id", "=", rec.manager_id.id),
                ("location_id", "=", rec.location_id.id),
            ])
            if duplicate:
                raise ValidationError(_(
                    "Ya existe la gestión del administrador %(manager)s para el local %(location)s en el período %(period)s."
                ) % {
                    "manager": rec.manager_id.display_name,
                    "location": rec.location_id.display_name,
                    "period": rec.period_id.display_name,
                })

    @api.constrains("manager_id", "line_ids")
    def _check_manager_not_in_lines(self):
        for rec in self:
            if rec.manager_id and rec.manager_id in rec.line_ids.mapped("seller_id"):
                raise ValidationError(_(
                    "El administrador no puede estar incluido como vendedor a su propio cargo."
                ))

    def action_load_related_sellers(self):
        """Permite refrescar manualmente el equipo después de cambios maestros."""
        self.ensure_one()
        existing = self.line_ids.mapped("seller_id")
        sellers = self._related_sellers() - existing

        if self.period_id and sellers:
            assigned = self.env["commission.manager.seller.rule"].search([
                ("period_id", "=", self.period_id.id),
                ("seller_id", "in", sellers.ids),
                ("active", "=", True),
                "|",
                ("management_id", "=", False),
                ("management_id.active", "=", True),
                ("management_id", "!=", self.id),
            ]).mapped("seller_id")
            sellers -= assigned

        if not sellers:
            return True
        self.write({
            "line_ids": [
                Command.create({
                    "seller_id": seller.id,
                    "minimum_type": "fixed",
                    "minimum_amount": 0.0,
                    "minimum_target_percent": 80.0,
                    "commission_percent": 0.0,
                    "basis": "net",
                    "active": True,
                })
                for seller in sellers
            ]
        })
        return True

    def action_open_copy_wizard(self):
        self.ensure_one()
        return self.env["commission.goal.copy.wizard"].open_for(self)

    def copy_to_period(self, destination_period):
        self.ensure_one()
        existing = self.search([
            ("period_id", "=", destination_period.id),
            ("manager_id", "=", self.manager_id.id),
            ("location_id", "=", self.location_id.id),
        ], limit=1)
        if existing:
            raise ValidationError(_(
                "El período destino ya tiene una gestión para %(manager)s / %(location)s."
            ) % {
                "manager": self.manager_id.display_name,
                "location": self.location_id.display_name,
            })

        line_commands = []
        for line in self.line_ids:
            line_commands.append(Command.create({
                "seller_id": line.seller_id.id,
                "minimum_type": line.minimum_type,
                "minimum_amount": line.minimum_amount,
                "minimum_target_percent": line.minimum_target_percent,
                "commission_percent": line.commission_percent,
                "basis": line.basis,
                "active": line.active,
            }))

        return self.create({
            "period_id": destination_period.id,
            "manager_id": self.manager_id.id,
            "location_id": self.location_id.id,
            "active": self.active,
            "line_ids": line_commands,
        })


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
        records = super().create(clean_vals)
        records._check_unique_active_seller_assignment()
        return records

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
        self._check_unique_active_seller_assignment()
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


class CommissionProjectRuleGoalRules(models.Model):
    _inherit = "commission.project.rule"

    @api.constrains("period_id", "seller_id", "origin")
    def _check_unique_project_parameter_normalized(self):
        """Evita duplicar el mismo origen por espacios o diferencias de mayúsculas."""
        for rec in self:
            if not rec.seller_id or not rec.origin:
                continue
            normalized = rec.origin.strip()
            domain = [
                ("id", "!=", rec.id),
                ("seller_id", "=", rec.seller_id.id),
                ("origin", "=ilike", normalized),
                ("period_id", "=", rec.period_id.id if rec.period_id else False),
            ]
            if self.search_count(domain):
                raise ValidationError(_(
                    "Ya existe una regla de proyecto para %(seller)s / %(origin)s "
                    "en este período."
                ) % {
                    "seller": rec.seller_id.display_name,
                    "origin": normalized,
                })

    def copy_to_period(self, destination_period):
        self.ensure_one()
        existing = self.search([
            ("period_id", "=", destination_period.id),
            ("seller_id", "=", self.seller_id.id),
            ("origin", "=ilike", (self.origin or "").strip()),
        ], limit=1)
        if existing:
            raise ValidationError(_(
                "El período destino ya tiene la regla de proyecto %(seller)s / %(origin)s."
            ) % {
                "seller": self.seller_id.display_name,
                "origin": self.origin,
            })
        return self.create({
            "period_id": destination_period.id,
            "seller_id": self.seller_id.id,
            "origin": self.origin,
            "commission_percent": self.commission_percent,
            "basis": self.basis,
            "active": self.active,
        })


class CommissionLiquidationRuleGoalRules(models.Model):
    _inherit = "commission.liquidation.rule"

    def copy_to_period(self, destination_period):
        self.ensure_one()
        existing = self.search([
            ("period_id", "=", destination_period.id),
            ("seller_id", "=", self.seller_id.id if self.seller_id else False),
            ("location_id", "=", self.location_id.id if self.location_id else False),
        ], limit=1)
        if existing:
            raise ValidationError(_(
                "El período destino ya tiene una regla de bono equivalente."
            ))
        return self.create({
            "period_id": destination_period.id,
            "seller_id": self.seller_id.id or False,
            "location_id": self.location_id.id or False,
            "indicator_value": self.indicator_value,
            "min_sales_amount": self.min_sales_amount,
            "amount_per_m2": self.amount_per_m2,
            "basis": self.basis,
        })
