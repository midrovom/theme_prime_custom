"""Default city policies using the real configuration/import model methods.

The ORM is simulated; native Odoo integration tests are included separately.
"""
from datetime import date
from types import SimpleNamespace
import unittest
from test_import_queue_standalone import Company, Environment, Job


class CityDefaultsTests(unittest.TestCase):
    def setUp(self):
        self.env = Environment()
        self.rules = self.env["dispatch.sla"]
        self.company = Company(1)

    def find(self, city, company=1):
        return [r for r in self.rules.records if r.company_id == company and r.city_key == city]

    def test_all_cities_nine_except_guayaquil_three(self):
        self.rules._ensure_city_defaults(self.company, ["Quito", "Cuenca", "Guayaquil"])
        self.assertEqual({r.city_key:r.max_days for r in self.rules.records}, {"QUITO":9, "CUENCA":9, "GUAYAQUIL":3})
        self.assertTrue(all(r.day_type == "calendar" and r.valid_from == date(1900,1,1) for r in self.rules.records))

    def test_variations_do_not_duplicate_cities_on_reimport(self):
        self.rules._ensure_city_defaults(self.company, ["  GuAyAqUiL ", "QUITO", " Santo   Domingo "])
        self.rules._ensure_city_defaults(self.company, ["GUAYAQUIL", "Quíto", "santo domingo"])
        self.assertEqual(len(self.rules.records), 3)

    def test_edited_days_and_calendar_are_never_reset(self):
        self.rules._ensure_city_defaults(self.company, ["Quito"])
        rule = self.find("QUITO")[0]; rule.max_days = 14; rule.day_type = "business"
        self.rules._ensure_city_defaults(self.company, ["Quito", "Loja"])
        pack = self.rules._policy_pack(self.company)
        custom = next(r for r in pack["rules"] if r["city_key"] == "QUITO")
        self.assertEqual((custom["max_days"], custom["day_type"]), (14, "business"))
        self.assertEqual(self.find("LOJA")[0].max_days, 9)

    def test_archived_city_is_not_recreated_or_reactivated(self):
        self.rules._ensure_city_defaults(self.company, ["Quito"])
        self.find("QUITO")[0].active = False
        self.rules._ensure_city_defaults(self.company, ["QUITO"])
        self.assertEqual(len(self.find("QUITO")), 1)
        self.assertFalse(self.find("QUITO")[0].active)
        self.assertFalse(any(r["city_key"] == "QUITO" for r in self.rules._policy_pack(self.company)["rules"]))

    def test_dated_city_rule_is_not_overlapped_by_default(self):
        self.rules.create([{"company_id":1,"city":"Quito","max_days":20,"valid_from":date(2027,1,1)}])
        self.rules._ensure_city_defaults(self.company, ["Quito"])
        self.assertEqual(len(self.find("QUITO")), 1)
        self.assertEqual(self.find("QUITO")[0].max_days, 20)

    def test_specific_delivery_keeps_priority_over_city_default(self):
        self.rules.create([{"company_id":1,"city":"Guayaquil","delivery":"Entrega Transcash","max_days":5}])
        self.rules._ensure_city_defaults(self.company, ["Guayaquil"])
        from dispatch_queue_test.services.engine import pick_policy
        pack = self.rules._policy_pack(self.company)
        invoice = {"city":"GUAYAQUIL","invoice_date":"2026-01-01","delivery":"Entrega Transcash"}
        self.assertEqual(pick_policy(invoice, pack)["max_days"], 5)
        self.assertEqual(pick_policy({**invoice,"delivery":"Retiro cliente"}, pack)["max_days"], 3)

    def test_companies_keep_separate_settings(self):
        self.rules._ensure_city_defaults(self.company, ["Quito"])
        self.find("GUAYAQUIL")[0].max_days = 12
        self.rules._ensure_city_defaults(Company(2), ["Quito"])
        self.assertEqual(self.find("GUAYAQUIL",1)[0].max_days, 12)
        self.assertEqual(self.find("GUAYAQUIL",2)[0].max_days, 3)
        self.assertEqual(len(self.find("QUITO",2)), 1)

    def test_empty_or_unknown_city_does_not_create_fake_city(self):
        self.rules._ensure_city_defaults(self.company, [None, False, " ", "SIN CIUDAD"])
        self.assertEqual([r.city_key for r in self.rules.records], ["GUAYAQUIL"])

    def test_update_backfills_old_invoices_and_preserves_edits(self):
        class Companies(list):
            @property
            def ids(self): return [c.id for c in self]
            def sudo(self): return self
            def search(self, domain): return self
        self.env.models["res.company"] = Companies([self.company,Company(2)])
        self.env.invoices.city_groups = [
            {"company_id":[1,"Main"],"city":"Quito"},
            {"company_id":[1,"Main"],"city":"QUITO"},
            {"company_id":[1,"Main"],"city":"SIN CIUDAD"},
            {"company_id":[2,"Other"],"city":"Loja"},
        ]
        self.rules._initialize_city_defaults()
        self.find("QUITO")[0].max_days = 18
        self.rules._initialize_city_defaults()
        self.assertEqual(len(self.rules.records), 4)
        self.assertEqual(self.find("QUITO")[0].max_days, 18)
        self.assertEqual(self.find("LOJA",2)[0].max_days, 9)

    def prepare(self, input_type):
        job = Job(); job.input_type = input_type
        rows = [{"TipoFactura":"FA","NumeroFactura":str(i),"FechaFactura":"2026-10-20",
            "Ciudad":city,"CodBodega":"A","Facturado":1,"DespachoFisico":0,"Pendiente":1}
            for i,city in enumerate(["Guayaquil","Quito"],1)]
        job._rows = lambda: iter(rows)
        job.total_rows = len(rows)
        job._prepare(); job._load_next()
        return job

    def test_excel_rules_apply_to_the_first_import(self):
        job = self.prepare("xlsx")
        self.assertEqual(job.env.invoices.sla_days_counts, {"GUAYAQUIL":{3},"QUITO":{9}})
        invoices = {i["city"]:i for i in job.env.invoices.created_values}
        self.assertEqual(invoices["GUAYAQUIL"]["deadline"], "2026-10-23")
        self.assertEqual(invoices["QUITO"]["deadline"], "2026-10-29")

    def test_api_uses_same_city_creation_and_initial_deadlines(self):
        job = self.prepare("api")
        self.assertEqual(job.env.invoices.sla_days_counts, {"GUAYAQUIL":{3},"QUITO":{9}})


if __name__ == "__main__": unittest.main()
