import base64
import json
import re
from datetime import datetime

from odoo import http, fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import request
from odoo.tools import file_open


VAT_CLEAN_RE = re.compile(r"[^A-Z0-9]")


class ConederaFieldAppController(http.Controller):
    def _static_response(self, path, content_type, cache=False):
        with file_open(path, "rb") as f:
            data = f.read()
        headers = [("Content-Type", content_type)]
        if cache:
            headers.append(("Cache-Control", "public, max-age=3600"))
        else:
            headers.append(("Cache-Control", "no-cache"))
        return request.make_response(data, headers=headers)

    @http.route("/conedera/app", type="http", auth="user", methods=["GET"], sitemap=False)
    def app(self, **kwargs):
        return self._static_response(
            "conedera_odoo_census_mobile/static/src/pwa/index.html",
            "text/html; charset=utf-8",
            cache=False,
        )

    @http.route("/conedera/sw.js", type="http", auth="public", methods=["GET"], csrf=False, sitemap=False)
    def service_worker(self, **kwargs):
        response = self._static_response(
            "conedera_odoo_census_mobile/static/src/pwa/sw.js",
            "application/javascript; charset=utf-8",
            cache=False,
        )
        response.headers["Service-Worker-Allowed"] = "/conedera/"
        return response

    @http.route("/conedera/manifest.webmanifest", type="http", auth="public", methods=["GET"], csrf=False, sitemap=False)
    def manifest(self, **kwargs):
        payload = {
            "name": "Catastro de Campo",
            "short_name": "Catastro",
            "description": "Catastro comercial y visitas de campo Conedera",
            "start_url": "/conedera/app",
            "scope": "/conedera/",
            "display": "standalone",
            "background_color": "#f7f6fb",
            "theme_color": "#6f5aa7",
            "icons": [
                {
                    "src": "/conedera_odoo_census_mobile/static/description/icon.svg",
                    "sizes": "any",
                    "type": "image/svg+xml",
                    "purpose": "any maskable",
                }
            ],
        }
        return request.make_response(
            json.dumps(payload, ensure_ascii=False).encode(),
            headers=[
                ("Content-Type", "application/manifest+json; charset=utf-8"),
                ("Cache-Control", "public, max-age=3600"),
            ],
        )

    @http.route("/conedera/app/ping", type="json", auth="user", methods=["POST"], readonly=True)
    def ping(self):
        return {"ok": True, "server_time": fields.Datetime.now()}

    def _existing_fields(self, model, names):
        return [name for name in names if name in model._fields]

    def _readable_partner_fields(self):
        candidates = [
            "id", "name", "vat", "phone", "mobile", "email", "street", "street2", "city",
            "state_id", "country_id", "user_id", "write_date", "commercial_partner_id",
            "census_active", "commercial_name", "census_store_count", "store_count", "capa",
            "owner_contact_name", "owner_phone", "commercial_contact_name", "commercial_contact_phone",
            "business_description", "customer_segment", "census_company_id", "census_team_id",
            "census_locked", "census_locked_at", "census_completion_percent", "census_completion_state",
            "opening_hours_summary", "census_opening_hours_summary",
        ]
        return self._existing_fields(request.env["res.partner"], candidates)

    def _current_team(self):
        user = request.env.user
        team = False
        if "sale_team_id" in user._fields:
            team = user.sale_team_id
        if not team and "crm.team" in request.env.registry:
            team = request.env["crm.team"].search([
                "|", ("user_id", "=", user.id), ("member_ids", "in", user.id),
                "|", ("company_id", "=", False), ("company_id", "=", request.env.company.id),
            ], limit=1)
        return team

    def _team_payload(self):
        if "crm.team" not in request.env.registry:
            return []
        Team = request.env["crm.team"]
        domain = ["|", ("company_id", "=", False), ("company_id", "in", request.env.companies.ids)]
        if "census_available" in Team._fields:
            domain.append(("census_available", "=", True))
        fields_list = self._existing_fields(Team, ["id", "name", "company_id", "user_id", "member_ids"])
        return Team.search_read(domain, fields_list, order="name", limit=100)

    def _catalog_payload(self, model_name):
        if model_name not in request.env.registry:
            return []
        Model = request.env[model_name]
        names = self._existing_fields(Model, ["id", "name", "active", "color", "sequence"])
        domain = [("active", "=", True)] if "active" in Model._fields else []
        try:
            return Model.search_read(domain, names, order="sequence, name" if "sequence" in Model._fields else "name", limit=200)
        except AccessError:
            return Model.sudo().search_read(domain, names, order="name", limit=200)

    def _visit_payload(self, partner_ids):
        model_name = "conedera.census.visit"
        if not partner_ids or model_name not in request.env.registry:
            return []
        Visit = request.env[model_name]
        partner_field = next((x for x in ["partner_id", "customer_id"] if x in Visit._fields), None)
        if not partner_field:
            return []
        candidates = [
            "id", partner_field, "name", "state", "create_date", "write_date", "visit_datetime", "visit_date", "date",
            "user_id", "salesperson_id", "purchase_made", "reschedule_visit", "has_stock", "no_credit_subject",
            "notes", "observation", "observations", "other_result", "location_status", "distance_to_customer_m",
        ]
        fields_list = self._existing_fields(Visit, candidates)
        date_field = next((x for x in ["visit_datetime", "visit_date", "date", "create_date"] if x in Visit._fields), "id")
        try:
            return Visit.search_read([(partner_field, "in", partner_ids)], fields_list, order=f"{date_field} desc, id desc", limit=800)
        except AccessError:
            return []

    def _sale_payload(self, partner_ids):
        if not partner_ids:
            return [], []
        Sale = request.env["sale.order"]
        domain = [("state", "!=", "cancel")]
        # Prefer commercial partner when available; otherwise include child contacts.
        if "commercial_partner_id" in Sale._fields:
            domain.append(("commercial_partner_id", "in", partner_ids))
        else:
            domain.append(("partner_id.commercial_partner_id", "in", partner_ids))
        sale_fields = self._existing_fields(Sale, [
            "id", "name", "partner_id", "commercial_partner_id", "date_order", "user_id", "amount_total",
            "currency_id", "state", "company_id", "write_date",
        ])
        try:
            orders = Sale.search_read(domain, sale_fields, order="date_order desc, id desc", limit=800)
        except AccessError:
            orders = []
        if not orders:
            return [], []

        order_map = {}
        for order in orders:
            cp = order.get("commercial_partner_id") or order.get("partner_id")
            if isinstance(cp, (list, tuple)):
                cp = cp[0]
            order_map[order["id"]] = cp

        Line = request.env["sale.order.line"]
        line_fields = self._existing_fields(Line, ["order_id", "product_id", "product_uom_qty", "price_subtotal", "price_unit", "discount"])
        lines = Line.search_read([("order_id", "in", list(order_map))], line_fields, limit=6000)
        agg = {}
        for line in lines:
            order = line.get("order_id")
            product = line.get("product_id")
            if not order or not product:
                continue
            order_id = order[0] if isinstance(order, (list, tuple)) else order
            partner_id = order_map.get(order_id)
            if not partner_id:
                continue
            product_id = product[0] if isinstance(product, (list, tuple)) else product
            product_name = product[1] if isinstance(product, (list, tuple)) and len(product) > 1 else str(product_id)
            key = (partner_id, product_id)
            rec = agg.setdefault(key, {
                "partner_id": partner_id,
                "product_id": product_id,
                "product_name": product_name,
                "qty": 0.0,
                "subtotal": 0.0,
                "lines": 0,
            })
            rec["qty"] += float(line.get("product_uom_qty") or 0.0)
            rec["subtotal"] += float(line.get("price_subtotal") or 0.0)
            rec["lines"] += 1
        summaries = []
        for rec in agg.values():
            rec["avg_price"] = rec["subtotal"] / rec["qty"] if rec["qty"] else 0.0
            summaries.append(rec)
        summaries.sort(key=lambda x: (x["partner_id"], -x["qty"], x["product_name"]))
        return orders, summaries[:2000]

    @http.route("/conedera/app/bootstrap", type="json", auth="user", methods=["POST"], readonly=True)
    def bootstrap(self):
        Partner = request.env["res.partner"]
        partner_fields = self._readable_partner_fields()
        domain = [("census_active", "=", True)] if "census_active" in Partner._fields else [("customer_rank", ">", 0)]
        partners = Partner.search_read(domain, partner_fields, order="write_date desc, id desc", limit=1000)
        partner_ids = [x["id"] for x in partners]
        visits = self._visit_payload(partner_ids)
        orders, products = self._sale_payload(partner_ids)
        team = self._current_team()
        return {
            "server_time": fields.Datetime.now(),
            "user": {
                "id": request.env.user.id,
                "name": request.env.user.name,
                "company_id": request.env.company.id,
                "company_name": request.env.company.name,
                "company_ids": request.env.companies.ids,
                "team_id": team.id if team else False,
                "team_name": team.name if team else False,
            },
            "partners": partners,
            "visits": visits,
            "orders": orders,
            "products": products,
            "teams": self._team_payload(),
            "business_types": self._catalog_payload("conedera.census.business.type"),
            "mobile_brands": self._catalog_payload("conedera.census.mobile.brand"),
            "capabilities": {
                "visit_model": "conedera.census.visit" in request.env.registry,
                "business_type_model": "conedera.census.business.type" in request.env.registry,
                "mobile_brand_model": "conedera.census.mobile.brand" in request.env.registry,
                "opening_hour_model": "conedera.partner.opening.hour" in request.env.registry,
            },
        }

    def _normalize_vat(self, vat):
        return VAT_CLEAN_RE.sub("", (vat or "").strip().upper())

    def _find_partner_global_by_vat(self, vat):
        normalized = self._normalize_vat(vat)
        if not normalized:
            return request.env["res.partner"].browse()
        request.env.cr.execute(
            """
            SELECT id
              FROM res_partner
             WHERE regexp_replace(upper(coalesce(vat, '')), '[^A-Z0-9]', '', 'g') = %s
             ORDER BY id
             LIMIT 20
            """,
            [normalized],
        )
        ids = [row[0] for row in request.env.cr.fetchall()]
        if not ids:
            return request.env["res.partner"].browse()
        candidates = request.env["res.partner"].sudo().browse(ids).exists()
        commercial = candidates.mapped("commercial_partner_id")
        return commercial[:1]

    def _can_read_partner(self, partner):
        try:
            user_partner = partner.with_user(request.env.user)
            user_partner.check_access_rights("read")
            user_partner.check_access_rule("read")
            return True
        except AccessError:
            return False

    def _m2m_field_by_comodel(self, model, comodel):
        for name, field in model._fields.items():
            if field.type == "many2many" and getattr(field, "comodel_name", None) == comodel:
                return name
        return None

    def _prepare_partner_vals(self, payload, create=False):
        Partner = request.env["res.partner"]
        vals = {}
        mapping = {
            "name": "name",
            "vat": "vat",
            "phone": "phone",
            "mobile": "mobile",
            "email": "email",
            "street": "street",
            "street2": "street2",
            "city": "city",
            "commercial_name": "commercial_name",
            "store_count": "census_store_count" if "census_store_count" in Partner._fields else "store_count",
            "capa": "capa",
            "owner_contact_name": "owner_contact_name",
            "owner_phone": "owner_phone",
            "commercial_contact_name": "commercial_contact_name",
            "commercial_contact_phone": "commercial_contact_phone",
            "business_description": "business_description",
            "customer_segment": "customer_segment",
        }
        for source, target in mapping.items():
            if target in Partner._fields and source in payload:
                value = payload.get(source)
                if source == "store_count" and value not in (None, ""):
                    try:
                        value = int(value)
                    except (TypeError, ValueError):
                        value = 0
                if source == "capa" and value not in (None, ""):
                    try:
                        value = float(value)
                    except (TypeError, ValueError):
                        value = 0.0
                vals[target] = value
        if create:
            if "census_active" in Partner._fields:
                vals["census_active"] = True
            if "census_user_id" in Partner._fields:
                vals["census_user_id"] = request.env.user.id
            if "user_id" in Partner._fields:
                vals["user_id"] = request.env.user.id
            if "census_company_id" in Partner._fields:
                vals["census_company_id"] = request.env.company.id
            team = self._current_team()
            if team and "census_team_id" in Partner._fields:
                vals["census_team_id"] = team.id
        business_field = self._m2m_field_by_comodel(Partner, "conedera.census.business.type")
        if business_field and "business_type_ids" in payload:
            vals[business_field] = [(6, 0, [int(x) for x in payload.get("business_type_ids") or [] if str(x).isdigit()])]
        brand_field = self._m2m_field_by_comodel(Partner, "conedera.census.mobile.brand")
        if brand_field and "mobile_brand_ids" in payload:
            vals[brand_field] = [(6, 0, [int(x) for x in payload.get("mobile_brand_ids") or [] if str(x).isdigit()])]
        return vals

    def _sync_opening_hours(self, partner, hours):
        model_name = "conedera.partner.opening.hour"
        if not hours or model_name not in request.env.registry:
            return
        Hour = request.env[model_name]
        partner_field = next((x for x in ["partner_id", "customer_id"] if x in Hour._fields), None)
        day_field = next((x for x in ["day", "weekday", "day_of_week"] if x in Hour._fields), None)
        from_field = next((x for x in ["hour_from", "time_from", "opening_hour"] if x in Hour._fields), None)
        to_field = next((x for x in ["hour_to", "time_to", "closing_hour"] if x in Hour._fields), None)
        if not all([partner_field, day_field, from_field, to_field]):
            return
        for item in hours:
            if not item.get("day"):
                continue
            vals = {
                partner_field: partner.id,
                day_field: str(item.get("day")),
                from_field: float(item.get("from") or 0),
                to_field: float(item.get("to") or 0),
            }
            try:
                Hour.create(vals)
            except (AccessError, UserError, ValidationError):
                Hour.sudo().create(vals)

    def _sync_catastro(self, payload):
        vat = payload.get("vat")
        existing = self._find_partner_global_by_vat(vat)
        if existing:
            visible = self._can_read_partner(existing)
            return {
                "state": "conflict",
                "message": "El RUC/cédula ya existe. Abra el cliente existente o solicite reasignación.",
                "result_model": "res.partner",
                "result_id": existing.id if visible else 0,
                "existing": {
                    "id": existing.id if visible else False,
                    "name": existing.name if visible else "Cliente ya registrado",
                    "vat": existing.vat if visible else vat,
                },
            }
        vals = self._prepare_partner_vals(payload, create=True)
        if not vals.get("name"):
            vals["name"] = payload.get("commercial_name") or vat or "Catastro móvil"
        partner = request.env["res.partner"].sudo().create(vals)
        self._sync_opening_hours(partner, payload.get("opening_hours") or [])
        return {
            "state": "synced",
            "message": "Catastro creado como borrador. Complete o proteja la ficha cuando tenga conexión.",
            "result_model": "res.partner",
            "result_id": partner.id,
        }

    def _sync_catastro_update(self, payload):
        partner_id = int(payload.get("partner_id") or 0)
        partner = request.env["res.partner"].browse(partner_id).exists()
        if not partner:
            raise UserError("El catastro ya no existe.")
        base_write_date = payload.get("base_write_date")
        if base_write_date and str(partner.write_date) != str(base_write_date):
            return {
                "state": "conflict",
                "message": "El catastro cambió en el servidor desde la última descarga. Refresque antes de sobrescribir.",
                "result_model": "res.partner",
                "result_id": partner.id,
            }
        vals = self._prepare_partner_vals(payload, create=False)
        partner.write(vals)
        return {
            "state": "synced",
            "message": "Catastro actualizado.",
            "result_model": "res.partner",
            "result_id": partner.id,
        }

    def _visit_values(self, payload):
        Visit = request.env["conedera.census.visit"]
        vals = {}
        partner_field = next((x for x in ["partner_id", "customer_id"] if x in Visit._fields), None)
        if not partner_field:
            raise UserError("El modelo de visitas no tiene campo de cliente compatible.")
        vals[partner_field] = int(payload.get("partner_id") or 0)
        user_field = next((x for x in ["user_id", "salesperson_id"] if x in Visit._fields and Visit._fields[x].type == "many2one"), None)
        if user_field:
            vals[user_field] = request.env.user.id
        company_field = "company_id" if "company_id" in Visit._fields else None
        if company_field:
            vals[company_field] = request.env.company.id
        date_field = next((x for x in ["visit_datetime", "visit_date", "date"] if x in Visit._fields), None)
        if date_field and payload.get("visit_datetime"):
            vals[date_field] = payload.get("visit_datetime")
        direct = ["purchase_made", "reschedule_visit", "has_stock", "no_credit_subject", "other_result"]
        for name in direct:
            if name in Visit._fields and name in payload:
                vals[name] = payload.get(name)
        note_field = next((x for x in ["notes", "observation", "observations"] if x in Visit._fields), None)
        if note_field and "notes" in payload:
            vals[note_field] = payload.get("notes")
        photo_field = "photo" if "photo" in Visit._fields else None
        photo = payload.get("photo")
        if photo_field and photo:
            if "," in photo:
                photo = photo.split(",", 1)[1]
            try:
                base64.b64decode(photo, validate=True)
                vals[photo_field] = photo
            except Exception:
                pass
        gps_mapping = {
            "gps_payload": ["gps_payload", "visit_gps_payload"],
            "gps_accuracy": ["gps_accuracy", "visit_gps_accuracy"],
            "gps_captured_at": ["gps_captured_at", "visit_gps_captured_at"],
        }
        for source, targets in gps_mapping.items():
            if source not in payload:
                continue
            target = next((x for x in targets if x in Visit._fields), None)
            if target:
                vals[target] = payload.get(source)
        return vals

    def _sync_visit(self, payload):
        if "conedera.census.visit" not in request.env.registry:
            raise UserError("El modelo de visitas del Catastro no está disponible.")
        partner = request.env["res.partner"].browse(int(payload.get("partner_id") or 0)).exists()
        if not partner:
            raise UserError("Seleccione un catastro válido.")
        Visit = request.env["conedera.census.visit"]
        record = Visit.create(self._visit_values(payload))
        warning = False
        if payload.get("finalize"):
            for method_name in ["action_finish", "action_finalize", "action_done"]:
                method = getattr(record, method_name, None)
                if callable(method):
                    try:
                        method()
                    except (UserError, ValidationError, AccessError) as exc:
                        warning = str(exc)
                    break
        return {
            "state": "warning" if warning else "synced",
            "message": warning or "Visita sincronizada correctamente.",
            "result_model": "conedera.census.visit",
            "result_id": record.id,
        }

    def _process_operation(self, operation):
        op_type = operation.get("type")
        payload = operation.get("payload") or {}
        if op_type == "visit":
            return self._sync_visit(payload)
        if op_type == "catastro":
            return self._sync_catastro(payload)
        if op_type == "catastro_update":
            return self._sync_catastro_update(payload)
        raise UserError("Tipo de operación móvil no soportado.")

    @http.route("/conedera/app/sync", type="json", auth="user", methods=["POST"])
    def sync(self, operations=None):
        operations = operations or []
        if not isinstance(operations, list):
            raise UserError("Formato de sincronización inválido.")
        Log = request.env["conedera.mobile.sync.log"].sudo()
        results = []
        for operation in operations[:100]:
            client_uuid = (operation.get("uuid") or "").strip()
            op_type = operation.get("type")
            if not client_uuid or op_type not in {"visit", "catastro", "catastro_update"}:
                results.append({"uuid": client_uuid, "state": "error", "message": "Operación inválida."})
                continue
            log = Log.search([("client_uuid", "=", client_uuid)], limit=1)
            if log and log.state in ("synced", "warning", "conflict"):
                results.append({
                    "uuid": client_uuid,
                    "state": log.state,
                    "message": log.message,
                    "result_model": log.result_model,
                    "result_id": log.result_id,
                })
                continue
            if not log:
                log = Log.create({
                    "client_uuid": client_uuid,
                    "user_id": request.env.user.id,
                    "company_id": request.env.company.id,
                    "operation_type": op_type,
                    "payload_json": Log._payload_dump(operation.get("payload")),
                    "state": "pending",
                })
            else:
                log.write({
                    "payload_json": Log._payload_dump(operation.get("payload")),
                    "state": "pending",
                    "message": False,
                })
            try:
                with request.env.cr.savepoint():
                    result = self._process_operation(operation)
                state = result.get("state", "synced")
                log.write({
                    "state": state,
                    "message": result.get("message"),
                    "result_model": result.get("result_model"),
                    "result_id": result.get("result_id") or 0,
                    "synced_at": fields.Datetime.now(),
                })
                results.append({"uuid": client_uuid, **result})
            except Exception as exc:  # keep queue auditable and return a retryable error
                message = str(exc) or exc.__class__.__name__
                log.write({"state": "error", "message": message})
                results.append({"uuid": client_uuid, "state": "error", "message": message})
        return {"results": results, "server_time": fields.Datetime.now()}
