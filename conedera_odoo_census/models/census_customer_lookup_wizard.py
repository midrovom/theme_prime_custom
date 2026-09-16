import re

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class CensusCustomerLookupWizard(models.TransientModel):
    _name = "conedera.census.customer.lookup.wizard"
    _description = "Validar cliente antes de crear catastro"

    vat = fields.Char(
        string="RUC / Cédula",
        help="Recomendado. Se normalizan espacios, guiones y puntos para localizar clientes ya registrados.",
    )
    customer_name = fields.Char(string="Nombre / razón social")
    validation_state = fields.Selection(
        [
            ("pending", "Pendiente"),
            ("found", "Cliente encontrado"),
            ("not_found", "No existe"),
            ("multiple", "Se requiere más precisión"),
        ],
        default="pending",
        readonly=True,
    )
    existing_partner_id = fields.Many2one("res.partner", string="Cliente encontrado", readonly=True)
    validation_message = fields.Text(string="Resultado", readonly=True)

    # Vista previa de la información que ya existe en Odoo. Al abrir la ficha de
    # catastro se reutiliza el mismo res.partner, por lo que estos datos aparecen
    # automáticamente y el vendedor solo completa lo que falte.
    existing_name = fields.Char(related="existing_partner_id.name", string="Razón social", readonly=True)
    existing_vat = fields.Char(related="existing_partner_id.vat", string="RUC / Cédula", readonly=True)
    existing_commercial_name = fields.Char(
        related="existing_partner_id.commercial_name", string="Nombre comercial", readonly=True
    )
    existing_phone = fields.Char(related="existing_partner_id.phone", string="Teléfono", readonly=True)
    existing_mobile = fields.Char(related="existing_partner_id.mobile", string="Móvil", readonly=True)
    existing_email = fields.Char(related="existing_partner_id.email", string="Email", readonly=True)
    existing_street = fields.Char(related="existing_partner_id.street", string="Dirección", readonly=True)
    existing_city = fields.Char(related="existing_partner_id.city", string="Ciudad", readonly=True)
    existing_user_id = fields.Many2one(
        related="existing_partner_id.user_id", string="Vendedor actual", readonly=True
    )

    @api.onchange("vat", "customer_name")
    def _onchange_identity(self):
        self.validation_state = "pending"
        self.existing_partner_id = False
        self.validation_message = False

    @staticmethod
    def _normalize_identity(value):
        return re.sub(r"[^0-9A-Za-z]", "", value or "").upper()

    def _reopen(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Nuevo catastro"),
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "views": [
                (
                    self.env.ref(
                        "conedera_odoo_census.view_census_customer_lookup_wizard_form"
                    ).id,
                    "form",
                )
            ],
            "target": "new",
        }

    def _find_by_normalized_vat(self, vat):
        normalized = self._normalize_identity(vat)
        if not normalized:
            return self.env["res.partner"]
        self.env.cr.execute(
            """
            SELECT id
              FROM res_partner
             WHERE parent_id IS NULL
               AND vat IS NOT NULL
               AND regexp_replace(upper(vat), '[^0-9A-Z]', '', 'g') = %s
             ORDER BY active DESC, id
             LIMIT 4
            """,
            [normalized],
        )
        ids = [row[0] for row in self.env.cr.fetchall()]
        if not ids:
            return self.env["res.partner"]
        # Reaplicamos el ORM para respetar permisos y reglas de acceso.
        return self.env["res.partner"].with_context(active_test=False).search(
            [("id", "in", ids), ("parent_id", "=", False)], order="active desc, id"
        )

    def _find_existing(self):
        self.ensure_one()
        Partner = self.env["res.partner"].with_context(active_test=False)
        vat = (self.vat or "").strip()
        name = (self.customer_name or "").strip()

        if vat:
            return self._find_by_normalized_vat(vat), "vat"

        matches = Partner.search(
            [
                ("parent_id", "=", False),
                "|",
                ("name", "=ilike", name),
                ("commercial_name", "=ilike", name),
            ],
            limit=4,
        )
        return matches, "name"

    def action_validate(self):
        self.ensure_one()
        vat = (self.vat or "").strip()
        name = (self.customer_name or "").strip()
        if not vat and not name:
            raise ValidationError(_("Ingrese primero el RUC / cédula o el nombre del cliente."))

        matches, mode = self._find_existing()
        if len(matches) == 1:
            partner = matches[0]
            self.write(
                {
                    "validation_state": "found",
                    "existing_partner_id": partner.id,
                    "validation_message": _(
                        "Cliente encontrado en Odoo. Se reutilizarán sus datos actuales y se completará el catastro sobre esta misma ficha; no se creará un duplicado."
                    ),
                }
            )
        elif len(matches) > 1:
            self.write(
                {
                    "validation_state": "multiple",
                    "existing_partner_id": False,
                    "validation_message": _(
                        "Hay varios clientes con esa identificación. Ingrese el RUC / cédula exacto para continuar sin riesgo de duplicados."
                    ),
                }
            )
        else:
            label = _("RUC / cédula") if mode == "vat" else _("nombre")
            self.write(
                {
                    "validation_state": "not_found",
                    "existing_partner_id": False,
                    "validation_message": _(
                        "No existe un cliente con ese %(label)s. Puede crear una ficha nueva."
                    )
                    % {"label": label},
                }
            )
        return self._reopen()

    def _open_partner(self, partner):
        return {
            "type": "ir.actions.act_window",
            "name": _("Catastro del cliente"),
            "res_model": "res.partner",
            "res_id": partner.id,
            "view_mode": "form",
            "views": [
                (
                    self.env.ref("conedera_odoo_census.view_partner_form_census_mobile").id,
                    "form",
                )
            ],
            "target": "current",
        }

    def action_open_existing(self):
        self.ensure_one()
        if self.validation_state != "found" or not self.existing_partner_id:
            raise UserError(_("Valide primero el RUC / cédula o nombre del cliente."))
        partner = self.existing_partner_id.with_context(active_test=False)
        vals = {}
        if not partner.active:
            vals["active"] = True
        if not partner.census_active:
            vals["census_active"] = True
        if self.vat and not partner.vat:
            vals["vat"] = self.vat.strip()
        if not partner.user_id:
            vals["user_id"] = self.env.user.id
        if vals:
            partner.write(vals)
        return self._open_partner(partner)

    def action_create_new(self):
        self.ensure_one()
        if self.validation_state != "not_found":
            raise UserError(_("Primero valide que el cliente no exista."))
        vat = (self.vat or "").strip()
        name = (self.customer_name or "").strip()
        if not vat and not name:
            raise ValidationError(_("Ingrese el RUC / cédula o el nombre del cliente."))

        # Defensa adicional contra carreras o validaciones antiguas: justo antes de
        # crear volvemos a comprobar la identificación normalizada.
        if vat:
            matches = self._find_by_normalized_vat(vat)
            if matches:
                raise UserError(
                    _("Ese RUC / cédula ya existe. Use la ficha existente en lugar de crear otra.")
                )

        record_name = name or (_("BORRADOR - RUC %s") % vat)
        partner = self.env["res.partner"].create(
            {
                "name": record_name,
                "vat": vat or False,
                "census_active": True,
                "company_type": "company",
                "customer_rank": 1,
                "user_id": self.env.user.id,
            }
        )
        return self._open_partner(partner)
