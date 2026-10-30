"""The real versioned upgrade must not touch historical data on a 1.6+ update."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import patch
import ast
import sys
import unittest
import xml.etree.ElementTree as ET

from test_planning_standalone import load

maintenance = load("maintenance")
ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "migrations/18.0.1.7.1/post-10-legacy-data.py"


def run_upgrade(version):
    calls = []
    cursor = object()

    class Models:
        def _initialize_city_defaults(self): calls.append("cities")
        def _initialize_unique_records(self): calls.append("unique_records")

    def environment(cr, uid, context):
        assert cr is cursor and uid == 1 and context == {}
        calls.append("environment")
        return {"dispatch.sla": Models(), "dispatch.invoice": Models()}

    odoo = ModuleType("odoo")
    odoo.api = SimpleNamespace(Environment=environment)
    odoo.SUPERUSER_ID = 1
    name = "odoo.addons.transcash_dispatch_analysis.services.maintenance"
    with patch.dict(sys.modules, {"odoo": odoo, name: maintenance}):
        spec = spec_from_file_location("dispatch_upgrade_regression", SCRIPT)
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
        module.migrate(cursor, version)
    return calls


class UpgradeTests(unittest.TestCase):
    def test_modern_versions_do_not_create_an_environment_or_read_invoices(self):
        for version in ("18.0.1.6.0", "18.0.1.6.1", "18.0.1.7.0", "18.0.1.7.1", "18.0.1.9.0"):
            self.assertEqual(run_upgrade(version), [], version)

    def test_legacy_weight_and_pallet_conversion_is_not_lost(self):
        for version in ("18.0.1.3.0", "18.0.1.4.0", "18.0.1.5.0", "18.0.1.5.1"):
            self.assertEqual(run_upgrade(version), ["environment", "unique_records"])

    def test_versions_before_city_defaults_run_city_then_unique_conversion(self):
        for version in ("18.0.1.0.0", "18.0.1.1.0", "18.0.1.2.0"):
            self.assertEqual(run_upgrade(version), ["environment", "cities", "unique_records"])

    def test_initial_install_needs_no_historical_upgrade(self):
        for version in (None, False, ""):
            self.assertEqual(run_upgrade(version), [])

    def test_short_and_padded_numeric_versions_keep_the_cutoff(self):
        self.assertEqual(maintenance.required_upgrade_steps("1.6.0"), ())
        self.assertEqual(maintenance.required_upgrade_steps("18.0.1.6"), ())
        self.assertEqual(maintenance.required_upgrade_steps("1.5.1"), ("unique_records",))

    def test_unknown_legacy_version_is_not_silently_declared_converted(self):
        self.assertEqual(run_upgrade("legacy-custom"), ["environment", "cities", "unique_records"])

    def test_large_conversion_functions_are_install_only_in_all_xml_data(self):
        manifest = ast.literal_eval((ROOT / "__manifest__.py").read_text())
        found = set()
        for path in manifest["data"]:
            if not path.endswith(".xml"):
                continue
            tree = ET.parse(ROOT / path).getroot()
            for function in tree.iter("function"):
                name = function.get("name")
                if name in ("_initialize_unique_records", "_initialize_city_defaults"):
                    self.assertEqual(tree.get("noupdate"), "1", path)
                    found.add(name)
        self.assertEqual(found, {"_initialize_unique_records", "_initialize_city_defaults"})

    def test_script_directory_matches_manifest_for_odoo_upgrade_discovery(self):
        manifest = ast.literal_eval((ROOT / "__manifest__.py").read_text())
        self.assertLessEqual(tuple(map(int, SCRIPT.parent.name.split("."))), tuple(map(int, manifest["version"].split("."))))
        self.assertTrue(SCRIPT.name.startswith("post-"))
        self.assertEqual(SCRIPT.parent.name, "18.0.1.7.1")


if __name__ == "__main__":
    unittest.main()
