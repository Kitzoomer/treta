import json
import tempfile
import unittest
from pathlib import Path
from urllib.request import Request, urlopen

from core.ipc_http import start_http_server
from core.product_proposal_store import ProductProposalStore


class RedditOpsEndpointTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_reddit_path = start_http_server.__globals__["Handler"]._reddit_posts_path

        def _temp_reddit_posts_path(handler):
            return Path(self.temp_dir.name) / "reddit_posts.json"

        start_http_server.__globals__["Handler"]._reddit_posts_path = _temp_reddit_posts_path

        self.proposal_store = ProductProposalStore(path=Path(self.temp_dir.name) / "product_proposals.json")
        self.proposal_store.add(
            {
                "id": "proposal_1",
                "product_name": "Reddit Micro SaaS",
                "target_audience": "indie hackers",
                "status": "ready_to_launch",
            }
        )

        self.server = start_http_server(
            host="127.0.0.1",
            port=0,
            product_proposal_store=self.proposal_store,
        )

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        start_http_server.__globals__["Handler"]._reddit_posts_path = self.original_reddit_path
        self.temp_dir.cleanup()

    def test_mark_posted_creates_entry(self):
        req = Request(
            f"http://127.0.0.1:{self.server.server_port}/reddit/mark_posted",
            data=json.dumps(
                {
                    "proposal_id": "proposal_1",
                    "subreddit": "indiehackers",
                    "post_url": "https://reddit.com/r/indiehackers/post/123",
                    "upvotes": 10,
                    "comments": 2,
                }
            ).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urlopen(req, timeout=2) as response:
            payload = json.loads(response.read().decode("utf-8"))

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["item"]["proposal_id"], "proposal_1")
        self.assertEqual(payload["item"]["product_name"], "Reddit Micro SaaS")

        stored = json.loads((Path(self.temp_dir.name) / "reddit_posts.json").read_text(encoding="utf-8"))
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0]["subreddit"], "indiehackers")

    def test_get_posts_returns_list(self):
        path = Path(self.temp_dir.name) / "reddit_posts.json"
        path.write_text(
            json.dumps(
                [
                    {
                        "id": "reddit_post_1",
                        "proposal_id": "proposal_1",
                        "product_name": "Reddit Micro SaaS",
                        "subreddit": "indiehackers",
                        "post_url": "https://reddit.com/r/indiehackers/post/123",
                        "upvotes": 3,
                        "comments": 1,
                        "status": "open",
                        "date": "2026-01-01",
                        "created_at": "2026-01-01T00:00:00Z",
                    }
                ]
            ),
            encoding="utf-8",
        )

        with urlopen(f"http://127.0.0.1:{self.server.server_port}/reddit/posts", timeout=2) as response:
            payload = json.loads(response.read().decode("utf-8"))

        self.assertIsInstance(payload["items"], list)
        self.assertEqual(len(payload["items"]), 1)
        self.assertEqual(payload["items"][0]["id"], "reddit_post_1")


if __name__ == "__main__":
    unittest.main()
