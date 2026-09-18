import re

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError

from .gps_utils import parse_gps_payload


class ResPartner(models.Model):
    _inherit = "res.partner"

    # Estado y auditoría del catastro
    census_active = fields.Boolean(string="Cliente catastrado", tracking=True)
    census_date = fields.Datetime(string="Fecha de catastro", readonly=True, copy=False)
    census_user_id = fields.Many2one(
        "res.users", string="Catastrado por", readonly=True, copy=False
    )
    census_team_id = fields.Many2one(
        "crm.team", string="Equipo comercial", tracking=True, copy=False, index=True,
        help="Equipo responsable del catastro. El líder del equipo actúa como supervisor.",
    )
    census_locked = fields.Boolean(
        string="Catastro registrado / bloqueado", default=False, copy=False, tracking=True
    )
    census_locked_at = fields.Datetime(string="Bloqueado el", readonly=True, copy=False)
    census_unlock_user_id = fields.Many2one(
        "res.users", string="Edición habilitada para", readonly=True, copy=False
    )
    census_unlock_until = fields.Datetime(
        string="Edición habilitada hasta", readonly=True, copy=False
    )
    census_can_edit_master = fields.Boolean(
        compute="_compute_census_edit_permissions", string="Puede editar el catastro"
    )
    census_edit_state = fields.Selection(
        [("draft", "Borrador"), ("locked", "Protegido"), ("enabled", "Edición habilitada")],
        compute="_compute_census_edit_permissions", string="Control de edición"
    )

    # Datos comerciales propios del catastro
    commercial_name = fields.Char(string="Nombre comercial / local")
    census_store_count = fields.Integer(
        string="Número de tiendas / locales",
        default=0,
        tracking=True,
        help="Ingrese la cantidad total de tiendas o locales del cliente. Debe ser mayor que cero para registrar visitas o crear proformas desde el catastro.",
    )
    owner_contact_name = fields.Char(string="Nombre del dueño")
    owner_phone = fields.Char(string="Teléfono del dueño")
    commercial_contact_name = fields.Char(string="Contacto comercial")
    commercial_contact_phone = fields.Char(string="Teléfono comercial (legado)")

    business_type_ids = fields.Many2many(
        "conedera.census.business.type",
        "conedera_partner_business_type_rel",
        "partner_id",
        "business_type_id",
        string="Tipos de negocio",
        tracking=True,
    )
    mobile_brand_ids = fields.Many2many(
        "conedera.census.mobile.brand",
        "conedera_partner_mobile_brand_rel",
        "partner_id",
        "brand_id",
        string="Marcas de celulares que maneja",
        tracking=True,
        help="Opcional. Seleccione una o varias marcas de celulares que comercializa o maneja el cliente.",
    )
    business_description = fields.Char(
        string="Especialidad / detalle",
        help="Detalle opcional para describir líneas de negocio no cubiertas por las etiquetas.",
    )
    customer_segment = fields.Selection(
        [
            ("wholesaler", "Mayorista"),
            ("reseller", "Revendedor / distribuidor"),
            ("retail", "Tienda al detalle"),
            ("mixed", "Mixto"),
            ("other", "Otro"),
        ],
        string="Canal comercial",
        tracking=True,
    )

    opening_hour_ids = fields.One2many(
        "conedera.partner.opening.hour",
        "partner_id",
        string="Horario de atención",
    )

    # Campos heredados de versiones anteriores. Se conservan para no romper datos existentes.
    business_type = fields.Selection(
        [
            ("cellphones", "Celulares"),
            ("accessories", "Accesorios"),
            ("mixed", "Mixto Cel/Acc."),
            ("commercial_house", "Casa comercial"),
            ("computing", "Cómputo"),
            ("other", "Otros"),
        ],
        string="Tipo de negocio (legado)",
    )
    customer_census_type = fields.Selection(
        [
            ("wholesaler", "Mayorista"),
            ("reseller", "Reseller"),
            ("route", "Ruteo"),
        ],
        string="Tipo de cliente (legado)",
    )
    capa = fields.Float(
        string="CAPA / Capacidad de compra",
        tracking=True,
        help="Monto estimado de capacidad de compra del cliente. Debe ser mayor que cero para habilitar visitas y proformas.",
    )

    # GPS del local
    census_gps_payload = fields.Char(string="Captura GPS", copy=False)
    census_gps_accuracy = fields.Float(string="Precisión GPS (m)", readonly=True, copy=False)
    census_gps_captured_at = fields.Datetime(
        string="GPS capturado el", readonly=True, copy=False
    )

    # Historial y métricas de UI
    census_visit_ids = fields.One2many(
        "conedera.census.visit", "partner_id", string="Visitas comerciales"
    )
    census_sale_order_ids = fields.One2many(
        "sale.order", "partner_id", string="Proformas / cotizaciones"
    )
    census_timeline_ids = fields.One2many(
        "conedera.census.commercial.timeline",
        "partner_id",
        string="Bitácora comercial",
    )
    census_product_summary_ids = fields.One2many(
        "conedera.census.product.quote.summary",
        "partner_id",
        string="Productos proformados",
    )
    census_visit_count = fields.Integer(compute="_compute_census_stats", string="Visitas")
    census_quotation_count = fields.Integer(compute="_compute_census_stats", string="Proformas")
    census_last_visit_datetime = fields.Datetime(
        compute="_compute_census_stats", string="Última visita"
    )
    census_completion_state = fields.Selection(
        [
            ("incomplete", "Faltan datos"),
            ("complete", "Datos completos"),
        ],
        compute="_compute_census_completion",
        string="Estado del catastro",
    )
    census_completion_pct = fields.Integer(
        compute="_compute_census_completion", string="Completitud"
    )
    census_ready_for_activity = fields.Boolean(
        compute="_compute_census_completion",
        string="Listo para visitas y proformas",
    )
    census_missing_requirements = fields.Char(
        compute="_compute_census_completion",
        string="Datos pendientes",
    )

    _CENSUS_MASTER_FIELDS = {
        "name", "vat", "commercial_name", "census_store_count", "owner_contact_name",
        "owner_phone", "commercial_contact_name", "phone", "mobile", "email",
        "street", "street2", "city", "state_id", "country_id", "zip",
        "business_type_ids", "mobile_brand_ids", "business_description",
        "customer_segment", "capa", "opening_hour_ids", "census_gps_payload", "partner_latitude",
        "partner_longitude", "company_id", "company_type", "parent_id",
    }
    _CENSUS_CONTROL_FIELDS = {
        "active", "census_active", "user_id", "census_team_id", "census_locked",
        "census_locked_at", "census_unlock_user_id", "census_unlock_until",
    }

    def _default_census_team(self, user=None):
        user = user or self.env.user
        team = user.sale_team_id
        if team and (not team.company_id or team.company_id in self.env.companies):
            return team
        return self.env["crm.team"].search([
            ("company_id", "in", [False] + self.env.companies.ids),
            "|", ("user_id", "=", user.id), ("member_ids", "in", [user.id]),
        ], limit=1)

    def _user_is_census_supervisor(self, user=None):
        self.ensure_one()
        user = user or self.env.user
        if user.has_group("sales_team.group_sale_manager"):
            return True
        # El líder del Equipo de Ventas es supervisor automáticamente.
        # No requiere un grupo adicional: reutilizamos la jerarquía estándar de Odoo.
        return bool(self.census_team_id and self.census_team_id.user_id == user)

    def _user_has_active_unlock(self, user=None):
        self.ensure_one()
        user = user or self.env.user
        return bool(
            self.census_unlock_user_id == user
            and self.census_unlock_until
            and self.census_unlock_until > fields.Datetime.now()
        )

    @api.depends("census_locked", "census_unlock_user_id", "census_unlock_until", "user_id", "census_team_id")
    @api.depends_context("uid")
    def _compute_census_edit_permissions(self):
        user = self.env.user
        for partner in self:
            if not partner.census_active:
                allowed = True
            elif partner._user_is_census_supervisor(user):
                allowed = True
            elif partner.user_id == user:
                allowed = (not partner.census_locked) or partner._user_has_active_unlock(user)
            else:
                allowed = False
            partner.census_can_edit_master = allowed
            if not partner.census_locked:
                partner.census_edit_state = "draft"
            elif partner._user_has_active_unlock(user):
                partner.census_edit_state = "enabled"
            else:
                partner.census_edit_state = "locked"

    def _check_census_master_write(self, vals):
        if self.env.su or self.env.context.get("census_system_write"):
            return
        if vals.get("census_active") and not self.env.user.has_group("sales_team.group_sale_manager"):
            raise AccessError(_("El Catastro debe activarse desde 'Nuevo catastro' para validar duplicados antes de crear o reutilizar una ficha."))
        touched = (set(vals) & self._CENSUS_MASTER_FIELDS) | (set(vals) & self._CENSUS_CONTROL_FIELDS)
        if not touched:
            return
        user = self.env.user
        for partner in self.filtered("census_active"):
            if partner._user_is_census_supervisor(user):
                continue
            # Los campos de control nunca los altera directamente el vendedor.
            if set(vals) & self._CENSUS_CONTROL_FIELDS:
                raise AccessError(_("La asignación, bloqueo y habilitación del catastro solo pueden gestionarlos un supervisor o administrador."))
            if partner.user_id != user:
                raise AccessError(_("Solo puede modificar catastros asignados a usted."))
            if partner.census_locked and not partner._user_has_active_unlock(user):
                raise AccessError(_("Este catastro está protegido. Solicite una habilitación de edición a su supervisor."))

    def action_register_census(self):
        self.ensure_one()
        if self.user_id != self.env.user and not self._user_is_census_supervisor():
            raise AccessError(_("Solo el comercial responsable, su supervisor o un administrador puede registrar este catastro."))
        missing = [label for label, ok in self._get_census_requirements() if not ok]
        if missing:
            raise UserError(_("Complete el catastro antes de registrarlo. Falta: %s") % ", ".join(missing))
        vals = {"census_locked": True, "census_locked_at": fields.Datetime.now()}
        if not self.census_team_id:
            team = self._default_census_team(self.user_id or self.env.user)
            if team:
                vals["census_team_id"] = team.id
        self.with_context(census_system_write=True).write(vals)
        return {"type": "ir.actions.client", "tag": "reload"}

    def action_request_census_unlock(self):
        self.ensure_one()
        if not self.census_locked:
            raise UserError(_("El catastro todavía está en borrador y no necesita habilitación."))
        if self.user_id != self.env.user:
            raise AccessError(_("Solo el comercial responsable puede solicitar habilitación."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Solicitar habilitación"),
            "res_model": "conedera.census.unlock.wizard",
            "view_mode": "form",
            "view_id": self.env.ref("conedera_odoo_census.view_census_unlock_wizard_form").id,
            "target": "new",
            "context": {"default_partner_id": self.id},
        }

    def action_finish_census_edit(self):
        self.ensure_one()
        if self.census_unlock_user_id != self.env.user and not self._user_is_census_supervisor():
            raise AccessError(_("No tiene una habilitación activa para cerrar."))
        now = fields.Datetime.now()
        self.env["conedera.census.unlock.request"].sudo().search([
            ("partner_id", "=", self.id),
            ("requested_by_id", "=", self.env.user.id),
            ("state", "=", "approved"),
        ], order="request_date desc, id desc", limit=1).write({"state": "expired", "valid_until": now})
        self.with_context(census_system_write=True).write({
            "census_unlock_user_id": False,
            "census_unlock_until": False,
        })
        return {"type": "ir.actions.client", "tag": "reload"}

    @api.depends("census_visit_ids.visit_datetime", "census_sale_order_ids")
    def _compute_census_stats(self):
        partner_ids = self.ids
        visit_counts = {partner_id: 0 for partner_id in partner_ids}
        quotation_counts = {partner_id: 0 for partner_id in partner_ids}
        last_visits = {partner_id: False for partner_id in partner_ids}

        if partner_ids:
            visits = self.env["conedera.census.visit"].search(
                [("partner_id", "in", partner_ids)], order="visit_datetime desc, id desc"
            )
            for visit in visits:
                partner_id = visit.partner_id.id
                visit_counts[partner_id] += 1
                if not last_visits[partner_id]:
                    last_visits[partner_id] = visit.visit_datetime

            commercial_ids = set(self.mapped("commercial_partner_id").ids)
            quotations = self.env["sale.order"].search(
                [("partner_id.commercial_partner_id", "in", list(commercial_ids))]
            )
            partner_by_commercial = {
                partner.commercial_partner_id.id: partner.id for partner in self
            }
            for quotation in quotations:
                target_id = partner_by_commercial.get(quotation.partner_id.commercial_partner_id.id)
                if target_id:
                    quotation_counts[target_id] += 1

        for partner in self:
            partner.census_visit_count = visit_counts.get(partner.id, 0)
            partner.census_quotation_count = quotation_counts.get(partner.id, 0)
            partner.census_last_visit_datetime = last_visits.get(partner.id, False)

    @api.depends(
        "name",
        "vat",
        "commercial_name",
        "census_store_count",
        "business_type_ids",
        "customer_segment",
        "capa",
        "owner_contact_name",
        "owner_phone",
        "commercial_contact_name",
        "phone",
        "mobile",
        "email",
        "street",
        "city",
        "opening_hour_ids",
        "opening_hour_ids.day_of_week",
        "opening_hour_ids.opening_time",
        "opening_hour_ids.closing_time",
    )
    def _compute_census_completion(self):
        for partner in self:
            requirements = partner._get_census_requirements()
            completed = sum(1 for _label, ok in requirements if ok)
            total = len(requirements) or 1
            missing = [label for label, ok in requirements if not ok]
            partner.census_completion_pct = round(completed * 100 / total)
            partner.census_ready_for_activity = not missing
            partner.census_missing_requirements = ", ".join(missing)
            partner.census_completion_state = "complete" if not missing else "incomplete"

    def _get_census_requirements(self):
        """Return the operational requirements for this customer's census.

        GPS is intentionally NOT part of this list while the deployment does not
        have HTTPS. The customer can therefore be fully operational without a GPS
        capture, while the location fields remain available for later use.
        """
        self.ensure_one()
        return [
            (_("Razón social / cliente"), bool((self.name or "").strip()) and not (self.name or "").startswith("BORRADOR - RUC ")),
            (_("RUC"), bool((self.vat or "").strip())),
            (_("Nombre comercial / local"), bool((self.commercial_name or "").strip())),
            (_("Número de tiendas / locales"), self.census_store_count > 0),
            (_("Tipo(s) de negocio"), bool(self.business_type_ids)),
            (_("Canal comercial"), bool(self.customer_segment)),
            (_("CAPA / Capacidad de compra"), self.capa > 0),
            (_("Nombre del dueño"), bool((self.owner_contact_name or "").strip())),
            (_("Teléfono del dueño"), bool((self.owner_phone or "").strip())),
            (_("Contacto comercial"), bool((self.commercial_contact_name or "").strip())),
            (_("Teléfono o móvil del contacto"), bool((self.phone or "").strip() or (self.mobile or "").strip())),
            (_("Email"), bool((self.email or "").strip())),
            (_("Dirección"), bool((self.street or "").strip())),
            (_("Ciudad"), bool((self.city or "").strip())),
            (_("Horario de atención"), bool(self.opening_hour_ids)),
        ]

    def _ensure_census_ready_for_activity(self):
        for partner in self:
            missing = [label for label, ok in partner._get_census_requirements() if not ok]
            if missing:
                raise UserError(
                    _(
                        "Complete el catastro antes de registrar visitas o crear proformas. "
                        "Falta: %(missing)s. La ubicación GPS es opcional por ahora."
                    )
                    % {"missing": ", ".join(missing)}
                )
            if not partner.census_locked:
                raise UserError(_("El catastro está completo pero todavía no ha sido registrado. Use 'Registrar catastro' para proteger la ficha antes de operar."))
        return True

    @api.constrains("census_store_count", "capa")
    def _check_census_store_count(self):
        """Allow an incomplete draft, but never accept a negative store count."""
        for partner in self:
            if partner.census_store_count < 0:
                raise ValidationError(_("El número de tiendas / locales no puede ser negativo."))
            if partner.capa < 0:
                raise ValidationError(_("La CAPA / capacidad de compra no puede ser negativa."))

    @api.constrains("vat", "name", "commercial_name", "census_active", "parent_id")
    def _check_unique_census_identity(self):
        """Evita una segunda ficha para el mismo cliente.

        - Con RUC: no puede existir un segundo CATastro activo con el mismo RUC.
          Pueden existir contactos históricos duplicados en Odoo; el asistente obliga
          a seleccionar cuál será la ficha canónica antes de activar el Catastro.
        - Sin RUC: mientras el catastro está en borrador, bloqueamos otro catastro
          con el mismo nombre exacto para obligar a identificarlo antes de duplicar.
        """
        for partner in self:
            if not partner.census_active or partner.parent_id:
                continue
            vat = (partner.vat or "").strip()
            if vat:
                normalized = re.sub(r"[^0-9A-Za-z]", "", vat).upper()
                self.env.cr.execute(
                    """
                    SELECT id
                      FROM res_partner
                     WHERE id != %s
                       AND parent_id IS NULL
                       AND vat IS NOT NULL
                       AND COALESCE(census_active, FALSE) IS TRUE
                       AND regexp_replace(upper(vat), '[^0-9A-Z]', '', 'g') = %s
                     LIMIT 1
                    """,
                    [partner.id, normalized],
                )
                duplicate_id = self.env.cr.fetchone()
                duplicate = (
                    self.with_context(active_test=False).browse(duplicate_id[0]).exists()
                    if duplicate_id
                    else self.browse()
                )
                if duplicate:
                    raise ValidationError(
                        _(
                            "El RUC / cédula %(vat)s ya pertenece a %(partner)s. "
                            "No cree otro cliente: use la ficha existente desde Nuevo catastro."
                        )
                        % {"vat": vat, "partner": duplicate.display_name}
                    )
            else:
                name = (partner.name or "").strip()
                if name and not name.startswith("BORRADOR - RUC "):
                    duplicate = self.with_context(active_test=False).search(
                        [
                            ("id", "!=", partner.id),
                            ("parent_id", "=", False),
                            ("census_active", "=", True),
                            ("name", "=ilike", name),
                        ],
                        limit=1,
                    )
                    if duplicate:
                        raise ValidationError(
                            _(
                                "Ya existe un catastro con el nombre %(name)s. "
                                "Ingrese el RUC para diferenciar clientes o abra la ficha existente."
                            )
                            % {"name": name}
                        )

    def copy(self, default=None):
        self.ensure_one()
        if self.census_active:
            raise UserError(
                _(
                    "El catastro es una ficha única por cliente y no se puede duplicar. "
                    "Registre nuevas visitas o proformas dentro de esta misma ficha."
                )
            )
        return super().copy(default=default)

    def unlink(self):
        if any(partner.census_active for partner in self) and not self.env.user.has_group("sales_team.group_sale_manager"):
            raise UserError(_("Los catastros no pueden eliminarse por comerciales ni supervisores. Solo un administrador de Ventas puede hacerlo."))
        return super().unlink()

    @api.onchange("census_gps_payload")
    def _onchange_census_gps_payload(self):
        for partner in self:
            parsed = parse_gps_payload(partner.census_gps_payload)
            if parsed:
                latitude, longitude, accuracy = parsed
                partner.partner_latitude = latitude
                partner.partner_longitude = longitude
                partner.census_gps_accuracy = accuracy
                partner.census_gps_captured_at = fields.Datetime.now()

    @api.model_create_multi
    def create(self, vals_list):
        if (
            any(vals.get("census_active") for vals in vals_list)
            and not self.env.context.get("census_system_write")
            and not self.env.user.has_group("sales_team.group_sale_manager")
        ):
            raise AccessError(_("Cree el Catastro desde 'Nuevo catastro' para buscar primero por RUC, cédula o nombre."))
        now = fields.Datetime.now()
        for vals in vals_list:
            parsed = parse_gps_payload(vals.get("census_gps_payload"))
            if parsed:
                latitude, longitude, accuracy = parsed
                vals.update(
                    {
                        "partner_latitude": latitude,
                        "partner_longitude": longitude,
                        "census_gps_accuracy": accuracy,
                        "census_gps_captured_at": now,
                    }
                )
            if vals.get("census_active"):
                vals.setdefault("census_date", now)
                vals.setdefault("census_user_id", self.env.user.id)
                vals.setdefault("customer_rank", 1)
                vals.setdefault("user_id", self.env.user.id)
                if not vals.get("census_team_id"):
                    user = self.env["res.users"].browse(vals.get("user_id") or self.env.user.id)
                    team = self._default_census_team(user)
                    if team:
                        vals["census_team_id"] = team.id
        return super().create(vals_list)

    def write(self, vals):
        vals = dict(vals)
        self._check_census_master_write(vals)
        if vals.get("user_id") and not vals.get("census_team_id") and (self.env.context.get("census_system_write") or self.env.user.has_group("sales_team.group_sale_manager")):
            user = self.env["res.users"].browse(vals["user_id"])
            team = self._default_census_team(user)
            if team:
                vals["census_team_id"] = team.id
        parsed = parse_gps_payload(vals.get("census_gps_payload"))
        if parsed:
            latitude, longitude, accuracy = parsed
            vals.update(
                {
                    "partner_latitude": latitude,
                    "partner_longitude": longitude,
                    "census_gps_accuracy": accuracy,
                    "census_gps_captured_at": fields.Datetime.now(),
                }
            )
        if vals.get("census_active"):
            vals.setdefault("census_date", fields.Datetime.now())
            vals.setdefault("census_user_id", self.env.user.id)
        return super().write(vals)

    def action_open_census_location(self):
        self.ensure_one()
        if not self.census_gps_captured_at:
            raise ValidationError(_("El cliente no tiene una ubicación GPS de catastro capturada."))
        url = (
            "https://www.openstreetmap.org/?mlat=%s&mlon=%s#map=18/%s/%s"
            % (
                self.partner_latitude,
                self.partner_longitude,
                self.partner_latitude,
                self.partner_longitude,
            )
        )
        return {"type": "ir.actions.act_url", "url": url, "target": "new"}

    def action_new_census_visit(self):
        self.ensure_one()
        self._ensure_census_ready_for_activity()
        return {
            "type": "ir.actions.act_window",
            "name": _("Nueva visita"),
            "res_model": "conedera.census.visit",
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_partner_id": self.id,
                "default_user_id": self.env.user.id,
                "default_company_id": self.env.company.id,
            },
        }

    def action_view_census_visits(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("conedera_odoo_census.action_census_visit")
        action["domain"] = [("partner_id.commercial_partner_id", "=", self.commercial_partner_id.id)]
        action["context"] = {
            "default_partner_id": self.id,
            "default_user_id": self.env.user.id,
            "default_company_id": self.env.company.id,
        }
        return action

    def action_view_census_quotations(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("sale.action_quotations_with_onboarding")
        action["domain"] = [("partner_id.commercial_partner_id", "=", self.commercial_partner_id.id)]
        action["context"] = {
            "default_partner_id": self.id,
            "default_user_id": self.env.user.id,
            "default_census_originated": True,
            "default_company_id": self.env.company.id,
        }
        return action

    def action_view_census_timeline(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "conedera_odoo_census.action_census_commercial_timeline"
        )
        action["domain"] = [("partner_id", "=", self.commercial_partner_id.id)]
        action["name"] = _("Bitácora - %s") % self.display_name
        return action

    def action_view_census_product_summary(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "conedera_odoo_census.action_census_product_quote_summary"
        )
        action["domain"] = [("partner_id", "=", self.commercial_partner_id.id)]
        action["name"] = _("Productos proformados - %s") % self.display_name
        return action

    def action_new_census_quotation(self):
        self.ensure_one()
        self._ensure_census_ready_for_activity()
        return {
            "type": "ir.actions.act_window",
            "name": _("Nueva proforma"),
            "res_model": "sale.order",
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_partner_id": self.id,
                "default_user_id": self.env.user.id,
                "default_company_id": self.env.company.id,
                "default_origin": _("Catastro - %s") % self.display_name,
                "default_census_originated": True,
            },
        }
