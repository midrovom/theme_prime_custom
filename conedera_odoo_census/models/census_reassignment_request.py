from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError

from .census_security_utils import is_census_manager, is_census_supervisor


class CensusReassignmentRequest(models.Model):
    _name = "conedera.census.reassignment.request"
    _description = "Solicitud de reasignación de Catastro"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "request_date desc, id desc"

    partner_id = fields.Many2one(
        "res.partner",
        string="Cliente / Catastro",
        required=True,
        ondelete="restrict",
        index=True,
        tracking=True,
    )
    request_type = fields.Selection(
        [
            ("reassign_census", "Reasignar catastro existente"),
            ("claim_contact", "Asignar contacto existente al catastro"),
        ],
        string="Tipo",
        required=True,
        default="reassign_census",
        readonly=True,
        tracking=True,
    )
    requested_by_id = fields.Many2one(
        "res.users",
        string="Solicitado por",
        required=True,
        default=lambda self: self.env.user,
        readonly=True,
        tracking=True,
    )
    target_team_id = fields.Many2one(
        "crm.team",
        string="Equipo destino",
        readonly=True,
        tracking=True,
    )
    source_user_id = fields.Many2one(
        "res.users",
        string="Comercial actual",
        readonly=True,
        tracking=True,
    )
    source_team_id = fields.Many2one(
        "crm.team",
        string="Equipo actual",
        readonly=True,
        tracking=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        readonly=True,
        index=True,
    )
    partner_name_snapshot = fields.Char(string="Cliente", readonly=True)
    partner_vat_snapshot = fields.Char(string="RUC / Cédula", readonly=True)
    reason = fields.Text(string="Motivo", required=True, tracking=True)
    request_date = fields.Datetime(
        string="Solicitado el", required=True, default=fields.Datetime.now, readonly=True
    )
    state = fields.Selection(
        [
            ("pending", "Pendiente"),
            ("approved", "Aprobada"),
            ("rejected", "Rechazada"),
            ("cancelled", "Cancelada"),
        ],
        string="Estado",
        required=True,
        default="pending",
        readonly=True,
        index=True,
        tracking=True,
    )
    reviewed_by_id = fields.Many2one("res.users", string="Revisado por", readonly=True)
    reviewed_at = fields.Datetime(string="Revisado el", readonly=True)
    review_note = fields.Text(string="Observación del supervisor", readonly=True)
    can_review = fields.Boolean(compute="_compute_can_review", string="Puede revisar")
    can_cancel = fields.Boolean(compute="_compute_can_cancel", string="Puede cancelar")

    @api.depends_context("uid")
    def _compute_can_cancel(self):
        user = self.env.user
        is_admin = is_census_manager(user)
        for request in self:
            request.can_cancel = bool(request.state == "pending" and (is_admin or request.requested_by_id == user))

    @api.depends("source_team_id", "source_team_id.user_id")
    @api.depends_context("uid")
    def _compute_can_review(self):
        user = self.env.user
        is_admin = is_census_manager(user)
        for request in self:
            request.can_review = bool(
                is_admin
                or (is_census_supervisor(user) and request.source_team_id and request.source_team_id.user_id == user)
            )

    def _check_can_review(self):
        for request in self:
            if not request.can_review:
                raise AccessError(
                    _(
                        "Solo el líder del equipo comercial que actualmente tiene el cliente, "
                        "o un administrador de Catastro, puede aprobar o rechazar esta reasignación."
                    )
                )

    @api.model_create_multi
    def create(self, vals_list):
        Partner = self.env["res.partner"].sudo().with_context(active_test=False)
        for vals in vals_list:
            partner = Partner.browse(vals.get("partner_id")).exists()
            if not partner:
                raise ValidationError(_("El cliente indicado ya no existe."))
            partner = partner.commercial_partner_id
            requester = self.env.user
            if vals.get("requested_by_id") and is_census_manager(self.env.user):
                requester = self.env["res.users"].browse(vals["requested_by_id"]).exists() or self.env.user
            elif not self.env.su:
                vals["requested_by_id"] = requester.id

            target_team = partner._default_census_team(requester)
            source_team = partner.census_team_id or partner.user_id.sale_team_id
            effective_company = partner.census_company_id or source_team.company_id or target_team.company_id or self.env.company
            if (
                effective_company
                and effective_company not in requester.company_ids
                and not is_census_manager(requester)
            ):
                raise AccessError(_("La reasignación entre compañías debe realizarla un administrador de Catastro."))
            if not target_team and not is_census_manager(requester):
                raise ValidationError(
                    _(
                        "No se encontró un Equipo de Ventas para el comercial solicitante. "
                        "Configure su equipo antes de solicitar una reasignación."
                    )
                )
            if not requester.active:
                raise ValidationError(_("No se puede solicitar una reasignación hacia un usuario archivado."))
            if partner.census_active and partner.user_id == requester and not is_census_manager(self.env.user):
                raise UserError(_("Este Catastro ya está asignado a usted; no necesita solicitar una reasignación."))

            request_type = vals.get("request_type") or (
                "reassign_census" if partner.census_active else "claim_contact"
            )
            if request_type == "reassign_census" and not partner.census_active:
                request_type = "claim_contact"
            vals.update(
                {
                    "partner_id": partner.id,
                    "request_type": request_type,
                    "target_team_id": target_team.id if target_team else False,
                    "source_user_id": partner.user_id.id or False,
                    "source_team_id": source_team.id or False,
                    "company_id": effective_company.id,
                    "partner_name_snapshot": partner.display_name,
                    "partner_vat_snapshot": partner._census_primary_identity() or False,
                    "state": "pending",
                }
            )

            existing = self.sudo().search(
                [
                    ("partner_id", "=", partner.id),
                    ("requested_by_id", "=", requester.id),
                    ("state", "=", "pending"),
                ],
                limit=1,
            )
            if existing:
                raise UserError(_("Ya existe una solicitud de reasignación pendiente para este cliente."))

        requests = super().create(vals_list)
        for request in requests:
            supervisor = request.source_team_id.user_id
            if supervisor and supervisor != request.requested_by_id:
                request.sudo().activity_schedule(
                    "mail.mail_activity_data_todo",
                    user_id=supervisor.id,
                    summary=_("Revisar reasignación de Catastro"),
                    note=_("%(user)s solicita la reasignación de %(partner)s.")
                    % {
                        "user": request.requested_by_id.display_name,
                        "partner": request.partner_name_snapshot,
                    },
                )
        return requests

    def write(self, vals):
        protected = {
            "partner_id",
            "request_type",
            "requested_by_id",
            "target_team_id",
            "source_user_id",
            "source_team_id",
            "company_id",
            "partner_name_snapshot",
            "partner_vat_snapshot",
            "reason",
            "request_date",
        }
        if not self.env.su and protected & set(vals):
            raise AccessError(_("Los datos de origen de una solicitud no se pueden modificar."))
        if not self.env.su and set(vals) & {"state", "reviewed_by_id", "reviewed_at", "review_note"}:
            self._check_can_review()
        return super().write(vals)

    def unlink(self):
        if not self.env.su and not is_census_manager(self.env.user):
            raise AccessError(_("Las solicitudes de reasignación se conservan como auditoría y no pueden eliminarse."))
        return super().unlink()

    def _ensure_single_canonical_census(self):
        """Prevent a transfer while historical duplicate active censuses remain unresolved."""
        for request in self:
            partner = request.partner_id.sudo().commercial_partner_id
            identity = partner._census_primary_identity()
            if not identity:
                continue
            duplicates = partner._census_global_active_by_identity(identity)
            if len(duplicates) > 1:
                raise UserError(
                    _(
                        "Existen varios catastros activos con este RUC / cédula. "
                        "Un administrador debe depurar los duplicados antes de reasignar el cliente."
                    )
                )

    def action_approve(self):
        self._check_can_review()
        self._ensure_single_canonical_census()
        now = fields.Datetime.now()
        for request in self.filtered(lambda r: r.state == "pending"):
            partner = request.partner_id.sudo().commercial_partner_id
            current_team = partner.census_team_id or partner.user_id.sale_team_id
            if partner.user_id != request.source_user_id or current_team != request.source_team_id:
                raise UserError(
                    _(
                        "La asignación del cliente cambió después de crear esta solicitud. "
                        "Por seguridad, genere una nueva solicitud con el responsable actual."
                    )
                )
            target_user = request.requested_by_id
            if not target_user.active:
                raise UserError(_("El comercial destino está archivado. Genere una nueva solicitud con un usuario activo."))
            target_company = partner.census_company_id or request.company_id or self.env.company
            target_team = partner._default_census_team(target_user, target_company)
            if not target_team:
                raise UserError(
                    _(
                        "El comercial destino no tiene un Equipo de Ventas configurado. "
                        "Asigne un equipo antes de aprobar."
                    )
                )
            if request.target_team_id and target_team != request.target_team_id:
                raise UserError(
                    _(
                        "El equipo del comercial destino cambió después de crear esta solicitud. "
                        "Por seguridad, cancele esta solicitud y genere una nueva."
                    )
                )

            old_user = partner.user_id
            old_team = current_team
            values = {
                "active": True,
                "user_id": target_user.id,
                "census_team_id": target_team.id,
                "census_unlock_user_id": False,
                "census_unlock_until": False,
            }
            if request.request_type == "claim_contact":
                values.update(
                    {
                        "census_active": True,
                        "census_company_id": target_company.id,
                        "census_date": now,
                        "census_user_id": target_user.id,
                        "census_locked": False,
                        "customer_rank": max(partner.customer_rank, 1),
                    }
                )
            partner.sudo().write(values)

            # Any edit authorization belonging to the previous assignment becomes invalid.
            unlocks = self.env["conedera.census.unlock.request"].sudo().search(
                [
                    ("partner_id", "=", partner.id),
                    ("state", "in", ["pending", "approved"]),
                ]
            )
            for unlock in unlocks:
                unlock.write(
                    {
                        "state": "rejected" if unlock.state == "pending" else "expired",
                        "reviewed_by_id": self.env.user.id,
                        "reviewed_at": now,
                        "valid_until": now,
                    }
                )

            request.sudo().write(
                {
                    "state": "approved",
                    "reviewed_by_id": self.env.user.id,
                    "reviewed_at": now,
                    "review_note": _(
                        "Reasignado de %(old_user)s / %(old_team)s a %(new_user)s / %(new_team)s."
                    )
                    % {
                        "old_user": old_user.display_name or _("Sin comercial"),
                        "old_team": old_team.display_name or _("Sin equipo"),
                        "new_user": target_user.display_name,
                        "new_team": target_team.display_name,
                    },
                }
            )
            request.sudo().activity_ids.action_done()

            # A client can only end with one responsible salesperson. Any competing
            # pending request becomes obsolete after the approved transfer.
            others = self.sudo().search(
                [
                    ("id", "!=", request.id),
                    ("partner_id", "=", partner.id),
                    ("state", "=", "pending"),
                ]
            )
            if others:
                others.write(
                    {
                        "state": "rejected",
                        "reviewed_by_id": self.env.user.id,
                        "reviewed_at": now,
                        "review_note": _("Solicitud cerrada automáticamente porque el cliente ya fue reasignado."),
                    }
                )
                others.activity_ids.action_done()

            if hasattr(partner, "message_post"):
                partner.sudo().message_post(
                    body=_(
                        "Catastro reasignado de <b>%(old)s</b> a <b>%(new)s</b> por %(reviewer)s. "
                        "Motivo de la solicitud: %(reason)s"
                    )
                    % {
                        "old": old_user.display_name or _("Sin comercial"),
                        "new": target_user.display_name,
                        "reviewer": self.env.user.display_name,
                        "reason": request.reason,
                    }
                )
        return True

    def action_reject(self):
        self._check_can_review()
        now = fields.Datetime.now()
        for request in self.filtered(lambda r: r.state == "pending"):
            request.sudo().write(
                {
                    "state": "rejected",
                    "reviewed_by_id": self.env.user.id,
                    "reviewed_at": now,
                }
            )
            request.sudo().activity_ids.action_done()
        return True

    def action_open_customer(self):
        self.ensure_one()
        partner = self.partner_id.sudo().commercial_partner_id
        can_open = bool(
            is_census_manager(self.env.user)
            or partner.user_id == self.env.user
            or (partner.census_team_id and partner.census_team_id.user_id == self.env.user)
        )
        if not can_open:
            raise AccessError(_("No tiene acceso al Catastro mientras pertenezca a otro comercial/equipo."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Catastro del cliente"),
            "res_model": "res.partner",
            "res_id": partner.id,
            "view_mode": "form",
            "views": [(self.env.ref("conedera_odoo_census.view_partner_form_census_mobile").id, "form")],
            "target": "current",
            "context": {
                "form_view_ref": "conedera_odoo_census.view_partner_form_census_mobile",
                "conedera_census_isolated_form": True,
            },
        }

    def action_cancel(self):
        for request in self:
            if request.state != "pending":
                raise UserError(_("Solo se puede cancelar una solicitud pendiente."))
            if request.requested_by_id != self.env.user and not is_census_manager(self.env.user):
                raise AccessError(_("Solo quien creó la solicitud o un administrador puede cancelarla."))
        self.sudo().write({"state": "cancelled"})
        self.sudo().activity_ids.action_done()
        return True
