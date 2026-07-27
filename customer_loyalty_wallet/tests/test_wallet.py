from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestLoyaltyWallet(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        manager_group = cls.env.ref(
            "customer_loyalty_wallet.group_wallet_manager"
        )
        cls.env.user.write({"groups_id": [Command.link(manager_group.id)]})
        cls.partner = cls.env["res.partner"].create({"name": "Cliente prueba"})
        cls.wallet = cls.env["loyalty.wallet"].create({"partner_id": cls.partner.id})

    def _movement(self, movement_type, amount, description="Prueba"):
        movement = self.env["loyalty.wallet.transaction"].create(
            {
                "wallet_id": self.wallet.id,
                "transaction_type": movement_type,
                "reason": "punctual_payment" if movement_type == "credit" else "redemption",
                "amount": amount,
                "description": description,
            }
        )
        movement.action_confirm()
        return movement

    def test_balance_and_insufficient_funds(self):
        self._movement("credit", 10)
        self._movement("debit", 3)
        self.assertEqual(self.wallet.balance, 7)
        with self.assertRaises(ValidationError):
            self._movement("debit", 8)

    def test_reversal_preserves_audit(self):
        credit = self._movement("credit", 5)
        credit.action_reverse()
        self.assertEqual(self.wallet.balance, 0)
        self.assertTrue(credit.reversal_id)
        self.assertEqual(credit.reversal_id.state, "confirmed")
