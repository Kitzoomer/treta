from core.state_machine import StateMachine, State
from core.events import Event

class Dispatcher:
    def __init__(self, state_machine: StateMachine):
        self.sm = state_machine

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
