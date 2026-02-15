import os
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from unittest.mock import Mock, patch

from core.gumroad_oauth import get_auth_url, load_token, save_token


class GumroadOAuthTest(unittest.TestCase):
    def test_auth_url_format(self):
        previous = {
            "GUMROAD_APP_ID": os.environ.get("GUMROAD_APP_ID"),
            "GUMROAD_REDIRECT_URI": os.environ.get("GUMROAD_REDIRECT_URI"),
        }
        os.environ["GUMROAD_APP_ID"] = "app-123"
        os.environ["GUMROAD_REDIRECT_URI"] = "http://localhost:7777/gumroad/callback"
        try:
            auth_url = get_auth_url()
            parsed = urlparse(auth_url)
            query = parse_qs(parsed.query)
            self.assertEqual(parsed.scheme, "https")
            self.assertEqual(parsed.netloc, "gumroad.com")
            self.assertEqual(parsed.path, "/oauth/authorize")
            self.assertEqual(query["client_id"][0], "app-123")
            self.assertEqual(query["redirect_uri"][0], "http://localhost:7777/gumroad/callback")
            self.assertEqual(query["response_type"][0], "code")
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def test_save_and_load_token_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            prev_data_dir = os.environ.get("TRETA_DATA_DIR")
            os.environ["TRETA_DATA_DIR"] = tmp_dir
            try:
                save_token("oauth-token")
                self.assertEqual(load_token(), "oauth-token")
                self.assertTrue((Path(tmp_dir) / "gumroad_oauth_token.json").exists())
            finally:
                if prev_data_dir is None:
                    os.environ.pop("TRETA_DATA_DIR", None)
                else:
                    os.environ["TRETA_DATA_DIR"] = prev_data_dir

    @patch("core.gumroad_oauth.requests.post")
    def test_exchange_code_for_token(self, mock_post):
        from core.gumroad_oauth import exchange_code_for_token

        previous = {
            "GUMROAD_APP_ID": os.environ.get("GUMROAD_APP_ID"),
            "GUMROAD_APP_SECRET": os.environ.get("GUMROAD_APP_SECRET"),
            "GUMROAD_REDIRECT_URI": os.environ.get("GUMROAD_REDIRECT_URI"),
        }
        os.environ["GUMROAD_APP_ID"] = "app-123"
        os.environ["GUMROAD_APP_SECRET"] = "secret-123"
        os.environ["GUMROAD_REDIRECT_URI"] = "http://localhost:7777/gumroad/callback"

        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"access_token": "oauth-token"}
        mock_post.return_value = response

        try:
            token = exchange_code_for_token("oauth-code")
            self.assertEqual(token, "oauth-token")
            mock_post.assert_called_once()
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


if __name__ == "__main__":
    unittest.main()
