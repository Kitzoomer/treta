import unittest
from unittest.mock import Mock

from core.integrations.gumroad_client import GumroadClient


class GumroadClientSmokeTest(unittest.TestCase):
    def test_reads_credentials_from_environment_and_fetches_resources(self):
        transport = Mock()
        transport.oauth_token.return_value = "token-123"
        transport.get.side_effect = [
            {"products": [{"id": "p1"}]},
            {"sales": [{"id": "s1"}]},
            {"balance": {"cents": 4200}},
        ]

        with unittest.mock.patch.dict(
            "os.environ",
            {"GUMROAD_APP_ID": "app-id", "GUMROAD_APP_SECRET": "app-secret"},
            clear=False,
        ):
            client = GumroadClient(transport=transport)
            self.assertEqual(client.get_products(), [{"id": "p1"}])
            self.assertEqual(client.get_sales(), [{"id": "s1"}])
            self.assertEqual(client.get_balance(), {"cents": 4200})

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

            self.assertEqual(client.get_products(), [])
            self.assertEqual(client.get_sales(), [])
            self.assertEqual(client.get_balance(), {})

        transport.oauth_token.assert_not_called()
        transport.get.assert_not_called()


if __name__ == "__main__":
    unittest.main()
