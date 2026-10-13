import unittest
from domain import normalize_order

class OrdersTests(unittest.TestCase):
    def test_normal_order(self):
        self.assertEqual(normalize_order({"item": "  training laptop  ", "quantity": 2}, "order-1", "dev"),
                         {"id": "order-1", "item": "training laptop", "quantity": 2, "environment": "dev"})
    def test_missing_item(self):
        with self.assertRaises(ValueError): normalize_order({}, "x", "dev")
    def test_invalid_quantity(self):
        for value in [0, -1, True, "2", 1.2, 1001]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_order({"item": "x", "quantity": value}, "x", "dev")
    def test_item_not_string_or_too_long(self):
        for value in [None, 5, "", " " * 4, "x" * 201]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_order({"item": value}, "x", "dev")
    def test_client_cannot_choose_id_or_environment(self):
        self.assertEqual(normalize_order({"item":"x", "id":"evil", "environment":"prod"}, "server-id", "dev")["id"], "server-id")
        self.assertEqual(normalize_order({"item":"x", "id":"evil", "environment":"prod"}, "server-id", "dev")["environment"], "dev")
    def test_default_quantity(self):
        self.assertEqual(normalize_order({"item":"x"}, "x", "dev")["quantity"], 1)

if __name__ == "__main__": unittest.main()
