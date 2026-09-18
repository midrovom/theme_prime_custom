from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


class CensusUnlockRequest(models.Model):
    _name = "conedera.census.unlock.request"
    _description = "Solicitud de habilitación de Catastro"
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
    supervisor_id = fields.Many2one(related="partner_id.census_team_id.user_id", string="Supervisor", store=True, readonly=True)
    company_id = fields.Many2one(related="partner_id.company_id", string="Compañía", store=True, readonly=True)
    can_review = fields.Boolean(compute="_compute_can_review", string="Puede revisar")

    @api.depends("partner_id", "partner_id.census_team_id", "partner_id.census_team_id.user_id")
    @api.depends_context("uid")
    def _compute_can_review(self):
        user = self.env.user
        is_admin = user.has_group("sales_team.group_sale_manager")
        for request in self:
            request.can_review = bool(
                is_admin
                or (
                    request.partner_id.census_team_id
                    and request.partner_id.census_team_id.user_id == user
                )
            )

    def _check_can_review(self):
        for request in self:
            if not request.can_review:
                raise AccessError(_("Solo el líder del Equipo de Ventas responsable o un administrador puede revisar esta solicitud."))

    @api.model_create_multi
    def create(self, vals_list):
        # No permitimos crear solicitudes en nombre de otro vendedor mediante RPC/importación.
        if not self.env.su and not self.env.user.has_group("sales_team.group_sale_manager"):
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
        return super().create(vals_list)

    def write(self, vals):
        # Los vendedores pueden CREAR solicitudes pero no alterar una solicitud persistida.
        # Los líderes de equipo y administradores sí pueden revisar/cambiar su estado.
        if not self.env.su:
            self._check_can_review()
        return super().write(vals)

    def unlink(self):
        if not self.env.su and not self.env.user.has_group("sales_team.group_sale_manager"):
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
            request.partner_id.with_context(census_system_write=True).sudo().write({
                "census_unlock_user_id": request.requested_by_id.id,
                "census_unlock_until": until,
            })
        return True

    def action_reject(self):
        self._check_can_review()
        now = fields.Datetime.now()
        for request in self.filtered(lambda r: r.state == "pending"):
            request.sudo().write({
                "state": "rejected",
                "reviewed_by_id": self.env.user.id,
                "reviewed_at": now,
                "valid_until": False,
            })
        return True

    @api.model
    def _expire_old_requests(self):
        now = fields.Datetime.now()
        old = self.sudo().search([("state", "=", "approved"), ("valid_until", "<", now)])
        old.write({"state": "expired"})
        partners = old.mapped("partner_id")
        for partner in partners:
            if partner.census_unlock_until and partner.census_unlock_until < now:
                partner.with_context(census_system_write=True).sudo().write({
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
        if partner.user_id != self.env.user and not self.env.user.has_group("sales_team.group_sale_manager"):
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
        return {"type": "ir.actions.act_window_close"}
