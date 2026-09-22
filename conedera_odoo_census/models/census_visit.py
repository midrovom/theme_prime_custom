from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

from .gps_utils import haversine_distance_m, parse_gps_payload

from .census_security_utils import is_census_manager, is_census_supervisor


class CensusVisit(models.Model):
    _name = "conedera.census.visit"
    _description = "Visita comercial de catastro"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "visit_datetime desc, id desc"
    _rec_name = "name"

    name = fields.Char(string="Visita", default="Nuevo", readonly=True, copy=False)
    partner_id = fields.Many2one(
        "res.partner",
        string="Cliente",
        required=True,
        index=True,
        tracking=True,
        domain="[('census_active', '=', True)]",
    )
    user_id = fields.Many2one(
        "res.users",
        string="Vendedor",
        required=True,
        default=lambda self: self.env.user,
        index=True,
        tracking=True,
    )
    company_id = fields.Many2one(
        "res.company", string="Compañía", default=lambda self: self.env.company, required=True
    )
    visit_datetime = fields.Datetime(
        string="Fecha y hora de visita",
        required=True,
        default=fields.Datetime.now,
        index=True,
        tracking=True,
    )
    state = fields.Selection(
        [("draft", "Borrador"), ("done", "Realizada"), ("cancel", "Cancelada")],
        default="draft",
        required=True,
        tracking=True,
    )

    purchase_made = fields.Selection(
        [("yes", "Sí"), ("no", "No")], string="Realizó compra", tracking=True
    )
    reschedule_visit = fields.Selection(
        [("yes", "Sí"), ("no", "No")], string="Reagendar visita", tracking=True
    )
    next_visit_datetime = fields.Datetime(string="Próxima visita", tracking=True)
    has_stock = fields.Selection(
        [("yes", "Sí"), ("no", "No")], string="Tiene stock"
    )
    not_creditworthy = fields.Selection(
        [("yes", "Sí"), ("no", "No")], string="No es sujeto de crédito"
    )
    other_result = fields.Selection(
        [("yes", "Sí"), ("no", "No")], string="Otros"
    )
    other_result_detail = fields.Char(string="Especificar otro resultado")
    notes = fields.Text(string="Observaciones")
    photo = fields.Image(string="Foto de la visita", attachment=True, max_width=1920, max_height=1920)

    gps_capture_payload = fields.Char(string="Captura GPS", copy=False)
    gps_latitude = fields.Float(string="Latitud visita", digits=(10, 7), readonly=True, copy=False)
    gps_longitude = fields.Float(string="Longitud visita", digits=(10, 7), readonly=True, copy=False)
    gps_accuracy = fields.Float(string="Precisión GPS (m)", readonly=True, copy=False)
    gps_captured_at = fields.Datetime(string="GPS capturado el", readonly=True, copy=False)

    location_tolerance_m = fields.Integer(
        string="Tolerancia ubicación (m)", default=300, required=True
    )
    distance_to_customer_m = fields.Float(
        string="Distancia al cliente (m)", compute="_compute_location_status", store=True
    )
    location_status = fields.Selection(
        [
            ("no_visit_gps", "Sin GPS de visita"),
            ("no_customer_gps", "Cliente sin GPS"),
            ("in_range", "Dentro de ubicación"),
            ("out_of_range", "Fuera de ubicación"),
        ],
        string="Validación ubicación",
        compute="_compute_location_status",
        store=True,
    )

    quotation_ids = fields.One2many("sale.order", "census_visit_id", string="Proformas")
    quotation_count = fields.Integer(compute="_compute_quotation_count", string="Proformas")

    @api.depends("quotation_ids")
    def _compute_quotation_count(self):
        for visit in self:
            visit.quotation_count = len(visit.quotation_ids)

    @api.depends(
        "gps_latitude",
        "gps_longitude",
        "gps_captured_at",
        "partner_id.partner_latitude",
        "partner_id.partner_longitude",
        "location_tolerance_m",
    )
    def _compute_location_status(self):
        for visit in self:
            visit.distance_to_customer_m = 0.0
            if not visit.gps_captured_at:
                visit.location_status = "no_visit_gps"
                continue
            customer_lat = visit.partner_id.partner_latitude
            customer_lon = visit.partner_id.partner_longitude
            if not visit.partner_id.census_gps_captured_at:
                visit.location_status = "no_customer_gps"
                continue
            distance = haversine_distance_m(
                visit.gps_latitude,
                visit.gps_longitude,
                customer_lat,
                customer_lon,
            )
            visit.distance_to_customer_m = distance
            visit.location_status = (
                "in_range" if distance <= visit.location_tolerance_m else "out_of_range"
            )

    @api.onchange("gps_capture_payload")
    def _onchange_gps_capture_payload(self):
        for visit in self:
            parsed = parse_gps_payload(visit.gps_capture_payload)
            if parsed:
                latitude, longitude, accuracy = parsed
                visit.gps_latitude = latitude
                visit.gps_longitude = longitude
                visit.gps_accuracy = accuracy
                visit.gps_captured_at = fields.Datetime.now()

    @api.model_create_multi
    def create(self, vals_list):
        is_manager = is_census_manager(self.env.user)
        for vals in vals_list:
            if not is_manager:
                # El vendedor que crea la visita es siempre el responsable auditado.
                vals["user_id"] = self.env.user.id
                vals["company_id"] = self.env.company.id
            partner_id = vals.get("partner_id")
            if partner_id:
                partner = self.env["res.partner"].browse(partner_id).exists()
                if partner:
                    partner._ensure_census_ready_for_activity()
            if vals.get("name", "Nuevo") == "Nuevo":
                vals["name"] = self.env["ir.sequence"].next_by_code("conedera.census.visit") or "Nuevo"
            parsed = parse_gps_payload(vals.get("gps_capture_payload"))
            if parsed:
                latitude, longitude, accuracy = parsed
                vals.update(
                    {
                        "gps_latitude": latitude,
                        "gps_longitude": longitude,
                        "gps_accuracy": accuracy,
                        "gps_captured_at": fields.Datetime.now(),
                    }
                )
        return super().create(vals_list)

    def write(self, vals):
        vals = dict(vals)
        protected_fields = {
            "partner_id",
            "user_id",
            "visit_datetime",
            "purchase_made",
            "reschedule_visit",
            "next_visit_datetime",
            "has_stock",
            "not_creditworthy",
            "other_result",
            "other_result_detail",
            "notes",
            "photo",
            "gps_capture_payload",
            "gps_latitude",
            "gps_longitude",
            "gps_accuracy",
            "gps_captured_at",
            "location_tolerance_m",
        }
        is_manager = is_census_manager(self.env.user)
        locked_states = {"done", "cancel"}
        if (
            any(visit.state in locked_states for visit in self)
            and protected_fields.intersection(vals)
            and not is_manager
        ):
            raise UserError(
                _("Una visita finalizada o cancelada solo puede ser modificada por un administrador de Catastro.")
            )
        if (
            "state" in vals
            and any(visit.state in locked_states and vals.get("state") != visit.state for visit in self)
            and not is_manager
        ):
            raise UserError(
                _("Solo un administrador de Catastro puede cambiar el estado de una visita finalizada o cancelada.")
            )
        if "user_id" in vals and not is_manager and vals.get("user_id") != self.env.user.id:
            raise UserError(_("Un vendedor no puede reasignar la visita a otro usuario."))
        if "company_id" in vals and not is_manager and vals.get("company_id") != self.env.company.id:
            raise UserError(_("Un vendedor no puede mover la visita a otra compañía."))

        parsed = parse_gps_payload(vals.get("gps_capture_payload"))
        if parsed:
            latitude, longitude, accuracy = parsed
            vals.update(
                {
                    "gps_latitude": latitude,
                    "gps_longitude": longitude,
                    "gps_accuracy": accuracy,
                    "gps_captured_at": fields.Datetime.now(),
                }
            )
        return super().write(vals)

    @api.constrains("reschedule_visit", "next_visit_datetime", "location_tolerance_m")
    def _check_visit_values(self):
        for visit in self:
            if visit.reschedule_visit == "yes" and not visit.next_visit_datetime:
                raise ValidationError(_("Debe indicar la fecha de la próxima visita."))
            if visit.location_tolerance_m <= 0:
                raise ValidationError(_("La tolerancia de ubicación debe ser mayor que cero."))

    def action_save_progress(self):
        """Botón táctil: el cliente web guarda antes de ejecutar la acción."""
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Visita guardada"),
                "message": _("Los datos, la encuesta y la fotografía quedaron guardados."),
                "type": "success",
                "sticky": False,
            },
        }

    def action_open_photo(self):
        self.ensure_one()
        if not self.photo:
            raise UserError(_("La visita todavía no tiene una fotografía."))
        return {
            "type": "ir.actions.act_url",
            "url": "/web/image/%s/%s/photo?unique=%s"
            % (
                self._name,
                self.id,
                (self.write_date or fields.Datetime.now()).strftime("%Y%m%d%H%M%S"),
            ),
            "target": "new",
        }

    def action_mark_done(self):
        required_answers = (
            "purchase_made",
            "reschedule_visit",
            "has_stock",
            "not_creditworthy",
            "other_result",
        )
        todo_type = self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)
        for visit in self:
            # GPS es opcional temporalmente mientras el despliegue no tenga HTTPS.
            # Si existe una captura, se conserva y se usa para validar ubicación.
            if any(not visit[field_name] for field_name in required_answers):
                raise UserError(_("Complete todas las preguntas de la mini encuesta."))
            if visit.reschedule_visit == "yes" and not visit.next_visit_datetime:
                raise UserError(_("Indique la fecha de la próxima visita."))
            if visit.other_result == "yes" and not visit.other_result_detail:
                raise UserError(_("Especifique el resultado en el campo Otros."))
            visit.state = "done"
            if todo_type and visit.reschedule_visit == "yes":
                deadline = fields.Datetime.context_timestamp(
                    visit, visit.next_visit_datetime
                ).date()
                existing = visit.activity_ids.filtered(
                    lambda activity: activity.activity_type_id == todo_type
                    and activity.user_id == visit.user_id
                    and activity.date_deadline == deadline
                )
                if not existing:
                    visit.activity_schedule(
                        activity_type_id=todo_type.id,
                        date_deadline=deadline,
                        user_id=visit.user_id.id,
                        summary=_("Nueva visita: %s") % visit.partner_id.display_name,
                    )
        return True

    def action_set_draft(self):
        self.write({"state": "draft"})
        return True

    def action_cancel(self):
        self.write({"state": "cancel"})
        return True

    def action_create_quotation(self):
        self.ensure_one()
        self.partner_id._ensure_census_ready_for_activity()
        return {
            "type": "ir.actions.act_window",
            "name": _("Nueva proforma"),
            "res_model": "sale.order",
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_partner_id": self.partner_id.id,
                "default_user_id": self.user_id.id,
                "default_census_visit_id": self.id,
                "default_origin": self.name,
                "default_census_originated": True,
                "default_company_id": self.company_id.id,
            },
        }

    def action_view_quotations(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("sale.action_quotations_with_onboarding")
        action["domain"] = [("census_visit_id", "=", self.id)]
        action["context"] = {
            "default_partner_id": self.partner_id.id,
            "default_user_id": self.user_id.id,
            "default_company_id": self.company_id.id,
            "default_census_visit_id": self.id,
            "default_census_originated": True,
        }
        return action

    def action_open_visit_location(self):
        self.ensure_one()
        if not self.gps_captured_at:
            raise UserError(_("La visita no tiene una ubicación GPS capturada."))
        url = (
            "https://www.openstreetmap.org/?mlat=%s&mlon=%s#map=18/%s/%s"
            % (self.gps_latitude, self.gps_longitude, self.gps_latitude, self.gps_longitude)
        )
        return {"type": "ir.actions.act_url", "url": url, "target": "new"}
