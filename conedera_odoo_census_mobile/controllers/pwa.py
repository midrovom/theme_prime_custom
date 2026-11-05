import base64
import json
import math
import re
from datetime import datetime

from odoo import http, fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import request
from odoo.tools import file_open, float_compare

from odoo.addons.conedera_odoo_census.models.census_security_utils import is_census_user, is_census_manager


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

    @http.route(["/catastro", "/catastro/", "/conedera/app"], type="http", auth="user", methods=["GET"], sitemap=False)
    def catastro_redirect(self, **kwargs):
        # Preserve existing bookmarks; never replace the default Odoo /web route.
        return request.redirect("/catastro/app", code=302)

    @http.route("/catastro/app", type="http", auth="user", methods=["GET"], sitemap=False)
    def app(self, **kwargs):
        return self._static_response(
            "conedera_odoo_census_mobile/static/src/pwa/index.html",
            "text/html; charset=utf-8",
            cache=False,
        )

    @http.route("/catastro/sw.js", type="http", auth="public", methods=["GET"], csrf=False, sitemap=False)
    def service_worker(self, **kwargs):
        response = self._static_response(
            "conedera_odoo_census_mobile/static/src/pwa/sw.js",
            "application/javascript; charset=utf-8",
            cache=False,
        )
        response.headers["Service-Worker-Allowed"] = "/catastro/"
        return response

    @http.route("/catastro/manifest.webmanifest", type="http", auth="public", methods=["GET"], csrf=False, sitemap=False)
    def manifest(self, **kwargs):
        payload = {
            "name": "Catastro de Campo",
            "short_name": "Catastro",
            "description": "Catastro comercial y visitas de campo para múltiples empresas",
            "start_url": "/catastro/app",
            "scope": "/catastro/",
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

    @http.route(["/catastro/app/ping", "/conedera/app/ping"], type="json", auth="user", methods=["POST"], readonly=True)
    def ping(self):
        return {"ok": True, "server_time": fields.Datetime.now(), "user_id": request.env.user.id,
                "company_id": request.env.company.id}

    def _existing_fields(self, model, names):
        return [name for name in names if name in model._fields]

    def _readable_partner_fields(self):
        candidates = [
            "id", "name", "vat", "phone", "mobile", "email", "street", "street2", "city",
            "state_id", "country_id", "user_id", "write_date", "commercial_partner_id",
            "census_active", "commercial_name", "census_store_count", "store_count", "capa",
            "owner_contact_name", "owner_phone", "commercial_contact_name", "commercial_contact_phone",
            "business_description", "customer_segment", "business_type_ids", "mobile_brand_ids",
            "census_company_id", "census_team_id",
            "census_locked", "census_locked_at", "census_completion_pct", "census_completion_state",
            "census_can_edit_master", "census_edit_state", "census_ready_for_activity", "census_missing_requirements",
            "census_unlock_until", "census_latest_unlock_state", "census_latest_unlock_review_note",
            "census_latest_unlock_reason", "census_latest_unlock_request_date", "census_latest_unlock_valid_until",
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
        if "census_enabled" in Team._fields:
            domain.append(("census_enabled", "=", True))
        if not is_census_manager(request.env.user):
            domain += ["|", ("user_id", "=", request.env.user.id),
                       ("member_ids", "in", [request.env.user.id])]
        fields_list = self._existing_fields(Team, ["id", "name", "company_id", "census_enabled"])
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
            "user_id", "salesperson_id", "purchase_made", "reschedule_visit", "has_stock", "not_creditworthy",
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
        line_domain = [("order_id", "in", list(order_map))]
        if "reward_id" in Line._fields:
            line_domain.append(("reward_id", "=", False))
        if "is_catastro_payment_surcharge" in Line._fields:
            line_domain.append(("is_catastro_payment_surcharge", "=", False))
        lines = Line.search_read(line_domain, line_fields, order="id desc", limit=4000)
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
        # Las líneas se leen de más reciente a más antigua. Conservar los
        # últimos 40 productos distintos por catastro, no miles de agregados.
        recent_by_partner = {}
        for rec in summaries:
            bucket = recent_by_partner.setdefault(rec["partner_id"], [])
            if len(bucket) < 40:
                bucket.append(rec)
        return orders, [r for bucket in recent_by_partner.values() for r in bucket][:2000]

    def _opening_hours_payload(self, partner_ids):
        if not partner_ids or "conedera.partner.opening.hour" not in request.env.registry:
            return {}
        Hour = request.env["conedera.partner.opening.hour"]
        rows = Hour.search_read(
            [("partner_id", "in", partner_ids)],
            ["partner_id", "day_of_week", "opening_time", "closing_time"],
            order="day_of_week, opening_time, id", limit=5000,
        )
        result = {}
        for row in rows:
            key = row["partner_id"][0]
            result.setdefault(key, []).append({
                "day": row["day_of_week"], "from": row["opening_time"],
                "to": row["closing_time"],
            })
        return result

    def _require_census_role(self):
        if not is_census_user(request.env.user):
            raise AccessError("Su usuario no tiene permisos de Catastro Comercial.")

    def _visible_partner(self, partner_id):
        partner = request.env["res.partner"].search([
            ("id", "=", int(partner_id or 0)), ("census_active", "=", True),
        ], limit=1)
        if not partner:
            raise AccessError("El catastro no existe o no tiene permiso para consultarlo.")
        return partner

    def _partner_status(self, partner):
        partner.invalidate_recordset()
        return {
            "id": partner.id,
            "census_locked": bool(partner.census_locked),
            "census_can_edit_master": bool(partner.census_can_edit_master),
            "census_edit_state": partner.census_edit_state,
            "census_completion_pct": partner.census_completion_pct,
            "census_missing_requirements": partner.census_missing_requirements or "",
            "census_latest_unlock_state": partner.census_latest_unlock_state or "",
            "census_latest_unlock_reason": partner.census_latest_unlock_reason or "",
            "census_latest_unlock_review_note": partner.census_latest_unlock_review_note or "",
            "census_latest_unlock_valid_until": str(partner.census_latest_unlock_valid_until or ""),
            "census_unlock_until": str(partner.census_unlock_until or ""),
        }

    @http.route(["/catastro/app/lookup", "/conedera/app/lookup"], type="json", auth="user", methods=["POST"], readonly=True)
    def lookup(self, term=""):
        self._require_census_role()
        term = (term or "").strip()[:120]
        return request.env["conedera.census.customer.lookup.wizard"].search_global_candidates(term, limit=12)

    @http.route(["/catastro/app/catastro/status", "/conedera/app/catastro/status"], type="json", auth="user", methods=["POST"], readonly=True)
    def catastro_status(self, partner_id):
        self._require_census_role()
        return self._partner_status(self._visible_partner(partner_id))

    @http.route(["/catastro/app/catastro/request-unlock", "/conedera/app/catastro/request-unlock"], type="json", auth="user", methods=["POST"])
    def request_unlock(self, partner_id, reason=""):
        self._require_census_role()
        partner = self._visible_partner(partner_id)
        partner.action_request_census_unlock()  # Aplica las reglas originales de responsable y bloqueo.
        reason = (reason or "").strip()
        if len(reason) < 5:
            raise ValidationError("Explique el motivo de la solicitud (mínimo 5 caracteres).")
        wizard = request.env["conedera.census.unlock.wizard"].create({
            "partner_id": partner.id, "reason": reason,
        })
        wizard.action_submit()  # Comprueba solicitudes pendientes y notifica al supervisor.
        return self._partner_status(partner)

    @http.route(["/catastro/app/catastro/finish-edit", "/conedera/app/catastro/finish-edit"], type="json", auth="user", methods=["POST"])
    def finish_edit(self, partner_id):
        self._require_census_role()
        partner = self._visible_partner(partner_id)
        partner.action_finish_census_edit()
        return self._partner_status(partner)

    @http.route(["/catastro/app/bootstrap", "/conedera/app/bootstrap"], type="json", auth="user", methods=["POST"], readonly=True)
    def bootstrap(self):
        census_role = is_census_user(request.env.user)
        retail_role = request.env.user.has_group("conedera_odoo_census_mobile.group_quote_retail")
        if not census_role and not retail_role:
            raise AccessError("Solicite permisos de Catastro o Cotizador de tienda.")
        # El perfil exclusivo de Tienda no descarga el padrón de catastros,
        # visitas o ventas comerciales ajenas, aunque Odoo permita leer contactos.
        partners, visits, orders, products = [], [], [], []
        team = self._current_team() if census_role else False
        if census_role:
            Partner = request.env["res.partner"]
            partner_fields = self._readable_partner_fields()
            domain = [("census_active", "=", True)] if "census_active" in Partner._fields else [("customer_rank", ">", 0)]
            partners = Partner.search_read(domain, partner_fields, order="write_date desc, id desc", limit=1000)
            partner_ids = [x["id"] for x in partners]
            hour_map = self._opening_hours_payload(partner_ids)
            for partner in partners:
                partner["opening_hours"] = hour_map.get(partner["id"], [])
            visits = self._visit_payload(partner_ids)
            orders, products = self._sale_payload(partner_ids)
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
            "teams": self._team_payload() if census_role else [],
            "business_types": self._catalog_payload("conedera.census.business.type") if census_role else [],
            "mobile_brands": self._catalog_payload("conedera.census.mobile.brand") if census_role else [],
            "capabilities": {
                "visit_model": "conedera.census.visit" in request.env.registry,
                "business_type_model": "conedera.census.business.type" in request.env.registry,
                "mobile_brand_model": "conedera.census.mobile.brand" in request.env.registry,
                "opening_hour_model": "conedera.partner.opening.hour" in request.env.registry,
                "sales_action_id": (request.env.ref("sale.action_quotations_with_onboarding", raise_if_not_found=False) or request.env["ir.actions.act_window"]).id or False,
                "quote_create": request.env["sale.order"].check_access_rights("create", raise_exception=False),
                "quote_read": request.env["sale.order"].check_access_rights("read", raise_exception=False),
                "quote_update": request.env["sale.order"].check_access_rights("write", raise_exception=False),
                "quote_negotiable_price_supported": "negotiable_price" in request.env["sale.order.line"]._fields,
                "quote_can_negotiate": self._quote_can_negotiate(),
                "pwa_server_version": "18.0.1.5.25",
                "census_role": census_role,
                "quote_retail_role": retail_role,
                "quote_retail_enabled": (request.env.user.has_group("conedera_odoo_census_mobile.group_quote_retail")
                    and bool(request.env.company.catastro_retail_partner_id)),
                "quote_retail_partner": ({"id": request.env.company.catastro_retail_partner_id.commercial_partner_id.id,
                    "name": request.env.company.catastro_retail_partner_id.display_name,
                    "census_locked": True} if request.env.user.has_group("conedera_odoo_census_mobile.group_quote_retail")
                    and request.env.company.catastro_retail_partner_id else None),
                "quote_payment_options": self._quote_payment_options(),
                "quote_loyalty_supported": self._quote_loyalty_enabled(),
                "quote_product_promotions_supported": hasattr(request.env["sale.order"], "catastro_pwa_product_promotion_choices"),
                "quote_warehouses": self._quote_warehouses(),
                "quote_pricelists": self._quote_pricelists(),
                "quote_stock_supported": "stock.warehouse" in request.env.registry,
            },
        }

    def _quote_is_retail(self, partner_id):
        retail_partner = request.env.company.catastro_retail_partner_id
        return bool(retail_partner and int(partner_id or 0) in (retail_partner.id, retail_partner.commercial_partner_id.id)
                    and request.env.user.has_group("conedera_odoo_census_mobile.group_quote_retail"))

    def _quote_partner(self, partner_id):
        if self._quote_is_retail(partner_id):
            partner = request.env.company.catastro_retail_partner_id.commercial_partner_id
            if not partner.exists():
                raise ValidationError("Configure un cliente Consumidor Final válido en la compañía.")
            return partner
        self._require_census_role()
        partner = self._visible_partner(partner_id).commercial_partner_id
        if not partner.census_locked:
            raise ValidationError("Primero finalice y proteja el catastro para cotizar.")
        partner._ensure_census_ready_for_activity()
        if partner.census_company_id and partner.census_company_id != request.env.company:
            raise AccessError("Cambie a la compañía del catastro antes de crear una cotización.")
        return partner

    def _quote_can_negotiate(self, retail=False):
        # Un usuario que pertenezca a ambos grupos no debe negociar nunca
        # sobre una cotización de Consumidor Final. El permiso de negociación
        # sí puede usarse para los catastros normales.
        return (not retail and request.env.user.has_group(
            "conedera_odoo_census_mobile.group_quote_negotiator"))

    def _quote_payment_options(self):
        Option = request.env["catastro.quote.payment.option"]
        return [{"id": opt.id, "name": opt.name,
                 "surcharge_percent": opt.surcharge_percent,
                 "payment_term": opt.payment_term_id.display_name or ""}
                for opt in Option.search([("active", "=", True),
                                          ("company_id", "=", request.env.company.id)], order="sequence,id", limit=60)]

    def _quote_payment_option(self, id_value):
        if not id_value:
            return False
        try:
            opt_id = int(id_value)
        except (TypeError, ValueError):
            raise ValidationError("Condición de pago inválida.")
        opt = request.env["catastro.quote.payment.option"].search([
            ("id", "=", opt_id), ("company_id", "=", request.env.company.id),
            ("active", "=", True)], limit=1)
        if not opt:
            raise AccessError("La condición de pago no está disponible en esta empresa.")
        return opt

    def _quote_loyalty_enabled(self):
        return "sale.loyalty.reward.wizard" in request.env.registry and hasattr(request.env["sale.order"], "_update_programs_and_rewards")

    def _quote_access(self, operation):
        Sale = request.env["sale.order"]
        if not Sale.check_access_rights(operation, raise_exception=False):
            raise AccessError("Necesita permisos de Ventas para gestionar cotizaciones.")
        return Sale

    def _quote_warehouses(self):
        """Almacenes autorizados para COTIZAR, no para consulta general.

        La asignación es explícita por usuario y empresa. Una asignación no
        concede acceso a otros modelos; Odoo sigue validando las ACL de Ventas.
        Solo administración puede configurar asignaciones. Los administradores
        funcionales del sistema ven las bodegas de la compañía activa.
        """
        if "stock.warehouse" not in request.env.registry:
            return []
        company = request.env.company
        user = request.env.user
        domain = [("company_id", "=", company.id)]
        if not user.has_group("base.group_system"):
            Access = request.env["catastro.quote.warehouse.access"].sudo()
            assigned = Access.search([
                ("user_id", "=", user.id),
                ("warehouse_id.company_id", "=", company.id),
            ]).mapped("warehouse_id").ids
            # No habilitar todas las bodegas por ausencia de configuración.
            if not assigned:
                return []
            domain.append(("id", "in", assigned))
        # sudo limitado estrictamente a bodegas autorizadas, para que el perfil
        # Tienda pueda operar aunque no tenga permisos generales de Inventario.
        records = request.env["stock.warehouse"].sudo().search(domain, order="name", limit=100)
        return [{"id": w.id, "name": w.display_name} for w in records]

    def _quote_warehouse(self, warehouse_id):
        if not warehouse_id:
            return False
        allowed = {w["id"] for w in self._quote_warehouses()}
        try:
            warehouse_id = int(warehouse_id)
        except (ValueError, TypeError):
            raise ValidationError("Identificador de almacén inválido.")
        if warehouse_id not in allowed:
            raise AccessError("Almacén no habilitado para cotizar con su usuario en esta empresa.")
        # Ya validado contra asignación por usuario y empresa. Los vendedores
        # pueden necesitar leer configuración básica sin ACL general de Stock.
        return request.env["stock.warehouse"].sudo().browse(warehouse_id)

    def _quote_stock_map(self, products, warehouse):
        """Saldo *físico* de stock.quant en ubicaciones internas del almacén.

        Evita el falso cero de qty_available con contexto heredado/alterado por
        personalizaciones. El almacén y variantes son validados antes; la elevación
        de stock.quant está acotada EXCLUSIVAMENTE a esos productos, compañía y
        al subárbol de ubicaciones internas del almacén elegido. No expone quants.
        """
        if not warehouse:
            raise ValidationError("Seleccione una bodega antes de consultar existencias.")
        if not warehouse.view_location_id:
            raise ValidationError("La bodega %s no tiene ubicación raíz configurada." % warehouse.display_name)
        if "stock.quant" not in request.env.registry:
            raise ValidationError("El módulo Inventario no está instalado en Odoo.")
        result = {p.id: 0.0 for p in products}
        if not result:
            return result
        Quants = request.env["stock.quant"].sudo().with_company(request.env.company)
        # El usuario solo puede seleccionar bodegas visibles de la compañía actual.
        # Para evitar fugas, siempre acotar producto, compañía y ubicaciones internas.
        domain = [
            ("product_id", "in", list(result)),
            ("location_id", "child_of", warehouse.view_location_id.id),
            ("location_id.usage", "=", "internal"),
            ("company_id", "in", [False, request.env.company.id]),
        ]
        # Agrupación SQL nativa de Odoo 18: una consulta, sin descargar cada quant.
        for product_rec, quantity in Quants._read_group(domain, ['product_id'], ['quantity:sum']):
            result[product_rec.id] = float(quantity)
        for product in products:
            if product.type == "service":
                result[product.id] = 0.0
            if not math.isfinite(result[product.id]):
                raise ValidationError("Cantidad de stock inválida para %s." % product.display_name)
        return result

    def _quote_stock_visibility_maps(self, products):
        """Existencias informativas por bodega y ubicación, en una sola agregación.

        Tienda: bodegas de la compañía activa (aunque no pueda cotizar allí).
        Campo: exclusivamente bodegas asignadas para cotizar.
        No mezcla compañías ni habilita utilizar otro almacén en la proforma.
        """
        product_ids = products.ids
        location_rows = {pid: [] for pid in product_ids}
        warehouse_rows = {pid: [] for pid in product_ids}
        if not product_ids or "stock.quant" not in request.env.registry:
            return location_rows, warehouse_rows
        user = request.env.user
        company = request.env.company
        retail = user.has_group("conedera_odoo_census_mobile.group_quote_retail")
        authorized = {row["id"] for row in self._quote_warehouses()}
        warehouse_domain = [("company_id", "=", company.id)]
        if not retail:
            if not authorized:
                return location_rows, warehouse_rows
            warehouse_domain.append(("id", "in", list(authorized)))
        # Los datos sudo se limitan a una compañía, los productos del lote y
        # las raíces de bodegas visibles. Nunca se devuelven quants individuales.
        warehouses = request.env["stock.warehouse"].sudo().search(
            warehouse_domain, order="name"
        ).filtered(lambda w: bool(w.view_location_id))
        if not warehouses:
            return location_rows, warehouse_rows
        roots = [(w, w.view_location_id.parent_path or "%s/" % w.view_location_id.id)
                 for w in warehouses]
        root_ids = [w.view_location_id.id for w in warehouses]
        quantities = {(pid, w.id): 0.0 for pid in product_ids for w in warehouses}
        Quant = request.env["stock.quant"].sudo().with_company(company)
        domain = [
            ("product_id", "in", product_ids),
            ("location_id", "child_of", root_ids),
            ("location_id.usage", "=", "internal"),
            ("location_id.company_id", "in", [False, company.id]),
            ("company_id", "in", [False, company.id]),
        ]
        for product, location, quantity in Quant._read_group(
            domain, ["product_id", "location_id"], ["quantity:sum"]
        ):
            if not product or not location or not math.isfinite(float(quantity)):
                continue
            path = location.parent_path or "%s/" % location.id
            # Ante raíces anidadas, atribuir el saldo solo a la raíz más cercana.
            matches = [(w, root_path) for w, root_path in roots if path.startswith(root_path)]
            if not matches:
                continue
            warehouse = max(matches, key=lambda item: len(item[1]))[0]
            qty = float(quantity)
            quantities[(product.id, warehouse.id)] += qty
            if float_compare(qty, 0, precision_rounding=product.uom_id.rounding or 0.01) > 0:
                location_rows[product.id].append({
                    "name": location.complete_name or location.display_name,
                    "quantity": qty,
                    "warehouse_id": warehouse.id,
                    "warehouse_name": warehouse.display_name,
                })
        for product in products:
            warehouse_rows[product.id] = [{
                "id": w.id,
                "name": w.display_name,
                "quantity": quantities[(product.id, w.id)],
                "can_quote": w.id in authorized or user.has_group("base.group_system"),
            } for w in warehouses]
            location_rows[product.id].sort(key=lambda item: (
                item["warehouse_name"], -item["quantity"], item["name"]
            ))
        return location_rows, warehouse_rows

    def _quote_stock_locations_map(self, products):
        # Se conserva el método privado por compatibilidad interna.
        return self._quote_stock_visibility_maps(products)[0]

    def _quote_stock_on_hand(self, product, warehouse):
        return self._quote_stock_map(product, warehouse).get(product.id, 0.0)

    @http.route(["/catastro/app/quote/stock-diagnostic", "/conedera/app/quote/stock-diagnostic"],
                type="json", auth="user", methods=["POST"], readonly=True)
    def quote_stock_diagnostic(self, partner_id, product_id, warehouse_id):
        self._quote_partner(partner_id)
        self._quote_access("read")
        warehouse = self._quote_warehouse(warehouse_id)
        product = self._quote_find_products(product_ids=[int(product_id)])
        if not product or not warehouse:
            raise ValidationError("Producto o bodega no disponibles.")
        quant_stock = self._quote_stock_on_hand(product, warehouse)
        qty_context = product.with_company(request.env.company).with_context(
            warehouse=warehouse.id, allowed_company_ids=[request.env.company.id]).qty_available
        return {"product": product.display_name, "warehouse": warehouse.display_name,
                "company": request.env.company.name, "location": warehouse.view_location_id.complete_name,
                "stock_internal": quant_stock, "stock_context": float(qty_context),
                "note": "Stock físico en ubicaciones internas de esta bodega. No suma otras bodegas ni reserva ventas."}

    @http.route("/catastro/app/quote/stock-audit", type="json", auth="user", methods=["POST"], readonly=True)
    def quote_stock_audit(self, partner_id, warehouse_id, term=""):
        """Diagnóstico legible al usuario, nunca nombres de otras bodegas.

        Se compara total de compañía con el subárbol de ubicaciones de la bodega.
        El stock global se muestra solo para productos ya visibles para ventas.
        """
        self._quote_partner(partner_id)
        self._quote_access("read")
        term = (term or "").strip()[:90]
        if len(term) < 2:
            raise ValidationError("Busque al menos dos caracteres del producto.")
        wh = self._quote_warehouse(warehouse_id)
        if not wh:
            raise ValidationError("Seleccione la bodega para revisar existencias.")
        products = self._quote_find_products(term=term)[:20]
        stock = self._quote_stock_map(products, wh)
        retail = request.env.user.has_group("conedera_odoo_census_mobile.group_quote_retail")
        return [{"id": product.id, "name": product.display_name,
                 "stock_warehouse": stock[product.id],
                 "stock_company": (float(product.with_company(request.env.company).qty_available)
                                   if retail else None),
                 "warehouse": wh.display_name, "root_location": wh.view_location_id.complete_name,
                 "uom": product.uom_id.name}
                for product in products]

    def _quote_pricelists(self):
        Pricelist = request.env["product.pricelist"]
        if not Pricelist.check_access_rights("read", raise_exception=False):
            return []
        return [{"id": pl.id, "name": pl.display_name} for pl in Pricelist.search([
            ("active", "=", True), ("company_id", "in", [False, request.env.company.id])
        ], order="sequence, name", limit=120)]

    def _quote_pricelist(self, partner, requested_id=None):
        """Misma compañía y defaults que sale.order; solo listas visibles al usuario."""
        Sale = self._quote_access("read").with_company(request.env.company)
        draft = Sale.new({"company_id": request.env.company.id, "partner_id": partner.id})
        pricelist = draft.pricelist_id or partner.with_company(request.env.company).property_product_pricelist
        if requested_id:
            if not self._quote_can_negotiate():
                raise AccessError("La selección de listas de precios requiere el perfil de negociación.")
            allowed = {pl["id"] for pl in self._quote_pricelists()}
            try:
                requested_id = int(requested_id)
            except (ValueError, TypeError):
                raise ValidationError("Identificador de lista de precios inválido.")
            if requested_id not in allowed:
                raise AccessError("La lista de precios seleccionada no está disponible en esta compañía.")
            pricelist = request.env["product.pricelist"].browse(requested_id)
        if not pricelist:
            raise ValidationError("El cliente no tiene una lista de precios de Ventas disponible.")
        return pricelist

    def _quote_payment_tax_previews(self, partner, product, pricelist_price, pricelist, fiscal_position, options, discount_percent=0.0):
        """Precios unitarios de consulta, con impuestos por forma de pago.

        Utilizar exactamente el motor fiscal de Ventas: adaptar los impuestos
        incluidos del producto a la posición fiscal, aplicar el cargo unitario
        redondeado en la moneda del pedido y ejecutar compute_all. No se
        modifica ni crea ninguna cotización durante la consulta del catálogo.

        Las recompensas Loyalty y los precios negociados se aplican al guardar
        el pedido, por lo que esta vista es orientativa (lista vigente).
        """
        company = request.env.company
        product = product.with_company(company)
        original_taxes = product.taxes_id._filter_taxes_by_company(company)
        mapped_taxes = fiscal_position.map_tax(original_taxes) if fiscal_position else original_taxes
        currency = pricelist.currency_id
        base_unit = product._get_tax_included_unit_price_from_price(
            pricelist_price, product_taxes=original_taxes,
            fiscal_position=fiscal_position,
        )
        def final_amount(percent):
            # Mismo redondeo que catastro_recompute_surcharge(), no un
            # porcentaje aproximado sobre el precio de etiqueta del navegador.
            fee = currency.round(base_unit * percent / 100.0)
            applied_unit = base_unit + fee
            # Mismo orden que sale.order.line: precio unitario con la forma
            # de pago, descuento de la línea y luego impuestos de Odoo.
            # No descontar IVA manualmente: puede haber impuestos incluidos,
            # posiciones fiscales y reglas de redondeo por compañía.
            discounted_unit = applied_unit * (1.0 - discount_percent / 100.0)
            amounts = mapped_taxes.compute_all(
                discounted_unit, currency=currency, quantity=1.0,
                product=product, partner=partner,
            )
            return currency.round(amounts['total_included'])

        return {
            'tax_included_base': final_amount(0.0),
            'payment_prices': [
                {'id': option.id, 'name': option.name,
                 'tax_included_price': final_amount(option.surcharge_percent)}
                for option in options
            ],
            'tax_price_source': 'server',
        }

    def _quote_catalog_rows(self, partner, products, quantities=None, warehouse_id=None, pricelist_id=None,
                            only_in_stock=False, max_results=60):
        quantities = quantities or {}
        warehouse = self._quote_warehouse(warehouse_id)
        if not warehouse:
            raise ValidationError("Seleccione una bodega para consultar stock real y precios.")
        pricelist = self._quote_pricelist(partner, pricelist_id)
        result = []
        stock_map = self._quote_stock_map(products, warehouse)
        stock_locations, stock_warehouses = self._quote_stock_visibility_maps(products)
        # La compañía, la posición fiscal y las formas de pago se consultan
        # una vez por lote (hasta 60 tarjetas). No se utiliza sudo para
        # consultar productos, compañías o formas de pago no permitidas.
        fiscal_position = request.env['account.fiscal.position'].with_company(
            request.env.company)._get_fiscal_position(partner)
        options = request.env['catastro.quote.payment.option'].search([
            ('active', '=', True),
            ('company_id', '=', request.env.company.id),
        ], order='sequence,id', limit=60)
        for product in products:
            qty = float(quantities.get(product.id, 1.0))
            if not math.isfinite(qty) or qty <= 0 or qty > 100000:
                raise ValidationError("Cantidad inválida para calcular precios.")
            onhand = stock_map[product.id]
            if only_in_stock and float_compare(onhand, 0, precision_rounding=min(product.uom_id.rounding or 0.000001, 0.000001)) <= 0:
                continue
            # Motor nativo de listas, considerando cliente y cantidad.
            price = pricelist._get_product_price(product, qty, partner=partner, uom=product.uom_id)
            tax_preview = self._quote_payment_tax_previews(
                partner, product, price, pricelist, fiscal_position, options,
            )
            result.append({
                **tax_preview,
                "id": product.id, "name": product.display_name, "code": product.default_code or "",
                "category_id": product.categ_id.id if product.categ_id else False,
                "category_name": product.categ_id.name if product.categ_id else "Sin categoría",
                "uom": product.uom_id.name, "price": float(price),
                "currency": pricelist.currency_id.symbol or pricelist.currency_id.name,
                "pricelist": pricelist.display_name, "qty_priced": qty,
                "stock_qty": onhand, "stock_kind": "physical", "stock_label": warehouse.display_name,
                "stock_locations": stock_locations.get(product.id, []),
                "stock_warehouses": stock_warehouses.get(product.id, []),
                "stock_location_scope": ("company" if request.env.user.has_group(
                    "conedera_odoo_census_mobile.group_quote_retail") else "authorized"),
                "warehouse_id": warehouse.id,
                "image_url": "/catastro/app/quote/image/%d?partner_id=%d&size=small" % (product.id, partner.id),
                "zoom_url": "/catastro/app/quote/image/%d?partner_id=%d&size=large" % (product.id, partner.id),
                "has_image": bool(product.image_128) if "image_128" in product._fields else False,
            })
            if only_in_stock and len(result) >= max_results:
                break
        return result

    def _quote_find_products(self, product_ids=None, term=""):
        Product = request.env["product.product"]
        if not Product.check_access_rights("read", raise_exception=False):
            raise AccessError("No dispone de permisos para consultar productos.")
        domain = [("sale_ok", "=", True), ("active", "=", True)]
        if product_ids is not None:
            domain.append(("id", "in", product_ids))
        else:
            domain += ["|", ("name", "ilike", term), ("default_code", "ilike", term)]
        if "company_id" in Product._fields:
            domain = ["|", ("company_id", "=", False),
                      ("company_id", "=", request.env.company.id)] + domain
        return Product.search(domain, order="name, id", limit=250 if product_ids is None else 120)

    def _quote_recent_products(self, partner, warehouse, pricelist_id):
        """40 productos recientes con existencia en ESTA bodega; búsqueda normal sin límite."""
        Line = request.env["sale.order.line"]
        if not Line.check_access_rights("read", raise_exception=False):
            return []
        domain = [("order_id.company_id", "=", request.env.company.id),
                  ("order_id.partner_id.commercial_partner_id", "=", partner.id),
                  ("order_id.state", "!=", "cancel"),
                  ("product_id", "!=", False),
                  ("display_type", "=", False)]
        if "reward_id" in Line._fields:
            domain.append(("reward_id", "=", False))
        try:
            # IDs recientes, sin generar un JOIN de miles de cotizaciones.
            past_lines = Line.search(domain, order="id desc", limit=320)
        except AccessError:
            return []
        ids = []
        for line in past_lines:
            pid = line.product_id.id
            if pid and pid not in ids:
                ids.append(pid)
            if len(ids) >= 100:
                break
        if not ids:
            return []
        available = self._quote_find_products(product_ids=ids)
        by_id = {product.id: product for product in available}
        ordered = request.env["product.product"].browse([pid for pid in ids if pid in by_id])
        return self._quote_catalog_rows(partner, ordered, warehouse_id=warehouse.id,
                                        pricelist_id=pricelist_id, only_in_stock=True,
                                        max_results=40)

    @http.route(["/catastro/app/quote/products", "/conedera/app/quote/products"], type="json", auth="user", methods=["POST"], readonly=True)
    def quote_products(self, term="", partner_id=None, warehouse_id=None, pricelist_id=None):
        partner = self._quote_partner(partner_id)
        self._quote_access("read")
        term = (term or "").strip()[:90]
        if len(term) == 1:
            return []
        warehouse = self._quote_warehouse(warehouse_id)
        if not warehouse:
            raise ValidationError("Seleccione una bodega para consultar productos.")
        if not term:
            recent = self._quote_recent_products(partner, warehouse, pricelist_id)
            if len(recent) >= 40:
                return recent[:40]
            # Completar con productos disponibles en la bodega; evitar duplicar
            # los recientes. No cargar el catálogo completo al abrir la PWA.
            used_ids = {row["id"] for row in recent}
            ordinary = self._quote_find_products(term="")
            extras = self._quote_catalog_rows(partner, ordinary,
                warehouse_id=warehouse.id, pricelist_id=pricelist_id,
                only_in_stock=True, max_results=40)
            return (recent + [row for row in extras if row["id"] not in used_ids])[:40]
        products = self._quote_find_products(term=term)
        return self._quote_catalog_rows(partner, products, warehouse_id=warehouse.id,
                                        pricelist_id=pricelist_id, only_in_stock=True)

    @http.route(["/catastro/app/quote/prices", "/conedera/app/quote/prices"], type="json", auth="user", methods=["POST"], readonly=True)
    def quote_prices(self, partner_id, lines=None, warehouse_id=None, pricelist_id=None):
        """Recalcular la lista para las cantidades seleccionadas; nunca aceptar precios del cliente."""
        partner = self._quote_partner(partner_id)
        self._quote_access("read")
        if not isinstance(lines, list) or len(lines) > 60:
            raise ValidationError("Seleccione como máximo 60 productos.")
        qty_by_id = {}
        for line in lines:
            if not isinstance(line, dict):
                raise ValidationError("Línea inválida.")
            try:
                pid, qty = int(line["product_id"]), float(line["qty"])
            except (ValueError, TypeError, KeyError):
                raise ValidationError("Producto o cantidad inválido.")
            if pid <= 0 or not math.isfinite(qty) or not 0 < qty <= 100000:
                raise ValidationError("Cantidad fuera de rango.")
            qty_by_id[pid] = qty
        products = self._quote_find_products(product_ids=list(qty_by_id))
        if set(products.ids) != set(qty_by_id):
            raise AccessError("Algún producto no está disponible para venta.")
        return self._quote_catalog_rows(partner, products, quantities=qty_by_id, warehouse_id=warehouse_id, pricelist_id=pricelist_id)

    @http.route("/catastro/app/quote/image/<int:product_id>", type="http", auth="user", methods=["GET"], sitemap=False)
    def quote_product_image(self, product_id, partner_id=None, size="small", **kwargs):
        # Las imágenes de productos respetan el acceso de producto y catastro del usuario.
        self._quote_partner(partner_id)
        self._quote_access("read")
        product = self._quote_find_products(product_ids=[product_id])
        if not product:
            return request.not_found()
        field = "image_1920" if size == "large" else "image_128"
        raw = product[field] if field in product._fields else False
        if not raw:
            return request.not_found()
        content = base64.b64decode(raw)
        mimetype = ("image/jpeg" if content.startswith(b"\xff\xd8\xff") else
                    "image/png" if content.startswith(b"\x89PNG") else
                    "image/webp" if content.startswith(b"RIFF") else "application/octet-stream")
        return request.make_response(content, headers=[
            ("Content-Type", mimetype), ("Cache-Control", "private, no-store"),
            ("X-Content-Type-Options", "nosniff")])

    def _quote_line_editable(self, line):
        return bool(line.product_id and not line.display_type
                    and not line.is_catastro_payment_surcharge
                    and not ("reward_id" in line._fields and line.reward_id)
                    and not ("is_reward_line" in line._fields and line.is_reward_line)
                    and not ("is_delivery" in line._fields and line.is_delivery))

    def _quote_radis_status(self, order):
        """Informative view of the original Radis integration; no duplicate API client.

        This is intentionally optional: companies not using stock_api_assing are
        not forced to install that addon just to use Catastro PWA.
        """
        Sale = request.env["sale.order"]
        if "export_send" not in Sale._fields or not hasattr(Sale, "action_export_to_radis"):
            return {"installed": False, "can_send": False}
        authorized = bool(request.env.user.has_group("base.group_user")
                          and request.env["sale.order"].check_access_rights("write", raise_exception=False))
        allowed_wh = bool(order.warehouse_id and order.warehouse_id.id in {
            wh["id"] for wh in self._quote_warehouses()
        })
        export_state = order.export_send or "P"
        percentage_lines = order.order_line.filtered(
            lambda l: l.product_id and not l.display_type and (
                abs(l.discount or 0.0) > 0.000001 or (
                    'catastro_payment_surcharge_applied' in l._fields
                    and l.catastro_payment_surcharge_applied
                    and abs(l.catastro_payment_surcharge_percent or 0.0) > 0.000001
                )
            )
        )
        supports_percentages = (
            hasattr(order, '_catastro_radis_bridge_version')
            and order._catastro_radis_bridge_version() >= 1
        )
        percentage_contract_pending = bool(percentage_lines and not supports_percentages)
        return {
            "installed": True,
            "authorized": authorized,
            "percentage_contract_pending": percentage_contract_pending,
            "status": export_state,
            "label": {"P": "Pendiente de envío", "N": "No enviado", "E": "Enviado a Radis"}.get(
                export_state, "Estado no disponible"),
            "can_send": bool(
                authorized and order.state == "draft" and export_state != "E"
                and request.env["sale.order"].check_access_rights("write", raise_exception=False)
                and allowed_wh and not percentage_contract_pending
                and order.order_line.filtered(
                    lambda l: l.product_id and not l.display_type
                )
            ),
        }

    def _quote_record_payload(self, order):
        # The caller already fetched the order under normal user ACLs / record rules.
        return {
            "id": order.id,
            "name": order.name,
            "partner_id": order.partner_id.id,
            "partner_name": order.partner_id.display_name,
            "company_name": order.company_id.name,
            "company_id": order.company_id.id,
            "warehouse_id": order.warehouse_id.id if "warehouse_id" in order._fields else False,
            "pricelist_id": order.pricelist_id.id,
            "payment_option_id": order.catastro_payment_option_id.id if order.catastro_payment_option_id else False,
            "write_date": str(order.write_date or ""),
            "can_edit": (order.state == "draft"
                         and not ("export_send" in order._fields and order.export_send == "E")
                         and request.env["sale.order"].check_access_rights("write", raise_exception=False)
                         and request.env["sale.order.line"].check_access_rights("write", raise_exception=False)),
            "visit_id": order.census_visit_id.id if order.census_visit_id else False,
            "state": order.state,
            "date_order": str(order.date_order or ""),
            "client_order_ref": order.client_order_ref or "",
            "currency": order.currency_id.symbol or order.currency_id.name,
            "radis": self._quote_radis_status(order),
            "amount_untaxed": order.amount_untaxed,
            "amount_tax": order.amount_tax,
            "amount_total": order.amount_total,
            "payment_option": order.catastro_payment_option_id.name if order.catastro_payment_option_id else "",
            "surcharge_percent": order.catastro_payment_option_id.surcharge_percent if order.catastro_payment_option_id else 0,
            "loyalty_enabled": self._quote_loyalty_enabled(),
            "loyalty_rewards": self._quote_available_rewards(order),
            "lines": [{"id": line.id, "product_id": line.product_id.id,
                       "editable": self._quote_line_editable(line),
                       "name": line.name,
                       "product_name": line.product_id.display_name if line.product_id else "",
                       "qty": line.product_uom_qty,
                       "uom": line.product_uom.name if line.product_uom else "",
                       "price_unit": line.price_unit, "discount": line.discount,
                       "promo_reward_id": (line.catastro_pwa_promo_reward_id.id if "catastro_pwa_promo_reward_id" in line._fields else False),
                       "promo_name": (line.catastro_pwa_promo_reward_id.description if "catastro_pwa_promo_reward_id" in line._fields and line.catastro_pwa_promo_reward_id else ""),
                       "negotiable_price": (line.negotiable_price if "negotiable_price" in line._fields else None),
                       "payment_base_price_unit": line.catastro_payment_base_price_unit if line.catastro_payment_surcharge_applied else line.price_unit,
                       "payment_surcharge_percent": line.catastro_payment_surcharge_percent,
                       "payment_surcharge_unit_amount": line.catastro_payment_surcharge_unit_amount,
                       "subtotal": line.price_subtotal, "total": line.price_total,
                       "surcharge": bool(line.is_catastro_payment_surcharge),
                       "loyalty_reward": bool("reward_id" in line._fields and line.reward_id),
                       "taxes": line.tax_id.mapped("name")}
                      for line in order.order_line if not line.display_type],
        }

    @http.route(["/catastro/app/quote/read", "/conedera/app/quote/read"], type="json", auth="user", methods=["POST"], readonly=True)
    def quote_read(self, quote_id):
        Sale = self._quote_access("read")
        # Search instead of sudo/browse to respect record rules and company isolation.
        order = Sale.search([("id", "=", int(quote_id or 0)),
                             ("company_id", "=", request.env.company.id)], limit=1)
        if not order:
            raise AccessError("Cotización no disponible para su usuario o compañía.")
        if not self._quote_is_retail(order.partner_id.commercial_partner_id.id):
            self._require_census_role()
            self._visible_partner(order.partner_id.commercial_partner_id.id)
        return self._quote_record_payload(order)


    @http.route("/catastro/app/quote/radis/send", type="json", auth="user", methods=["POST"])
    def quote_send_radis(self, quote_id, base_write_date=None):
        """Send saved quotation through stock_api_assing's original method.

        Never queue Radis submissions offline.  A duplicate external submission
        cannot be safely undone if the external API confirmed the first one.
        """
        Sale = self._quote_access("write")
        if "export_send" not in Sale._fields or not hasattr(Sale, "action_export_to_radis"):
            raise UserError("La integración Radis no está instalada en Odoo.")
        try:
            order_id = int(quote_id)
        except (TypeError, ValueError):
            raise ValidationError("Identificador de cotización inválido.")
        order = Sale.search([
            ("id", "=", order_id), ("company_id", "=", request.env.company.id)
        ], limit=1)
        if not order:
            raise AccessError("Cotización no disponible para su usuario o empresa.")
        # Enforce both the user's Odoo write rule and the PWA's customer scope.
        order.check_access_rule("write")
        if not self._quote_is_retail(order.partner_id.commercial_partner_id.id):
            self._require_census_role()
            self._visible_partner(order.partner_id.commercial_partner_id.id)
        if order.state != "draft" or order.export_send == "E":
            raise ValidationError("Solo puede enviar a Radis una cotización en borrador y no enviada.")
        if not base_write_date or str(order.write_date or "") != str(base_write_date):
            raise ValidationError("La proforma cambió en Odoo. Recárguela y revise los importes antes de enviarla.")
        if not order.warehouse_id:
            raise ValidationError("Seleccione la bodega del pedido antes de enviarlo a Radis.")
        self._quote_warehouse(order.warehouse_id.id)  # Bodega autorizada para este usuario.
        # The original sender exports every product line.  Loyalty rewards that
        # use extra product lines cannot be represented as sold merchandise.
        reward_lines = order.order_line.filtered(lambda l:
            l.product_id and not l.display_type and (
                ("reward_id" in l._fields and bool(l.reward_id)) or
                ("is_reward_line" in l._fields and bool(l.is_reward_line))
            ))
        if reward_lines:
            raise ValidationError(
                "La proforma contiene recompensas Loyalty como líneas de producto. "
                "No se enviarán como mercancía a Radis; revise el tratamiento de estas recompensas."
            )
        # Compatibilidad en despliegues mixtos: versiones antiguas de Radis
        # no incluyen el porcentaje de descuento en su JSON. Solo enviar
        # descuentos cuando el módulo Radis declara el nuevo formato.
        percentage_lines = order.order_line.filtered(lambda l:
            l.product_id and not l.display_type and (
                abs(l.discount or 0.0) > 0.000001 or (
                    'catastro_payment_surcharge_applied' in l._fields
                    and l.catastro_payment_surcharge_applied
                    and abs(l.catastro_payment_surcharge_percent or 0.0) > 0.000001
                )
            ))
        supports_percentages = (
            hasattr(order, '_catastro_radis_bridge_version')
            and order._catastro_radis_bridge_version() >= 1
        )
        if percentage_lines and not supports_percentages:
            raise ValidationError(
                "Instale y actualice catastro_radis_percentage_bridge antes de enviar "
                "proformas con descuentos o incrementos. El módulo stock_api_assing "
                "original se mantiene sin modificaciones."
            )
        # There is deliberately no direct HTTP call to Radis in the PWA.
        # Stock_api_assing creates the payload, checks the API response and
        # marks the order export_send='E', state='async' after success.
        order.action_export_to_radis()
        order.invalidate_recordset(["state", "export_send", "write_date"])
        if order.export_send != "E" or order.state != "async":
            raise UserError("Odoo no confirmó el estado enviado a Radis. Compruebe el resultado antes de reintentar.")
        return {
            "ok": True,
            "message": "La proforma %s fue aceptada por Radis." % order.name,
            "quote": self._quote_record_payload(order),
        }

    def _retail_quote_partner(self):
        """Check the active company and the *retail* group for every endpoint.

        No sudo; the caller's sale.order ACL and record rules must also apply.
        """
        if not request.env.user.has_group('conedera_odoo_census_mobile.group_quote_retail'):
            raise AccessError('Necesita el perfil Cotizador de tienda.')
        partner = request.env.company.catastro_retail_partner_id
        if not partner:
            raise ValidationError('Configure Consumidor Final para la empresa activa.')
        return partner.commercial_partner_id

    def _retail_quote_record(self, quote_id, operation='read'):
        partner = self._retail_quote_partner()
        Sale = self._quote_access(operation)
        try:
            order_id = int(quote_id)
        except (ValueError, TypeError):
            raise ValidationError('Cotización inválida.')
        order = Sale.search([
            ('id', '=', order_id),
            ('company_id', '=', request.env.company.id),
            ('partner_id.commercial_partner_id', '=', partner.id),
        ], limit=1)
        if not order:
            raise AccessError('La proforma no pertenece al Consumidor Final de esta empresa o no tiene acceso.')
        return order

    @http.route('/catastro/app/quote/retail/search', type='json', auth='user', methods=['POST'], readonly=True)
    def quote_retail_search(self, term='', offset=0):
        partner = self._retail_quote_partner()
        Sale = self._quote_access('read')
        text = str(term or '').strip()[:100]
        try:
            offset = int(offset or 0)
        except (ValueError, TypeError):
            offset = 0
        offset = max(0, min(1000, offset))
        domain = [
            ('company_id', '=', request.env.company.id),
            ('partner_id.commercial_partner_id', '=', partner.id),
            ('state', 'in', ['draft', 'sent', 'async']),
        ]
        if text:
            domain += ['|', ('name', 'ilike', text), ('client_order_ref', 'ilike', text)]
        orders = Sale.search(domain, order='date_order desc, id desc', limit=21, offset=offset)
        return {
            'items': [{
                'id': so.id, 'name': so.name, 'date_order': str(so.date_order or ''),
                'state': so.state, 'amount_total': so.amount_total,
                'currency': so.currency_id.symbol or so.currency_id.name,
                'client_order_ref': so.client_order_ref or '',
                'can_duplicate': (so.state in ('draft', 'sent')
                                  and not ('export_send' in so._fields and so.export_send == 'E')
                                  and so.warehouse_id.id in {w['id'] for w in self._quote_warehouses()}
                                  and Sale.check_access_rights('create', raise_exception=False)),
            } for so in orders[:20]],
            'has_more': len(orders) > 20, 'offset': offset,
        }

    @http.route('/catastro/app/quote/retail/duplicate', type='json', auth='user', methods=['POST'])
    def quote_retail_duplicate(self, quote_id):
        source = self._retail_quote_record(quote_id, 'read')
        Sale = self._quote_access('create')
        if not source.warehouse_id:
            raise ValidationError('La proforma original no tiene bodega asignada.')
        self._quote_warehouse(source.warehouse_id.id)
        if source.state not in ('draft', 'sent'):
            raise ValidationError('Solo puede duplicar proformas en borrador o enviadas.')
        # Do not let a retail profile reproduce a specially negotiated price.
        regular = source.order_line.filtered(self._quote_line_editable)
        if 'negotiable_price' in request.env['sale.order.line']._fields and any(
                line.negotiable_price for line in regular):
            raise AccessError('Esta proforma tiene precios negociados. Solicite autorización para duplicarla.')
        if not regular:
            raise ValidationError('La proforma original no contiene productos para duplicar.')
        original_options = source.catastro_payment_option_id
        if original_options and original_options.company_id != request.env.company:
            raise ValidationError('La condición de pago no pertenece a esta empresa.')
        if original_options and not original_options.active:
            raise ValidationError('La condición de pago de la proforma original ya no está disponible. Cree una nueva cotización y elija otra forma de pago.')
        # Native copy keeps installed sale.order and sale.order.line extensions.
        # Keep it as a new draft; never overwrite / cancel the source.
        duplicated = source.with_company(request.env.company).copy(default={
            'partner_id': self._retail_quote_partner().id,
            'company_id': request.env.company.id,
            'user_id': request.env.user.id,
            'state': 'draft',
            'date_order': fields.Datetime.now(),
            'client_order_ref': False,
            'origin': source.name,
            'census_originated': False,
            'census_visit_id': False,
            'catastro_payment_option_id': False,
        })
        if duplicated.company_id != request.env.company or duplicated.state != 'draft':
            raise ValidationError('Odoo no pudo crear un nuevo borrador válido.')
        if not duplicated.order_line.filtered(self._quote_line_editable):
            raise ValidationError('La copia no conservó productos. Revise la personalización de Ventas.')
        # The source unit price already includes any old payment fee. The audit
        # base is copy=False, so restore the original base by matching line
        # signatures before applying the selected payment option on the copy.
        before = list(source.order_line.filtered(self._quote_line_editable))
        after = list(duplicated.order_line.filtered(self._quote_line_editable))
        if len(before) != len(after) or any(
                a.product_id != b.product_id or a.product_uom_qty != b.product_uom_qty
                for a, b in zip(before, after)):
            raise ValidationError('La duplicación cambió productos u orden de líneas. No se guardó una copia incompleta.')
        for old, new in zip(before, after):
            base = (old.catastro_payment_base_price_unit
                    if old.catastro_payment_surcharge_applied else old.price_unit)
            values = {}
            if duplicated.currency_id.compare_amounts(new.price_unit, base):
                values['price_unit'] = base
            # copy=False strips the promo marker but not the discount field.
            # Restore original non-promo discount to avoid stacking rewards.
            if 'catastro_pwa_promo_reward_id' in old._fields and old.catastro_pwa_promo_reward_id:
                values['discount'] = old.catastro_pwa_promo_base_discount
            if values:
                new.write(values)
        if original_options:
            duplicated.write({'catastro_payment_option_id': original_options.id})
        if self._quote_loyalty_enabled():
            # Recompensas de una copia anterior no se deben contar dos veces.
            reward_lines = duplicated.order_line.filtered(
                lambda line: ('reward_id' in line._fields and line.reward_id) or
                             ('is_reward_line' in line._fields and line.is_reward_line))
            if reward_lines:
                reward_lines.unlink()
            duplicated._update_programs_and_rewards()
        if hasattr(duplicated, "catastro_pwa_apply_product_promotions"):
            duplicated.catastro_pwa_apply_product_promotions()
        else:
            duplicated.catastro_recompute_surcharge()
        return {'id': duplicated.id, 'name': duplicated.name,
                'message': 'Copia creada como borrador; revise stock y promociones antes de confirmar.'}

    @http.route('/catastro/app/quote/pdf/<int:quote_id>', type='http', auth='user', methods=['GET'], sitemap=False)
    def quote_pdf(self, quote_id, **kwargs):
        # Use the active user's ACLs, record rules and company. Never publish
        # unprotected report attachments or a link accessible to outsiders.
        Sale = self._quote_access('read')
        order = Sale.search([('id', '=', quote_id),
                             ('company_id', '=', request.env.company.id)], limit=1)
        if not order:
            raise AccessError('No tiene permiso para descargar esta proforma.')
        if self._quote_is_retail(order.partner_id.commercial_partner_id.id):
            self._retail_quote_record(order.id, 'read')
        else:
            self._require_census_role()
            self._visible_partner(order.partner_id.commercial_partner_id.id)
        report = request.env.ref('sale.action_report_saleorder', raise_if_not_found=False)
        if not report or report.model != 'sale.order':
            raise UserError('No se encontró el reporte de cotización de Ventas de Odoo.')
        pdf_bytes, _ = request.env['ir.actions.report']._render_qweb_pdf(
            'sale.action_report_saleorder', [order.id])
        if not pdf_bytes or not pdf_bytes.startswith(b'%PDF'):
            raise UserError('Odoo no pudo generar el PDF de esta proforma.')
        filename = 'Proforma_%s.pdf' % re.sub(r'[^a-zA-Z0-9_-]', '_', order.name or str(order.id))
        return request.make_response(pdf_bytes, headers=[
            ('Content-Type', 'application/pdf'),
            ('Content-Disposition', 'attachment; filename="%s"' % filename),
            ('Cache-Control', 'no-store, private'),
            ('X-Content-Type-Options', 'nosniff'),
        ])

    def _quote_available_rewards(self, order):
        if not self._quote_loyalty_enabled() or order.state != "draft":
            return []
        # No mostrar recompensas que el usuario pueda convertir por error en
        # líneas de descuento genéricas. En modo línea solo se ofrecen las
        # promociones porcentuales automáticas verificadas en cada artículo.
        if hasattr(order, "catastro_pwa_apply_product_promotions"):
            return []
        claimable = order._get_claimable_rewards()
        result = []
        for coupon, rewards in claimable.items():
            for reward in rewards:
                result.append({"id": reward.id, "name": reward.description or reward.display_name,
                    "type": reward.reward_type,
                    "multi_product": bool(reward.multi_product),
                    "products": ([{"id": p.id, "name": p.display_name} for p in reward.reward_product_ids]
                                 if reward.reward_type == "product" else [])})
        return result

    def _quote_get_writable(self, quote_id):
        Sale = self._quote_access("write")
        order = Sale.search([("id", "=", int(quote_id)), ("state", "=", "draft"),
                             ("company_id", "=", request.env.company.id)], limit=1)
        if not order:
            raise AccessError("No puede modificar esta cotización o ya fue confirmada.")
        if "export_send" in order._fields and order.export_send == "E":
            raise AccessError("La cotización ya fue enviada a Radis y no permite editar sus líneas.")
        self._quote_partner(order.partner_id.commercial_partner_id.id)
        return order

    @http.route("/catastro/app/quote/promotions/preview", type="json", auth="user", methods=["POST"], readonly=True)
    def quote_promotions_preview(self, partner_id, lines=None, warehouse_id=None, pricelist_id=None):
        """Read-only preview using the native Loyalty rule engine; no sale is created.

        Return only eligible percent discounts on individual products. Other
        native rewards retain their original behavior and are not offered as
        line discounts because converting them alters the accounting semantics.
        """
        Sale = self._quote_access("create")
        if not hasattr(Sale, "catastro_pwa_product_promotion_choices"):
            return {"supported": False, "items": [],
                    "message": "Actualice el complemento Loyalty de Catastro para descuentos por producto."}
        partner = self._quote_partner(partner_id)
        warehouse = self._quote_warehouse(warehouse_id)
        if not warehouse:
            raise ValidationError("Seleccione una bodega para consultar promociones.")
        if not isinstance(lines, list) or len(lines) > 60:
            raise ValidationError("Revise los productos seleccionados.")
        parsed = []
        for entry in lines:
            if not isinstance(entry, dict):
                raise ValidationError("Producto inválido.")
            try:
                pid = int(entry["product_id"])
                qty = float(entry["qty"])
            except (KeyError, TypeError, ValueError):
                raise ValidationError("Producto o cantidad inválidos.")
            if pid <= 0 or not math.isfinite(qty) or not 0 < qty <= 100000:
                raise ValidationError("Cantidad fuera de rango.")
            parsed.append((pid, qty))
        products = self._quote_find_products(product_ids=list(set(pid for pid, _ in parsed))) if parsed else request.env['product.product']
        if {p.id for p in products} != {pid for pid, _ in parsed}:
            raise AccessError("Producto no disponible para esta empresa.")
        vals = {
            "partner_id": partner.id,
            "company_id": request.env.company.id,
            "warehouse_id": warehouse.id,
            "order_line": [(0, 0, {"product_id": pid, "product_uom_qty": qty}) for pid, qty in parsed],
        }
        if pricelist_id:
            if not self._quote_can_negotiate(retail=self._quote_is_retail(partner.id)):
                raise AccessError("La lista de precios está fijada por el cliente.")
            vals["pricelist_id"] = self._quote_pricelist(partner, pricelist_id).id
        # new() has no SQL INSERT, consumes no sale sequence and is safe for
        # frequent live previews. Computed order lines use regular Odoo ORM.
        virtual = Sale.with_company(request.env.company).new(vals)
        choices = virtual.catastro_pwa_product_promotion_choices()
        # Cada oferta elegible incluye su propio precio final CON impuestos,
        # calculado por Odoo para cada forma de pago. La PWA nunca calcula
        # IVA ni modifica el descuento en el navegador.
        pricelist = self._quote_pricelist(partner, pricelist_id)
        fiscal_position = request.env['account.fiscal.position'].with_company(
            request.env.company)._get_fiscal_position(partner)
        options = request.env['catastro.quote.payment.option'].search([
            ('active', '=', True),
            ('company_id', '=', request.env.company.id),
        ], order='sequence,id', limit=60)
        computed_lines = {line.product_id.id: line for line in virtual.order_line
                          if line.product_id and not line.display_type}
        items = []
        for pid, qty in parsed:
            product = products.filtered(lambda product: product.id == pid)
            line = computed_lines.get(pid)
            if not product or not line:
                continue
            list_price = pricelist._get_product_price(
                product, qty, partner=partner, uom=product.uom_id)
            base_discount = max(0.0, min(100.0, float(line.discount or 0.0)))
            offers = []
            for offer in choices.get(pid, []):
                # Combinar descuentos como hace el puente Loyalty al grabar.
                combined = 100.0 - ((100.0 - base_discount) *
                                     (100.0 - offer['discount']) / 100.0)
                tax_prices = self._quote_payment_tax_previews(
                    partner, product, list_price, pricelist,
                    fiscal_position, options, discount_percent=combined)
                offers.append({**offer, **tax_prices, 'qty_priced': qty})
            items.append({'product_id': pid, 'offers': offers})
        return {'supported': True, 'items': items}

    @http.route("/catastro/app/quote/loyalty/rewards", type="json", auth="user", methods=["POST"])
    def quote_loyalty_rewards(self, quote_id):
        order = self._quote_get_writable(quote_id)
        if not self._quote_loyalty_enabled():
            raise ValidationError("Instale y configure sale_loyalty para aplicar promociones de Ventas.")
        order.catastro_restore_base_prices()
        order._update_programs_and_rewards()
        if hasattr(order, "catastro_pwa_apply_product_promotions"):
            order.catastro_pwa_apply_product_promotions()
        else:
            order.catastro_recompute_surcharge()
        return self._quote_record_payload(order)

    @http.route("/catastro/app/quote/loyalty/apply", type="json", auth="user", methods=["POST"])
    def quote_loyalty_apply(self, quote_id, reward_id, product_id=None):
        order = self._quote_get_writable(quote_id)
        if hasattr(order, "catastro_pwa_apply_product_promotions"):
            raise ValidationError("En el cotizador PWA las promociones compatibles se eligen en cada producto. No se crearán recompensas como líneas adicionales. Use Ventas de Odoo para los demás tipos de Loyalty y revise su tratamiento fiscal.")
        if not self._quote_loyalty_enabled():
            raise ValidationError("El módulo sale_loyalty no está instalado.")
        order.catastro_restore_base_prices()
        order._update_programs_and_rewards()
        candidates = order._get_claimable_rewards()
        chosen = request.env["loyalty.reward"].browse(int(reward_id))
        coupon = next((c for c, rewards in candidates.items() if chosen in rewards), False)
        if not coupon:
            raise ValidationError("La recompensa no es aplicable al cliente o a esta cotización.")
        args = {}
        if chosen.reward_type == "product" and chosen.multi_product:
            prod = request.env["product.product"].browse(int(product_id or 0))
            if prod not in chosen.reward_product_ids:
                raise ValidationError("Seleccione un producto válido para la recompensa.")
            args["product"] = prod
        if hasattr(order, "catastro_pwa_apply_product_promotions") and chosen.reward_type == "discount":
            raise ValidationError("Esta recompensa nativa usa una línea especial. Para descuentos por artículo, configure una promoción automática porcentual sobre productos específicos. Otras recompensas necesitan una integración fiscal separada.")
        order._apply_program_reward(chosen, coupon, **args)
        order._update_programs_and_rewards()
        if hasattr(order, "catastro_pwa_apply_product_promotions"):
            order.catastro_pwa_apply_product_promotions()
        else:
            order.catastro_recompute_surcharge()
        return self._quote_record_payload(order)

    @http.route("/catastro/app/quote/loyalty/code", type="json", auth="user", methods=["POST"])
    def quote_loyalty_code(self, quote_id, code):
        order = self._quote_get_writable(quote_id)
        if hasattr(order, "catastro_pwa_apply_product_promotions"):
            raise ValidationError("Por seguridad fiscal, esta versión aplica desde la PWA únicamente promociones automáticas porcentuales por producto. La conversión de cupones requiere una implementación de puntos y redenciones adicional.")
        if not self._quote_loyalty_enabled():
            raise ValidationError("El módulo sale_loyalty no está instalado.")
        code = (code or "").strip()[:100]
        if not code:
            raise ValidationError("Indique un código de promoción.")
        order.catastro_restore_base_prices()
        status = order._try_apply_code(code)
        if "error" in status:
            raise ValidationError(status["error"])
        order._update_programs_and_rewards()
        if hasattr(order, "catastro_pwa_apply_product_promotions"):
            order.catastro_pwa_apply_product_promotions()
        else:
            order.catastro_recompute_surcharge()
        return self._quote_record_payload(order)

    def _sync_quote(self, payload):
        partner = self._quote_partner(payload.get("partner_id"))
        Sale = self._quote_access("create")
        Product = request.env["product.product"]
        if not Product.check_access_rights("read", raise_exception=False):
            raise AccessError("Sin permisos para consultar productos.")
        lines = payload.get("lines") or []
        if not isinstance(lines, list) or not 1 <= len(lines) <= 60:
            raise ValidationError("La cotización debe contener entre 1 y 60 productos.")
        retail_quote = self._quote_is_retail(partner.id)
        products = []
        # No se crea ningún campo nuevo: esta integración utiliza el campo
        # personalizado existente de sale.order.line, cuando está instalado.
        Line = request.env["sale.order.line"]
        custom_negotiated_field = Line._fields.get("negotiable_price")
        for line in lines:
            if not isinstance(line, dict):
                raise ValidationError("Formato inválido de línea de cotización.")
            try:
                pid, qty = int(line.get("product_id")), float(line.get("qty"))
            except (ValueError, TypeError):
                raise ValidationError("Producto y cantidad deben ser válidos.")
            if not math.isfinite(qty) or not (0 < qty <= 100000):
                raise ValidationError("La cantidad debe ser mayor a cero y estar dentro del límite permitido.")
            # Compatibilidad con operaciones offline previas a 18.0.1.5.6:
            # en la cola antigua se enviaba negotiated_price. Ambos valores se
            # escriben SOLO en negotiable_price, nunca en price_unit.
            negotiated = line.get("negotiable_price", line.get("negotiated_price", None))
            if negotiated not in (None, ""):
                try:
                    negotiated = float(negotiated)
                except (ValueError, TypeError):
                    raise ValidationError("Precio negociado inválido.")
                if not math.isfinite(negotiated) or not 0 <= negotiated <= 1000000000:
                    raise ValidationError("El precio negociado debe ser no negativo y válido.")
            else:
                negotiated = None
            products.append((pid, qty, negotiated))
        if any(negotiated is not None for _, _, negotiated in products) and not self._quote_can_negotiate(retail=retail_quote):
            raise AccessError("Este perfil no puede modificar negotiable_price: las ventas de Tienda usan precios de lista y Loyalty.")
        if payload.get("pricelist_id") and not self._quote_can_negotiate(retail=retail_quote):
            raise AccessError("Este perfil debe utilizar la lista de precios asignada al cliente.")
        # price_unit, discount y los campos de auditoría se calculan en Odoo:
        # no aceptar cambios manuales provenientes de la PWA o de colas antiguas.
        if any(any(k in line for k in (
                'price_unit', 'price', 'discount',
                'catastro_payment_surcharge_percent', 'catastro_payment_base_price_unit',
                'catastro_payment_surcharge_unit_amount')) for line in lines):
            raise AccessError("Los precios y recargos los calcula Odoo; no se aceptan importes manuales.")
        if any(negotiated is not None for _, _, negotiated in products):
            if custom_negotiated_field is None:
                raise ValidationError(
                    "El campo personalizado negotiable_price no está instalado en las líneas "
                    "de cotización (sale.order.line). Instale o actualice la personalización "
                    "de Ventas antes de guardar precios negociados.")
            if custom_negotiated_field.type not in ("float", "monetary", "integer"):
                raise ValidationError(
                    "El campo negotiable_price debe ser numérico en sale.order.line. "
                    "Verifique la personalización de Ventas.")
            if custom_negotiated_field.compute and not custom_negotiated_field.inverse:
                raise ValidationError(
                    "El campo negotiable_price se calcula sin permitir escritura. "
                    "Revise el módulo personalizado de cotizaciones.")
        unique_ids = {p for p, _, _ in products}
        if len(unique_ids) != len(products):
            raise ValidationError("Un mismo producto debe aparecer en una sola línea; acumule la cantidad.")
        domain = [("id", "in", list(unique_ids)), ("sale_ok", "=", True), ("active", "=", True)]
        if "company_id" in Product._fields:
            domain = ["|", ("company_id", "=", False), ("company_id", "=", request.env.company.id)] + domain
        accessible = Product.search(domain)
        if {p.id for p in accessible} != unique_ids:
            raise ValidationError("Uno o varios productos no están disponibles para venta en esta compañía.")
        warehouse = self._quote_warehouse(payload.get("warehouse_id"))
        if not warehouse and not payload.get("warehouse_id"):
            # Compatibilidad: una cotización offline anterior puede no incluir
            # bodega; solo elegir por defecto si existe exactamente una válida.
            candidates = self._quote_warehouses()
            if len(candidates) == 1:
                warehouse = self._quote_warehouse(candidates[0]["id"])
        if not warehouse:
            raise ValidationError("Debe seleccionar una bodega antes de guardar la proforma. Revise la operación en Pendientes.")
        if "warehouse_id" not in Sale._fields:
            raise ValidationError("Ventas no tiene bodega en las cotizaciones. Revise la integración de Ventas con Inventario (sale_stock).")
        requested_qty = {pid: qty for pid, qty, _ in products}
        stock_map = self._quote_stock_map(accessible, warehouse)
        for product in accessible:
            stock = stock_map[product.id]
            needed = requested_qty[product.id]
            rounding = min(product.uom_id.rounding or 0.000001, 0.000001)
            if float_compare(stock, 0, precision_rounding=rounding) <= 0:
                raise ValidationError("%s está sin stock físico en %s (ubicación raíz: %s). "
                                      "Revise la variante, compañía, ubicaciones internas y quants; "
                                      "la cifra general de Inventario puede incluir otras bodegas."
                                      % (product.display_name, warehouse.display_name,
                                         warehouse.view_location_id.complete_name))
            if float_compare(needed, stock, precision_rounding=rounding) > 0:
                raise ValidationError("Stock insuficiente de %s en %s: solicitado %s %s, a mano %s %s." %
                                      (product.display_name, warehouse.display_name, needed,
                                       product.uom_id.name, stock, product.uom_id.name))
        visit_id = int(payload.get("visit_id") or 0)
        if visit_id and self._quote_is_retail(partner.id):
            raise ValidationError("Una proforma de Consumidor Final no puede vincularse a una visita de catastro.")
        # El campo negociable se escribe con los valores de creación de las
        # líneas para respetar los métodos create() de los módulos instalados.
        order_lines = []
        for pid, qty, negotiated in products:
            line_vals = {"product_id": pid, "product_uom_qty": qty}
            if negotiated is not None:
                line_vals["negotiable_price"] = negotiated
            order_lines.append((0, 0, line_vals))
        option = self._quote_payment_option(payload.get("payment_option_id"))
        # El recargo por línea no requiere una línea de servicio ni instalar
        # el puente antiguo: la PWA calcula Loyalty antes del recargo y,
        # cuando se actualizan promociones, restaura y recalcula los precios.
        vals = {"partner_id": partner.id, "company_id": request.env.company.id,
                "user_id": request.env.user.id, "census_originated": not self._quote_is_retail(partner.id),
                "order_line": order_lines}
        # La bodega es obligatoria para que validación, pedido y consulta coincidan.
        vals["warehouse_id"] = warehouse.id
        if option:
            vals["catastro_payment_option_id"] = option.id
            if option.payment_term_id:
                vals["payment_term_id"] = option.payment_term_id.id
        selected_pricelist = payload.get("pricelist_id")
        if selected_pricelist:
            vals["pricelist_id"] = self._quote_pricelist(partner, selected_pricelist).id
        if visit_id:
            Visit = request.env["conedera.census.visit"]
            visit = Visit.search([("id", "=", visit_id), ("partner_id", "=", partner.id),
                                  ("company_id", "=", request.env.company.id)], limit=1)
            if not visit:
                raise ValidationError("La visita seleccionada no corresponde a este cliente y compañía.")
            vals["census_visit_id"] = visit.id
            vals["origin"] = visit.name
        reference = (payload.get("client_order_ref") or "").strip()[:100]
        if reference:
            vals["client_order_ref"] = reference
        # Primero crear usando create() nativo y sus personalizaciones: cálculo de listas,
        # impuestos, descuentos y condiciones de cliente en el servidor Odoo.
        order = Sale.with_company(request.env.company).create(vals)
        if order.state != "draft":
            raise ValidationError("La cotización no quedó en estado borrador.")
        if self._quote_loyalty_enabled():
            order._update_programs_and_rewards()
            # Un cupón puede habilitar varias recompensas. No se aplica una
            # arbitrariamente: se elige desde la ficha de la cotización PWA.
            coupon_code = (payload.get("loyalty_code") or "").strip()[:100]
            if coupon_code:
                status = order._try_apply_code(coupon_code)
                if "error" in status:
                    raise ValidationError(status["error"])
                order._update_programs_and_rewards()
        elif payload.get("loyalty_code"):
            raise ValidationError("Para códigos de promoción debe instalarse sale_loyalty.")
        selected_promos = {}
        for entry in lines:
            if "promo_reward_id" in entry and entry["promo_reward_id"] is not None:
                try:
                    selected_promos[int(entry["product_id"])] = int(entry["promo_reward_id"] or 0)
                except (TypeError, ValueError):
                    raise ValidationError("La promoción elegida no es válida.")
        if hasattr(order, "catastro_pwa_apply_product_promotions"):
            order.catastro_pwa_apply_product_promotions(selected_promos)
        elif any(selected_promos.values()):
            raise ValidationError("El complemento Loyalty por producto no está instalado.")
        else:
            order.catastro_recompute_surcharge()
        if order.warehouse_id.id != warehouse.id:
            raise ValidationError("La personalización de Ventas cambió la bodega durante la creación; se canceló el guardado para evitar diferencias de inventario.")
        for pid, _qty, negotiated in products:
            if negotiated is None:
                continue
            matches = order.order_line.filtered(lambda l: not l.display_type and l.product_id.id == pid)
            if len(matches) != 1:
                raise ValidationError("No se puede verificar negotiable_price: las líneas del producto fueron alteradas por una personalización.")
            # negotiable_price es independiente del recargo por forma de pago;
            # el módulo personalizado calcula la base, la PWA aplica el recargo
            # al price_unit resultante y conserva su porcentaje en la línea.
            saved_price = matches.negotiable_price
            if saved_price is False or order.currency_id.compare_amounts(saved_price, negotiated):
                raise ValidationError(
                    "Odoo no conservó negotiable_price para %s. Revise las reglas de su módulo personalizado."
                    % matches.product_id.display_name)
        return {"state": "synced", "message": "Cotización %s guardada en Odoo. Revise precios e impuestos calculados antes de enviarla." % order.name,
                "result_model": "sale.order", "result_id": order.id}

    @http.route(["/catastro/app/quote/update", "/conedera/app/quote/update"],
                type="json", auth="user", methods=["POST"])
    def quote_update(self, quote_id, lines=None, warehouse_id=None,
                     payment_option_id=None, client_order_ref="", base_write_date="",
                     original_line_ids=None):
        """Actualizar un borrador EXISTENTE sin sustituirlo ni borrar Loyalty.

        Solo productos ordinarios; descuentos automáticos, recompensas y demás
        líneas especiales permanecen bajo control de las extensiones de Odoo.
        Todo ocurre en la transacción RPC: ante un error, Odoo revierte cambios.
        """
        order = self._quote_get_writable(quote_id)
        if not base_write_date or str(order.write_date or "") != str(base_write_date):
            raise ValidationError("La cotización cambió en Odoo desde que la abrió. "
                                  "Vuelva a cargarla para evitar sobrescribir otros cambios.")
        if not isinstance(lines, list) or not 1 <= len(lines) <= 60:
            raise ValidationError("Indique entre 1 y 60 productos para editar la proforma.")
        if "warehouse_id" not in order._fields:
            raise ValidationError("Instale sale_stock para elegir una bodega en las cotizaciones.")
        warehouse = self._quote_warehouse(warehouse_id)
        if not warehouse:
            raise ValidationError("Seleccione una bodega válida para guardar el borrador.")
        retail = self._quote_is_retail(order.partner_id.commercial_partner_id.id)
        can_negotiate = self._quote_can_negotiate(retail=retail)
        normal_lines = order.order_line.filtered(self._quote_line_editable)
        normal_by_id = {line.id: line for line in normal_lines}
        if not isinstance(original_line_ids, list) or sorted(normal_by_id) != sorted(
                int(v) for v in original_line_ids if isinstance(v, int)):
            raise ValidationError("Las líneas del borrador cambiaron en Odoo. Vuelva a abrirlo antes de editar.")
        Line = request.env["sale.order.line"]
        negotiated_field = Line._fields.get("negotiable_price")
        parsed, unique_products, used_lines = [], set(), set()
        for vals in lines:
            if not isinstance(vals, dict) or any(k in vals for k in (
                    "price", "price_unit", "discount", "catastro_payment_surcharge_percent",
                    "catastro_payment_base_price_unit", "catastro_payment_surcharge_unit_amount")):
                raise AccessError("El navegador no puede modificar precios, descuentos ni recargos internos.")
            try:
                pid = int(vals.get("product_id"))
                qty = float(vals.get("qty"))
                line_id = int(vals.get("sale_line_id") or 0)
            except (TypeError, ValueError):
                raise ValidationError("Producto, cantidad o línea inválidos.")
            if pid <= 0 or not math.isfinite(qty) or qty <= 0 or qty > 100000:
                raise ValidationError("Indique cantidades positivas y válidas.")
            if pid in unique_products or (line_id and line_id in used_lines):
                raise ValidationError("No duplique productos o líneas en una misma cotización.")
            unique_products.add(pid)
            if line_id:
                used_lines.add(line_id)
                if line_id not in normal_by_id or normal_by_id[line_id].product_id.id != pid:
                    raise AccessError("La línea no pertenece a los productos editables de esta cotización.")
            negotiated = vals.get("negotiable_price")
            if negotiated not in (None, ""):
                if not can_negotiate:
                    raise AccessError("Este perfil no puede modificar negotiable_price.")
                if not negotiated_field or (negotiated_field.compute and not negotiated_field.inverse):
                    raise ValidationError("El precio negociado personalizado no permite escritura.")
                try:
                    negotiated = float(negotiated)
                except (TypeError, ValueError):
                    raise ValidationError("Precio negociado inválido.")
                if not math.isfinite(negotiated) or not 0 <= negotiated <= 1000000000:
                    raise ValidationError("Precio negociado fuera de rango.")
            else:
                negotiated = None
            parsed.append((line_id, pid, qty, negotiated))
        products = self._quote_find_products(product_ids=list(unique_products))
        if set(products.ids) != unique_products:
            raise AccessError("Hay productos que no se pueden vender o no pertenecen a la empresa.")
        stock_map = self._quote_stock_map(products, warehouse)
        for product in products:
            qty = next(row[2] for row in parsed if row[1] == product.id)
            rounding = min(product.uom_id.rounding or 0.000001, 0.000001)
            if float_compare(qty, stock_map[product.id], precision_rounding=rounding) > 0:
                raise ValidationError("Stock insuficiente para %s en %s. Solicitado %s, a mano %s."
                                      % (product.display_name, warehouse.display_name, qty, stock_map[product.id]))
        option = self._quote_payment_option(payment_option_id)
        # Primero quitar el recargo antiguo para no duplicarlo en líneas que
        # cambian de cantidad, y después dejar actuar a las reglas nativas.
        order.catastro_restore_base_prices()
        changes = {"warehouse_id": warehouse.id,
                   "catastro_payment_option_id": option.id if option else False,
                   "client_order_ref": (client_order_ref or "").strip()[:100]}
        if option and option.payment_term_id:
            changes["payment_term_id"] = option.payment_term_id.id
        order.write(changes)
        for line_id, pid, qty, negotiated in parsed:
            values = {"product_uom_qty": qty}
            if negotiated is not None:
                values["negotiable_price"] = negotiated
            if line_id:
                normal_by_id[line_id].write(values)
            else:
                values.update({"order_id": order.id, "product_id": pid})
                Line.create(values)
        for line_id, line in normal_by_id.items():
            if line_id not in used_lines:
                line.unlink()
        if self._quote_loyalty_enabled():
            order._update_programs_and_rewards()
        selected_promos = {}
        for entry in lines:
            if "promo_reward_id" in entry and entry["promo_reward_id"] is not None:
                try:
                    selected_promos[int(entry["product_id"])] = int(entry["promo_reward_id"] or 0)
                except (TypeError, ValueError):
                    raise ValidationError("La promoción elegida no es válida.")
        if hasattr(order, "catastro_pwa_apply_product_promotions"):
            order.catastro_pwa_apply_product_promotions(selected_promos)
        elif any(selected_promos.values()):
            raise ValidationError("Instale el complemento Loyalty por producto.")
        else:
            order.catastro_recompute_surcharge()
        if order.warehouse_id.id != warehouse.id:
            raise ValidationError("Odoo cambió la bodega al guardar. No se aplicaron los cambios.")
        if order.state != "draft":
            raise ValidationError("La cotización cambió de estado durante la edición.")
        return self._quote_record_payload(order)

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
            "census_gps_payload": "census_gps_payload",
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
                if source == "census_gps_payload" and not value:
                    continue
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
            team = Partner._default_census_team(request.env.user, request.env.company)
            if payload.get("team_id"):
                selected = request.env["crm.team"].browse(int(payload["team_id"])).exists()
                if not selected or not selected.census_enabled or not selected.active or selected.company_id != request.env.company:
                    raise ValidationError("El equipo seleccionado no está habilitado en su compañía.")
                if not is_census_manager(request.env.user) and selected.user_id != request.env.user and request.env.user not in selected.member_ids:
                    raise AccessError("No forma parte del equipo comercial seleccionado.")
                team = selected
            if team and "census_team_id" in Partner._fields:
                vals["census_team_id"] = team.id
        business_field = self._m2m_field_by_comodel(Partner, "conedera.census.business.type")
        if business_field and "business_type_ids" in payload:
            vals[business_field] = [(6, 0, [int(x) for x in payload.get("business_type_ids") or [] if str(x).isdigit()])]
        brand_field = self._m2m_field_by_comodel(Partner, "conedera.census.mobile.brand")
        if brand_field and "mobile_brand_ids" in payload:
            vals[brand_field] = [(6, 0, [int(x) for x in payload.get("mobile_brand_ids") or [] if str(x).isdigit()])]
        return vals

    def _sync_opening_hours(self, partner, hours, replace=False):
        if hours is None:
            return
        Hour = request.env["conedera.partner.opening.hour"]
        if not isinstance(hours, list) or len(hours) > 35:
            raise ValidationError("El horario debe contener hasta 35 franjas válidas.")
        valid = []
        by_day = {}
        for item in hours:
            day = str(item.get("day", ""))
            if day not in {str(n) for n in range(7)}:
                raise ValidationError("Seleccione un día válido para cada horario.")
            try:
                begin, finish = float(item["from"]), float(item["to"])
            except (ValueError, TypeError, KeyError):
                raise ValidationError("Las horas de apertura y cierre son obligatorias.")
            if not (0 <= begin < 24 and 0 < finish <= 24 and begin < finish):
                raise ValidationError("Cada horario debe terminar después de comenzar, entre 00:00 y 24:00.")
            for other_start, other_end in by_day.setdefault(day, []):
                if begin < other_end and finish > other_start:
                    raise ValidationError("Hay horarios superpuestos para el mismo día.")
            by_day[day].append((begin, finish))
            valid.append({"partner_id": partner.id, "day_of_week": day,
                          "opening_time": begin, "closing_time": finish})
        if replace:
            Hour.search([("partner_id", "=", partner.id)]).unlink()
        if valid:
            Hour.create(valid)

    def _register_or_warn(self, partner, requested):
        if not requested:
            return "synced", "Catastro guardado como borrador. Puede finalizarlo desde su ficha."
        try:
            with request.env.cr.savepoint():
                partner.action_register_census()  # Método original: requisitos, equipo, permiso y bloqueo.
        except (AccessError, UserError, ValidationError) as exc:
            return "warning", "Borrador guardado; NO está protegido. " + str(exc)
        return "synced", "Catastro finalizado y protegido correctamente. Ya puede registrar visitas."

    def _sync_catastro(self, payload):
        self._require_census_role()
        Partner = request.env["res.partner"]
        vat = (payload.get("vat") or "").strip()
        name = (payload.get("name") or "").strip()
        existing_id = int(payload.get("selected_partner_id") or 0)
        contact = Partner.browse()
        if existing_id:
            # Autorización de la búsqueda original; no confiar en IDs recibidos de la PWA.
            contact = Partner.sudo().browse(existing_id).exists().commercial_partner_id
            if not contact:
                raise UserError("El cliente seleccionado ya no existe.")
            query = (payload.get("lookup_query") or "").strip()
            candidates = request.env["conedera.census.customer.lookup.wizard"].search_global_candidates(query, limit=20)
            if not any(c["id"] == contact.id and c["can_use"] for c in candidates):
                raise AccessError("El cliente no está disponible para su usuario. Vuelva a buscarlo.")
            if contact.census_active:
                raise UserError("El cliente ya tiene catastro. Abra su ficha; no cree otro.")
            if contact.vat and vat and self._normalize_vat(contact.vat) != self._normalize_vat(vat):
                raise ValidationError("El RUC/cédula del cliente seleccionado no coincide con su ficha. Verifique la identificación.")
        if vat:
            matching = self._find_partner_global_by_vat(vat)
            if matching and (not contact or matching.id != contact.id):
                visible = self._can_read_partner(matching)
                return {
                    "state": "conflict", "message": "El RUC/cédula ya existe. Seleccione el cliente o solicite reasignación.",
                    "result_model": "res.partner", "result_id": matching.id if visible else 0,
                }
        if not contact and name:
            name_matches = Partner.sudo().with_context(active_test=False).search([
                ("parent_id", "=", False), "|", ("name", "=ilike", name),
                ("commercial_name", "=ilike", name),
            ], limit=1)
            if name_matches:
                return {"state": "conflict", "message": "Ya existe un contacto con ese nombre. Búsquelo antes de crear otra ficha.",
                        "result_model": "res.partner", "result_id": 0}
        vals = self._prepare_partner_vals(payload, create=not bool(contact))
        if contact:
            company = request.env.company
            owner = contact.user_id or request.env.user
            team = request.env["crm.team"].browse(vals.get("census_team_id")) if vals.get("census_team_id") else contact._default_census_team(owner, company)
            if team and (team.company_id != company or (owner != team.user_id and owner not in team.member_ids)):
                raise ValidationError("El responsable no pertenece al equipo seleccionado.")
            vals.update({"census_active": True, "census_date": fields.Datetime.now(),
                         "census_user_id": request.env.user.id, "user_id": owner.id,
                         "census_company_id": company.id, "census_locked": False,
                         "customer_rank": max(contact.customer_rank, 1)})
            if team:
                vals["census_team_id"] = team.id
            # El módulo base usa sudo tras validar candidato disponible en su wizard.
            contact.sudo().write(vals)
            partner = Partner.browse(contact.id)
        else:
            if not name and not vat:
                raise ValidationError("Ingrese el nombre o RUC/cédula del cliente.")
            vals.setdefault("name", name or "BORRADOR - RUC " + vat)
            partner = Partner.browse(Partner.sudo().create(vals).id)
        if "opening_hours" in payload:
            self._sync_opening_hours(partner, payload["opening_hours"], replace=bool(contact))
        state, message = self._register_or_warn(partner, bool(payload.get("finalize")))
        return {"state": state, "message": message, "result_model": "res.partner", "result_id": partner.id}

    def _sync_catastro_update(self, payload):
        self._require_census_role()
        partner = self._visible_partner(payload.get("partner_id"))
        base_write_date = payload.get("base_write_date")
        if base_write_date and str(partner.write_date) != str(base_write_date):
            return {"state": "conflict", "message": "La ficha cambió en Odoo; actualice antes de sobrescribir.",
                    "result_model": "res.partner", "result_id": partner.id}
        if not partner.census_can_edit_master:
            raise AccessError("Catastro protegido. Solicite habilitación antes de editar.")
        vals = self._prepare_partner_vals(payload)
        if vals:
            partner.write(vals)
        if "opening_hours" in payload:
            self._sync_opening_hours(partner, payload["opening_hours"], replace=True)
        return {"state": "synced", "message": "Cambios guardados correctamente.",
                "result_model": "res.partner", "result_id": partner.id}

    def _sync_catastro_finalize(self, payload):
        self._require_census_role()
        partner = self._visible_partner(payload.get("partner_id"))
        if partner.census_locked:
            return {"state": "synced", "message": "Este catastro ya estaba protegido.",
                    "result_model": "res.partner", "result_id": partner.id}
        # Para cierres en cola offline evitar cerrar una versión modificada por otra persona.
        base = payload.get("base_write_date")
        if base and str(partner.write_date) != str(base):
            return {"state": "conflict", "message": "El catastro cambió desde la última descarga. Actualice y confirme el cierre.",
                    "result_model": "res.partner", "result_id": partner.id}
        partner.action_register_census()
        return {"state": "synced", "message": "Catastro finalizado y protegido. Puede registrar visitas.",
                "result_model": "res.partner", "result_id": partner.id}

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
        direct = ["purchase_made", "reschedule_visit", "has_stock", "not_creditworthy", "other_result"]
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
        if payload.get("gps_capture_payload") and "gps_capture_payload" in Visit._fields:
            vals["gps_capture_payload"] = payload["gps_capture_payload"]
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
            for method_name in ["action_mark_done"]:
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
        if op_type == "quote":
            return self._sync_quote(payload)
        if op_type == "visit":
            return self._sync_visit(payload)
        if op_type == "catastro":
            return self._sync_catastro(payload)
        if op_type == "catastro_update":
            return self._sync_catastro_update(payload)
        if op_type == "catastro_finalize":
            return self._sync_catastro_finalize(payload)
        raise UserError("Tipo de operación móvil no soportado.")

    @http.route(["/catastro/app/sync", "/conedera/app/sync"], type="json", auth="user", methods=["POST"])
    def sync(self, operations=None):
        operations = operations or []
        if not isinstance(operations, list):
            raise UserError("Formato de sincronización inválido.")
        Log = request.env["conedera.mobile.sync.log"].sudo()
        results = []
        for operation in operations[:100]:
            client_uuid = (operation.get("uuid") or "").strip()
            op_type = operation.get("type")
            if not client_uuid or op_type not in {"visit", "catastro", "catastro_update", "catastro_finalize", "quote"}:
                results.append({"uuid": client_uuid, "state": "error", "message": "Operación inválida."})
                continue
            if operation.get("user_id") and int(operation["user_id"]) != request.env.user.id:
                results.append({"uuid": client_uuid, "state": "error", "message": "La operación pertenece a otro usuario de Odoo."})
                continue
            if operation.get("company_id") and int(operation["company_id"]) != request.env.company.id:
                results.append({"uuid": client_uuid, "state": "error", "message": "La operación pertenece a otra compañía."})
                continue
            log = Log.search([("client_uuid", "=", client_uuid)], limit=1)
            if log and (log.user_id != request.env.user or log.company_id != request.env.company):
                results.append({"uuid": client_uuid, "state": "error", "message": "Operación de otra sesión; no se sincronizó."})
                continue
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
