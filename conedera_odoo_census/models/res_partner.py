from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

from .gps_utils import parse_gps_payload


class ResPartner(models.Model):
    _inherit = "res.partner"

    census_active = fields.Boolean(string="Cliente catastrado", tracking=True)
    census_date = fields.Datetime(string="Fecha de catastro", readonly=True, copy=False)
    census_user_id = fields.Many2one(
        "res.users", string="Catastrado por", readonly=True, copy=False
    )

    owner_phone = fields.Char(string="Contacto dueño")
    commercial_contact_phone = fields.Char(string="Contacto comercial")
    commercial_name = fields.Char(string="Nombre de la tienda")
    store_count = fields.Integer(string="Número de tiendas", default=1)
    capa = fields.Float(string="CAPA", help="Campo CAPA definido en el formulario original.")

    business_type = fields.Selection(
        [
            ("cellphones", "Celulares"),
            ("accessories", "Accesorios"),
            ("mixed", "Mixto Cel/Acc."),
            ("commercial_house", "Casa comercial"),
            ("computing", "Cómputo"),
            ("other", "Otros"),
        ],
        string="Tipo de negocio",
        tracking=True,
    )
    business_type_other = fields.Char(string="Especificar otro negocio")
    customer_census_type = fields.Selection(
        [
            ("wholesaler", "Mayorista"),
            ("reseller", "Reseller"),
            ("route", "Ruteo"),
        ],
        string="Tipo de cliente",
        tracking=True,
    )

    census_gps_payload = fields.Char(string="Captura GPS", copy=False)
    census_gps_accuracy = fields.Float(string="Precisión GPS (m)", readonly=True, copy=False)
    census_gps_captured_at = fields.Datetime(
        string="GPS capturado el", readonly=True, copy=False
    )

    census_visit_ids = fields.One2many(
        "conedera.census.visit", "partner_id", string="Visitas comerciales"
    )
    census_visit_count = fields.Integer(compute="_compute_census_stats", string="Visitas")
    census_quotation_count = fields.Integer(
        compute="_compute_census_stats", string="Proformas"
    )
    census_last_visit_datetime = fields.Datetime(
        compute="_compute_census_stats", string="Última visita"
    )

    @api.depends("census_visit_ids.visit_datetime", "census_visit_ids.quotation_ids")
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

            quotations = self.env["sale.order"].search(
                [("partner_id", "in", partner_ids), ("census_originated", "=", True)]
            )
            for quotation in quotations:
                quotation_counts[quotation.partner_id.id] += 1

        for partner in self:
            partner.census_visit_count = visit_counts.get(partner.id, 0)
            partner.census_quotation_count = quotation_counts.get(partner.id, 0)
            partner.census_last_visit_datetime = last_visits.get(partner.id, False)

    @api.constrains(
        "census_active",
        "store_count",
        "vat",
        "commercial_name",
        "business_type",
        "business_type_other",
        "customer_census_type",
    )
    def _check_census_required_values(self):
        for partner in self:
            if not partner.census_active:
                continue
            if partner.store_count < 1:
                raise ValidationError(_("El número de tiendas debe ser al menos 1."))
            if not partner.vat:
                raise ValidationError(_("El RUC es obligatorio para un cliente catastrado."))
            if not partner.commercial_name:
                raise ValidationError(_("El nombre de la tienda es obligatorio para un cliente catastrado."))
            if not partner.business_type:
                raise ValidationError(_("Seleccione el tipo de negocio."))
            if partner.business_type == "other" and not partner.business_type_other:
                raise ValidationError(_("Especifique el tipo de negocio en Otros."))
            if not partner.customer_census_type:
                raise ValidationError(_("Seleccione el tipo de cliente."))

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
        return super().create(vals_list)

    def write(self, vals):
        vals = dict(vals)
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
        return {
            "type": "ir.actions.act_window",
            "name": _("Nueva visita"),
            "res_model": "conedera.census.visit",
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_partner_id": self.id,
                "default_user_id": self.user_id.id or self.env.user.id,
            },
        }

    def action_view_census_visits(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("conedera_odoo_census.action_census_visit")
        action["domain"] = [("partner_id", "=", self.id)]
        action["context"] = {"default_partner_id": self.id}
        return action

    def action_view_census_quotations(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("sale.action_quotations_with_onboarding")
        action["domain"] = [
            ("partner_id", "=", self.id),
            ("census_originated", "=", True),
        ]
        action["context"] = {
            "default_partner_id": self.id,
            "default_user_id": self.user_id.id or self.env.user.id,
            "default_census_originated": True,
        }
        return action

    def action_new_census_quotation(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Nueva proforma"),
            "res_model": "sale.order",
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_partner_id": self.id,
                "default_user_id": self.user_id.id or self.env.user.id,
                "default_origin": _("Catastro - %s") % self.display_name,
                "default_census_originated": True,
            },
        }
