import unittest
from unittest.mock import Mock, patch

from core.integrations.gumroad_client import GumroadAPIError, GumroadClient


class GumroadClientSmokeTest(unittest.TestCase):
    @patch("core.integrations.gumroad_client.requests.get")
    def test_get_sales_normalizes_payload(self, mock_get):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "sales": [
                {"id": "sale-2", "price": "19.99", "created_at": "2026-01-02T00:00:00Z"},
                {"id": "sale-1", "amount_cents": 1000, "created_at": "2026-01-01T00:00:00Z"},
            ]
        }
        mock_get.return_value = response

        client = GumroadClient("token-123")
        sales = client.get_sales("product-abc")

        self.assertEqual(
            sales,
            [
                {"sale_id": "sale-2", "amount": 19.99, "created_at": "2026-01-02T00:00:00Z"},
                {"sale_id": "sale-1", "amount": 10.0, "created_at": "2026-01-01T00:00:00Z"},
            ],
        )
        mock_get.assert_called_once_with(
            "https://api.gumroad.com/v2/sales",
            params={"product_id": "product-abc"},
            headers={"Authorization": "Bearer token-123"},
            timeout=10,
        )

    @patch("core.integrations.gumroad_client.requests.get")
    def test_get_sales_raises_api_error(self, mock_get):
        mock_get.side_effect = RuntimeError("boom")
        client = GumroadClient("token-123")

        with self.assertRaisesRegex(GumroadAPIError, "Gumroad API request failed"):
            client.get_sales("product-abc")

    def test_missing_access_token_raises_value_error(self):
        with self.assertRaisesRegex(ValueError, "Missing Gumroad access token"):
            GumroadClient("")


if __name__ == "__main__":
    unittest.main()
