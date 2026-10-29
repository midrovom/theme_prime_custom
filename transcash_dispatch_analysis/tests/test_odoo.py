from odoo.tests import TransactionCase, tagged
from odoo.exceptions import ValidationError, AccessError


@tagged("post_install", "-at_install")
class TestDispatchIntegration(TransactionCase):
    def setUp(self):
        super().setUp()
        self.source = self.env["dispatch.source"].create({"name": "Test", "code": "TEST-DISPATCH", "company_id": self.env.company.id})
        self.env["dispatch.sla"].create({"company_id": self.env.company.id, "city": "Guayaquil", "max_days": 2})
        self.row = {"TipoFactura": "FA", "NumeroFactura": "1", "Factura": "001", "FechaFactura": "2026-01-01", "Ciudad": "Guayaquil", "CodProducto": "A", "CodBodega": "X", "Facturado": 1, "DespachoFisico": 0, "Pendiente": 1}

    def _snapshot(self, key):
        value = self.source.api_start_batch(key, "2026-01-10")
        result = self.env["dispatch.snapshot"].browse(value["id"])
        result.api_append_chunk(0, [self.row])
        result.api_finalize(1, 1)
        return result

    def test_api_retry_is_idempotent(self):
        snapshot = self._snapshot("idempotent")
        self.assertTrue(snapshot.api_append_chunk(0, [self.row])["duplicate"])
        self.assertEqual(self.source.api_start_batch("idempotent", "2026-01-10")["id"], snapshot.id)
        with self.assertRaises(ValidationError): snapshot.api_append_chunk(0, [{**self.row, "Pendiente": 0}])

    def test_atomic_snapshot_activation(self):
        first = self._snapshot("first")
        first._prepare()
        self.assertFalse(self.source.active_snapshot_id)
        first._load_next()
        self.assertEqual(self.source.active_snapshot_id, first)
        second = self._snapshot("second")
        second._prepare()
        self.assertEqual(self.source.active_snapshot_id, first)
        second._load_next()
        self.assertEqual(self.source.active_snapshot_id, second)
        self.assertEqual(first.state, "archived")
        self.assertEqual(self.env["dispatch.dashboard"].get_data({"source_id": self.source.id})["stats"]["pending"], 1)

    def test_older_cutoff_never_overwrites_newer(self):
        latest = self._snapshot("latest")
        latest._prepare(); latest._load_next()
        old_id = self.source.api_start_batch("old", "2026-01-05")["id"]
        old = self.env["dispatch.snapshot"].browse(old_id)
        old.api_finalize(0, 0)
        old._prepare()
        self.assertEqual(self.source.active_snapshot_id, latest)
        self.assertEqual(old.state, "archived")

    def test_reader_cannot_ingest(self):
        user = self.env["res.users"].create({"name": "Reader", "login": "dispatch_reader_test", "company_id": self.env.company.id,
            "company_ids": [(6, 0, [self.env.company.id])], "groups_id": [(6, 0, [self.env.ref("transcash_dispatch_analysis.group_dispatch_user").id])]})
        with self.assertRaises(AccessError): self.source.with_user(user).api_start_batch("forbidden", "2026-01-10")

    def test_other_company_not_visible(self):
        company = self.env["res.company"].create({"name": "Another dispatch company"})
        foreign = self.env["dispatch.source"].create({"name": "Foreign", "code": "FOREIGN", "company_id": company.id})
        user = self.env["res.users"].create({"name": "Operator", "login": "dispatch_operator_test", "company_id": self.env.company.id,
            "company_ids": [(6, 0, [self.env.company.id])], "groups_id": [(6, 0, [self.env.ref("transcash_dispatch_analysis.group_dispatch_operator").id])]})
        with self.assertRaises(AccessError): foreign.with_user(user).api_start_batch("cross-company", "2026-01-10")

    def test_policy_reapply_preserves_history(self):
        first = self._snapshot("policy-first")
        first._prepare(); first._load_next()
        rule = self.env["dispatch.sla"].search([("company_id", "=", self.env.company.id), ("city_key", "=", "GUAYAQUIL")], limit=1)
        rule.max_days = 20
        self.assertEqual(first.invoice_ids.sla_days, 2)
        action = first.action_recalculate()
        second = self.env["dispatch.snapshot"].browse(action["res_id"])
        second._prepare(); second._load_next()
        self.assertEqual(second.invoice_ids.sla_days, 20)
        self.assertEqual(first.invoice_ids.sla_days, 2)
