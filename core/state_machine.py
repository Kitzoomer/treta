import logging
class State:
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    THINKING = "THINKING"
    SPEAKING = "SPEAKING"
    ERROR = "ERROR"


VALID_TRANSITIONS = {
    State.IDLE: [State.LISTENING, State.THINKING, State.SPEAKING],
    State.LISTENING: [State.THINKING, State.IDLE],
    State.THINKING: [State.SPEAKING, State.IDLE],
    State.SPEAKING: [State.IDLE],
    State.ERROR: [State.IDLE],
}


logger = logging.getLogger("treta.state")


class StateMachine:
    def __init__(self, initial_state=State.IDLE):
        self.state = initial_state

    def can_transition(self, new_state: str) -> bool:
        return new_state in VALID_TRANSITIONS.get(self.state, [])

    def transition(self, new_state: str):
        if self.can_transition(new_state):
            old = self.state
            self.state = new_state
            logger.info("State transition", extra={"from_state": old, "to_state": new_state, "event_type": "state_transition"})
        else:
            logger.warning("Invalid state transition", extra={"from_state": self.state, "to_state": new_state, "event_type": "state_transition_invalid"})
