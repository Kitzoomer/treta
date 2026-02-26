import logging
from core.state_machine import StateMachine, State
from core.events import Event
from core.control import Control
from core.bus import EventBus
from core.memory_store import MemoryStore
from core.conversation_core import ConversationCore
from core.storage import Storage
from core.logging_config import set_decision_id, set_event_id, set_request_id, set_trace_id


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
        }:
            if event.type == "UserMessageSubmitted":
                self.conversation_core.consume(event)
            elif event.type == "AssistantMessageGenerated":
                pass
            else:

                actions = self.control.consume(event)
                for action in actions:
                    logger.info("Action emitted", extra={"event_type": action.type, "payload": action.payload, **ids})
                    action_payload = dict(action.payload) if isinstance(action.payload, dict) else {"value": action.payload}
                    action_payload.setdefault("request_id", event.request_id)
                    action_payload.setdefault("trace_id", event.trace_id)
                    action_payload.setdefault("parent_event_id", event.event_id)
                    self.bus.push(Event(type=action.type, payload=action_payload, source="control", request_id=event.request_id, trace_id=event.trace_id))

        self.storage.mark_event_processed(event.event_id, event.type)
