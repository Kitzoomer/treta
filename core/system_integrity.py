from __future__ import annotations

from collections import defaultdict
from typing import Any


def _safe_id(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _safe_list(items: Any) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def compute_system_integrity(
    proposals: list,
    plans: list,
    launches: list,
) -> dict:
    """
    Returns:
    {
      "status": "healthy" | "warning" | "critical",
      "issues": [
         {"type": "...", "severity": "...", "id": "...", "details": {...}}
      ],
      "counts": {
         "proposals": int, "plans": int, "launches": int, "issues": int
      }
    }
    """
    issues: list[dict[str, Any]] = []

    safe_proposals = _safe_list(proposals)
    safe_plans = _safe_list(plans)
    safe_launches = _safe_list(launches)

    proposals_by_id: dict[str, dict[str, Any]] = {}
    plans_by_id: dict[str, dict[str, Any]] = {}
    plans_by_proposal_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    launches_by_id: dict[str, dict[str, Any]] = {}
    launches_by_proposal_id: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for proposal in safe_proposals:
        proposal_id = _safe_id(proposal.get("id"))
        if proposal_id:
            proposals_by_id[proposal_id] = proposal

    for plan in safe_plans:
        plan_id = _safe_id(plan.get("plan_id") or plan.get("id"))
        proposal_id = _safe_id(plan.get("proposal_id"))
        if plan_id:
            plans_by_id[plan_id] = plan
        if proposal_id:
            plans_by_proposal_id[proposal_id].append(plan)

        if not proposal_id or proposal_id not in proposals_by_id:
            issues.append(
                {
                    "type": "orphan_plan",
                    "severity": "warning",
                    "id": plan_id or proposal_id or "unknown",
                    "details": {
                        "plan_id": plan_id,
                        "proposal_id": proposal_id,
                    },
                }
            )

    for launch in safe_launches:
        launch_id = _safe_id(launch.get("id"))
        proposal_id = _safe_id(launch.get("proposal_id"))
        if launch_id:
            launches_by_id[launch_id] = launch
        if proposal_id:
            launches_by_proposal_id[proposal_id].append(launch)

        if not proposal_id or proposal_id not in proposals_by_id:
            issues.append(
                {
                    "type": "launch_without_proposal",
                    "severity": "critical",
                    "id": launch_id or proposal_id or "unknown",
                    "details": {
                        "launch_id": launch_id,
                        "proposal_id": proposal_id,
                    },
                }
            )

        if proposal_id and proposal_id not in plans_by_proposal_id:
            issues.append(
                {
                    "type": "launch_without_plan",
                    "severity": "critical",
                    "id": launch_id or proposal_id,
                    "details": {
                        "launch_id": launch_id,
                        "proposal_id": proposal_id,
                    },
                }
            )

    lifecycle_required_plan_statuses = {
        "approved",
        "building",
        "ready_to_launch",
        "ready_for_review",
        "launched",
    }

    for proposal in safe_proposals:
        proposal_id = _safe_id(proposal.get("id"))
        status = _safe_id(proposal.get("status"))
        has_plan = proposal_id in plans_by_proposal_id
        has_launch = proposal_id in launches_by_proposal_id

        if status in lifecycle_required_plan_statuses and not has_plan:
            issues.append(
                {
                    "type": "missing_plan",
                    "severity": "critical",
                    "id": proposal_id or "unknown",
                    "details": {
                        "proposal_id": proposal_id,
                        "status": status,
                    },
                }
            )

        if status == "archived" and (has_plan or has_launch):
            issues.append(
                {
                    "type": "archived_with_active_artifacts",
                    "severity": "warning",
                    "id": proposal_id or "unknown",
                    "details": {
                        "proposal_id": proposal_id,
                        "has_plan": has_plan,
                        "has_launch": has_launch,
                    },
                }
            )

        if status == "draft" and has_launch:
            issues.append(
                {
                    "type": "draft_with_launch",
                    "severity": "warning",
                    "id": proposal_id or "unknown",
                    "details": {
                        "proposal_id": proposal_id,
                    },
                }
            )

    severities = {str(issue.get("severity", "")).lower() for issue in issues}
    if "critical" in severities:
        status = "critical"
    elif issues:
        status = "warning"
    else:
        status = "healthy"

    return {
        "status": status,
        "issues": issues,
        "counts": {
            "proposals": len(safe_proposals),
            "plans": len(safe_plans),
            "launches": len(safe_launches),
            "issues": len(issues),
        },
    }
