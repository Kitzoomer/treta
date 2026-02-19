from datetime import datetime
from typing import Callable


def validate_openclaw_output(raw: object) -> None:
    if not isinstance(raw, dict):
        raise ValueError("openclaw_output_must_be_dict")

    posts = raw.get("posts")
    if not isinstance(posts, list):
        raise ValueError("openclaw_output_posts_must_be_list")

    for index, post in enumerate(posts):
        if not isinstance(post, dict):
            raise ValueError(f"openclaw_output_post_{index}_must_be_dict")

        if not str(post.get("subreddit", "")).strip():
            raise ValueError(f"openclaw_output_post_{index}_missing_subreddit")


def normalize_openclaw_to_scan_summary(raw: dict) -> dict:
    validate_openclaw_output(raw)
    posts = raw.get("posts", [])

    by_subreddit: dict[str, int] = {}
    opportunities: list[dict[str, object]] = []
    for post in posts:
        subreddit_name = str(post.get("subreddit", "")).strip() or "unknown"
        by_subreddit[subreddit_name] = by_subreddit.get(subreddit_name, 0) + 1
        opportunities.append(
            {
                "title": str(post.get("title", "")).strip(),
                "subreddit": subreddit_name,
                "pain_score": int(post.get("pain_score", 60) or 60),
                "intent_type": str(post.get("intent_type", "openclaw_signal")).strip() or "openclaw_signal",
                "urgency_level": str(post.get("urgency_level", "medium")).strip() or "medium",
            }
        )

    return {
        "analyzed": len(posts),
        "qualified": len(opportunities),
        "by_subreddit": by_subreddit,
        "posts": opportunities,
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


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

        if self.runner is not None:
            return self.runner(subreddits=normalized_subreddits, limit=limit)

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
