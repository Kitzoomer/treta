from __future__ import annotations

from typing import Any, Dict


class ExecutionEngine:
    """Build a deterministic execution package from a stored proposal."""

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

        return {
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
