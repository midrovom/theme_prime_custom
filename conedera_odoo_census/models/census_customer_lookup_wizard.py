from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class CensusCustomerLookupWizard(models.TransientModel):
    _name = "conedera.census.customer.lookup.wizard"
    _description = "Validar cliente antes de crear catastro"

    vat = fields.Char(string="RUC", help="Recomendado. Permite identificar al cliente de forma inequívoca.")
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

    @api.onchange("vat", "customer_name")
    def _onchange_identity(self):
        self.validation_state = "pending"
        self.existing_partner_id = False
        self.validation_message = False

    def _reopen(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Nuevo catastro"),
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "views": [(self.env.ref("conedera_odoo_census.view_census_customer_lookup_wizard_form").id, "form")],
            "target": "new",
        }

    def _find_existing(self):
        self.ensure_one()
        Partner = self.env["res.partner"].with_context(active_test=False)
        vat = (self.vat or "").strip()
        name = (self.customer_name or "").strip()

        if vat:
            matches = Partner.search(
                [("parent_id", "=", False), ("vat", "=ilike", vat)],
                limit=3,
            )
            return matches, "vat"

        # Sin RUC se exige coincidencia exacta por razón social o nombre comercial.
        matches = Partner.search(
            [
                ("parent_id", "=", False),
                "|",
                ("name", "=ilike", name),
                ("commercial_name", "=ilike", name),
            ],
            limit=3,
        )
        return matches, "name"

    def action_validate(self):
        self.ensure_one()
        vat = (self.vat or "").strip()
        name = (self.customer_name or "").strip()
        if not vat and not name:
            raise ValidationError(_("Ingrese primero el RUC o el nombre del cliente."))

        matches, mode = self._find_existing()
        if len(matches) == 1:
            partner = matches[0]
            self.write(
                {
                    "validation_state": "found",
                    "existing_partner_id": partner.id,
                    "validation_message": _(
                        "Cliente encontrado. Se reutilizará esta ficha; no se creará un duplicado."
                    ),
                }
            )
        elif len(matches) > 1:
            self.write(
                {
                    "validation_state": "multiple",
                    "existing_partner_id": False,
                    "validation_message": _(
                        "Hay varios clientes con esa identificación. Ingrese el RUC exacto para continuar."
                    ),
                }
            )
        else:
            label = _("RUC") if mode == "vat" else _("nombre")
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
            "views": [(self.env.ref("conedera_odoo_census.view_partner_form_census_mobile").id, "form")],
            "target": "current",
        }

    def action_open_existing(self):
        self.ensure_one()
        if self.validation_state != "found" or not self.existing_partner_id:
            raise UserError(_("Valide primero el RUC o nombre del cliente."))
        partner = self.existing_partner_id.with_context(active_test=False)
        vals = {}
        if not partner.active:
            vals["active"] = True
        if not partner.census_active:
            vals["census_active"] = True
        if self.vat and not partner.vat:
            vals["vat"] = self.vat.strip()
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
            raise ValidationError(_("Ingrese el RUC o el nombre del cliente."))

        # Si se validó solo por RUC, usamos un nombre de borrador explícito. No cuenta
        # como razón social completa y el usuario deberá reemplazarlo antes de operar.
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
