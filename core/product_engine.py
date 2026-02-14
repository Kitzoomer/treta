from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict
import uuid


class ProductEngine:
    """Generate infoproduct proposals from opportunity keywords."""

    _THEMES = [
        {
            "name": "media_kit",
            "keywords": [
                "media kit",
                "brand collaboration",
                "sponsorship",
                "ugc",
                "rate sheet",
            ],
            "product_name": "Media Kit + Pitch Kit",
            "product_type": "kit",
            "target_audience": "Creators and freelancers pitching brand partnerships",
            "core_problem": "They struggle to present value and rates clearly to brands.",
            "solution": "A ready-to-customize media kit and outreach pitch flow.",
            "format": "Canva+Notion",
            "price_min": 19,
            "price_max": 29,
            "deliverables": [
                "Media kit template",
                "Rate sheet template",
                "Brand pitch email scripts",
                "Collaboration tracker",
            ],
            "positioning": "Close brand deals faster with a polished creator offer.",
            "distribution_plan": [
                "Post before/after media kit examples on social",
                "Share case study thread with one brand win",
                "Add lead magnet teaser in newsletter",
            ],
            "validation_plan": [
                "Run 3 customer interviews with creators",
                "Pre-sell to newsletter audience with waitlist",
                "A/B test €19 vs €29 pricing",
            ],
        },
        {
            "name": "onboarding",
            "keywords": ["onboarding", "client intake", "coaching", "automation"],
            "product_name": "Client Onboarding System Kit",
            "product_type": "kit",
            "target_audience": "Service providers and coaches onboarding new clients",
            "core_problem": "Manual onboarding is inconsistent and wastes billable time.",
            "solution": "Standardized onboarding assets and automations for smoother delivery.",
            "format": "Notion+Google Docs",
            "price_min": 29,
            "price_max": 59,
            "deliverables": [
                "Client intake form templates",
                "Onboarding checklist",
                "Welcome email automation copy",
                "Kickoff call agenda",
            ],
            "positioning": "Deliver a premium first impression without extra admin work.",
            "distribution_plan": [
                "Publish onboarding workflow reel",
                "Offer free mini-checklist as lead magnet",
                "Cross-sell to existing service clients",
            ],
            "validation_plan": [
                "Interview 5 service providers",
                "Soft launch to warm audience",
                "Collect completion time improvements",
            ],
        },
        {
            "name": "proposal_pricing",
            "keywords": ["proposal", "client proposal", "freelance", "pricing"],
            "product_name": "Proposal + Pricing Pack",
            "product_type": "template_pack",
            "target_audience": "Freelancers and boutique studios selling services",
            "core_problem": "Weak proposals and unclear pricing reduce close rates.",
            "solution": "Reusable proposal and pricing templates designed to convert.",
            "format": "Canva+Google Docs",
            "price_min": 19,
            "price_max": 39,
            "deliverables": [
                "Service proposal templates",
                "Pricing menu templates",
                "Scope of work blocks",
                "Objection handling snippets",
            ],
            "positioning": "Send clearer proposals and justify premium pricing.",
            "distribution_plan": [
                "Share proposal teardown content",
                "Post pricing mistakes checklist",
                "Bundle with discovery call script",
            ],
            "validation_plan": [
                "Run a pre-order with founding customer bonus",
                "Measure conversion rate uplift from buyers",
                "Offer 10 pilot licenses and gather testimonials",
            ],
        },
        {
            "name": "notion_template",
            "keywords": ["notion template"],
            "product_name": "Notion Template Pack",
            "product_type": "template_pack",
            "target_audience": "Solopreneurs organizing workflows in Notion",
            "core_problem": "They spend too much time building systems from scratch.",
            "solution": "A plug-and-play bundle of business workflow templates.",
            "format": "Notion",
            "price_min": 9,
            "price_max": 29,
            "deliverables": [
                "Notion dashboard template",
                "Task and project tracker",
                "Content planner",
                "CRM mini-database",
            ],
            "positioning": "Get an organized business OS in minutes.",
            "distribution_plan": [
                "Publish template walkthrough video",
                "Offer free lite template",
                "List on Notion template communities",
            ],
            "validation_plan": [
                "Track downloads of free lite version",
                "Survey users on desired add-ons",
                "Test €9 entry vs €29 premium bundle",
            ],
        },
        {
            "name": "outreach_email",
            "keywords": ["email pitch", "outreach"],
            "product_name": "Outreach Email Scripts Pack",
            "product_type": "guide",
            "target_audience": "Freelancers and creators doing cold outreach",
            "core_problem": "Cold pitches are generic and get ignored.",
            "solution": "Proven outreach scripts with personalization framework.",
            "format": "Google Docs",
            "price_min": 9,
            "price_max": 19,
            "deliverables": [
                "Cold outreach script library",
                "Follow-up sequence templates",
                "Personalization prompt matrix",
                "Subject line swipe file",
            ],
            "positioning": "Book more replies with concise, high-intent outreach.",
            "distribution_plan": [
                "Post outreach reply-rate case studies",
                "Offer one free script in lead magnet",
                "Partner with creator newsletters",
            ],
            "validation_plan": [
                "Test scripts with 20-email pilot",
                "Gather baseline and improved reply rates",
                "Collect buyer feedback on script clarity",
            ],
        },
    ]

    def generate(self, opportunity: dict) -> dict:
        source_text = f"{opportunity.get('title', '')} {opportunity.get('summary', '')}".lower()

        best_theme = None
        best_matches = 0
        for theme in self._THEMES:
            matches = sum(1 for keyword in theme["keywords"] if keyword in source_text)
            if matches > best_matches:
                best_matches = matches
                best_theme = theme

        if best_theme is None:
            best_theme = self._THEMES[2]

        midpoint_price = round((best_theme["price_min"] + best_theme["price_max"]) / 2)
        confidence = min(10, 5 + max(best_matches, 1))

        now = datetime.now(timezone.utc).isoformat()

        return {
            "id": uuid.uuid4().hex,
            "created_at": now,
            "updated_at": now,
            "status": "draft",
            "source_opportunity_id": str(opportunity.get("id", "")),
            "product_name": best_theme["product_name"],
            "product_type": best_theme["product_type"],
            "target_audience": best_theme["target_audience"],
            "core_problem": best_theme["core_problem"],
            "solution": best_theme["solution"],
            "format": best_theme["format"],
            "price_suggestion": midpoint_price,
            "deliverables": list(best_theme["deliverables"]),
            "positioning": best_theme["positioning"],
            "distribution_plan": list(best_theme["distribution_plan"]),
            "validation_plan": list(best_theme["validation_plan"]),
            "confidence": confidence,
            "reasoning": (
                f"Selected {best_theme['product_name']} from keyword heuristic matches "
                f"({best_matches} keyword hit(s)) in title/summary."
            ),
        }
