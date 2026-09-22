import re

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError

from .census_security_utils import is_census_manager, is_census_supervisor


class CensusCustomerLookupWizard(models.TransientModel):
    _name = "conedera.census.customer.lookup.wizard"
    _description = "Validar cliente antes de crear catastro"

    # Primary mobile-first global lookup. A custom field widget queries a sudo-safe
    # server method and only exposes a controlled snapshot, never the restricted record.
    lookup_query = fields.Char(
        string="RUC, cédula o nombre",
        help="Busque primero. La consulta global detecta clientes aunque pertenezcan a otro comercial.",
    )
    selected_partner_ref_id = fields.Integer(string="Cliente seleccionado", readonly=True)
    selected_candidate_status = fields.Selection(
        [
            ("own_census", "Mi catastro"),
            ("team_census", "Catastro del equipo"),
            ("other_census", "Catastro de otro comercial"),
            ("available_contact", "Contacto disponible"),
            ("assigned_contact", "Contacto asignado a otro comercial"),
            ("company_restricted", "Otra compañía"),
        ],
        readonly=True,
    )
    selected_can_open = fields.Boolean(readonly=True)
    selected_can_use = fields.Boolean(readonly=True)
    selected_can_request_reassignment = fields.Boolean(readonly=True)
    selected_is_census = fields.Boolean(readonly=True)
    reassignment_reason = fields.Text(string="Motivo de la reasignación")

    # Backward-compatible field kept for old saved wizard metadata/tests. The new UI
    # no longer relies on it for global duplicate detection because record rules can
    # hide a partner belonging to another salesperson.
    existing_partner_id = fields.Many2one(
        "res.partner",
        string="Cliente existente",
        help="Compatibilidad con versiones anteriores.",
    )
    vat = fields.Char(string="RUC / Cédula exacto")
    customer_name = fields.Char(string="Nombre / razón social")
    validation_state = fields.Selection(
        [
            ("pending", "Pendiente"),
            ("found", "Cliente seleccionado"),
            ("not_found", "No existe"),
            ("multiple", "Hay varias coincidencias"),
            ("restricted", "Ya existe en otro catastro"),
            ("request_sent", "Solicitud enviada"),
        ],
        default="pending",
        readonly=True,
    )
    validation_message = fields.Text(string="Resultado", readonly=True)

    # Snapshot fields. They are intentionally NOT related fields: related fields would
    # try to read a partner hidden by record rules and could leak or raise AccessError.
    existing_name = fields.Char(string="Razón social", readonly=True)
    existing_vat = fields.Char(string="RUC / Cédula", readonly=True)
    existing_commercial_name = fields.Char(string="Nombre comercial", readonly=True)
    existing_phone = fields.Char(string="Teléfono", readonly=True)
    existing_mobile = fields.Char(string="Móvil", readonly=True)
    existing_email = fields.Char(string="Email", readonly=True)
    existing_street = fields.Char(string="Dirección", readonly=True)
    existing_city = fields.Char(string="Ciudad", readonly=True)
    existing_user_id = fields.Many2one("res.users", string="Vendedor actual", readonly=True)
    existing_owner_label = fields.Char(string="Responsable", readonly=True)
    existing_team_label = fields.Char(string="Equipo", readonly=True)
    existing_census_active = fields.Boolean(string="Ya catastrado", readonly=True)

    @staticmethod
    def _normalize_identity(value):
        return re.sub(r"[^0-9A-Za-z]", "", value or "").upper()

    @staticmethod
    def _looks_like_identity(value):
        normalized = re.sub(r"[^0-9A-Za-z]", "", value or "")
        digits = sum(ch.isdigit() for ch in normalized)
        return bool(normalized) and digits >= max(4, int(len(normalized) * 0.7))

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

    @api.model
    def _candidate_payload(self, partner):
        partner = partner.sudo().commercial_partner_id
        user = self.env.user
        manager = is_census_manager(user)
        team = partner.census_team_id if partner.census_team_id and partner.census_team_id.census_enabled else partner._default_census_team(partner.user_id)
        leader = bool(is_census_supervisor(user) and team and team.user_id == user)
        own = partner.user_id == user
        effective_company = partner.company_id or team.company_id
        company_allowed = not effective_company or effective_company in user.company_ids

        if not company_allowed and not manager:
            status = "company_restricted"
            can_open = can_use = can_request = False
        elif partner.census_active:
            can_open = bool(manager or own or leader)
            can_use = False
            can_request = bool(not can_open and partner.user_id)
            status = "own_census" if own else ("team_census" if leader or manager else "other_census")
        else:
            can_use = bool(manager or not partner.user_id or own or leader)
            can_open = False
            can_request = bool(not can_use and partner.user_id)
            status = "available_contact" if can_use else "assigned_contact"

        privileged_owner_view = bool(manager or own or leader)
        owner_label = (
            partner.user_id.display_name
            if partner.user_id and privileged_owner_view
            else (_("Otro comercial") if partner.user_id else _("Sin asignar"))
        )
        team_label = (
            team.display_name
            if team and privileged_owner_view
            else (_("Otro equipo") if team else _("Sin equipo"))
        )
        display_vat = partner._census_primary_identity()
        status_labels = {
            "own_census": _("Ya es su Catastro"),
            "team_census": _("Catastro de su equipo"),
            "other_census": _("Catastro asignado a otro comercial"),
            "available_contact": _("Cliente existente disponible para Catastro"),
            "assigned_contact": _("Cliente existente asignado a otro comercial"),
            "company_restricted": _("Cliente existente en otra compañía"),
        }
        return {
            "id": partner.id,
            "name": partner.name or _("Sin nombre"),
            "vat": display_vat or "",
            "commercial_name": partner.commercial_name or "",
            "city": partner.city or "",
            "phone": (partner.phone or "") if (can_use or can_open) else "",
            "mobile": (partner.mobile or "") if (can_use or can_open) else "",
            "email": (partner.email or "") if (can_use or can_open) else "",
            "street": (partner.street or "") if (can_use or can_open) else "",
            "owner_id": partner.user_id.id if partner.user_id and privileged_owner_view else False,
            "owner_label": owner_label,
            "team_label": team_label,
            "census_active": bool(partner.census_active),
            "status": status,
            "status_label": status_labels[status],
            "can_open": can_open,
            "can_use": can_use,
            "can_request": can_request,
        }

    @api.model
    def search_global_candidates(self, term, limit=12):
        """Autocomplete that detects duplicates globally without bypassing UX security.

        Search is sudo only for existence. Returned data is a deliberately limited snapshot;
        another salesperson's contact details and owner name are not exposed.
        """
        term = (term or "").strip()
        if len(term) < 2:
            return []
        Partner = self.env["res.partner"].sudo().with_context(active_test=False)
        ids = []
        normalized = self._normalize_identity(term)
        if normalized and len(normalized) >= 3:
            self.env.cr.execute(
                """
                SELECT id
                  FROM res_partner
                 WHERE vat IS NOT NULL
                   AND regexp_replace(upper(vat), '[^0-9A-Z]', '', 'g') LIKE %s
                 ORDER BY
                       CASE WHEN regexp_replace(upper(vat), '[^0-9A-Z]', '', 'g') = %s THEN 0 ELSE 1 END,
                       active DESC,
                       parent_id NULLS FIRST,
                       id
                 LIMIT 40
                """,
                [normalized + "%", normalized],
            )
            ids.extend(row[0] for row in self.env.cr.fetchall())

        if len(term) >= 3:
            name_matches = Partner.search(
                [
                    "|",
                    ("name", "ilike", term),
                    ("commercial_name", "ilike", term),
                ],
                limit=30,
            )
            ids.extend(name_matches.ids)

        seen = set()
        partners = Partner.browse(ids).exists().mapped("commercial_partner_id")
        candidates = []
        for partner in partners:
            if partner.id in seen:
                continue
            seen.add(partner.id)
            candidates.append(self._candidate_payload(partner))

        # Exact document first, then active census, then alphabetical.
        candidates.sort(
            key=lambda c: (
                0 if self._normalize_identity(c["vat"]) == normalized and normalized else 1,
                0 if c["census_active"] else 1,
                (c["name"] or "").lower(),
                c["id"],
            )
        )
        return candidates[: max(1, min(int(limit or 12), 20))]

    def _clear_selection(self):
        self.ensure_one()
        self.write(
            {
                "selected_partner_ref_id": False,
                "selected_candidate_status": False,
                "selected_can_open": False,
                "selected_can_use": False,
                "selected_can_request_reassignment": False,
                "selected_is_census": False,
                "existing_partner_id": False,
                "existing_name": False,
                "existing_vat": False,
                "existing_commercial_name": False,
                "existing_phone": False,
                "existing_mobile": False,
                "existing_email": False,
                "existing_street": False,
                "existing_city": False,
                "existing_user_id": False,
                "existing_owner_label": False,
                "existing_team_label": False,
                "existing_census_active": False,
            }
        )

    def _set_selected_partner(self, partner):
        self.ensure_one()
        partner = partner.sudo().commercial_partner_id
        payload = self._candidate_payload(partner)
        # Only set the real Many2one if the user can normally read/use the partner.
        accessible_partner_id = partner.id if (payload["can_open"] or payload["can_use"]) else False
        values = {
            "selected_partner_ref_id": partner.id,
            "selected_candidate_status": payload["status"],
            "selected_can_open": payload["can_open"],
            "selected_can_use": payload["can_use"],
            "selected_can_request_reassignment": payload["can_request"],
            "selected_is_census": payload["census_active"],
            "existing_partner_id": accessible_partner_id,
            "existing_name": payload["name"],
            "existing_vat": payload["vat"],
            "existing_commercial_name": payload["commercial_name"],
            "existing_phone": payload["phone"],
            "existing_mobile": payload["mobile"],
            "existing_email": payload["email"],
            "existing_street": payload["street"],
            "existing_city": payload["city"],
            "existing_user_id": payload["owner_id"],
            "existing_owner_label": payload["owner_label"],
            "existing_team_label": payload["team_label"],
            "existing_census_active": payload["census_active"],
            "validation_state": "restricted" if (payload["can_request"] or (not payload["can_open"] and not payload["can_use"])) else "found",
            "validation_message": payload["status_label"],
        }
        self.write(values)
        return payload

    @api.model
    def action_select_candidate(self, wizard_id, partner_id):
        wizard = self.browse(wizard_id).exists()
        if not wizard:
            raise UserError(_("La búsqueda venció. Abra nuevamente 'Nuevo catastro'."))

        # Never trust an arbitrary partner_id sent by the browser. The selected row
        # must still belong to the current global lookup result. This keeps the
        # sudo-backed autocomplete useful for duplicate detection without turning it
        # into a generic way to probe hidden contacts by ID.
        query = (wizard.lookup_query or wizard.vat or wizard.customer_name or "").strip()
        if not query:
            raise UserError(_("Escriba primero RUC, cédula o nombre para seleccionar un cliente."))
        candidate_ids = {item["id"] for item in self.search_global_candidates(query, limit=20)}
        partner = (
            self.env["res.partner"]
            .sudo()
            .with_context(active_test=False)
            .browse(partner_id)
            .exists()
        )
        if not partner:
            raise UserError(_("El cliente seleccionado ya no existe."))
        partner = partner.commercial_partner_id
        if partner.id not in candidate_ids:
            raise AccessError(
                _("La ficha seleccionada no corresponde a los resultados de la búsqueda actual. Vuelva a buscar y selecciónela nuevamente.")
            )
        wizard._set_selected_partner(partner)
        return True

    @api.onchange("existing_partner_id")
    def _onchange_existing_partner(self):
        if self.existing_partner_id:
            partner = self.existing_partner_id.commercial_partner_id
            self.lookup_query = partner.vat or partner.name
            self.selected_partner_ref_id = partner.id

    def _selected_partner_sudo(self, validate_lookup=False):
        self.ensure_one()
        partner_id = self.selected_partner_ref_id or self.existing_partner_id.id
        partner = (
            self.env["res.partner"]
            .sudo()
            .with_context(active_test=False)
            .browse(partner_id)
            .exists()
        )
        partner = partner.commercial_partner_id if partner else partner
        if partner and validate_lookup:
            query = (self.lookup_query or self.vat or self.customer_name or "").strip()
            if not query:
                raise UserError(_("La búsqueda ya no es válida. Escriba nuevamente RUC, cédula o nombre."))
            candidate_ids = {
                item["id"] for item in self.search_global_candidates(query, limit=20)
            }
            if partner.id not in candidate_ids:
                raise AccessError(
                    _("La ficha seleccionada no pertenece a los resultados actuales. Vuelva a buscar el cliente antes de continuar.")
                )
        return partner

    def _is_accessible_partner(self, partner):
        if not partner:
            return False
        return bool(
            self.env["res.partner"]
            .with_context(active_test=False)
            .search([("id", "=", partner.id)], limit=1)
        )

    def _open_partner(self, partner):
        partner = partner.sudo().commercial_partner_id
        if not self._is_accessible_partner(partner):
            raise AccessError(
                _(
                    "Este Catastro pertenece a otro comercial/equipo. "
                    "Solicite la reasignación en lugar de abrirlo directamente."
                )
            )
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
            "context": {
                "form_view_ref": "conedera_odoo_census.view_partner_form_census_mobile",
                "conedera_census_isolated_form": True,
            },
        }

    def _can_take_existing_partner(self, partner):
        partner = partner.sudo().commercial_partner_id
        if not partner.company_id or partner.company_id in self.env.user.company_ids:
            if not partner.user_id or partner.user_id == self.env.user:
                return True
            if is_census_manager(self.env.user):
                return True
            team = partner.census_team_id if partner.census_team_id and partner.census_team_id.census_enabled else partner._default_census_team(partner.user_id)
            return bool(is_census_supervisor(self.env.user) and team and team.user_id == self.env.user)
        return is_census_manager(self.env.user)

    def action_validate(self):
        self.ensure_one()
        query = (self.lookup_query or self.vat or self.customer_name or "").strip()
        if not query:
            raise ValidationError(_("Ingrese RUC, cédula o nombre antes de continuar."))

        candidates = self.search_global_candidates(query, limit=20)
        normalized = self._normalize_identity(query)
        exact = [
            c
            for c in candidates
            if (normalized and self._normalize_identity(c.get("vat")) == normalized)
            or ((c.get("name") or "").strip().lower() == query.lower())
        ]
        if len(exact) == 1:
            partner = self.env["res.partner"].sudo().browse(exact[0]["id"])
            self._set_selected_partner(partner)
            return self._reopen()
        if len(exact) > 1:
            self.validation_state = "multiple"
            self.validation_message = _(
                "Hay varias fichas que coinciden exactamente. Seleccione una en los resultados mostrados debajo del buscador."
            )
            return self._reopen()
        if candidates:
            self.validation_state = "multiple"
            self.validation_message = _(
                "Se encontraron clientes similares. Seleccione primero la ficha correcta; no se permite crear otro registro mientras existan coincidencias."
            )
            return self._reopen()

        self.validation_state = "not_found"
        self.validation_message = _("No se encontró un cliente. Complete los datos mínimos para crear una ficha nueva.")
        if self._looks_like_identity(query):
            self.vat = query
        elif not self.customer_name:
            self.customer_name = query
        return self._reopen()

    def action_use_selected(self):
        self.ensure_one()
        partner = self._selected_partner_sudo(validate_lookup=True)
        if not partner:
            raise UserError(_("Seleccione primero uno de los clientes encontrados."))

        # A globally existing census always wins, even if the selected Contact was a duplicate.
        identity = partner._census_primary_identity() or self.existing_vat or self.vat
        if identity:
            canonical = partner._census_global_active_by_identity(identity)
            if len(canonical) > 1:
                raise UserError(
                    _(
                        "Existen varios catastros activos con este RUC / cédula. "
                        "Un administrador debe depurar esos duplicados antes de continuar."
                    )
                )
            if canonical and canonical.id != partner.id:
                partner = canonical
                payload = self._set_selected_partner(partner)
                if not payload["can_open"]:
                    self.validation_state = "restricted"
                    self.validation_message = _(
                        "El RUC / cédula ya tiene un Catastro asignado a otro comercial. Solicite la reasignación; no se creará otro Catastro."
                    )
                    return self._reopen()

        payload = self._candidate_payload(partner)
        if partner.census_active:
            if not payload["can_open"]:
                self._set_selected_partner(partner)
                self.validation_state = "restricted"
                return self._reopen()
            return self._open_partner(partner)

        if not payload["can_use"]:
            self._set_selected_partner(partner)
            self.validation_state = "restricted"
            self.validation_message = _(
                "El cliente existe y está asignado a otro comercial. Solicite la asignación para reutilizar esta ficha; no cree otra."
            )
            return self._reopen()

        owner = partner.user_id or self.env.user
        team = partner._default_census_team(owner)
        vals = {
            "active": True,
            "census_active": True,
            "census_date": fields.Datetime.now(),
            "census_user_id": self.env.user.id,
            "user_id": owner.id,
            "census_locked": False,
            "customer_rank": max(partner.customer_rank, 1),
        }
        if team:
            vals["census_team_id"] = team.id
        # If the historic VAT lived on an invoice/contact child, copy it to the
        # commercial partner when activating the Catastro so the operational ficha
        # is complete and future lookups do not depend on the child record.
        if identity and not partner.vat:
            vals["vat"] = identity.strip()
        partner.sudo().write(vals)
        return self._open_partner(partner)

    # Compatibility alias used by older views/tests.
    def action_open_existing(self):
        return self.action_use_selected()

    def action_request_reassignment(self):
        self.ensure_one()
        reason = (self.reassignment_reason or "").strip()
        if not reason:
            raise ValidationError(_("Indique por qué necesita que este cliente sea reasignado."))
        partner = self._selected_partner_sudo(validate_lookup=True)
        if not partner:
            raise UserError(_("Seleccione primero el cliente que desea solicitar."))

        identity = partner._census_primary_identity()
        if identity:
            canonical = partner._census_global_active_by_identity(identity)
            if len(canonical) > 1:
                raise UserError(
                    _(
                        "Existen varios Catastros activos con esta identificación. "
                        "Un administrador debe depurarlos antes de tramitar una reasignación."
                    )
                )
            if canonical:
                partner = canonical

        payload = self._candidate_payload(partner)
        if payload["can_open"] or payload["can_use"]:
            raise UserError(_("Este cliente ya está disponible para usted; no necesita reasignación."))
        if payload["status"] == "company_restricted":
            raise AccessError(_("La reasignación entre compañías debe realizarla un administrador de Catastro."))

        request_type = "reassign_census" if partner.census_active else "claim_contact"
        self.env["conedera.census.reassignment.request"].create(
            {
                "partner_id": partner.id,
                "request_type": request_type,
                "requested_by_id": self.env.user.id,
                "reason": reason,
            }
        )
        self.validation_state = "request_sent"
        self.validation_message = _(
            "Solicitud enviada. El supervisor del comercial que actualmente tiene el cliente debe aprobarla. La ficha y todo su historial permanecen intactos."
        )
        return self._reopen()

    def action_create_new(self):
        self.ensure_one()
        if self.validation_state != "not_found":
            raise UserError(_("Primero confirme que el cliente no exista o seleccione una ficha existente."))
        vat = (self.vat or "").strip()
        name = (self.customer_name or "").strip()
        query = (self.lookup_query or "").strip()
        if not vat and self._looks_like_identity(query):
            vat = query
        if not name and query and not self._looks_like_identity(query):
            name = query
        if not vat and not name:
            raise ValidationError(_("Ingrese el RUC / cédula o el nombre del cliente."))

        Partner = self.env["res.partner"]
        if vat and Partner._census_global_partners_by_identity(vat):
            raise UserError(
                _(
                    "Ese RUC / cédula ya existe en Odoo. Vuelva a buscarlo y seleccione una ficha existente; no se permite crear un duplicado."
                )
            )
        if name:
            name_matches = Partner.sudo().with_context(active_test=False).search(
                [
                    ("parent_id", "=", False),
                    "|",
                    ("name", "=ilike", name),
                    ("commercial_name", "=ilike", name),
                ],
                limit=2,
            )
            if name_matches:
                raise UserError(
                    _(
                        "Ya existe un cliente con ese nombre o nombre comercial. "
                        "Búsquelo y seleccione la ficha existente antes de crear otra."
                    )
                )

        record_name = name or (_("BORRADOR - RUC %s") % vat)
        team = Partner._default_census_team(self.env.user)
        vals = {
            "name": record_name,
            "vat": vat or False,
            "census_active": True,
            "census_date": fields.Datetime.now(),
            "census_user_id": self.env.user.id,
            "census_locked": False,
            "company_type": "company",
            "customer_rank": 1,
            "user_id": self.env.user.id,
        }
        if team:
            vals["census_team_id"] = team.id
        partner = Partner.sudo().create(vals)
        return self._open_partner(partner)
