from __future__ import annotations

from enum import Enum
from typing import Any


class EventType(str, Enum):
    WAKE_WORD_DETECTED = "WakeWordDetected"
    TRANSCRIPT_READY = "TranscriptReady"
    LLM_RESPONSE_READY = "LLMResponseReady"
    TTS_FINISHED = "TTSFinished"
    ERROR_OCCURRED = "ErrorOccurred"
    HEARTBEAT = "Heartbeat"

    USER_MESSAGE_SUBMITTED = "UserMessageSubmitted"
    ASSISTANT_MESSAGE_GENERATED = "AssistantMessageGenerated"

    DAILY_BRIEF_REQUESTED = "DailyBriefRequested"
    OPPORTUNITY_SCAN_REQUESTED = "OpportunityScanRequested"
    RUN_INFOPRODUCT_SCAN = "RunInfoproductScan"
    EMAIL_TRIAGE_REQUESTED = "EmailTriageRequested"
    EVALUATE_OPPORTUNITY = "EvaluateOpportunity"
    OPPORTUNITY_DETECTED = "OpportunityDetected"
    LIST_OPPORTUNITIES = "ListOpportunities"
    EVALUATE_OPPORTUNITY_BY_ID = "EvaluateOpportunityById"
    OPPORTUNITY_DISMISSED = "OpportunityDismissed"

    LIST_PRODUCT_PROPOSALS = "ListProductProposals"
    GET_PRODUCT_PROPOSAL_BY_ID = "GetProductProposalById"
    BUILD_PRODUCT_PLAN_REQUESTED = "BuildProductPlanRequested"
    LIST_PRODUCT_PLANS_REQUESTED = "ListProductPlansRequested"
    GET_PRODUCT_PLAN_REQUESTED = "GetProductPlanRequested"
    EXECUTE_PRODUCT_PLAN_REQUESTED = "ExecuteProductPlanRequested"

    APPROVE_PROPOSAL = "ApproveProposal"
    REJECT_PROPOSAL = "RejectProposal"
    START_BUILDING_PROPOSAL = "StartBuildingProposal"
    MARK_READY_TO_LAUNCH = "MarkReadyToLaunch"
    MARK_PROPOSAL_LAUNCHED = "MarkProposalLaunched"
    ARCHIVE_PROPOSAL = "ArchiveProposal"

    LIST_PRODUCT_LAUNCHES_REQUESTED = "ListProductLaunchesRequested"
    GET_PRODUCT_LAUNCH_REQUESTED = "GetProductLaunchRequested"
    ADD_PRODUCT_LAUNCH_SALE = "AddProductLaunchSale"
    TRANSITION_PRODUCT_LAUNCH_STATUS = "TransitionProductLaunchStatus"

    GUMROAD_STATS_REQUESTED = "GumroadStatsRequested"

    ACTION_APPROVED = "ActionApproved"
    ACTION_PLAN_GENERATED = "ActionPlanGenerated"
    CONFIRM_ACTION = "ConfirmAction"
    REJECT_ACTION = "RejectAction"
    LIST_PENDING_CONFIRMATIONS = "ListPendingConfirmations"

    RUN_STRATEGY_DECISION = "RunStrategyDecision"
    STRATEGY_DECISION_COMPLETED = "StrategyDecisionCompleted"
    EXECUTE_STRATEGY_ACTION = "ExecuteStrategyAction"

    REDDIT_DAILY_PLAN_GENERATED = "RedditDailyPlanGenerated"


EVENT_SCHEMAS: dict[str, dict[str, set[str]]] = {
    EventType.EVALUATE_OPPORTUNITY_BY_ID.value: {"required_keys": {"id"}},
    EventType.OPPORTUNITY_DISMISSED.value: {"required_keys": {"id"}},
    EventType.GET_PRODUCT_PROPOSAL_BY_ID.value: {"required_keys": {"proposal_id"}},
    EventType.BUILD_PRODUCT_PLAN_REQUESTED.value: {"required_keys": {"proposal_id"}},
    EventType.EXECUTE_PRODUCT_PLAN_REQUESTED.value: {"required_keys": {"proposal_id"}},
    EventType.CONFIRM_ACTION.value: {"required_keys": {"plan_id"}},
    EventType.REJECT_ACTION.value: {"required_keys": {"plan_id"}},
    EventType.EXECUTE_STRATEGY_ACTION.value: {"required_keys": {"action_id"}},
}


KNOWN_EVENT_TYPES = {item.value for item in EventType}


def normalize_event_type(value: str | EventType) -> str:
    if isinstance(value, EventType):
        return value.value
    return str(value)


def event_type_is_known(value: str | EventType) -> bool:
    return normalize_event_type(value) in KNOWN_EVENT_TYPES


def validate_event_payload(event_type: str | EventType, payload: dict[str, Any] | None) -> tuple[bool, list[str]]:
    normalized_type = normalize_event_type(event_type)
    schema = EVENT_SCHEMAS.get(normalized_type)
    if not schema:
        return True, []

    payload_dict = payload if isinstance(payload, dict) else {}
    missing = sorted(k for k in schema.get("required_keys", set()) if k not in payload_dict)
    return len(missing) == 0, missing
