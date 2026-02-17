import json
import os
import tempfile
import unittest
from pathlib import Path
from urllib.request import Request, urlopen

from core.ipc_http import start_http_server


class RedditIntelligenceEndpointTest(unittest.TestCase):
    def test_create_list_and_update_signal_status(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            previous_data_dir = os.environ.get("TRETA_DATA_DIR")
            os.environ["TRETA_DATA_DIR"] = str(root)
            server = start_http_server(host="127.0.0.1", port=0)
            try:
                create_request = Request(
                    f"http://127.0.0.1:{server.server_port}/reddit/signals",
                    data=json.dumps(
                        {
                            "subreddit": "freelance",
                            "post_url": "https://reddit.com/r/freelance/post-1",
                            "post_text": "Need help with a template to pitch clients",
                        }
                    ).encode("utf-8"),
                    method="POST",
                    headers={"Content-Type": "application/json"},
                )
                with urlopen(create_request, timeout=2) as response:
                    created = json.loads(response.read().decode("utf-8"))

                self.assertEqual(created["subreddit"], "freelance")
                self.assertEqual(created["detected_pain_type"], "direct")
                self.assertEqual(created["intent_level"], "direct")
                self.assertEqual(created["suggested_action"], "value_plus_mention")
                self.assertEqual(created["status"], "pending")

                with urlopen(
                    f"http://127.0.0.1:{server.server_port}/reddit/signals?limit=20",
                    timeout=2,
                ) as response:
                    listed = json.loads(response.read().decode("utf-8"))
                self.assertEqual(len(listed["items"]), 1)

                patch_request = Request(
                    f"http://127.0.0.1:{server.server_port}/reddit/signals/{created['id']}/status",
                    data=json.dumps({"status": "approved"}).encode("utf-8"),
                    method="PATCH",
                    headers={"Content-Type": "application/json"},
                )
                with urlopen(patch_request, timeout=2) as response:
                    updated = json.loads(response.read().decode("utf-8"))
                self.assertEqual(updated["status"], "approved")

                with urlopen(
                    f"http://127.0.0.1:{server.server_port}/reddit/signals?limit=20",
                    timeout=2,
                ) as response:
                    listed_after_update = json.loads(response.read().decode("utf-8"))
                self.assertEqual(listed_after_update["items"], [])
            finally:
                if previous_data_dir is None:
                    os.environ.pop("TRETA_DATA_DIR", None)
                else:
                    os.environ["TRETA_DATA_DIR"] = previous_data_dir
                server.shutdown()
                server.server_close()

    def test_list_respects_limit_and_score_order(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            previous_data_dir = os.environ.get("TRETA_DATA_DIR")
            os.environ["TRETA_DATA_DIR"] = str(root)
            server = start_http_server(host="127.0.0.1", port=0)
            try:
                for idx in range(25):
                    text = "Need help with template" if idx % 2 == 0 else "I am struggling with offer"
                    create_request = Request(
                        f"http://127.0.0.1:{server.server_port}/reddit/signals",
                        data=json.dumps(
                            {
                                "subreddit": "entrepreneur",
                                "post_url": f"https://reddit.com/r/entrepreneur/{idx}",
                                "post_text": text,
                            }
                        ).encode("utf-8"),
                        method="POST",
                        headers={"Content-Type": "application/json"},
                    )
                    with urlopen(create_request, timeout=2):
                        pass

                with urlopen(
                    f"http://127.0.0.1:{server.server_port}/reddit/signals?limit=20",
                    timeout=2,
                ) as response:
                    payload = json.loads(response.read().decode("utf-8"))

                items = payload["items"]
                self.assertEqual(len(items), 20)
                scores = [item["opportunity_score"] for item in items]
                self.assertEqual(scores, sorted(scores, reverse=True))
            finally:
                if previous_data_dir is None:
                    os.environ.pop("TRETA_DATA_DIR", None)
                else:
                    os.environ["TRETA_DATA_DIR"] = previous_data_dir
                server.shutdown()
                server.server_close()




class RedditIntelligenceModelPathTest(unittest.TestCase):
    def test_default_db_path_uses_local_relative_fallback(self):
        from core.reddit_intelligence.models import get_db_path

        previous_data_dir = os.environ.get("TRETA_DATA_DIR")
        try:
            os.environ.pop("TRETA_DATA_DIR", None)
            db_path = get_db_path()
            self.assertEqual(db_path.name, "reddit_intelligence.db")
            self.assertFalse(db_path.is_absolute())
        finally:
            if previous_data_dir is None:
                os.environ.pop("TRETA_DATA_DIR", None)
            else:
                os.environ["TRETA_DATA_DIR"] = previous_data_dir

if __name__ == "__main__":
    unittest.main()
