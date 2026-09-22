import json

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase


class TestConederaCensus(TransactionCase):
    def setUp(self):
        super().setUp()
        self.business_type = self.env.ref("conedera_odoo_census.business_type_cellphones")
        self.team = self.env["crm.team"].create(
            {
                "name": "Equipo Catastro Test",
                "user_id": self.env.user.id,
                "member_ids": [(4, self.env.user.id)],
                "company_id": self.env.company.id,
                "census_enabled": True,
            }
        )
        self.partner = self.env["res.partner"].create(
            {
                "name": "Cliente GPS S.A.",
                "census_active": True,
                "customer_rank": 1,
                "vat": "0999999999001",
                "commercial_name": "Cliente GPS",
                "census_store_count": 2,
                "business_type_ids": [(6, 0, [self.business_type.id])],
                "customer_segment": "reseller",
                "capa": 5000.0,
                "owner_contact_name": "Ana Dueña",
                "owner_phone": "0990000001",
                "commercial_contact_name": "Carlos Compras",
                "phone": "042000001",
                "email": "compras@example.com",
                "street": "Av. Principal 123",
                "city": "Guayaquil",
                "user_id": self.env.user.id,
                "census_team_id": self.team.id,
            }
        )
        self.env["conedera.partner.opening.hour"].create(
            {
                "partner_id": self.partner.id,
                "day_of_week": "0",
                "opening_time": 9.0,
                "closing_time": 18.0,
            }
        )
        # Desde 18.0.1.7.0 una ficha completa debe registrarse/bloquearse antes de operar.
        self.partner.action_register_census()


    def test_technical_sales_team_cannot_be_enabled_for_census(self):
        technical = self.env.ref("sales_team.salesteam_website_sales", raise_if_not_found=False)
        if technical:
            self.assertFalse(technical.census_enabled)
            with self.assertRaises(UserError):
                technical.write({"census_enabled": True})

    def test_multiple_business_types(self):
        accessories = self.env.ref("conedera_odoo_census.business_type_accessories")
        self.partner.write({"business_type_ids": [(4, accessories.id)]})
        self.assertEqual(len(self.partner.business_type_ids), 2)

    def test_structured_opening_hours(self):
        line = self.env["conedera.partner.opening.hour"].create(
            {
                "partner_id": self.partner.id,
                "day_of_week": "0",
                "opening_time": 9.0,
                "closing_time": 18.0,
            }
        )
        self.assertEqual(line.partner_id, self.partner)
        self.assertEqual(line.opening_time, 9.0)


    def test_opening_hours_summary_is_human_readable(self):
        self.partner.invalidate_recordset(["opening_hours_summary_html"])
        summary = self.partner.opening_hours_summary_html or ""
        self.assertIn("Lunes", summary)
        self.assertIn("09:00", summary)
        self.assertIn("18:00", summary)

    def test_visit_gps_distance(self):
        self.partner.write(
            {
                "census_gps_payload": json.dumps(
                    {"latitude": -2.170998, "longitude": -79.922359, "accuracy": 6.0}
                )
            }
        )
        payload = json.dumps(
            {"latitude": -2.171000, "longitude": -79.922360, "accuracy": 8.0}
        )
        visit = self.env["conedera.census.visit"].create(
            {
                "partner_id": self.partner.id,
                "gps_capture_payload": payload,
                "location_tolerance_m": 300,
            }
        )
        self.assertTrue(visit.gps_captured_at)
        self.assertEqual(visit.location_status, "in_range")
        self.assertLess(visit.distance_to_customer_m, 10)

    def test_quotation_context_links_visit(self):
        visit = self.env["conedera.census.visit"].create({"partner_id": self.partner.id})
        action = visit.action_create_quotation()
        self.assertEqual(action["context"]["default_partner_id"], self.partner.id)
        self.assertEqual(action["context"]["default_census_visit_id"], visit.id)

    def test_last_visit_metric_is_ui_compute(self):
        visit = self.env["conedera.census.visit"].create({"partner_id": self.partner.id})
        self.partner.invalidate_recordset(["census_last_visit_datetime"])
        self.assertEqual(self.partner.census_last_visit_datetime, visit.visit_datetime)

    def test_visit_quotation_marks_census_origin(self):
        visit = self.env["conedera.census.visit"].create({"partner_id": self.partner.id})
        order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "census_visit_id": visit.id,
            }
        )
        self.assertTrue(order.census_originated)
        self.assertEqual(order.census_visit_id, visit)

    def test_unique_census_per_vat(self):
        with self.assertRaises(ValidationError):
            self.env["res.partner"].create(
                {
                    "name": "Duplicado",
                    "census_active": True,
                    "vat": self.partner.vat,
                    "commercial_name": "Duplicado",
                }
            )

    def test_census_cannot_be_duplicated(self):
        with self.assertRaises(UserError):
            self.partner.copy()

    def test_active_census_is_detected_when_vat_is_on_child_contact(self):
        vat = self.partner.vat
        self.partner.sudo().write({"vat": False})
        self.env["res.partner"].create(
            {
                "name": "Contacto fiscal",
                "parent_id": self.partner.id,
                "vat": vat,
            }
        )
        matches = self.env["res.partner"]._census_global_active_by_identity(vat)
        self.assertIn(self.partner, matches)
        with self.assertRaises(ValidationError):
            self.env["res.partner"].create(
                {
                    "name": "Duplicado con RUC del contacto hijo",
                    "census_active": True,
                    "vat": vat,
                    "commercial_name": "Duplicado",
                }
            )

    def test_existing_contact_with_vat_on_child_is_reused_and_parent_gets_vat(self):
        parent = self.env["res.partner"].create(
            {
                "name": "Cliente histórico sin RUC en matriz",
                "customer_rank": 1,
            }
        )
        child = self.env["res.partner"].create(
            {
                "name": "Facturación",
                "parent_id": parent.id,
                "type": "invoice",
                "vat": "0912345678",
            }
        )
        wizard = self.env["conedera.census.customer.lookup.wizard"].create(
            {
                "lookup_query": child.vat,
                "selected_partner_ref_id": parent.id,
                "selected_can_use": True,
                "selected_candidate_status": "available_contact",
                "existing_vat": child.vat,
            }
        )
        action = wizard.action_use_selected()
        parent.invalidate_recordset(["vat", "census_active"])
        self.assertEqual(action["res_id"], parent.id)
        self.assertTrue(parent.census_active)
        self.assertEqual(parent.vat, child.vat)

    def test_lookup_rejects_partner_id_outside_current_search_results(self):
        unrelated = self.env["res.partner"].create({"name": "No coincide con búsqueda"})
        wizard = self.env["conedera.census.customer.lookup.wizard"].create(
            {
                "lookup_query": self.partner.vat,
                "selected_partner_ref_id": unrelated.id,
                "selected_can_use": True,
                "selected_candidate_status": "available_contact",
            }
        )
        with self.assertRaises(AccessError):
            self.env["conedera.census.customer.lookup.wizard"].action_select_candidate(
                wizard.id, unrelated.id
            )
        with self.assertRaises(AccessError):
            wizard.action_use_selected()

    def test_store_count_is_editable_field(self):
        self.partner.write({"census_store_count": 4})
        self.assertEqual(self.partner.census_store_count, 4)

    def test_customer_history_contains_all_sale_orders(self):
        order = self.env["sale.order"].create({"partner_id": self.partner.id})
        self.assertIn(order, self.partner.census_sale_order_ids)

    def test_catastro_ready_without_gps(self):
        self.partner.invalidate_recordset(["census_ready_for_activity", "census_completion_state"])
        self.assertTrue(self.partner.census_ready_for_activity)
        self.assertEqual(self.partner.census_completion_state, "complete")
        self.assertFalse(self.partner.census_gps_captured_at)

    def test_incomplete_catastro_blocks_visit_and_quotation(self):
        self.partner.write({"census_store_count": 0})
        self.partner.invalidate_recordset(["census_ready_for_activity", "census_missing_requirements"])
        self.assertFalse(self.partner.census_ready_for_activity)
        with self.assertRaises(UserError):
            self.partner.action_new_census_visit()
        with self.assertRaises(UserError):
            self.partner.action_new_census_quotation()
        with self.assertRaises(UserError):
            self.env["conedera.census.visit"].create({"partner_id": self.partner.id})

    def test_visit_can_finish_without_gps(self):
        visit = self.env["conedera.census.visit"].create(
            {
                "partner_id": self.partner.id,
                "purchase_made": "no",
                "reschedule_visit": "no",
                "has_stock": "yes",
                "not_creditworthy": "no",
                "other_result": "no",
            }
        )
        visit.action_mark_done()
        self.assertEqual(visit.state, "done")
        self.assertEqual(visit.location_status, "no_visit_gps")
    def test_lookup_wizard_reuses_existing_partner(self):
        wizard = self.env["conedera.census.customer.lookup.wizard"].create(
            {"vat": self.partner.vat}
        )
        wizard.action_validate()
        self.assertEqual(wizard.validation_state, "found")
        self.assertEqual(wizard.existing_partner_id, self.partner)
        count_before = self.env["res.partner"].search_count([("vat", "=", self.partner.vat)])
        action = wizard.action_open_existing()
        count_after = self.env["res.partner"].search_count([("vat", "=", self.partner.vat)])
        self.assertEqual(count_before, count_after)
        self.assertEqual(action["res_id"], self.partner.id)

    def test_lookup_wizard_can_create_draft_from_name(self):
        wizard = self.env["conedera.census.customer.lookup.wizard"].create(
            {"customer_name": "Cliente Nuevo Sin RUC"}
        )
        wizard.action_validate()
        self.assertEqual(wizard.validation_state, "not_found")
        action = wizard.action_create_new()
        partner = self.env["res.partner"].browse(action["res_id"])
        self.assertTrue(partner.census_active)
        self.assertEqual(partner.name, "Cliente Nuevo Sin RUC")
        self.assertFalse(partner.census_ready_for_activity)

    def test_capa_is_required_for_activity(self):
        self.partner.write({"capa": 0})
        self.partner.invalidate_recordset(["census_ready_for_activity", "census_missing_requirements"])
        self.assertFalse(self.partner.census_ready_for_activity)
        self.assertIn("CAPA", self.partner.census_missing_requirements)
        with self.assertRaises(UserError):
            self.partner.action_new_census_visit()

    def test_mobile_brands_are_optional(self):
        brand = self.env.ref("conedera_odoo_census.mobile_brand_samsung")
        self.partner.write({"mobile_brand_ids": [(6, 0, [brand.id])]})
        self.partner.invalidate_recordset(["census_ready_for_activity"])
        self.assertTrue(self.partner.census_ready_for_activity)
        self.partner.write({"mobile_brand_ids": [(5, 0, 0)]})
        self.partner.invalidate_recordset(["census_ready_for_activity"])
        self.assertTrue(self.partner.census_ready_for_activity)


    def test_lookup_wizard_normalizes_vat_separators(self):
        self.partner.write({"vat": "09-99999999-001"})
        wizard = self.env["conedera.census.customer.lookup.wizard"].create(
            {"vat": "0999999999001"}
        )
        wizard.action_validate()
        self.assertEqual(wizard.validation_state, "found")
        self.assertEqual(wizard.existing_partner_id, self.partner)
        self.assertEqual(wizard.existing_name, self.partner.name)

    def test_timeline_contains_visit_and_quotation(self):
        visit = self.env["conedera.census.visit"].create({"partner_id": self.partner.id})
        order = self.env["sale.order"].create({"partner_id": self.partner.id})
        timeline = self.env["conedera.census.commercial.timeline"].search(
            [("partner_id", "=", self.partner.id)]
        )
        self.assertIn(visit, timeline.mapped("visit_id"))
        self.assertIn(order, timeline.mapped("sale_order_id"))

    def test_product_quote_summary_and_history(self):
        product = self.env["product.product"].create(
            {"name": "Equipo Demo", "list_price": 100.0}
        )
        order = self.env["sale.order"].create({"partner_id": self.partner.id})
        self.env["sale.order.line"].create(
            {
                "order_id": order.id,
                "product_id": product.id,
                "product_uom_qty": 3,
                "price_unit": 100.0,
                "discount": 10.0,
            }
        )
        summary = self.env["conedera.census.product.quote.summary"].search(
            [
                ("partner_id", "=", self.partner.id),
                ("product_id", "=", product.id),
            ],
            limit=1,
        )
        self.assertTrue(summary)
        self.assertEqual(summary.quoted_qty, 3)
        self.assertAlmostEqual(summary.avg_net_unit_price, 90.0, places=2)
        detail = self.env["conedera.census.product.quote.line"].search(
            [
                ("partner_id", "=", self.partner.id),
                ("product_id", "=", product.id),
            ],
            limit=1,
        )
        self.assertTrue(detail)
        self.assertAlmostEqual(detail.net_unit_price, 90.0, places=2)

    def test_global_lookup_detects_foreign_census_and_reassigns_same_record(self):
        sales_group = self.env.ref("conedera_odoo_census.group_census_user")
        supervisor_group = self.env.ref("conedera_odoo_census.group_census_supervisor")
        seller_a = self.env["res.users"].with_context(no_reset_password=True).create(
            {
                "name": "Comercial Destino",
                "login": "census_seller_a_test",
                "groups_id": [(6, 0, [sales_group.id])],
                "company_id": self.env.company.id,
                "company_ids": [(6, 0, [self.env.company.id])],
            }
        )
        seller_b = self.env["res.users"].with_context(no_reset_password=True).create(
            {
                "name": "Comercial Origen",
                "login": "census_seller_b_test",
                "groups_id": [(6, 0, [sales_group.id])],
                "company_id": self.env.company.id,
                "company_ids": [(6, 0, [self.env.company.id])],
            }
        )
        supervisor_a = self.env["res.users"].with_context(no_reset_password=True).create(
            {
                "name": "Supervisor Destino",
                "login": "census_supervisor_a_test",
                "groups_id": [(6, 0, [supervisor_group.id])],
                "company_id": self.env.company.id,
                "company_ids": [(6, 0, [self.env.company.id])],
            }
        )
        supervisor_b = self.env["res.users"].with_context(no_reset_password=True).create(
            {
                "name": "Supervisor Origen",
                "login": "census_supervisor_b_test",
                "groups_id": [(6, 0, [supervisor_group.id])],
                "company_id": self.env.company.id,
                "company_ids": [(6, 0, [self.env.company.id])],
            }
        )
        team_a = self.env["crm.team"].create(
            {
                "name": "Equipo Destino Test",
                "user_id": supervisor_a.id,
                "member_ids": [(6, 0, [seller_a.id])],
                "company_id": self.env.company.id,
                "census_enabled": True,
            }
        )
        team_b = self.env["crm.team"].create(
            {
                "name": "Equipo Origen Test",
                "user_id": supervisor_b.id,
                "member_ids": [(6, 0, [seller_b.id])],
                "company_id": self.env.company.id,
                "census_enabled": True,
            }
        )
        self.partner.sudo().write(
            {"user_id": seller_b.id, "census_team_id": team_b.id}
        )
        # El líder puede revisar/modificar el maestro, pero no saltarse la auditoría
        # cambiando directamente el comercial responsable.
        with self.assertRaises(AccessError):
            self.partner.with_user(supervisor_b).write({"user_id": seller_a.id})
        with self.assertRaises(AccessError):
            self.partner.with_user(supervisor_b).write({"active": False})
        with self.assertRaises(AccessError):
            self.partner.with_user(supervisor_b).write({"census_active": False})

        child_contact = self.env["res.partner"].sudo().create(
            {"name": "Contacto protegido", "parent_id": self.partner.id}
        )
        self.assertFalse(
            self.env["res.partner"].with_user(seller_a).search(
                [("id", "=", child_contact.id)], limit=1
            )
        )

        visit = self.env["conedera.census.visit"].create({"partner_id": self.partner.id})
        historic_order = self.env["sale.order"].sudo().create(
            {
                "partner_id": self.partner.id,
                "user_id": seller_b.id,
            }
        )
        historic_product = self.env["product.product"].create(
            {"name": "Equipo Histórico Reasignación", "list_price": 250.0}
        )
        historic_line = self.env["sale.order.line"].sudo().create(
            {
                "order_id": historic_order.id,
                "product_id": historic_product.id,
                "product_uom_qty": 2.0,
                "price_unit": 250.0,
            }
        )
        partner_id_before = self.partner.id

        Wizard = self.env["conedera.census.customer.lookup.wizard"].with_user(seller_a)
        candidates = Wizard.search_global_candidates(self.partner.vat)
        match = next(c for c in candidates if c["id"] == self.partner.id)
        self.assertEqual(match["status"], "other_census")
        self.assertFalse(match["can_open"])
        self.assertTrue(match["can_request"])
        self.assertEqual(match["owner_label"], "Otro comercial")

        wizard = Wizard.create(
            {
                "lookup_query": self.partner.vat,
                "selected_partner_ref_id": self.partner.id,
                "selected_candidate_status": "other_census",
                "selected_can_request_reassignment": True,
                "selected_is_census": True,
                "existing_name": self.partner.name,
                "existing_vat": self.partner.vat,
                "reassignment_reason": "Cambio de zona comercial",
            }
        )
        wizard.action_request_reassignment()
        request = self.env["conedera.census.reassignment.request"].sudo().search(
            [
                ("partner_id", "=", self.partner.id),
                ("requested_by_id", "=", seller_a.id),
                ("state", "=", "pending"),
            ],
            limit=1,
        )
        self.assertTrue(request)
        request.with_user(supervisor_b).action_approve()
        self.partner.invalidate_recordset(["user_id", "census_team_id"])
        self.assertEqual(self.partner.id, partner_id_before)
        self.assertEqual(self.partner.user_id, seller_a)
        self.assertEqual(self.partner.census_team_id, team_a)
        self.assertIn(visit, self.partner.census_visit_ids)

        # The new responsible salesperson can open the same customer's child contacts
        # and historical quotations, but our added rules are read-only for those sales
        # documents and do not rewrite their original salesperson/history.
        self.assertTrue(
            self.env["res.partner"].with_user(seller_a).search(
                [("id", "=", child_contact.id)], limit=1
            )
        )
        self.assertTrue(
            self.env["sale.order"].with_user(seller_a).search(
                [("id", "=", historic_order.id)], limit=1
            )
        )
        self.assertTrue(
            self.env["sale.order.line"].with_user(seller_a).search(
                [("id", "=", historic_line.id)], limit=1
            )
        )
        self.assertEqual(historic_order.user_id, seller_b)

    def test_non_census_duplicate_contact_can_be_selected_without_new_partner(self):
        duplicate = self.env["res.partner"].create(
            {
                "name": "Contacto histórico duplicado",
                "vat": "0911111111",
                "customer_rank": 1,
            }
        )
        wizard = self.env["conedera.census.customer.lookup.wizard"].create(
            {
                "lookup_query": "0911111111",
                "selected_partner_ref_id": duplicate.id,
                "selected_can_use": True,
                "selected_candidate_status": "available_contact",
                "existing_vat": duplicate.vat,
            }
        )
        count_before = self.env["res.partner"].search_count([("vat", "=", "0911111111")])
        action = wizard.action_use_selected()
        count_after = self.env["res.partner"].search_count([("vat", "=", "0911111111")])
        self.assertEqual(count_before, count_after)
        self.assertEqual(action["res_id"], duplicate.id)
        self.assertTrue(duplicate.census_active)

    def test_draft_salesperson_can_select_valid_commercial_team(self):
        census_group = self.env.ref("conedera_odoo_census.group_census_user")
        seller = self.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Comercial Selector",
            "login": "census_team_selector_test",
            "groups_id": [(6, 0, [census_group.id])],
            "company_id": self.env.company.id,
            "company_ids": [(6, 0, [self.env.company.id])],
        })
        team = self.env["crm.team"].create({
            "name": "Equipo Seleccionable",
            "member_ids": [(6, 0, [seller.id])],
            "company_id": self.env.company.id,
            "census_enabled": True,
        })
        draft = self.env["res.partner"].sudo().create({
            "name": "Cliente Borrador Equipo",
            "commercial_name": "Cliente Borrador Equipo",
            "vat": "0918181818",
            "census_active": True,
            "user_id": seller.id,
            "census_locked": False,
        })
        draft.with_user(seller).write({"census_team_id": team.id})
        draft.invalidate_recordset(["census_team_id"])
        self.assertEqual(draft.census_team_id, team)

    def test_locked_salesperson_cannot_change_team_directly(self):
        census_group = self.env.ref("conedera_odoo_census.group_census_user")
        seller = self.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Comercial Bloqueado",
            "login": "census_locked_team_test",
            "groups_id": [(6, 0, [census_group.id])],
            "company_id": self.env.company.id,
            "company_ids": [(6, 0, [self.env.company.id])],
        })
        team_a = self.env["crm.team"].create({
            "name": "Equipo Bloqueado A",
            "member_ids": [(6, 0, [seller.id])],
            "company_id": self.env.company.id,
            "census_enabled": True,
        })
        team_b = self.env["crm.team"].create({
            "name": "Equipo Bloqueado B",
            "member_ids": [(6, 0, [seller.id])],
            "company_id": self.env.company.id,
            "census_enabled": True,
        })
        locked = self.partner.sudo()
        locked._census_internal_control_update({"census_team_id": team_a.id, "census_locked": True})
        locked.sudo().write({"user_id": seller.id})
        with self.assertRaises(AccessError):
            locked.with_user(seller).write({"census_team_id": team_b.id})

    def test_register_census_reopens_isolated_catastro_form(self):
        action = self.partner.action_register_census()
        view = self.env.ref("conedera_odoo_census.view_partner_form_census_mobile")
        self.partner.invalidate_recordset(["census_locked"])
        self.assertTrue(self.partner.census_locked)
        self.assertEqual(action["res_model"], "res.partner")
        self.assertEqual(action["res_id"], self.partner.id)
        self.assertEqual(action["views"], [(view.id, "form")])
        self.assertTrue(action["context"]["conedera_census_isolated_form"])
        self.assertNotEqual(action.get("tag"), "reload")

    def test_role_wizard_assigns_commercial_team_without_opening_team_dashboard(self):
        manager_group = self.env.ref("conedera_odoo_census.group_census_manager")
        census_group = self.env.ref("conedera_odoo_census.group_census_user")
        admin = self.env.user
        admin.sudo().write({"groups_id": [(4, manager_group.id)]})
        seller = self.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Comercial Permisos",
            "login": "census_permissions_team_test",
            "groups_id": [(6, 0, [census_group.id])],
            "company_id": self.env.company.id,
            "company_ids": [(6, 0, [self.env.company.id])],
        })
        team = self.env["crm.team"].create({
            "name": "Equipo Permisos",
            "company_id": self.env.company.id,
            "census_enabled": True,
        })
        wizard = self.env["conedera.census.role.wizard"].create({
            "user_id": seller.id,
            "role": "user",
            "team_id": team.id,
        })
        wizard.action_apply()
        self.assertIn(seller, team.member_ids)
    def test_unlock_request_rejection_keeps_reason_for_salesperson(self):
        request = self.env["conedera.census.unlock.request"].create({
            "partner_id": self.partner.id,
            "requested_by_id": self.env.user.id,
            "reason": "Actualizar dirección",
        })
        request._reject_with_reason("Falta documento de respaldo")
        self.assertEqual(request.state, "rejected")
        self.assertEqual(request.review_note, "Falta documento de respaldo")
        self.partner.invalidate_recordset([
            "census_latest_unlock_state",
            "census_latest_unlock_review_note",
        ])
        self.assertEqual(self.partner.census_latest_unlock_state, "rejected")
        self.assertEqual(
            self.partner.census_latest_unlock_review_note,
            "Falta documento de respaldo",
        )

    def test_refresh_unlock_status_reopens_dedicated_census_form(self):
        action = self.partner.action_refresh_census_unlock_status()
        self.assertEqual(action["res_model"], "res.partner")
        self.assertEqual(action["res_id"], self.partner.id)
        self.assertEqual(
            action["view_id"],
            self.env.ref("conedera_odoo_census.view_partner_form_census_mobile").id,
        )

