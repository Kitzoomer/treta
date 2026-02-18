import json
import tempfile
import unittest
from pathlib import Path
from urllib.request import Request, urlopen
from unittest.mock import patch

from core.bus import event_bus
from core.control import Control
from core.ipc_http import start_http_server
from core.product_proposal_store import ProductProposalStore




class RedditOpsEndpointTest(unittest.TestCase):
    def _drain_events(self):
        while event_bus.pop(timeout=0.001) is not None:
            pass

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_reddit_path = start_http_server.__globals__["Handler"]._reddit_posts_path

        def _temp_reddit_posts_path(handler):
            return Path(self.temp_dir.name) / "reddit_posts.json"

        start_http_server.__globals__["Handler"]._reddit_posts_path = _temp_reddit_posts_path

        self.proposal_store = ProductProposalStore(path=Path(self.temp_dir.name) / "product_proposals.json")
        self.control = Control(product_proposal_store=self.proposal_store)
        self.original_control_reddit_path = self.control._reddit_posts_path

        def _control_temp_reddit_posts_path():
            return Path(self.temp_dir.name) / "reddit_posts.json"

        self.control._reddit_posts_path = _control_temp_reddit_posts_path
        self.proposal_store.add(
            {
                "id": "proposal_1",
                "product_name": "Reddit Micro SaaS",
                "target_audience": "indie hackers",
                "status": "launched",
            }
        )

        self.server = start_http_server(
            host="127.0.0.1",
            port=0,
            product_proposal_store=self.proposal_store,
            control=self.control,
        )

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        start_http_server.__globals__["Handler"]._reddit_posts_path = self.original_reddit_path
        self.control._reddit_posts_path = self.original_control_reddit_path
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

    def test_run_scan_is_incremental_for_duplicate_posts(self):
        self._drain_events()
        posts = [
            {
                "id": "dup_1",
                "title": "How do I set client pricing?",
                "selftext": "I am struggling with proposal rate and need help asap",
                "score": 15,
                "num_comments": 6,
                "subreddit": "freelance",
                "url": "https://reddit.com/r/freelance/comments/dup_1/example",
            }
        ]

        with patch("core.reddit_public.service.RedditPublicService.scan_subreddits", return_value=posts):
            first = self.control.run_reddit_public_scan()
            second = self.control.run_reddit_public_scan()

        emitted = []
        while True:
            event = event_bus.pop(timeout=0.001)
            if event is None:
                break
            if event.type == "OpportunityDetected":
                emitted.append(event)

        self.assertEqual(first["qualified"], 1)
        self.assertEqual(second["qualified"], 0)
        self.assertEqual(len(emitted), 1)

    def test_mark_posted_post_id_excludes_post_from_next_scan(self):
        self._drain_events()
        req = Request(
            f"http://127.0.0.1:{self.server.server_port}/reddit/mark_posted",
            data=json.dumps(
                {
                    "proposal_id": "proposal_1",
                    "subreddit": "indiehackers",
                    "post_url": "https://reddit.com/r/indiehackers/comments/reuse_1/test",
                    "post_id": "reuse_1",
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

        posts = [
            {
                "id": "reuse_1",
                "title": "How do I set client pricing?",
                "selftext": "I am struggling with proposal rate and need help asap",
                "score": 15,
                "num_comments": 6,
                "subreddit": "indiehackers",
                "url": "https://reddit.com/r/indiehackers/comments/reuse_1/test",
            }
        ]

        with patch("core.reddit_public.service.RedditPublicService.scan_subreddits", return_value=posts):
            result = self.control.run_reddit_public_scan()

        self.assertEqual(result["qualified"], 0)

        emitted = []
        while True:
            event = event_bus.pop(timeout=0.001)
            if event is None:
                break
            if event.type == "OpportunityDetected":
                emitted.append(event)

        self.assertEqual(len(emitted), 0)


if __name__ == "__main__":
    unittest.main()
