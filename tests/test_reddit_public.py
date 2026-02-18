import unittest
from unittest.mock import Mock, patch

from core.reddit_public.client import RedditPublicClient
from core.reddit_public.service import RedditPublicService


class RedditPublicClientTest(unittest.TestCase):
    @patch("core.reddit_public.client.requests.get")
    def test_fetch_subreddit_posts_parses_reddit_json(self, mock_get):
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "data": {
                "children": [
                    {
                        "data": {
                            "id": "abc123",
                            "title": "Need a proposal template",
                            "selftext": "I am struggling with pricing",
                            "score": 12,
                            "num_comments": 4,
                            "created_utc": 1700000000,
                            "subreddit": "freelance",
                        }
                    }
                ]
            }
        }
        mock_get.return_value = response

        posts = RedditPublicClient().fetch_subreddit_posts("freelance")

        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0]["id"], "abc123")
        self.assertEqual(posts[0]["title"], "Need a proposal template")
        self.assertEqual(posts[0]["score"], 12)
        self.assertEqual(posts[0]["num_comments"], 4)

    def test_scan_subreddits_filters_low_engagement(self):
        client = Mock()
        client.fetch_subreddit_posts.return_value = [
            {"id": "ok", "score": 3, "num_comments": 1},
            {"id": "low-score", "score": 2, "num_comments": 4},
            {"id": "low-comments", "score": 8, "num_comments": 0},
        ]

        items = RedditPublicService(client=client).scan_subreddits(["freelance"])

        self.assertEqual([item["id"] for item in items], ["ok"])


if __name__ == "__main__":
    unittest.main()
