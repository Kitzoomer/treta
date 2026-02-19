from typing import Callable


class OpenClawRedditScanner:
    def __init__(self, runner: Callable[..., object] | None = None):
        self.runner = runner

    def scan(self, subreddits: list[str], limit: int = 10) -> dict:
        """
        Returns:
        {
            "posts": [
                {
                    "id": str,
                    "subreddit": str,
                    "title": str,
                    "body": str,
                    "url": str,
                    "score": int,
                    "comments": int
                }
            ]
        }
        """
        normalized_subreddits = [item.strip() for item in subreddits if item.strip()]
        if not normalized_subreddits:
            normalized_subreddits = ["all"]

        posts = []
        max_posts = max(1, min(int(limit or 1), len(normalized_subreddits)))
        for index, subreddit in enumerate(normalized_subreddits[:max_posts], start=1):
            posts.append(
                {
                    "id": f"openclaw_mock_{subreddit}_{index}",
                    "subreddit": subreddit,
                    "title": f"[Mock] Opportunity signal in r/{subreddit}",
                    "body": "Mocked OpenClaw payload for Phase 1 scaffold.",
                    "url": f"https://reddit.com/r/{subreddit}/comments/openclaw_mock_{index}",
                    "score": 0,
                    "comments": 0,
                }
            )

        return {"posts": posts}
