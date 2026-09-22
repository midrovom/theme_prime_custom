from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError

from .census_security_utils import is_census_manager, is_census_supervisor


class CensusUnlockRequest(models.Model):
    _name = "conedera.census.unlock.request"
    _description = "Solicitud de habilitación de Catastro"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "request_date desc, id desc"

    partner_id = fields.Many2one("res.partner", string="Catastro", required=True, ondelete="cascade", index=True)
    requested_by_id = fields.Many2one("res.users", string="Solicitado por", required=True, default=lambda self: self.env.user, readonly=True)
    request_date = fields.Datetime(string="Solicitado el", required=True, default=fields.Datetime.now, readonly=True)
    reason = fields.Text(string="Motivo", required=True)
    state = fields.Selection([
        ("pending", "Pendiente"),
        ("approved", "Aprobada"),
        ("rejected", "Rechazada"),
        ("expired", "Vencida"),
    ], string="Estado", default="pending", required=True, readonly=True, index=True)
    reviewed_by_id = fields.Many2one("res.users", string="Revisado por", readonly=True)
    reviewed_at = fields.Datetime(string="Revisado el", readonly=True)
    valid_until = fields.Datetime(string="Habilitado hasta", readonly=True)
    review_note = fields.Text(string="Respuesta / motivo de rechazo", readonly=True, tracking=True)
    supervisor_id = fields.Many2one(related="partner_id.census_team_id.user_id", string="Supervisor", store=True, readonly=True)
    company_id = fields.Many2one(related="partner_id.census_company_id", string="Compañía", store=True, readonly=True)
    can_review = fields.Boolean(compute="_compute_can_review", string="Puede revisar")

    @api.depends("partner_id", "partner_id.census_team_id", "partner_id.census_team_id.user_id")
    @api.depends_context("uid")
    def _compute_can_review(self):
        user = self.env.user
        is_admin = is_census_manager(user)
        for request in self:
            request.can_review = bool(
                is_admin
                or (
                    is_census_supervisor(user)
                    and request.partner_id.census_team_id
                    and request.partner_id.census_team_id.user_id == user
                )
            )

    def _check_can_review(self):
        for request in self:
            if not request.can_review:
                raise AccessError(_("Solo un usuario con rol Supervisor que lidere el Equipo comercial responsable, o un Administrador de Catastro, puede revisar esta solicitud."))

    @api.model_create_multi
    def create(self, vals_list):
        # No permitimos crear solicitudes en nombre de otro vendedor mediante RPC/importación.
        if not self.env.su and not is_census_manager(self.env.user):
            for vals in vals_list:
                partner = self.env["res.partner"].browse(vals.get("partner_id")).exists()
                if not partner or not partner.census_active or not partner.census_locked:
                    raise ValidationError(_("La solicitud debe corresponder a un catastro registrado y protegido."))
                if partner.user_id != self.env.user:
                    raise AccessError(_("Solo puede solicitar cambios sobre su propio catastro."))
                vals["requested_by_id"] = self.env.user.id
                vals["state"] = "pending"
                vals.pop("reviewed_by_id", None)
                vals.pop("reviewed_at", None)
                vals.pop("valid_until", None)
        requests = super().create(vals_list)
        for request in requests:
            supervisor = request.partner_id.census_team_id.user_id
            if supervisor and supervisor != request.requested_by_id:
                request.sudo().activity_schedule(
                    "mail.mail_activity_data_todo",
                    user_id=supervisor.id,
                    summary=_("Revisar solicitud de edición de Catastro"),
                    note=_("%(user)s solicita habilitación temporal para corregir %(partner)s. Motivo: %(reason)s")
                    % {
                        "user": request.requested_by_id.display_name,
                        "partner": request.partner_id.display_name,
                        "reason": request.reason,
                    },
                )
        return requests

    def write(self, vals):
        # Los vendedores pueden CREAR solicitudes pero no alterar una solicitud persistida.
        # Los líderes de equipo y administradores sí pueden revisar/cambiar su estado.
        if not self.env.su:
            self._check_can_review()
        return super().write(vals)

    def unlink(self):
        if not self.env.su and not is_census_manager(self.env.user):
            raise AccessError(_("Las solicitudes de edición no se eliminan; se conservan como auditoría."))
        return super().unlink()

    def action_approve(self):
        self._check_can_review()
        now = fields.Datetime.now()
        until = now + timedelta(hours=2)
        for request in self.filtered(lambda r: r.state == "pending"):
            request.sudo().write({
                "state": "approved",
                "reviewed_by_id": self.env.user.id,
                "reviewed_at": now,
                "valid_until": until,
            })
            request.partner_id.sudo().write({
                "census_unlock_user_id": request.requested_by_id.id,
                "census_unlock_until": until,
            })
            request.sudo().activity_ids.action_done()
        return True

    def action_reject(self):
        self.ensure_one()
        self._check_can_review()
        if self.state != "pending":
            raise UserError(_("Esta solicitud ya fue revisada."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Rechazar solicitud"),
            "res_model": "conedera.census.unlock.reject.wizard",
            "view_mode": "form",
            "view_id": self.env.ref("conedera_odoo_census.view_census_unlock_reject_wizard_form").id,
            "target": "new",
            "context": {"default_request_id": self.id},
        }

    def _reject_with_reason(self, reason):
        self.ensure_one()
        self._check_can_review()
        if self.state != "pending":
            raise UserError(_("Esta solicitud ya fue revisada."))
        reason = (reason or "").strip()
        if not reason:
            raise ValidationError(_("Indique el motivo del rechazo."))
        now = fields.Datetime.now()
        self.sudo().write({
            "state": "rejected",
            "reviewed_by_id": self.env.user.id,
            "reviewed_at": now,
            "valid_until": False,
            "review_note": reason,
        })
        self.sudo().activity_ids.action_done()
        return True

    @api.model
    def _expire_old_requests(self):
        now = fields.Datetime.now()
        old = self.sudo().search([("state", "=", "approved"), ("valid_until", "<", now)])
        old.write({"state": "expired"})
        partners = old.mapped("partner_id")
        for partner in partners:
            if partner.census_unlock_until and partner.census_unlock_until < now:
                partner.sudo().write({
                    "census_unlock_user_id": False,
                    "census_unlock_until": False,
                })


class CensusUnlockWizard(models.TransientModel):
    _name = "conedera.census.unlock.wizard"
    _description = "Solicitar habilitación de Catastro"

    partner_id = fields.Many2one("res.partner", string="Catastro", required=True, readonly=True)
    reason = fields.Text(string="Motivo del cambio", required=True)

    def action_submit(self):
        self.ensure_one()
        partner = self.partner_id
        if not partner.census_active or not partner.census_locked:
            raise UserError(_("Este catastro no está bloqueado."))
        if partner.user_id != self.env.user and not is_census_manager(self.env.user):
            raise AccessError(_("Solo el comercial responsable puede solicitar habilitación para este catastro."))
        reason = (self.reason or "").strip()
        if not reason:
            raise ValidationError(_("Indique el motivo del cambio."))
        pending = self.env["conedera.census.unlock.request"].search([
            ("partner_id", "=", partner.id),
            ("requested_by_id", "=", self.env.user.id),
            ("state", "=", "pending"),
        ], limit=1)
        if pending:
            raise UserError(_("Ya existe una solicitud pendiente para este catastro."))
        self.env["conedera.census.unlock.request"].create({
            "partner_id": partner.id,
            "requested_by_id": self.env.user.id,
            "reason": reason,
        })
        # Reabrimos exclusivamente la vista de Catastro para mostrar el estado
        # pendiente inmediatamente, evitando un reload genérico de res.partner.
        return partner._action_open_census_form()


class CensusUnlockRejectWizard(models.TransientModel):
    _name = "conedera.census.unlock.reject.wizard"
    _description = "Rechazar solicitud de habilitación de Catastro"

    request_id = fields.Many2one(
        "conedera.census.unlock.request", string="Solicitud", required=True, readonly=True
    )
    reason = fields.Text(string="Motivo del rechazo", required=True)

    def action_confirm(self):
        self.ensure_one()
        self.request_id._reject_with_reason(self.reason)
        return {"type": "ir.actions.act_window_close"}
