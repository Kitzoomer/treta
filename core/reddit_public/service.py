from __future__ import annotations

from typing import Any, Dict, List

from core.reddit_public.client import RedditPublicClient


class RedditPublicService:
    def __init__(self, client: RedditPublicClient | None = None):
        self.client = client or RedditPublicClient()

    def scan_subreddits(self, subreddits: list[str]) -> List[Dict[str, Any]]:
        consolidated: List[Dict[str, Any]] = []
        for subreddit in subreddits:
            posts = self.client.fetch_subreddit_posts(subreddit=subreddit)
            filtered = [
                post
                for post in posts
                if int(post.get("score", 0)) >= 3 and int(post.get("num_comments", 0)) >= 1
            ]
            consolidated.extend(filtered)
        return consolidated
