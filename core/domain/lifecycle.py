from __future__ import annotations

ALL_PROPOSAL_STATUSES = {
    "draft",
    "approved",
    "building",
    "ready_to_launch",
    "ready_for_review",
    "launched",
    "rejected",
    "archived",
}

PROPOSAL_TRANSITIONS = {
    "draft": {"approved", "rejected"},
    "approved": {"building", "archived"},
    "building": {"ready_to_launch"},
    "ready_to_launch": {"ready_for_review"},
    "ready_for_review": {"launched"},
    "launched": {"archived"},
    "rejected": {"archived"},
    "archived": set(),
}

TERMINAL_STATUSES = {"archived"}

LAUNCHABLE_STATUSES = {"ready_for_review"}

EXECUTION_STATUSES = {"approved", "building"}

ACTIVE_PROPOSAL_STATUSES = {"approved", "building", "ready_to_launch"}

PLAN_BUILDABLE_STATUSES = {"approved", "building", "ready_to_launch", "ready_for_review"}
