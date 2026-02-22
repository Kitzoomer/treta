import logging
from core.state_machine import StateMachine, State
from core.events import Event
from core.control import Control
from core.bus import EventBus
from core.memory_store import MemoryStore
from core.conversation_core import ConversationCore


logger = logging.getLogger("treta.dispatcher")


class Dispatcher:
    def __init__(
        self,
        state_machine: StateMachine,
        control: Control | None = None,
        memory_store: MemoryStore | None = None,
        conversation_core: ConversationCore | None = None,
        bus: EventBus | None = None,
    ):
        self.sm = state_machine
        self.bus = bus or EventBus()
        self.control = control or Control(bus=self.bus)
        self.memory_store = memory_store or MemoryStore()
        self.conversation_core = conversation_core or ConversationCore(
            bus=self.bus,
            state_machine=self.sm,
            memory_store=self.memory_store,
        )

    def handle(self, event: Event):
        logger.info("Dispatching event", extra={"event_type": event.type, "source": event.source, "request_id": event.request_id})

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
                return

            if event.type == "AssistantMessageGenerated":
                return

            actions = self.control.consume(event)
            for action in actions:
                logger.info("Action emitted", extra={"event_type": action.type, "payload": action.payload, "request_id": event.request_id})
                self.bus.push(Event(type=action.type, payload=action.payload, source="control"))
