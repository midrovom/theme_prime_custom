import re

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError

from .gps_utils import parse_gps_payload
from .census_security_utils import is_census_manager, is_census_supervisor, is_census_user


class ResPartner(models.Model):
    _inherit = "res.partner"

    # Estado y auditoría del catastro
    census_active = fields.Boolean(string="Cliente catastrado", tracking=True)
    census_date = fields.Datetime(string="Fecha de catastro", readonly=True, copy=False)
    census_user_id = fields.Many2one(
        "res.users", string="Catastrado por", readonly=True, copy=False
    )
    census_team_id = fields.Many2one(
        "crm.team", string="Equipo comercial", tracking=True, copy=False, index=True, check_company=True,
        domain=[("census_enabled", "=", True)],
        help="Equipo responsable del catastro. Solo se permiten equipos habilitados para Catastro.",
    )
    census_allowed_team_ids = fields.Many2many(
        "crm.team",
        compute="_compute_census_allowed_team_ids",
        string="Equipos comerciales permitidos",
        help="Equipos válidos para el vendedor responsable. Se usa únicamente para filtrar la selección en la ficha de Catastro.",
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
    census_reassignment_ids = fields.One2many(
        "conedera.census.reassignment.request",
        "partner_id",
        string="Reasignaciones",
    )
    census_reassignment_count = fields.Integer(
        compute="_compute_census_reassignment_count", string="Reasignaciones"
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
        "business_type", "customer_census_type", "commercial_contact_phone",
        "customer_segment", "capa", "opening_hour_ids", "census_gps_payload", "partner_latitude",
        "partner_longitude", "company_id", "company_type", "parent_id",
    }
    _CENSUS_CONTROL_FIELDS = {
        "active", "census_active", "user_id", "census_team_id", "census_locked",
        "census_date", "census_user_id", "census_locked_at",
        "census_unlock_user_id", "census_unlock_until",
        "census_gps_accuracy", "census_gps_captured_at",
    }
    _CENSUS_ASSIGNMENT_FIELDS = {"user_id", "census_team_id"}

    @api.model
    def _census_normalize_identity(self, value):
        return re.sub(r"[^0-9A-Za-z]", "", value or "").upper()

    @api.model
    def _census_lock_identity(self, value):
        """Serialize writes for the same normalized identity inside PostgreSQL.

        The Python constraint remains the user-friendly validation, while this
        transaction-scoped advisory lock closes the race where two salespeople
        could try to activate the same RUC/cédula at the same instant.
        """
        normalized = self._census_normalize_identity(value)
        if normalized:
            self.env.cr.execute(
                "SELECT pg_advisory_xact_lock(hashtext(%s))",
                ["conedera.census.identity:" + normalized],
            )
        return normalized

    def _census_primary_identity(self):
        """Return the identity displayed/used by the commercial customer.

        Historic Odoo databases sometimes keep the VAT on a child invoice/contact
        record.  The Catastro is always anchored on commercial_partner_id, so we
        use the parent's VAT first and then a child's VAT as a safe compatibility
        fallback.
        """
        self.ensure_one()
        partner = self.sudo().commercial_partner_id
        if partner.vat:
            return partner.vat
        child = partner.child_ids.filtered(lambda c: bool((c.vat or "").strip())).sorted("id")[:1]
        return child.vat if child else False

    @api.model
    def _census_global_partners_by_identity(self, value, active_only=False):
        """Global lookup used only to protect the unique-census invariant.

        This intentionally bypasses record rules for existence checks. Callers must
        not expose restricted commercial information to unauthorized users.
        """
        normalized = self._census_normalize_identity(value)
        if not normalized:
            return self.sudo().browse()
        # Do not filter census_active on the row that carries the VAT. In Odoo it is
        # common for an identification to be stored on a child contact/address while
        # the Catastro belongs to its commercial parent. We first resolve every VAT
        # match to commercial_partner_id and only then apply the active-Catastro filter.
        clauses = [
            "vat IS NOT NULL",
            "regexp_replace(upper(vat), '[^0-9A-Z]', '', 'g') = %s",
        ]
        self.env.cr.execute(
            "SELECT id FROM res_partner WHERE %s ORDER BY active DESC, parent_id NULLS FIRST, id"
            % " AND ".join(clauses),
            [normalized],
        )
        ids = [row[0] for row in self.env.cr.fetchall()]
        records = self.sudo().with_context(active_test=False).browse(ids).exists()
        result = self.sudo().browse()
        seen = set()
        for partner in records.mapped("commercial_partner_id"):
            if active_only and not partner.census_active:
                continue
            if partner.id not in seen:
                result |= partner
                seen.add(partner.id)
        return result

    @api.model
    def _census_global_active_by_identity(self, value):
        return self._census_global_partners_by_identity(value, active_only=True).filtered("census_active")

    def _default_census_team(self, user=None):
        """Return a real sales team enabled for Catastro.

        Odoo ships technical teams such as Website/POS. They are valid ``crm.team``
        records but are not appropriate for this workflow and may not define the sales
        dashboard graph outside the Sales context. Never auto-assign them here.
        """
        user = user or self.env.user
        team = user.sale_team_id
        if (
            team
            and team.census_enabled
            and team.active
            and (not team.company_id or team.company_id in self.env.companies)
            and (team.user_id == user or user in team.member_ids)
        ):
            return team
        return self.env["crm.team"].search([
            ("census_enabled", "=", True),
            ("active", "=", True),
            ("company_id", "in", [False] + self.env.companies.ids),
            "|", ("user_id", "=", user.id), ("member_ids", "in", [user.id]),
        ], limit=1)

    @api.depends("user_id")
    @api.depends_context("uid", "allowed_company_ids")
    def _compute_census_allowed_team_ids(self):
        """Teams that may be selected from the mobile Catastro form.

        The list is intentionally calculated without opening the standard Sales Team
        dashboard.  This keeps technical teams such as Website/POS out of the selector
        and avoids the ``Undefined graph model`` error raised by those dashboard-only
        teams in Odoo Community.
        """
        Team = self.env["crm.team"].sudo().with_context(active_test=True)
        technical_ids = Team._census_technical_team_ids() if hasattr(Team, "_census_technical_team_ids") else set()
        allowed_company_ids = self.env.companies.ids
        for partner in self:
            salesperson = partner.user_id or self.env.user
            domain = [
                ("census_enabled", "=", True),
                ("active", "=", True),
                ("company_id", "in", [False] + allowed_company_ids),
            ]
            if salesperson:
                domain += ["|", ("user_id", "=", salesperson.id), ("member_ids", "in", [salesperson.id])]
            teams = Team.search(domain)
            if technical_ids:
                teams = teams.filtered(lambda team: team.id not in technical_ids)
            partner.census_allowed_team_ids = teams

    def _validate_census_team_assignment(self, team, salesperson=None):
        """Validate a Catastro team without invoking the Sales Team dashboard."""
        self.ensure_one()
        salesperson = salesperson or self.user_id or self.env.user
        if not team:
            raise UserError(_("Seleccione un Equipo comercial para registrar el Catastro."))
        technical_ids = team._census_technical_team_ids() if hasattr(team, "_census_technical_team_ids") else set()
        if team.id in technical_ids or not team.census_enabled or not team.active:
            raise UserError(
                _("El equipo '%s' no está habilitado para Catastro Comercial. Seleccione un equipo comercial válido.")
                % team.display_name
            )
        if team.company_id and team.company_id not in self.env.companies:
            raise AccessError(_("El Equipo comercial pertenece a una compañía no permitida para su sesión."))
        if salesperson and salesperson != team.user_id and salesperson not in team.member_ids:
            raise UserError(
                _("El vendedor %(seller)s no pertenece al Equipo comercial %(team)s. Agréguelo como miembro o seleccione otro equipo.")
                % {"seller": salesperson.display_name, "team": team.display_name}
            )
        return True

    def _census_internal_control_update(self, values):
        """Update only Conedera lifecycle columns without calling third-party partner hooks.

        Some deployments extend ``res.partner.write`` with route/field-service logic and
        require permissions on unrelated models (for example ``route.sale.visit``).
        Registering or closing the Catastro must not require those optional modules.
        We therefore update our own control columns directly and invalidate the ORM cache.
        No customer master data is written through this helper.
        """
        allowed = {
            "census_team_id", "census_locked", "census_locked_at",
            "census_unlock_user_id", "census_unlock_until",
        }
        unexpected = set(values) - allowed
        if unexpected:
            raise UserError(_("Actualización interna no permitida: %s") % ", ".join(sorted(unexpected)))
        if not self:
            return True
        columns = []
        params = []
        for field_name, value in values.items():
            field = self._fields[field_name]
            columns.append(f'"{field_name}" = %s')
            if field.type == "many2one":
                value = value.id if hasattr(value, "id") else value
                params.append(value or None)
            else:
                params.append(value)
        columns.extend(['"write_uid" = %s', '"write_date" = NOW()'])
        params.append(self.env.uid)
        params.append(tuple(self.ids))
        self.env.cr.execute(
            "UPDATE res_partner SET %s WHERE id IN %%s" % ", ".join(columns),
            params,
        )
        field_names = list(values) + ["write_uid", "write_date"]
        self.invalidate_recordset(field_names)
        self.modified(list(values))
        return True

    def _action_open_census_form(self):
        """Reopen the isolated Catastro form explicitly.

        Returning a generic ``reload`` may let another addon replace/extend the current
        ``res.partner`` form.  In databases with a route-sales addon this can trigger
        access checks on ``route.sale.visit``.  Always reopen our standalone form instead.
        """
        self.ensure_one()
        view = self.env.ref("conedera_odoo_census.view_partner_form_census_mobile")
        return {
            "type": "ir.actions.act_window",
            "name": _("Catastro - %s") % (self.commercial_name or self.display_name),
            "res_model": "res.partner",
            "res_id": self.id,
            "view_mode": "form",
            "views": [(view.id, "form")],
            "view_id": view.id,
            "target": "current",
            "context": {
                "form_view_ref": "conedera_odoo_census.view_partner_form_census_mobile",
                "conedera_census_isolated_form": True,
            },
        }

    def _user_is_census_supervisor(self, user=None):
        self.ensure_one()
        user = user or self.env.user
        if is_census_manager(user):
            return True
        # El líder del Equipo de Ventas es supervisor automáticamente.
        # No requiere un grupo adicional: reutilizamos la jerarquía estándar de Odoo.
        return bool(
            is_census_supervisor(user)
            and self.census_team_id
            and self.census_team_id.user_id == user
        )

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
        if self.env.su:
            return
        if vals.get("census_active") and not is_census_manager(self.env.user):
            raise AccessError(_("El Catastro debe activarse desde 'Nuevo catastro' para validar duplicados antes de crear o reutilizar una ficha."))
        touched = (set(vals) & self._CENSUS_MASTER_FIELDS) | (set(vals) & self._CENSUS_CONTROL_FIELDS)
        if not touched:
            return

        user = self.env.user
        is_sales_admin = is_census_manager(user)
        for partner in self.filtered("census_active"):
            # Vendedor/equipo are assignment fields.  The salesperson can choose a
            # valid team while the Catastro is still a draft, but after registration
            # team changes must go through reassignment (or a Catastro administrator).
            if "user_id" in vals and not is_sales_admin:
                raise AccessError(
                    _("El vendedor responsable solo puede cambiarse mediante una Solicitud de reasignación.")
                )
            if "census_team_id" in vals and not is_sales_admin:
                if partner.census_locked:
                    raise AccessError(
                        _("El Equipo comercial de un Catastro protegido solo puede cambiarse mediante una Solicitud de reasignación.")
                    )
                if partner.user_id != user and not partner._user_is_census_supervisor(user):
                    raise AccessError(_("Solo el responsable o su supervisor puede seleccionar el Equipo comercial del borrador."))
                team = self.env["crm.team"].browse(vals.get("census_team_id")) if vals.get("census_team_id") else self.env["crm.team"]
                if team:
                    partner._validate_census_team_assignment(team, partner.user_id or user)

            other_control_fields = self._CENSUS_CONTROL_FIELDS - {"census_team_id", "user_id"}
            if set(vals) & other_control_fields and not is_sales_admin:
                raise AccessError(
                    _(
                        "Los campos de control del Catastro (activar, archivar o bloquear) "
                        "solo se modifican mediante los flujos auditados. Un administrador "
                        "de Catastro puede forzarlos directamente."
                    )
                )

            if partner._user_is_census_supervisor(user):
                continue
            if partner.user_id != user:
                raise AccessError(_("Solo puede modificar catastros asignados a usted."))
            if partner.census_locked and not partner._user_has_active_unlock(user):
                raise AccessError(_("Este catastro está protegido. Solicite una habilitación de edición a su supervisor."))

    def action_register_census(self):
        self.ensure_one()
        user = self.env.user
        if not is_census_user(user):
            raise AccessError(_("Su usuario no tiene un rol de Catastro Comercial asignado."))
        if self.user_id != user and not self._user_is_census_supervisor(user):
            raise AccessError(_("Solo el comercial responsable, su supervisor o un administrador de Catastro puede registrar esta ficha."))
        missing = [label for label, ok in self._get_census_requirements() if not ok]
        if missing:
            raise UserError(_("Complete el catastro antes de registrarlo. Falta: %s") % ", ".join(missing))

        team = self.census_team_id or self._default_census_team(self.user_id or user)
        if not team or not team.census_enabled:
            raise UserError(
                _(
                    "No hay un Equipo comercial válido para este Catastro. "
                    "Un administrador debe asignar un equipo marcado como 'Disponible para Catastro' "
                    "y configurar su líder/miembros antes de registrar la ficha."
                )
            )
        self._validate_census_team_assignment(team, self.user_id or user)

        # Only our lifecycle columns are changed here.  Avoid third-party
        # res.partner.write hooks (e.g. route-sales addons) and reopen the dedicated
        # Catastro form explicitly instead of a generic reload.
        self._census_internal_control_update({
            "census_team_id": team.id,
            "census_locked": True,
            "census_locked_at": fields.Datetime.now(),
        })
        return self._action_open_census_form()

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
        self._census_internal_control_update({
            "census_unlock_user_id": False,
            "census_unlock_until": False,
        })
        return self._action_open_census_form()

    def _compute_census_reassignment_count(self):
        for partner in self:
            partner.census_reassignment_count = self.env["conedera.census.reassignment.request"].search_count(
                [("partner_id", "=", partner.id)]
            )

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
                raise UserError(_("El catastro está completo pero todavía no ha sido registrado. Use 'Registrar y proteger' para proteger la ficha antes de operar."))
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
        """Guarantee one active Catastro per normalized identity.

        The check also runs when a VAT is stored on a child contact of a catastrated
        commercial partner, because global lookup intentionally treats that VAT as an
        identity of the commercial customer.
        """
        checked_parents = self.env["res.partner"]
        for record in self:
            parent = record.sudo().commercial_partner_id
            if not parent.census_active or parent.parent_id:
                continue

            # If this exact record carries a VAT, validate that identity.  Otherwise
            # validate the commercial parent's primary identity (which may live on a
            # historic child contact).
            identity = record.vat or parent._census_primary_identity()
            if identity:
                duplicates = parent._census_global_active_by_identity(identity).filtered(
                    lambda p: p.id != parent.id
                )
                if duplicates:
                    duplicate = duplicates[0].sudo()
                    raise ValidationError(
                        _(
                            "El RUC / cédula %(vat)s ya pertenece al catastro %(partner)s. "
                            "No cree otro cliente: use 'Nuevo catastro' y solicite reasignación "
                            "si pertenece a otro comercial."
                        )
                        % {"vat": identity, "partner": duplicate.display_name}
                    )

            if parent not in checked_parents:
                checked_parents |= parent
                if not parent._census_primary_identity():
                    name = (parent.name or "").strip()
                    if name and not name.startswith("BORRADOR - RUC "):
                        duplicate = self.sudo().with_context(active_test=False).search(
                            [
                                ("id", "!=", parent.id),
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
        if any(partner.census_active for partner in self) and not is_census_manager(self.env.user):
            raise UserError(_("Los catastros no pueden eliminarse por comerciales ni supervisores. Solo un administrador de Catastro puede hacerlo."))
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
            and not self.env.su
            and not is_census_manager(self.env.user)
        ):
            raise AccessError(_("Cree el Catastro desde 'Nuevo catastro' para buscar primero por RUC, cédula o nombre."))
        # Serialize simultaneous attempts for the same RUC/cédula before INSERT.
        for vals in vals_list:
            if vals.get("census_active") and vals.get("vat"):
                self._census_lock_identity(vals.get("vat"))
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
        # Lock the target identity before the write/constraint sequence.  This closes
        # concurrent duplicate activation or VAT changes across users/workers.
        if vals.get("vat"):
            for record in self:
                parent = record.sudo().commercial_partner_id
                if vals.get("census_active") or parent.census_active:
                    self._census_lock_identity(vals.get("vat"))
        elif vals.get("census_active"):
            for record in self:
                identity = record.sudo().commercial_partner_id._census_primary_identity()
                if identity:
                    self._census_lock_identity(identity)
        self._check_census_master_write(vals)
        if vals.get("user_id") and not vals.get("census_team_id") and (self.env.su or is_census_manager(self.env.user)):
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

    def action_view_census_reassignments(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "conedera_odoo_census.action_census_reassignment_requests"
        )
        action["domain"] = [("partner_id", "=", self.id)]
        action["name"] = _("Reasignaciones - %s") % self.display_name
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
