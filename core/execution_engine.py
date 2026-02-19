from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List

from core.persistence.json_io import atomic_read_json, atomic_write_json


class ExecutionEngine:
    """Build a deterministic execution package from a stored proposal."""

    _DEFAULT_DATA_DIR = "./.treta_data"

    def __init__(self, path: Path | None = None):
        data_dir = Path(os.getenv("TRETA_DATA_DIR", self._DEFAULT_DATA_DIR))
        self._path = path or data_dir / "executions.json"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._history: List[Dict[str, Any]] = self._load_history()

    def _load_history(self) -> List[Dict[str, Any]]:
        if not self._path.exists():
            return []
        loaded = atomic_read_json(self._path, [])
        if not isinstance(loaded, list):
            return []
        return [dict(item) for item in loaded if isinstance(item, dict)]

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(self._path, self._history)

    def list_history(self) -> List[Dict[str, Any]]:
        return [dict(item) for item in self._history]

    def generate_execution_package(self, proposal: Dict[str, Any]) -> Dict[str, Any]:
        product_name = str(proposal.get("product_name", "Untitled Product")).strip() or "Untitled Product"
        target_audience = (
            str(proposal.get("target_audience", "professionals")).strip() or "professionals"
        )
        price_suggestion = proposal.get("price_suggestion", "")
        reasoning = str(proposal.get("reasoning", "")).strip() or "Generated from existing proposal data."

        price_text = f"${price_suggestion}" if str(price_suggestion).strip() else "a clear starter price"

        reddit_title = f"Built a new {product_name} for {target_audience} — looking for feedback"
        reddit_body = "\n".join(
            [
                f"I just packaged a product called '{product_name}'.",
                f"It is designed for {target_audience}.",
                f"Current price direction: {price_text}.",
                "",
                "Why this product:",
                reasoning,
                "",
                "I can share details if this sounds useful.",
            ]
        )

        gumroad_description = "\n".join(
            [
                f"{product_name} helps {target_audience} implement a practical workflow faster.",
                f"Suggested price point: {price_text}.",
                "",
                "What this solves:",
                reasoning,
                "",
                "Built for immediate use with simple copy/paste implementation.",
            ]
        )

        execution_package = {
            "reddit_post": {
                "title": reddit_title,
                "body": reddit_body,
            },
            "gumroad_description": gumroad_description,
            "short_pitch": f"{product_name} for {target_audience} with a focused, ready-to-ship workflow.",
            "pricing_strategy": (
                f"Launch at {price_text}, gather first buyer feedback, then adjust in small increments "
                "after validating conversion and buyer outcomes."
            ),
            "launch_steps": [
                "Publish the Reddit post and collect early feedback signals.",
                "Publish the Gumroad product page with the prepared description and pricing.",
                "Promote to existing audience and track first-week conversion notes.",
            ],
        }

        self._history.append({"proposal_id": str(proposal.get("id", "")), "execution_package": execution_package})
        self._save()

        return execution_package
