import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PackageContractTests(unittest.TestCase):
    def load_doctype(self, name):
        return json.loads((ROOT / "brightsteps_gls" / "bright_steps_gls" / "doctype" / name / f"{name}.json").read_text())

    def test_shipment_has_unique_open_group_lock(self):
        fields = {field["fieldname"]: field for field in self.load_doctype("gls_shipment")["fields"]}
        self.assertEqual(fields["open_grouping_key"].get("unique"), 1)
        self.assertIn("delivery_notes", fields)
        self.assertIn("parcels", fields)

    def test_sandbox_and_production_credentials_are_separate(self):
        fields = {field["fieldname"] for field in self.load_doctype("gls_settings")["fields"]}
        self.assertTrue({
            "sandbox_client_id", "sandbox_client_secret", "sandbox_contact_id",
            "production_client_id", "production_client_secret", "production_contact_id",
            "production_approved",
        }.issubset(fields))

    def test_scheduler_runs_twice_daily(self):
        hooks = (ROOT / "brightsteps_gls" / "hooks.py").read_text()
        self.assertIn('"0 12,18 * * *"', hooks)

    def test_shipping_run_stops_after_pick_lists(self):
        service = (ROOT / "brightsteps_gls" / "services" / "shipping_run.py").read_text()
        execute_body = service.split("def execute_shipping_run", 1)[1].split("def confirm_packing", 1)[0]
        self.assertIn('run.status = "Pick Lists Created"', execute_body)
        self.assertNotIn("_create_delivery_note(", execute_body)

    def test_packing_confirmation_creates_delivery_notes_before_labels(self):
        service = (ROOT / "brightsteps_gls" / "services" / "shipping_run.py").read_text()
        confirmation = service.split("def confirm_packing", 1)[1].split("def _picked_allocations", 1)[0]
        self.assertLess(confirmation.index("_create_delivery_note"), confirmation.index("create_labels(shipment_name)"))
        api = (ROOT / "brightsteps_gls" / "api.py").read_text()
        self.assertIn("def confirm_packed_pick_list", api)

    def test_shipping_run_has_warehouse_confirmation_ui(self):
        hooks = (ROOT / "brightsteps_gls" / "hooks.py").read_text()
        self.assertIn('"Shipping Run": "public/js/shipping_run.js"', hooks)
        script = (ROOT / "brightsteps_gls" / "public" / "js" / "shipping_run.js").read_text()
        self.assertIn("Lieferscheine und Paketscheine erstellen", script)

    def test_fresh_install_is_inert(self):
        fields = {field["fieldname"]: field for field in self.load_doctype("shipping_run_settings")["fields"]}
        for name in ("enabled", "automatic_run", "submit_pick_lists", "submit_delivery_notes"):
            self.assertEqual(fields[name].get("default"), "0")
        installer = (ROOT / "brightsteps_gls" / "setup" / "install.py").read_text()
        self.assertIn("seed_shipping_run_settings(force_safe=True)", installer)
        self.assertIn('"enabled": 0', installer)
        gls = {field["fieldname"]: field for field in self.load_doctype("gls_settings")["fields"]}
        self.assertEqual(gls["enabled"].get("default"), "0")
        self.assertEqual(gls["environment"].get("default"), "Sandbox")

    def test_legacy_scripts_are_disabled_not_deleted(self):
        installer = (ROOT / "brightsteps_gls" / "setup" / "install.py").read_text()
        self.assertIn('"disabled", 1', installer)
        self.assertNotIn("delete_doc", installer)

    def test_all_package_versions_match(self):
        expected = "0.3.1"
        self.assertIn(f'version = "{expected}"', (ROOT / "pyproject.toml").read_text())
        self.assertIn(f'version="{expected}"', (ROOT / "setup.py").read_text())
        self.assertIn(f'__version__ = "{expected}"', (ROOT / "brightsteps_gls" / "__init__.py").read_text())
        self.assertIn(f'app_version = "{expected}"', (ROOT / "brightsteps_gls" / "hooks.py").read_text())


if __name__ == "__main__":
    unittest.main()
