import math
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

from ..services.engine import normalize
from ..services.planning import DEFAULT_SETTINGS, DEFAULT_VEHICLES, validate_settings


class DispatchVehicleType(models.Model):
    _name = "dispatch.vehicle.type"
    _description = "Tipo de vehículo para planificación de despachos"
    _order = "capacity_tons, id"

    name = fields.Char(string="Tipo de vehículo", required=True)
    code = fields.Char(required=True, default="CUSTOM")
    company_id = fields.Many2one("res.company", required=True, default=lambda s: s.env.company, index=True)
    active = fields.Boolean(default=True)
    capacity_tons = fields.Float(string="Capacidad de carga (t)", required=True, digits=(16, 3))
    utilization_pct = fields.Float(string="Utilización prevista (%)", required=True, default=90)
    useful_tons = fields.Float(string="Carga útil planificada (t)", compute="_compute_useful_tons", digits=(16, 3))
    notes = fields.Text(string="Observaciones")

    @api.depends("capacity_tons", "utilization_pct")
    def _compute_useful_tons(self):
        for vehicle in self:
            vehicle.useful_tons = vehicle.capacity_tons * vehicle.utilization_pct / 100

    @api.constrains("capacity_tons", "utilization_pct")
    def _check_capacity(self):
        for vehicle in self:
            if not math.isfinite(vehicle.capacity_tons) or vehicle.capacity_tons <= 0 or not math.isfinite(vehicle.utilization_pct) or not 0 < vehicle.utilization_pct <= 100:
                raise ValidationError(_("La capacidad debe ser positiva y la utilización mayor a 0 y hasta 100%."))


class DispatchTransportSettings(models.Model):
    _name = "dispatch.transport.settings"
    _description = "Escenario de capacidad para despachos"
    _rec_name = "company_id"

    company_id = fields.Many2one("res.company", required=True, default=lambda s: s.env.company, index=True)
    target_days = fields.Integer(string="Días operativos objetivo para vaciar pendientes", required=True, default=3)
    available_vehicles = fields.Integer(string="Vehículos asignados por ruta (escenario)", required=True, default=1)
    trips_per_day = fields.Float(string="Viajes completos por vehículo y día operativo", required=True, default=1, digits=(16, 3))
    _sql_constraints = [("transport_company_unique", "unique(company_id)", "Ya existe un escenario para esta compañía.")]

    @api.constrains("target_days", "available_vehicles", "trips_per_day")
    def _check_settings(self):
        for record in self:
            try:
                validate_settings({key: record[key] for key in DEFAULT_SETTINGS})
            except ValueError as exc:
                raise ValidationError(str(exc)) from exc

    @api.model
    def _initialize_transport_defaults(self, companies=None):
        """Installation/update only: retain edited, archived and custom values."""
        settings = self.sudo()
        vehicles = self.env["dispatch.vehicle.type"].sudo().with_context(active_test=False)
        for company in companies if companies is not None else self.env["res.company"].sudo().search([]):
            self.env.cr.execute("SELECT pg_advisory_xact_lock(%s, %s)", (180106, company.id))
            if not settings.search([("company_id", "=", company.id)], limit=1):
                settings.create({"company_id": company.id, **DEFAULT_SETTINGS})
            codes = set(vehicles.search([("company_id", "=", company.id)]).mapped("code"))
            values = [{"company_id": company.id, "code": code, "name": name, "capacity_tons": tons,
                "utilization_pct": 90, "notes": "Capacidad de referencia editable. Confirme la carga real del vehículo y las restricciones de la ruta antes de contratar."}
                for code, name, tons in DEFAULT_VEHICLES if code not in codes]
            if values:
                vehicles.create(values)

    @api.model
    def _planning_packs(self, companies):
        packs = {}
        for company in companies:
            settings = self.search([("company_id", "=", company.id)], limit=1)
            vehicles = self.env["dispatch.vehicle.type"].search([("company_id", "=", company.id)])
            routes = self.env["dispatch.transport.route"].search([("company_id", "=", company.id)])
            packs[company.id] = {"company_name": company.name,
                "settings": {key: settings[key] for key in DEFAULT_SETTINGS} if settings else dict(DEFAULT_SETTINGS),
                "vehicles": [{"id": v.id, "name": v.name, "capacity_tons": v.capacity_tons,
                              "utilization_pct": v.utilization_pct} for v in vehicles],
                "routes": [{"city": r.city, "warehouse_code": r.warehouse_code or "",
                            "vehicle_id": r.vehicle_id.id, **{key:r[key] for key in DEFAULT_SETTINGS}} for r in routes]}
        return packs


class DispatchTransportRoute(models.Model):
    _name = "dispatch.transport.route"
    _description = "Capacidad y vehículos por destino"
    _order = "city, warehouse_code"
    _rec_name = "city"
    _check_company_auto = True

    company_id = fields.Many2one("res.company", required=True, default=lambda s: s.env.company, index=True)
    active = fields.Boolean(default=True)
    city = fields.Char(string="Ciudad de destino", required=True)
    warehouse_code = fields.Char(string="Código de bodega de origen", help="Vacío: todas las bodegas de esta ciudad. Una regla por código de bodega tiene prioridad.")
    route_key = fields.Char(compute="_compute_route_key", store=True, index=True)
    vehicle_id = fields.Many2one("dispatch.vehicle.type", string="Vehículo preferido", check_company=True,
        domain="[('company_id', '=', company_id)]", help="Vacío: sugerir el tipo con menos vehículos para el plazo objetivo. No calcula costos.")
    target_days = fields.Integer(string="Días operativos objetivo", required=True, default=3)
    available_vehicles = fields.Integer(string="Vehículos asignados a cada ruta de origen", required=True, default=1)
    trips_per_day = fields.Float(string="Viajes completos por vehículo y día operativo", required=True, default=1, digits=(16, 3))
    notes = fields.Text(string="Restricciones y observaciones")

    @api.depends("city", "warehouse_code")
    def _compute_route_key(self):
        for route in self:
            route.route_key = "%s|%s" % (normalize(route.city), normalize(route.warehouse_code) or "*")

    @api.constrains("city", "warehouse_code", "company_id", "active", "target_days", "available_vehicles", "trips_per_day")
    def _check_route(self):
        for route in self:
            if not normalize(route.city) or normalize(route.city) == "SIN CIUDAD":
                raise ValidationError(_("Indique una ciudad de destino válida."))
            try:
                validate_settings({key:route[key] for key in DEFAULT_SETTINGS})
            except ValueError as exc:
                raise ValidationError(str(exc)) from exc
            if route.active and self.search_count([("id", "!=", route.id), ("company_id", "=", route.company_id.id),
                                                   ("route_key", "=", route.route_key)]):
                raise ValidationError(_("Ya existe una configuración activa para ese destino y bodega."))
