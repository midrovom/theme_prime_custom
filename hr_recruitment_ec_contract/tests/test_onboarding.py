from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestEcOnboarding(TransactionCase):
    def test_default_templates_exist(self):
        document_types = set(self.env["hr.ec.document.template"].search([]).mapped("document_type"))
        self.assertTrue({"contract", "thirteenth", "employee_file"}.issubset(document_types))
