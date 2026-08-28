from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestWebsiteProductOffer(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.website = cls.env["website"].search([], limit=1)
        cls.website.write(
            {
                "offer_enabled": True,
                "offer_product_scope": "all",
                "offer_in_stock_only": False,
                "offer_limit_to_stock": False,
            }
        )
        cls.partner = cls.env["res.partner"].create(
            {"name": "Cliente de prueba", "email": "cliente@example.com"}
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "Teléfono de prueba",
                "sale_ok": True,
                "type": "consu",
                "list_price": 500.0,
            }
        )

    def _create_offer(self, **extra_values):
        values = {
            "website_id": self.website.id,
            "company_id": self.website.company_id.id,
            "partner_id": self.partner.id,
            "contact_name": self.partner.name,
            "contact_email": self.partner.email,
            "product_id": self.product.id,
            "quantity": 2.0,
            "pricelist_id": self.website.pricelist_id.id,
            "list_price": 500.0,
            "offered_price": 450.0,
        }
        values.update(extra_values)
        return self.env["website.sale.offer"].create(values)

    def test_convert_offer_creates_native_quotation(self):
        offer = self._create_offer()
        offer.action_accept_offer()
        self.assertTrue(offer.sale_order_id)
        self.assertEqual(offer.state, "converted")
        self.assertEqual(offer.sale_order_id.website_id, self.website)
        self.assertEqual(offer.sale_order_id.website_offer_id, offer)
        self.assertEqual(offer.sale_order_id.order_line.product_id, self.product)
        self.assertEqual(offer.sale_order_id.order_line.product_uom_qty, 2.0)
        self.assertEqual(offer.sale_order_id.order_line.price_unit, 450.0)

    def test_offer_positive_values(self):
        with self.assertRaises(ValidationError):
            self._create_offer(quantity=0)

    def test_counteroffer_uses_counter_price(self):
        offer = self._create_offer(counter_price=470.0)
        offer.action_send_counter()
        self.assertEqual(offer.state, "counter")
        offer.action_customer_accept_counter()
        self.assertEqual(offer.sale_order_id.order_line.price_unit, 470.0)

