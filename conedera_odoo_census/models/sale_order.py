from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    census_originated = fields.Boolean(
        string="Originada desde catastro", copy=False, index=True
    )
    census_visit_id = fields.Many2one(
        "conedera.census.visit",
        string="Visita comercial",
        copy=False,
        index=True,
        ondelete="set null",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            visit_id = vals.get("census_visit_id")
            if visit_id:
                visit = self.env["conedera.census.visit"].browse(visit_id).exists()
                if visit:
                    vals["census_originated"] = True
                    vals.setdefault("partner_id", visit.partner_id.id)
                    vals.setdefault("user_id", visit.user_id.id)
                    vals.setdefault("company_id", visit.company_id.id)
            if vals.get("census_originated") and vals.get("partner_id"):
                partner = self.env["res.partner"].browse(vals["partner_id"]).exists()
                if partner:
                    partner = partner.commercial_partner_id
                    partner._ensure_census_ready_for_activity()
                    if partner.census_company_id:
                        vals.setdefault("company_id", partner.census_company_id.id)
        return super().create(vals_list)

    def write(self, vals):
        vals = dict(vals)
        if vals.get("census_visit_id"):
            vals["census_originated"] = True
        return super().write(vals)

    @api.constrains("census_visit_id", "partner_id", "company_id", "census_originated")
    def _check_census_visit_consistency(self):
        for order in self:
            if order.census_originated and order.partner_id.commercial_partner_id.census_company_id and order.company_id != order.partner_id.commercial_partner_id.census_company_id:
                raise ValidationError(_("La proforma originada desde Catastro debe pertenecer a la misma Empresa del Catastro."))
            if not order.census_visit_id:
                continue
            visit = order.census_visit_id
            if order.partner_id != visit.partner_id:
                raise ValidationError(
                    _("La proforma debe pertenecer al mismo cliente de la visita comercial.")
                )
            if order.company_id != visit.company_id:
                raise ValidationError(
                    _("La proforma y la visita comercial deben pertenecer a la misma compañía.")
                )
