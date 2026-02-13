from typing import Any, Dict


class ActionPlanner:
    def plan(self, opportunity: Dict[str, Any]) -> Dict[str, Any]:
        opportunity_type = opportunity.get("type")

        if opportunity_type == "stale_product":
            return {
                "action": "relaunch",
                "steps": [
                    "Review product description",
                    "Adjust pricing",
                    "Create limited-time promotion",
                    "Post value thread in relevant forum",
                ],
                "priority": 7,
            }

        if opportunity_type == "growing_product":
            return {
                "action": "scale",
                "steps": [
                    "Increase price slightly",
                    "Create bundle",
                    "Promote to email list",
                ],
                "priority": 8,
            }

        if opportunity_type == "top_product":
            return {
                "action": "optimize",
                "steps": [
                    "Add upsell",
                    "Improve landing page copy",
                    "Collect testimonials",
                ],
                "priority": 9,
            }

        return {"action": "analyze", "steps": ["Collect additional context"], "priority": 1}
