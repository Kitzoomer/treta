from __future__ import annotations

import json
from typing import Any, Dict, List
from urllib import error, request

try:
    import requests  # type: ignore
except ImportError:  # pragma: no cover
    class _FallbackResponse:
        def __init__(self, status_code: int, body: bytes):
            self.status_code = status_code
            self._body = body

        def json(self) -> Dict[str, Any]:
            return json.loads(self._body.decode("utf-8"))

    class _FallbackRequests:
        RequestException = Exception

        @staticmethod
        def get(url: str, headers: Dict[str, str] | None = None, timeout: int = 10) -> _FallbackResponse:
            req = request.Request(url, headers=headers or {})
            try:
                with request.urlopen(req, timeout=timeout) as response:
                    return _FallbackResponse(response.status, response.read())
            except error.HTTPError as exc:
                body = exc.read() if hasattr(exc, "read") else b"{}"
                return _FallbackResponse(exc.code, body)

    requests = _FallbackRequests()  # type: ignore[assignment]


class RedditPublicClient:
    BASE_URL = "https://www.reddit.com"
    HEADERS = {"User-Agent": "TRETA/1.0 (by Marian)"}

    def fetch_subreddit_posts(self, subreddit: str, sort: str = "new", limit: int = 25) -> List[Dict[str, Any]]:
        endpoint = f"/r/{subreddit}/{sort}.json?limit={limit}"
        url = f"{self.BASE_URL}{endpoint}"

        try:
            response = requests.get(url, headers=self.HEADERS, timeout=10)
        except requests.RequestException:
            return []

        if response.status_code != 200:
            return []

        try:
            payload = response.json()
        except ValueError:
            return []

        children = payload.get("data", {}).get("children", [])
        posts: List[Dict[str, Any]] = []
        for item in children:
            post = item.get("data", {})
            posts.append(
                {
                    "id": post.get("id", ""),
                    "title": post.get("title", ""),
                    "selftext": post.get("selftext", ""),
                    "score": post.get("score", 0),
                    "num_comments": post.get("num_comments", 0),
                    "created_utc": post.get("created_utc", 0),
                    "subreddit": post.get("subreddit", subreddit),
                }
            )

        return posts
