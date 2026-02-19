from __future__ import annotations

import os
from copy import deepcopy
from pathlib import Path

from core.persistence.json_io import atomic_read_json, atomic_write_json, quarantine_corrupt_file


class SubredditPerformanceStore:
    _DEFAULT_DATA_DIR = "./.treta_data"

    def __init__(self, path: Path | None = None) -> None:
        data_dir = Path(os.getenv("TRETA_DATA_DIR", self._DEFAULT_DATA_DIR))
        self._path = path or data_dir / "subreddit_performance.json"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._items: dict[str, dict[str, float | int | str]] = self._load_items()

    def _default_stats(self, subreddit: str) -> dict[str, float | int | str]:
        return {
            "name": subreddit,
            "posts_attempted": 0,
            "proposals_generated": 0,
            "plans_executed": 0,
            "sales": 0,
        }

    def _load_items(self) -> dict[str, dict[str, float | int | str]]:
        if not self._path.exists():
            return {}

        loaded = atomic_read_json(self._path, {})
        if not isinstance(loaded, dict):
            quarantine_corrupt_file(self._path, ValueError("expected dict"))
            return {}

        items: dict[str, dict[str, float | int | str]] = {}
        for key, row in loaded.items():
            if not isinstance(row, dict):
                continue
            name = str(key).strip() or str(row.get("name") or "").strip()
            if not name:
                continue
            items[name] = {
                "name": name,
                "posts_attempted": int(row.get("posts_attempted", 0) or 0),
                "proposals_generated": int(row.get("proposals_generated", 0) or 0),
                "plans_executed": int(row.get("plans_executed", 0) or 0),
                "sales": int(row.get("sales", 0) or 0),
            }
        return items

    def _save(self) -> None:
        atomic_write_json(self._path, self._items)

    def _ensure(self, subreddit: str) -> dict[str, float | int | str]:
        name = str(subreddit).strip()
        if not name:
            raise ValueError("subreddit is required")
        if name not in self._items:
            self._items[name] = self._default_stats(name)
        return self._items[name]

    def record_post_attempt(self, subreddit: str) -> None:
        stats = self._ensure(subreddit)
        stats["posts_attempted"] = int(stats["posts_attempted"]) + 1
        self._save()

    def record_proposal_generated(self, subreddit: str) -> None:
        stats = self._ensure(subreddit)
        stats["proposals_generated"] = int(stats["proposals_generated"]) + 1
        self._save()

    def record_plan_executed(self, subreddit: str) -> None:
        stats = self._ensure(subreddit)
        stats["plans_executed"] = int(stats["plans_executed"]) + 1
        self._save()

    def record_sale(self, subreddit: str) -> None:
        stats = self._ensure(subreddit)
        stats["sales"] = int(stats["sales"]) + 1
        self._save()

    def get_subreddit_stats(self, subreddit: str) -> dict[str, float | int | str]:
        name = str(subreddit).strip()
        if not name:
            return self._default_stats("unknown")
        return deepcopy(self._items.get(name, self._default_stats(name)))

    def get_summary(self) -> dict[str, list[dict[str, float | int | str]]]:
        items = [deepcopy(item) for item in self._items.values()]
        items.sort(key=lambda row: str(row.get("name") or ""))
        return {"subreddits": items}
