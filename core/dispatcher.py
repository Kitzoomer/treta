import logging
from core.state_machine import StateMachine, State
from core.events import Event, make_event
from core.control import Control
from core.bus import EventBus
from core.memory_store import MemoryStore
from core.conversation_core import ConversationCore
from core.storage import Storage
from core.strategic_snapshot_engine import StrategicSnapshotEngine
from core.logging_config import set_decision_id, set_event_id, set_request_id, set_trace_id
from core.event_catalog import event_type_is_known, validate_event_payload


logger = logging.getLogger("treta.dispatcher")


class Dispatcher:
    def _ids_from_event(self, event: Event) -> dict:
        decision_id = str(event.payload.get("decision_id", "")) if isinstance(event.payload, dict) else ""
        return {
            "request_id": event.request_id,
            "trace_id": event.trace_id,
            "event_id": event.event_id,
            "decision_id": decision_id,
        }

    def __init__(
        self,
        state_machine: StateMachine,
        control: Control | None = None,
        memory_store: MemoryStore | None = None,
        conversation_core: ConversationCore | None = None,
        bus: EventBus | None = None,
        storage: Storage | None = None,
    ):
        self.sm = state_machine
        self.bus = bus or EventBus()
        self.control = control or Control(bus=self.bus)
        self.memory_store = memory_store or MemoryStore()
        self.storage = storage or Storage()
        self.conversation_core = conversation_core or ConversationCore(
            bus=self.bus,
            state_machine=self.sm,
            memory_store=self.memory_store,
        )
        self.strategic_snapshot_engine = StrategicSnapshotEngine(
            gpt_client_optional=getattr(self.conversation_core, "gpt_client", None)
        )

    def _build_strategic_full_state(self) -> dict:
        opportunity_store = getattr(self.control, "opportunity_store", None)
        strategy_action_store = getattr(self.control, "strategy_action_execution_layer", None)
        action_store = getattr(strategy_action_store, "_strategy_action_store", None)

        opportunities = opportunity_store.list() if opportunity_store is not None and hasattr(opportunity_store, "list") else []
        actions = action_store.list() if action_store is not None and hasattr(action_store, "list") else []

        active_opportunities = [
            {
                "id": item.get("id"),
                "title": item.get("title"),
                "status": item.get("status"),
            }
            for item in opportunities
            if isinstance(item, dict) and str(item.get("status", "")).strip() not in {"dismissed", "archived"}
        ][:12]

        current_strategies = [
            {
                "id": item.get("id"),
                "type": item.get("type"),
                "status": item.get("status"),
            }
            for item in actions
            if isinstance(item, dict) and str(item.get("status", "")).strip() in {"executed", "auto_executed", "completed", "pending_confirmation"}
        ][:16]

        pending_actions = [
            {
                "id": item.get("id"),
                "type": item.get("type"),
                "reasoning": item.get("reasoning"),
                "risk_score": item.get("risk_score"),
            }
            for item in actions
            if isinstance(item, dict) and str(item.get("status", "")).strip() == "pending_confirmation"
        ][:16]

        active_risks = [
            {
                "action_id": item.get("id"),
                "risk_score": float(item.get("risk_score", 0) or 0),
                "type": item.get("type"),
            }
            for item in actions
            if isinstance(item, dict)
            and str(item.get("status", "")).strip() in {"pending_confirmation", "failed"}
            and float(item.get("risk_score", 0) or 0) > 0
        ][:16]

        return {
            "active_opportunities": active_opportunities,
            "current_strategies": current_strategies,
            "pending_actions": pending_actions,
            "active_risks": active_risks,
        }

    def _maybe_generate_strategic_snapshot(self, event: Event, actions: list) -> None:
        if event.type != "RunStrategyDecision":
            return
        if not actions:
            return
        if not any(getattr(action, "type", "") == "StrategyDecisionCompleted" for action in actions):
            return

        full_state = self._build_strategic_full_state()
        snapshot_text = self.strategic_snapshot_engine.generate_snapshot(full_state)
        if snapshot_text:
            self.memory_store.save_snapshot(snapshot_text)

    def _validate_event_catalog(self, event: Event) -> bool:
        if not event_type_is_known(event.type):
            logger.warning("Unknown event type not in catalog", extra={"event_type": event.type, "trace_id": event.trace_id, "event_id": event.event_id})

        is_valid, missing_keys = validate_event_payload(event.type, event.payload if isinstance(event.payload, dict) else {})
        if is_valid:
            return True

        event.invalid = True
        event.invalid_reason = f"missing required keys: {', '.join(missing_keys)}"
        logger.warning(
            "Invalid event payload for catalog schema",
            extra={"event_type": event.type, "trace_id": event.trace_id, "event_id": event.event_id, "missing_keys": missing_keys},
        )
        return False

    def handle(self, event: Event):
        if isinstance(event.payload, dict):
            event.request_id = event.request_id or str(event.payload.get("request_id", "") or "")
            event.trace_id = event.trace_id or str(event.payload.get("trace_id", "") or "")
            if not event.payload.get("event_id"):
                event.payload["event_id"] = event.event_id
            if event.trace_id and not event.payload.get("trace_id"):
                event.payload["trace_id"] = event.trace_id
            if event.request_id and not event.payload.get("request_id"):
                event.payload["request_id"] = event.request_id

        ids = self._ids_from_event(event)
        set_request_id(str(ids.get("request_id", "")))
        set_trace_id(str(ids.get("trace_id", "")))
        set_event_id(str(ids.get("event_id", "")))
        set_decision_id(str(ids.get("decision_id", "")))
        logger.info("Dispatching event", extra={"event_type": event.type, "source": event.source, **ids})

        if not self._validate_event_catalog(event):
            self.storage.mark_event_processed(event.event_id, event.type)
            return

        if self.storage.is_event_processed(event.event_id):
            logger.info("Skipping duplicate event", extra={"event_type": event.type, **ids})
            return

        if event.type == "WakeWordDetected":
            self.sm.transition(State.LISTENING)

        elif event.type == "TranscriptReady":
            self.sm.transition(State.THINKING)

        elif event.type == "LLMResponseReady":
            self.sm.transition(State.SPEAKING)

        elif event.type == "TTSFinished":
            self.sm.transition(State.IDLE)

        elif event.type == "ErrorOccurred":
            self.sm.transition(State.ERROR)

        elif event.type in {
            "UserMessageSubmitted",
            "AssistantMessageGenerated",
            "DailyBriefRequested",
            "OpportunityScanRequested",
            "RunInfoproductScan",
            "EmailTriageRequested",
            "EvaluateOpportunity",
            "OpportunityDetected",
            "ListOpportunities",
            "EvaluateOpportunityById",
            "OpportunityDismissed",
            "ListProductProposals",
            "GetProductProposalById",
            "BuildProductPlanRequested",
            "ListProductPlansRequested",
            "GetProductPlanRequested",
            "ListProductLaunchesRequested",
            "GetProductLaunchRequested",
            "AddProductLaunchSale",
            "TransitionProductLaunchStatus",
            "ExecuteProductPlanRequested",
            "ApproveProposal",
            "RejectProposal",
            "StartBuildingProposal",
            "MarkReadyToLaunch",
            "MarkProposalLaunched",
            "ArchiveProposal",
            "GumroadStatsRequested",
            "ActionApproved",
            "ActionPlanGenerated",
            "ConfirmAction",
            "RejectAction",
            "ListPendingConfirmations",
            "RunStrategyDecision",
            "ExecuteStrategyAction",
        }:
            if event.type == "UserMessageSubmitted":
                self.conversation_core.consume(event)
            elif event.type == "AssistantMessageGenerated":
                pass
            else:

                actions = self.control.consume(event)
                self._maybe_generate_strategic_snapshot(event, actions)
                for action in actions:
                    logger.info("Action emitted", extra={"event_type": action.type, "payload": action.payload, **ids})
                    action_payload = dict(action.payload) if isinstance(action.payload, dict) else {"value": action.payload}
                    action_payload.setdefault("request_id", event.request_id)
                    action_payload.setdefault("trace_id", event.trace_id)
                    action_payload.setdefault("parent_event_id", event.event_id)
                    self.bus.push(make_event(action.type, action_payload, source="control", request_id=event.request_id, trace_id=event.trace_id))

        self.storage.mark_event_processed(event.event_id, event.type)
