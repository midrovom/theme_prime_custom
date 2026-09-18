import re

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


class CensusCustomerLookupWizard(models.TransientModel):
    _name = "conedera.census.customer.lookup.wizard"
    _description = "Validar cliente antes de crear catastro"

    existing_partner_id = fields.Many2one(
        "res.partner",
        string="Buscar cliente existente",
        help="Escriba RUC, cédula o nombre. Odoo mostrará coincidencias mientras escribe.",
    )
    vat = fields.Char(
        string="RUC / Cédula exacto",
        help="Úselo si no encontró el cliente en la búsqueda predictiva. Se ignoran puntos, espacios y guiones.",
    )
    customer_name = fields.Char(string="Nombre / razón social")
    validation_state = fields.Selection(
        [
            ("pending", "Pendiente"),
            ("found", "Cliente seleccionado"),
            ("not_found", "No existe"),
            ("multiple", "Hay varias coincidencias"),
            ("restricted", "Ya existe en otro catastro"),
        ],
        default="pending",
        readonly=True,
    )
    validation_message = fields.Text(string="Resultado", readonly=True)

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
    existing_census_active = fields.Boolean(
        related="existing_partner_id.census_active", string="Ya catastrado", readonly=True
    )

    @api.onchange("existing_partner_id")
    def _onchange_existing_partner(self):
        if self.existing_partner_id:
            partner = self.existing_partner_id.commercial_partner_id
            self.existing_partner_id = partner
            self.vat = partner.vat or self.vat
            self.customer_name = partner.name or self.customer_name
            self.validation_state = "found"
            self.validation_message = _(
                "Cliente seleccionado. Se reutilizará esta misma ficha; no se creará un duplicado."
            )
        else:
            self.validation_state = "pending"
            self.validation_message = False

    @api.onchange("vat", "customer_name")
    def _onchange_identity(self):
        if not self.existing_partner_id:
            self.validation_state = "pending"
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
            "views": [(self.env.ref("conedera_odoo_census.view_census_customer_lookup_wizard_form").id, "form")],
            "target": "new",
        }

    def _find_by_normalized_vat_sudo(self, vat):
        normalized = self._normalize_identity(vat)
        if not normalized:
            return self.env["res.partner"].sudo().browse()
        self.env.cr.execute(
            """
            SELECT id
              FROM res_partner
             WHERE vat IS NOT NULL
               AND regexp_replace(upper(vat), '[^0-9A-Z]', '', 'g') = %s
             ORDER BY active DESC, parent_id NULLS FIRST, id
             LIMIT 30
            """,
            [normalized],
        )
        ids = [row[0] for row in self.env.cr.fetchall()]
        if not ids:
            return self.env["res.partner"].sudo().browse()
        records = self.env["res.partner"].sudo().with_context(active_test=False).browse(ids).exists()
        commercial = records.mapped("commercial_partner_id")
        # de-duplicate commercial entities while preserving order
        seen = set()
        result = self.env["res.partner"].sudo().browse()
        for partner in commercial:
            if partner.id not in seen:
                result |= partner
                seen.add(partner.id)
        return result

    def _accessible_subset(self, records):
        if not records:
            return self.env["res.partner"]
        return self.env["res.partner"].with_context(active_test=False).search([("id", "in", records.ids)])

    def action_validate(self):
        self.ensure_one()
        if self.existing_partner_id:
            self.validation_state = "found"
            self.validation_message = _("Cliente seleccionado. Continúe con esta misma ficha.")
            return self._reopen()

        vat = (self.vat or "").strip()
        name = (self.customer_name or "").strip()
        if not vat and not name:
            raise ValidationError(_("Seleccione un cliente existente o ingrese RUC / cédula o nombre."))

        if vat:
            all_matches = self._find_by_normalized_vat_sudo(vat)
            accessible = self._accessible_subset(all_matches)
            accessible_census = accessible.filtered("census_active")
            any_census = all_matches.filtered("census_active")
            if len(accessible_census) == 1:
                self.existing_partner_id = accessible_census[0]
                self.validation_state = "found"
                self.validation_message = _("Ese documento ya tiene Catastro. Se abrirá la ficha existente.")
            elif len(accessible_census) > 1:
                self.validation_state = "multiple"
                self.validation_message = _(
                    "Existen varios catastros históricos con esa identificación. Seleccione la ficha correcta en la búsqueda predictiva y solicite al administrador depurar los duplicados."
                )
            elif any_census:
                self.validation_state = "restricted"
                self.validation_message = _(
                    "Ese RUC / cédula ya tiene un Catastro asignado a otro comercial/equipo. No puede crear otro; solicite apoyo a su supervisor."
                )
            elif len(accessible) == 1:
                self.existing_partner_id = accessible[0]
                self.validation_state = "found"
                self.validation_message = _("Cliente encontrado. Se reutilizará esta ficha y sus datos actuales.")
            elif len(accessible) > 1:
                self.validation_state = "multiple"
                self.validation_message = _(
                    "Hay varias fichas de Contactos con esa identificación. Use el campo 'Buscar cliente existente' y seleccione cuál será la ficha canónica del Catastro."
                )
            else:
                self.validation_state = "not_found"
                self.validation_message = _("No existe un cliente con ese RUC / cédula. Puede crear una ficha nueva.")
            return self._reopen()

        Partner = self.env["res.partner"].with_context(active_test=False)
        matches = Partner.search([
            ("parent_id", "=", False),
            "|", ("name", "ilike", name), ("commercial_name", "ilike", name),
        ], limit=12)
        if len(matches) == 1:
            self.existing_partner_id = matches[0]
            self.validation_state = "found"
            self.validation_message = _("Cliente encontrado. Se reutilizará esta ficha.")
        elif len(matches) > 1:
            self.validation_state = "multiple"
            self.validation_message = _(
                "Hay varios clientes con nombres similares. Seleccione uno en la búsqueda predictiva o ingrese el RUC / cédula exacto."
            )
        else:
            self.validation_state = "not_found"
            self.validation_message = _("No existe un cliente con ese nombre. Puede crear una ficha nueva.")
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

    def _can_take_existing_partner(self, partner):
        if not partner.user_id or partner.user_id == self.env.user:
            return True
        if self.env.user.has_group("sales_team.group_sale_manager"):
            return True
        team = partner.census_team_id or partner.user_id.sale_team_id
        return bool(team and team.user_id == self.env.user)

    def action_open_existing(self):
        self.ensure_one()
        partner = self.existing_partner_id.commercial_partner_id
        if not partner:
            raise UserError(_("Seleccione primero uno de los clientes encontrados."))
        if partner.census_active:
            return self._open_partner(partner)

        # Si el usuario escogió uno de varios Contactos duplicados, pero otro de
        # ellos ya es el Catastro canónico, nunca intentamos activar un segundo.
        # Abrimos el canónico cuando es visible o informamos que pertenece a otro equipo.
        identity = partner.vat or self.vat
        if identity:
            canonical = (self._find_by_normalized_vat_sudo(identity).filtered("census_active") - partner)[:1]
            if canonical:
                accessible_canonical = self._accessible_subset(canonical)
                if accessible_canonical:
                    return self._open_partner(accessible_canonical[0])
                raise AccessError(_(
                    "Ese RUC / cédula ya tiene un Catastro asignado a otro comercial/equipo. "
                    "No puede activar otra ficha duplicada; solicite apoyo a su supervisor."
                ))

        if not self._can_take_existing_partner(partner):
            raise AccessError(_("Este cliente ya está asignado a otro comercial. El supervisor debe habilitar o reasignar la ficha."))
        owner = partner.user_id or self.env.user
        team = owner.sale_team_id or self.env["crm.team"]._get_default_team_id(user_id=owner.id)
        vals = {
            "active": True,
            "census_active": True,
            "user_id": owner.id,
            "census_locked": False,
        }
        if team:
            vals["census_team_id"] = team.id
        if self.vat and not partner.vat:
            vals["vat"] = self.vat.strip()
        partner.with_context(census_system_write=True).write(vals)
        return self._open_partner(partner)

    def action_create_new(self):
        self.ensure_one()
        if self.validation_state != "not_found":
            raise UserError(_("Primero confirme que el cliente no exista o seleccione una ficha existente."))
        vat = (self.vat or "").strip()
        name = (self.customer_name or "").strip()
        if not vat and not name:
            raise ValidationError(_("Ingrese el RUC / cédula o el nombre del cliente."))
        if vat and self._find_by_normalized_vat_sudo(vat):
            raise UserError(_("Ese RUC / cédula ya existe. Seleccione una de las fichas existentes; no se permite crear otro catastro."))
        record_name = name or (_("BORRADOR - RUC %s") % vat)
        team = self.env.user.sale_team_id or self.env["crm.team"]._get_default_team_id(user_id=self.env.user.id)
        vals = {
            "name": record_name,
            "vat": vat or False,
            "census_active": True,
            "census_locked": False,
            "company_type": "company",
            "customer_rank": 1,
            "user_id": self.env.user.id,
        }
        if team:
            vals["census_team_id"] = team.id
        partner = self.env["res.partner"].with_context(census_system_write=True).create(vals)
        return self._open_partner(partner)
