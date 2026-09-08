from odoo import api, fields, models


class CommissionSeller(models.Model):
    _name = "commission.seller"
    _description = "Vendedor de comisiones"
    _order = "code, name"

    name = fields.Char(required=True, index=True)
    code = fields.Char(required=True, index=True)
    active = fields.Boolean(default=True)
    role = fields.Selection(
        [
            ("seller", "Vendedor retail"),
            ("project", "Vendedor de proyectos"),
            ("manager", "Administrador"),
            ("hybrid", "Híbrido"),
        ],
        default="seller",
        required=True,
    )
    manager_id = fields.Many2one(
        "commission.seller",
        string="Administrador responsable",
        domain="[('role', 'in', ['manager', 'hybrid'])]",
        ondelete="set null",
    )
    default_location_id = fields.Many2one(
        "commission.location",
        string="Localidad principal",
        ondelete="set null",
    )
    created_from_sales = fields.Boolean(
        string="Creado desde ventas",
        default=False,
        readonly=True,
        help="Indica que el maestro fue creado automáticamente al ingresar una venta.",
    )
    notes = fields.Text()

    _sql_constraints = [
        ("seller_code_unique", "unique(code)", "El código de vendedor debe ser único."),
    ]

    @api.model
    def get_or_create_from_sale(self, code, name=None, location=None):
        """Return the seller master for external sales data, creating it if needed."""
        code = (code or "").strip()
        if not code:
            return self.browse()

        seller = self.search([("code", "=", code)], limit=1)
        clean_name = (name or "").strip()
        vals = {}
        # Existing masters are not overwritten by recurring source data. Only
        # complete placeholder values and fill a missing default location.
        if seller and clean_name and seller.name == seller.code:
            vals["name"] = clean_name
        if location and (not seller or not seller.default_location_id):
            vals["default_location_id"] = location.id

        if seller:
            if vals:
                seller.write(vals)
            return seller

        return self.create({
            "code": code,
            "name": clean_name or code,
            "default_location_id": location.id if location else False,
            "created_from_sales": True,
        })

    # Backward-compatible helper name used by the first version of the addon.
    @api.model
    def get_or_create_from_api(self, code, name=None, location=None):
        return self.get_or_create_from_sale(code, name, location)


class CommissionLocation(models.Model):
    _name = "commission.location"
    _description = "Localidad / almacén para comisiones"
    _order = "code, name"

    name = fields.Char(required=True, index=True)
    code = fields.Char(required=True, index=True)
    active = fields.Boolean(default=True)
    created_from_sales = fields.Boolean(
        string="Creada desde ventas",
        default=False,
        readonly=True,
        help="Indica que la localidad fue creada automáticamente al ingresar una venta.",
    )
    notes = fields.Text()

    _sql_constraints = [
        ("location_code_unique", "unique(code)", "El código de localidad debe ser único."),
    ]

    @api.model
    def get_or_create_from_sale(self, code, name=None):
        """Return the location master for external sales data, creating it if needed."""
        code = (code or "").strip()
        if not code:
            return self.browse()

        location = self.search([("code", "=", code)], limit=1)
        clean_name = (name or "").strip()
        if location:
            if clean_name and location.name == location.code:
                location.name = clean_name
            return location

        return self.create({
            "code": code,
            "name": clean_name or code,
            "created_from_sales": True,
        })

    @api.model
    def get_or_create_from_api(self, code, name=None):
        return self.get_or_create_from_sale(code, name)
