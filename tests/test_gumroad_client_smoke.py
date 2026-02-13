import unittest
from unittest.mock import Mock

from core.integrations.gumroad_client import GumroadClient


class GumroadClientSmokeTest(unittest.TestCase):
    def test_reads_credentials_from_environment_and_fetches_resources(self):
        transport = Mock()
        transport.oauth_token.return_value = "token-123"
        transport.get.side_effect = [
            {"products": [{"id": "p1"}]},
            {"sales": [{"id": "s1", "price": "19.99"}]},
            {"sales": [{"id": "s1", "price": "19.99"}, {"id": "s2", "price": 5}]},
        ]

        with unittest.mock.patch.dict(
            "os.environ",
            {"GUMROAD_APP_ID": "app-id", "GUMROAD_APP_SECRET": "app-secret"},
            clear=False,
        ):
            client = GumroadClient(transport=transport)
            self.assertEqual(client.get_products(), {"products": [{"id": "p1"}]})
            self.assertEqual(
                client.get_sales(),
                {"sales": [{"id": "s1", "price": "19.99"}], "limit": 10},
            )
            self.assertEqual(
                client.get_total_revenue(),
                {"total_revenue": 24.99, "currency": "USD", "sales_count": 2},
            )

        transport.oauth_token.assert_called_once_with(
            app_id="app-id",
            app_secret="app-secret",
        )
        self.assertEqual(transport.get.call_count, 3)

    def test_missing_credentials_fails_safely(self):
        transport = Mock()

        with unittest.mock.patch.dict(
            "os.environ",
            {"GUMROAD_APP_ID": "", "GUMROAD_APP_SECRET": ""},
            clear=False,
        ):
            client = GumroadClient(transport=transport)

            with self.assertLogs("core.integrations.gumroad_client", level="WARNING") as log_cm:
                self.assertEqual(client.get_products(), {"products": []})
                self.assertEqual(client.get_sales(), {"sales": [], "limit": 10})
                self.assertEqual(
                    client.get_total_revenue(),
                    {"total_revenue": 0.0, "currency": "USD", "sales_count": 0},
                )

        self.assertTrue(any("credentials are missing" in m for m in log_cm.output))
        transport.oauth_token.assert_not_called()
        transport.get.assert_not_called()


if __name__ == "__main__":
    unittest.main()
