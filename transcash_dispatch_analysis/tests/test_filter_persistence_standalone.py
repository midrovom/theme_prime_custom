"""Regression tests for persisted dispatch dashboard filters without PostgreSQL.

Odoo integration is still needed for ORM schema, ACLs and client navigation.
"""
from copy import deepcopy
from types import SimpleNamespace
import unittest

from test_import_queue_standalone import load_model

module = load_model("dashboard")


class StoredPreference:
    def __init__(self, values):
        self.write(values)

    def write(self, values):
        for key, value in deepcopy(values).items():
            if key in ("board_id", "favorite_id"):
                value = SimpleNamespace(id=value) if value else False
            setattr(self, key, value)


class StateStore:
    def __init__(self):
        self.rows = []

    def sudo(self):
        return self

    def search(self, domain, limit=1):
        conditions = {key: value for key, _, value in domain}
        return next((row for row in self.rows if all(
            getattr(row, key) == value for key, value in conditions.items())), False)

    def create(self, values):
        item = StoredPreference(values)
        self.rows.append(item)
        return item


class Scope:
    def __init__(self, uid, company_ids, store):
        self.uid = uid
        self.su = True
        self.companies = SimpleNamespace(ids=company_ids)
        self.models = {"dispatch.dashboard.state": store}

    def __getitem__(self, name):
        return self.models[name]


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.store = StateStore()

    def service(self, uid=3, companies=(1,)):
        service = module.DispatchDashboard()
        service.env = Scope(uid, list(companies), self.store)
        service.get_saved_filters = lambda: [{"id": 55, "name": "Mis bodegas"}]
        return service

    def test_reentering_dashboard_restores_dates_multiple_warehouses_and_favorite(self):
        filters = {"source_id": "", "snapshot_id": "", "city": "QUITO", "delivery": "",
                   "date_from": "2026-01-01", "date_to": "2026-11-27", "warehouse_ids": [2, 5],
                   "planning_scope": "filtered", "planning_grouping": "destination"}
        self.service().save_active_filter_state(filters, favorite_id="55")
        result = self.service().get_active_filter_state()
        self.assertEqual(result["filters"], filters)
        self.assertEqual(result["favorite_id"], 55)
        self.assertFalse(result["board_id"])

    def test_following_changes_replace_last_applied_filters_and_remove_favorite(self):
        service = self.service()
        service.save_active_filter_state({"warehouse_ids": [5]}, favorite_id=55)
        service.save_active_filter_state({"warehouse_ids": [9, 10], "date_to": ""})
        self.assertEqual(len(self.store.rows), 1)
        self.assertEqual(service.get_active_filter_state()["filters"],
                         {"warehouse_ids": [9, 10], "date_to": ""})
        self.assertFalse(service.get_active_filter_state()["favorite_id"])

    def test_users_and_company_selections_do_not_share_preferences(self):
        self.service(uid=3, companies=(1, 2)).save_active_filter_state({"city": "CUENCA"})
        self.service(uid=4, companies=(1, 2)).save_active_filter_state({"city": "QUITO"})
        self.service(uid=3, companies=(1,)).save_active_filter_state({"city": "GUAYAQUIL"})
        self.assertEqual(self.service(uid=3, companies=(2, 1)).get_active_filter_state()["filters"]["city"], "CUENCA")
        self.assertEqual(self.service(uid=4, companies=(1, 2)).get_active_filter_state()["filters"]["city"], "QUITO")
        self.assertEqual(self.service(uid=3, companies=(1,)).get_active_filter_state()["filters"]["city"], "GUAYAQUIL")
        self.assertFalse(self.service(uid=3, companies=(2,)).get_active_filter_state())

    def test_invalid_filters_are_rejected_without_overwriting_last_state(self):
        service = self.service()
        service.save_active_filter_state({"warehouse_ids": [5]})
        for invalid in ({"warehouse_ids": [True]}, {"planning_scope": "wrong"},
                        {"planning_grouping": "wrong"}, {"date_from": "2026-12-01", "date_to": "2026-01-01"}):
            with self.assertRaises(module.ValidationError):
                service.save_active_filter_state(invalid)
        self.assertEqual(service.get_active_filter_state()["filters"], {"warehouse_ids": [5]})

    def test_no_other_user_favorite_can_be_activated(self):
        service = self.service()
        service.save_active_filter_state({"warehouse_ids": [5]}, favorite_id="999")
        self.assertFalse(service.get_active_filter_state()["favorite_id"])


if __name__ == "__main__":
    unittest.main()
