from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


class ExecutionEngine:
    """Build a deterministic execution package from a stored proposal."""

    def __init__(self, path: Path | None = None):
        self._path = path or Path("/data/executions.json")
        self._history: List[Dict[str, Any]] = self._load_history()

    def _load_history(self) -> List[Dict[str, Any]]:
        if not self._path.exists():
            return []
        loaded = json.loads(self._path.read_text(encoding="utf-8"))
        if not isinstance(loaded, list):
            return []
        return [dict(item) for item in loaded if isinstance(item, dict)]

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._history, indent=2), encoding="utf-8")

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
