import json
import unittest
from urllib.request import Request, urlopen
from unittest.mock import patch

from core.control import Control
from core.ipc_http import start_http_server
from core.reddit_public.config import DEFAULT_CONFIG, update_config


class RedditConfigEndpointTest(unittest.TestCase):
    def setUp(self):
        update_config(DEFAULT_CONFIG.copy())

    def tearDown(self):
        update_config(DEFAULT_CONFIG.copy())

    def test_get_and_update_config(self):
        server = start_http_server(host="127.0.0.1", port=0, control=Control())
        try:
            with urlopen(f"http://127.0.0.1:{server.server_port}/reddit/config", timeout=2) as response:
                payload = json.loads(response.read().decode("utf-8"))
            self.assertEqual(payload["pain_threshold"], 60)
            self.assertEqual(payload["subreddits"], ["UGCcreators", "freelance", "ContentCreators", "smallbusiness"])

            req = Request(
                f"http://127.0.0.1:{server.server_port}/reddit/config",
                data=json.dumps(
                    {
                        "pain_threshold": 80,
                        "pain_keywords": ["blocked", "need support"],
                        "commercial_keywords": "pricing, proposal",
                        "enable_engagement_boost": False,
                        "subreddits": "freelance, UGCcreators",
                    }
                ).encode("utf-8"),
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with urlopen(req, timeout=2) as response:
                updated = json.loads(response.read().decode("utf-8"))

            self.assertEqual(updated["pain_threshold"], 80)
            self.assertEqual(updated["pain_keywords"], ["blocked", "need support"])
            self.assertEqual(updated["commercial_keywords"], ["pricing", "proposal"])
            self.assertFalse(updated["enable_engagement_boost"])
            self.assertEqual(updated["subreddits"], ["freelance", "UGCcreators"])
        finally:
            server.shutdown()
            server.server_close()

    def test_run_scan_returns_summary(self):
        expected = {
            "analyzed": 2,
            "qualified": 1,
            "by_subreddit": {"freelance": 1},
            "posts": [
                {
                    "title": "Need help with rates",
                    "subreddit": "freelance",
                    "pain_score": 75,
                    "intent_type": "monetization",
                    "urgency_level": "high",
                }
            ],
        }
        control = Control()

        with patch.object(control, "run_reddit_public_scan", return_value=expected):
            server = start_http_server(host="127.0.0.1", port=0, control=control)
            try:
                req = Request(
                    f"http://127.0.0.1:{server.server_port}/reddit/run_scan",
                    data=b"{}",
                    method="POST",
                    headers={"Content-Type": "application/json"},
                )
                with urlopen(req, timeout=2) as response:
                    payload = json.loads(response.read().decode("utf-8"))

                self.assertEqual(payload, expected)
            finally:
                server.shutdown()
                server.server_close()

    def test_get_last_scan_returns_saved_scan(self):
        expected = {
            "analyzed": 2,
            "qualified": 1,
            "by_subreddit": {"freelance": 1},
            "posts": [
                {
                    "title": "Need help with rates",
                    "subreddit": "freelance",
                    "pain_score": 75,
                    "intent_type": "monetization",
                    "urgency_level": "high",
                }
            ],
        }
        control = Control()

        server = start_http_server(host="127.0.0.1", port=0, control=control)
        try:
            with urlopen(f"http://127.0.0.1:{server.server_port}/reddit/last_scan", timeout=2) as response:
                empty_payload = json.loads(response.read().decode("utf-8"))
            self.assertEqual(empty_payload, {"message": "No scan executed yet."})

            with patch.object(control, "get_last_reddit_scan", return_value=expected):
                with urlopen(f"http://127.0.0.1:{server.server_port}/reddit/last_scan", timeout=2) as response:
                    last_payload = json.loads(response.read().decode("utf-8"))

            self.assertEqual(last_payload, expected)
        finally:
            server.shutdown()
            server.server_close()



if __name__ == "__main__":
    unittest.main()
