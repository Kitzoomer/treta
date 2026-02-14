from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict
import uuid


class ProductBuilder:
    """Build deterministic product plans from product proposals."""

    _FORMAT_HINTS = {
        "notion": ["Notion setup checklist", "Template database structure", "Video walkthrough"],
        "canva": ["Editable Canva file organization", "Branding customization notes", "Export presets"],
        "google docs": ["Document structure", "Reusable copy blocks", "Versioning and sharing settings"],
        "gumroad": ["Listing setup", "Checkout optimization", "Post-purchase message flow"],
    }

    _CHANNEL_HINTS = {
        "creator": ["X/Twitter", "Instagram", "Creator newsletters"],
        "freelancer": ["LinkedIn", "X/Twitter", "Freelancer communities"],
        "coach": ["Instagram", "Email newsletter", "Private community"],
        "service": ["LinkedIn", "Email list", "Industry communities"],
        "solopreneur": ["X/Twitter", "Indie Hackers", "Email newsletter"],
    }

    def build(self, proposal: Dict[str, Any]) -> Dict[str, Any]:
        proposal_id = str(proposal.get("id", ""))
        plan_id = uuid.uuid4().hex
        created_at = datetime.now(timezone.utc).isoformat()

        product_name = str(proposal.get("product_name", "Untitled Product"))
        target_audience = str(proposal.get("target_audience", "General digital product buyers"))
        product_format = str(proposal.get("format", "Digital"))
        price_suggestion = str(proposal.get("price_suggestion", ""))

        outline = self._build_outline(proposal)
        deliverables = self._build_deliverables(proposal)
        build_steps = self._build_steps(product_name, product_format, deliverables)
        launch_plan = self._build_launch_plan(proposal)

        return {
            "plan_id": plan_id,
            "proposal_id": proposal_id,
            "created_at": created_at,
            "product_name": product_name,
            "target_audience": target_audience,
            "format": product_format,
            "price_suggestion": price_suggestion,
            "outline": outline,
            "deliverables": deliverables,
            "build_steps": build_steps,
            "launch_plan": launch_plan,
        }

    def _build_outline(self, proposal: Dict[str, Any]) -> list[str]:
        problem = str(proposal.get("core_problem", "Problem definition"))
        solution = str(proposal.get("solution", "Core solution"))
        validation = list(proposal.get("validation_plan", []))
        first_validation = validation[0] if validation else "Run a small beta with 3-5 ideal users"
        return [
            f"Context: {problem}",
            f"Method: {solution}",
            "Implementation assets and templates",
            f"Validation: {first_validation}",
            "Launch and iteration loop",
        ]

    def _build_deliverables(self, proposal: Dict[str, Any]) -> list[str]:
        base = [str(item) for item in proposal.get("deliverables", []) if str(item).strip()]
        format_text = str(proposal.get("format", "")).lower()
        for keyword, hints in self._FORMAT_HINTS.items():
            if keyword in format_text:
                for hint in hints:
                    if hint not in base:
                        base.append(hint)
        if "Launch checklist" not in base:
            base.append("Launch checklist")
        return base

    def _build_steps(self, product_name: str, product_format: str, deliverables: list[str]) -> list[Dict[str, Any]]:
        selected_assets = ", ".join(deliverables[:3]) if deliverables else "core product assets"
        return [
            {
                "step": 1,
                "title": "Define scope and success metric",
                "details": f"Set one measurable outcome for {product_name} and lock v1 boundaries.",
            },
            {
                "step": 2,
                "title": "Build core assets",
                "details": f"Create and QA the key deliverables: {selected_assets}.",
            },
            {
                "step": 3,
                "title": "Package and publish",
                "details": f"Export final files in {product_format}, prepare listing copy, and configure delivery automation.",
            },
            {
                "step": 4,
                "title": "Run launch loop",
                "details": "Publish hooks across selected channels, collect feedback, and ship one improvement within 7 days.",
            },
        ]

    def _build_launch_plan(self, proposal: Dict[str, Any]) -> Dict[str, Any]:
        positioning = str(proposal.get("positioning", "Practical product solving a concrete business pain quickly."))
        audience_text = str(proposal.get("target_audience", "")).lower()
        distribution_channels = self._distribution_channels(audience_text)

        product_name = str(proposal.get("product_name", "This product"))
        core_problem = str(proposal.get("core_problem", "an expensive workflow problem"))
        solution = str(proposal.get("solution", "a faster implementation path"))

        return {
            "positioning": positioning,
            "hook_ideas": [
                f"Stop losing time to {core_problem.lower()}",
                f"How to implement {solution.lower()} in one afternoon",
                f"What changed after shipping {product_name}",
            ],
            "distribution_channels": distribution_channels,
            "forum_post_templates": [
                f"Built {product_name} to solve {core_problem}. Looking for 3 beta users in exchange for feedback.",
                f"If you work with {proposal.get('target_audience', 'service clients')}, this may save you hours this week.",
            ],
            "gumroad_listing_copy": {
                "title": product_name,
                "subtitle": f"A practical {proposal.get('product_type', 'digital product')} for {proposal.get('target_audience', 'professionals')}",
                "bullets": [
                    f"Built to solve: {core_problem}",
                    f"Includes: {', '.join(str(d) for d in proposal.get('deliverables', [])[:3]) or 'core templates'}",
                    f"Suggested price anchor: {proposal.get('price_suggestion', '')}",
                ],
            },
        }

    def _distribution_channels(self, audience_text: str) -> list[str]:
        for keyword, channels in self._CHANNEL_HINTS.items():
            if keyword in audience_text:
                return list(channels)
        return ["X/Twitter", "Email newsletter", "Relevant niche communities"]
