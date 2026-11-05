import unittest
from types import SimpleNamespace
from pathlib import Path
from importlib.util import spec_from_file_location, module_from_spec

# Pruebas unitarias sin Odoo en el entorno de desarrollo.
spec = spec_from_file_location('radis_payload_under_test', Path(__file__).resolve().parents[1] / 'radis_payload.py')
module = module_from_spec(spec)
spec.loader.exec_module(module)
enrich_payload = module.enrich_payload
PayloadMismatch = module.PayloadMismatch


class Lines(list):
    def filtered(self, fn):
        return Lines(l for l in self if fn(l))


def line(sku, qty, price, warehouse, discount=0, increase=0, applied=False):
    return SimpleNamespace(product_id=SimpleNamespace(default_code=sku),
                           product_uom_qty=qty, price_unit=price,
                           warehouse_id=SimpleNamespace(code=warehouse),
                           display_type=False, discount=discount, increase=increase,
                           applied=applied)


class Order:
    def __init__(self, items):
        self.order_line = Lines(items)
        self.warehouse_id = SimpleNamespace(code='MAIN')

    def _catastro_radis_line_percentages(self, item):
        return {'discount_percent': round(item.discount, 4),
                'increase_percent': round(item.increase if item.applied else 0.0, 4)}


class PayloadTest(unittest.TestCase):
    def setUp(self):
        self.order = Order([line('A1', 2, 105, 'WH1', discount=10, increase=5, applied=True),
                            line('B2', 1, 50, 'WH2')])
        self.data = [{'order_name': 'SO001', 'order_lines': [
            {'sku': 'A1', 'quantity': 2, 'price_unit': '105.0', 'order_location_wh': 'WH1'},
            {'sku': 'B2', 'quantity': 1, 'price_unit': '50.0', 'order_location_wh': 'WH2'},
        ]}]

    def test_sends_both_fields_preserving_original(self):
        output = enrich_payload(self.data, lambda name: self.order)
        self.assertEqual(output[0]['order_lines'][0]['discount_percent'], 10)
        self.assertEqual(output[0]['order_lines'][0]['increase_percent'], 5)
        self.assertEqual(output[0]['order_lines'][0]['price_unit'], '105.0')
        self.assertEqual(output[0]['order_lines'][1]['discount_percent'], 0)
        self.assertEqual(output[0]['order_lines'][1]['increase_percent'], 0)
        self.assertNotIn('discount_percent', self.data[0]['order_lines'][0])

    def test_rejects_wrong_line_alignment(self):
        self.data[0]['order_lines'][0]['sku'] = 'WRONG'
        with self.assertRaises(PayloadMismatch):
            enrich_payload(self.data, lambda name: self.order)

    def test_rejects_wrong_price(self):
        self.data[0]['order_lines'][1]['price_unit'] = '123'
        with self.assertRaises(PayloadMismatch):
            enrich_payload(self.data, lambda name: self.order)

    def test_rejects_wrong_count(self):
        self.data[0]['order_lines'].pop()
        with self.assertRaises(PayloadMismatch):
            enrich_payload(self.data, lambda name: self.order)


if __name__ == '__main__':
    unittest.main()
