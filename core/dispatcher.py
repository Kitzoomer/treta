from core.state_machine import StateMachine, State
from core.events import Event
from core.control import Control
from core.bus import event_bus


class Dispatcher:
    def __init__(self, state_machine: StateMachine, control: Control | None = None):
        self.sm = state_machine
        self.control = control or Control()

    def handle(self, event: Event):
        print(f"[DISPATCH] {event.type} from {event.source}")

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
            "DailyBriefRequested",
            "OpportunityScanRequested",
            "RunInfoproductScan",
            "EmailTriageRequested",
            "EvaluateOpportunity",
            "OpportunityDetected",
            "ListOpportunities",
            "EvaluateOpportunityById",
            "OpportunityDismissed",
            "GumroadStatsRequested",
            "ActionApproved",
            "ActionPlanGenerated",
            "ConfirmAction",
            "RejectAction",
            "ListPendingConfirmations",
        }:
            actions = self.control.consume(event)
            for action in actions:
                print(f"[ACTION] {action.type} payload={action.payload}")
                event_bus.push(Event(type=action.type, payload=action.payload, source="control"))
