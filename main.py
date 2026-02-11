import time
from core.state_machine import StateMachine, State
from core.storage import Storage
from core.events import Event
from core.ipc_http import start_http_server


def main():
    print("🧠 Treta Core starting...")

    storage = Storage()
    last_state = storage.get_state("last_state") or State.IDLE

    sm = StateMachine(initial_state=last_state)
    print(f"🧠 Restored state: {sm.state}")
    print("[BOOT] Starting HTTP server")
    try:
        start_http_server(state_machine=sm)
    except TypeError:
        start_http_server()

    try:
        while True:
            # Loop principal (siempre activa)
            time.sleep(5)

            # Evento dummy (por ahora)
            event = Event(
                type="Heartbeat",
                payload={"state": sm.state},
                source="core"
            )

            print(f"[EVENT] {event.type} | state={sm.state}")

            # Persistimos estado
            storage.set_state("last_state", sm.state)

    except KeyboardInterrupt:
        print("🛑 Treta Core stopped by user")
        storage.set_state("last_state", sm.state)


if __name__ == "__main__":
    main()
