class State:
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    THINKING = "THINKING"
    SPEAKING = "SPEAKING"
    ERROR = "ERROR"


VALID_TRANSITIONS = {
    State.IDLE: [State.LISTENING],
    State.LISTENING: [State.THINKING, State.IDLE],
    State.THINKING: [State.SPEAKING, State.IDLE],
    State.SPEAKING: [State.IDLE],
    State.ERROR: [State.IDLE],
}


class StateMachine:
    def __init__(self, initial_state=State.IDLE):
        self.state = initial_state

    def can_transition(self, new_state: str) -> bool:
        return new_state in VALID_TRANSITIONS.get(self.state, [])

    def transition(self, new_state: str):
        if self.can_transition(new_state):
            old = self.state
            self.state = new_state
            print(f"[STATE] {old} -> {new_state}")
        else:
            print(f"[STATE] Invalid transition: {self.state} -> {new_state}")
